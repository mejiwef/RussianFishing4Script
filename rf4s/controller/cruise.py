"""拖钓自动巡航控制器。

功能：
- 使用 mss 截取坐标显示区域 + OpenCV 数字模板匹配识别当前位置
- 向量叉积计算转向方向，按 A/D 键纠正行驶方向
- 后台守护线程运行，不阻塞主钓鱼循环
"""

import logging
import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import pyautogui

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]

# 游戏中坐标格式: "x:y"，支持的字符
DIGIT_CHARS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
COLON_CHAR = "colon"


class CruiseController:
    """两点（多点）间自动巡航控制器。

    在后台线程中循环执行：截取坐标 → OCR 读取位置 → 向量计算 → 按键转向。
    与 Player 主循环解耦，通过 start() / stop() 控制生命周期。
    """

    def __init__(self, cfg, sct):
        """初始化巡航控制器。

        :param cfg: yacs 配置节点
        :param sct: mss 截图器实例（复用 Detection 的）
        """
        self.cfg = cfg
        self._sct = sct
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # 航点列表
        self._waypoints: list[np.ndarray] = []
        self._waypoint_idx = 0

        # 位置追踪
        self._last_pos: Optional[np.ndarray] = None
        self._cur_pos: Optional[np.ndarray] = None

        # 加载数字模板
        self._digit_templates: dict[str, np.ndarray] = {}
        self._colon_template: Optional[np.ndarray] = None
        self._load_digit_templates()

    def _load_digit_templates(self) -> None:
        """加载 0-9 和冒号的数字模板图片。

        模板存放在 static/{DIGIT_TEMPLATE_DIR}/ 目录下，
        文件名: 0.png ~ 9.png, colon.png
        """
        template_dir = ROOT / "static" / self.cfg.BOT.CRUISE.DIGIT_TEMPLATE_DIR
        if not template_dir.exists():
            logger.warning("数字模板目录不存在: %s", template_dir)
            logger.warning("请运行校准工具生成模板，或手动准备模板文件")
            return

        for digit in DIGIT_CHARS:
            path = template_dir / f"{digit}.png"
            if path.exists():
                tpl = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if tpl is not None:
                    self._digit_templates[digit] = tpl
            else:
                logger.warning("缺少数字模板: %s", path)

        colon_path = template_dir / "colon.png"
        if colon_path.exists():
            self._colon_template = cv2.imread(str(colon_path), cv2.IMREAD_GRAYSCALE)
        else:
            logger.warning("缺少冒号模板: %s", colon_path)

        loaded = len(self._digit_templates)
        logger.info("已加载 %d/10 个数字模板", loaded)

    def start(self, waypoints: list) -> None:
        """启动巡航后台线程。

        :param waypoints: 航点列表，格式 [[x1,y1], [x2,y2], ...]
        """
        if not self._digit_templates:
            logger.error("数字模板未加载，无法启动巡航")
            return

        if len(waypoints) < 2:
            logger.error("航点数量不足（最少需要 2 个），无法启动巡航")
            return

        self._waypoints = [np.array(wp, dtype=float) for wp in waypoints]
        self._waypoint_idx = 0
        self._last_pos = None
        self._cur_pos = None
        self._running = True

        self._thread = threading.Thread(
            target=self._cruise_loop,
            name="CruiseController",
            daemon=True,
        )
        self._thread.start()
        logger.info("巡航控制器已启动，航点: %s", waypoints)

    def stop(self) -> None:
        """停止巡航线程。"""
        if not self._running:
            return
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        logger.info("巡航控制器已停止")

    @property
    def is_running(self) -> bool:
        return self._running

    # ======================== 巡航主循环 ========================

    def _cruise_loop(self) -> None:
        """巡航主循环，在后台线程中运行。"""
        interval = self.cfg.BOT.CRUISE.CHECK_INTERVAL

        while self._running:
            try:
                time.sleep(interval)
                if not self._running:
                    break

                new_pos = self._read_position()
                if new_pos is None:
                    logger.debug("坐标识别失败，跳过本轮")
                    continue

                # 更新位置
                self._last_pos = self._cur_pos
                self._cur_pos = new_pos

                if self._last_pos is None:
                    continue

                # 和上次位置一样则跳过
                if np.array_equal(self._cur_pos, self._last_pos):
                    continue

                target = self._waypoints[self._waypoint_idx]

                # 检查是否到达航点
                dist = np.linalg.norm(self._cur_pos - target)
                if dist < self.cfg.BOT.CRUISE.ARRIVAL_RADIUS:
                    self._waypoint_idx = (self._waypoint_idx + 1) % len(self._waypoints)
                    logger.info(
                        "到达航点，切换到下一个: %s",
                        self._waypoints[self._waypoint_idx].tolist(),
                    )
                    continue

                # 计算转向
                direction, duration = self._calc_steering(
                    self._last_pos, self._cur_pos, target,
                    self.cfg.BOT.CRUISE.TURN_RATE,
                )

                logger.info(
                    "位置: %s, 目标: %s, 距离: %.1f, 转向: %s %.2fs",
                    self._cur_pos.tolist(),
                    target.tolist(),
                    dist,
                    direction or "直行",
                    duration,
                )

                # 执行转向
                if direction and duration > 0.01:
                    pyautogui.keyDown(direction)
                    time.sleep(duration)
                    pyautogui.keyUp(direction)

            except Exception:
                logger.exception("巡航循环异常")

    # ======================== OCR 坐标识别 ========================

    def _read_position(self) -> Optional[np.ndarray]:
        """从游戏屏幕右下角读取地图坐标。

        流程：
        1. mss 截取坐标显示区域
        2. 灰度 → 二值化（保留白色文字）
        3. 轮廓分割出各字符
        4. 每个字符与数字模板做 matchTemplate 匹配
        5. 解析 "x:y" 格式

        :return: [x, y] 坐标数组，识别失败返回 None
        """
        try:
            region = self.cfg.BOT.CRUISE.COORD_REGION
            monitor = {
                "left": int(region[0]),
                "top": int(region[1]),
                "width": int(region[2]),
                "height": int(region[3]),
            }
            raw = self._sct.grab(monitor)
            img = np.array(raw)[:, :, :3]  # BGRA → BGR

            # 灰度化 + 二值化（白色文字在深色背景上）
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

            # 轻微形态学处理，去噪 + 连接断裂笔画
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

            # 寻找轮廓
            contours, _ = cv2.findContours(
                binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if not contours:
                return None

            # 按 x 坐标排序，得到从左到右的字符序列
            bboxes = []
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                # 过滤太小的噪点
                if w >= 3 and h >= 5:
                    bboxes.append((x, y, w, h))

            bboxes.sort(key=lambda b: b[0])
            if not bboxes:
                return None

            # 识别每个字符
            text = ""
            for x, y, w, h in bboxes:
                char_img = binary[y : y + h, x : x + w]
                char = self._match_digit(char_img)
                text += char

            # 解析 "x:y" 格式
            if ":" not in text:
                return None

            parts = text.split(":")
            if len(parts) != 2:
                return None

            coord_x = int(parts[0])
            coord_y = int(parts[1])
            return np.array([coord_x, coord_y], dtype=float)

        except (ValueError, IndexError):
            return None
        except Exception:
            logger.debug("坐标读取异常", exc_info=True)
            return None

    def _match_digit(self, char_img: np.ndarray) -> str:
        """将单个字符图片与数字模板匹配。

        :param char_img: 二值化的单字符图片
        :return: 匹配到的字符（'0'-'9' 或 ':'）
        """
        best_score = -1.0
        best_char = "?"

        # 先检查冒号（通常更窄更小）
        if self._colon_template is not None:
            score = self._template_match_score(char_img, self._colon_template)
            if score > 0.7:  # 冒号阈值
                return ":"

        # 匹配数字 0-9
        for digit, template in self._digit_templates.items():
            score = self._template_match_score(char_img, template)
            if score > best_score:
                best_score = score
                best_char = digit

        if best_score < 0.5:  # 最低置信度
            return "?"

        return best_char

    @staticmethod
    def _template_match_score(
        char_img: np.ndarray, template: np.ndarray
    ) -> float:
        """计算字符图片与模板的匹配分数。

        将两者 resize 到相同大小后做归一化相关匹配。

        :param char_img: 待匹配的字符图片
        :param template: 模板图片
        :return: 匹配分数 (0.0 ~ 1.0)
        """
        # 统一 resize 到模板大小
        target_h, target_w = template.shape[:2]
        if target_h == 0 or target_w == 0:
            return 0.0

        resized = cv2.resize(
            char_img, (target_w, target_h), interpolation=cv2.INTER_AREA
        )

        # 确保是单通道
        if len(resized.shape) > 2:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        if len(template.shape) > 2:
            template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        # 归一化相关匹配
        result = cv2.matchTemplate(
            resized, template, cv2.TM_CCOEFF_NORMED
        )
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return float(max_val)

    # ======================== 转向计算 ========================

    @staticmethod
    def _calc_steering(
        prev_pos: np.ndarray,
        cur_pos: np.ndarray,
        target: np.ndarray,
        turn_rate: float = 0.152,
    ) -> tuple[Optional[str], float]:
        """通过向量叉积计算转向方向和持续时间。

        :param prev_pos: 上一个位置 [x, y]
        :param cur_pos: 当前位置 [x, y]
        :param target: 目标位置 [x, y]
        :param turn_rate: 每度角转向需要按键的秒数
        :return: (转向键 'a'/'d'/None, 按键时长)
        """
        # 当前行驶方向向量
        v1 = cur_pos - prev_pos
        # 当前位置到目标的向量
        v2 = target - cur_pos

        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        if norm_v1 < 1e-6 or norm_v2 < 1e-6:
            return None, 0.0

        # 计算夹角（弧度 → 角度）
        cos_angle = np.dot(v1, v2) / (norm_v1 * norm_v2)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle_deg = np.degrees(np.arccos(cos_angle))

        # 按键时长 = 角度 × 转向速率
        duration = angle_deg * turn_rate

        # 叉积判断转向方向（2D 叉积 = v1.x*v2.y - v1.y*v2.x）
        cross = v1[0] * v2[1] - v1[1] * v2[0]
        if cross > 0:
            return "a", duration  # 逆时针（左转）
        elif cross < 0:
            return "d", duration  # 顺时针（右转）
        else:
            return None, 0.0  # 方向正确
