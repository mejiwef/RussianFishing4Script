"""Helper functions for image detection.

优化说明：
- 使用 mss 替代 GDI 截图（快 3-5 倍）
- 支持「一次截图多次匹配」模式：capture_frame() 截一帧，后续检测复用
- 像素检测也支持从帧上直接读取，避免额外的 GetPixel 调用
- 向后兼容：不传 frame 时退回原始 locateOnScreen 行为
"""

import time
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Generator, Optional

import cv2
import mss
import numpy as np
import pyautogui as pag
from PIL import Image, ImageFilter
from pyscreeze import Box

from rf4s import utils
from rf4s.controller.window import Window
from rf4s.utils import add_jitter

CRITICAL_COLOR = (206, 56, 21)
WARNING_COLOR = (227, 149, 23)

MIN_GRAY_SCALE_LEVEL = 160
YELLOW_FRICTION_BRAKE = (200, 214, 63)
ORANGE_FRICTION_BRAKE = (229, 188, 0)
RED_FRICTION_BRAKE = (206, 56, 21)
COLOR_TOLERANCE = 32
CAMERA_OFFSET = 40
SIDE_LENGTH = 160
SIDE_LENGTH_HALF = 80
ORANGE_REEL = (227, 149, 23)

ROOT = Path(__file__).resolve().parents[2]


class TagColor(Enum):
    GREEN = "green_tag"
    YELLOW = "yellow_tag"
    PINK = "pink_tag"
    BLUE = "blue_tag"
    PURPLE = "purple_tag"


COORD_OFFSETS = {
    "1600x900": {
        "friction_brake_very_high": (502, 872),  # Left point only
        "friction_brake_high": (459, 872),
        "friction_brake_medium": (417, 872),
        "friction_brake_low": (396, 872),
        "fish_icon": (389, 844),
        "clip_icon": (1042, 844),
        "spool_icon": (1077, 844),  # x + 15, y + 15
        "reel_burning_icon": (1112, 842),
        "snag_icon": (1147, 829),  # x + 15, y
        "float_camera": (720, 654),
        "bait_icon": (35, 31),
    },
    "1920x1080": {
        "friction_brake_very_high": (662, 1052),
        "friction_brake_high": (619, 1052),
        "friction_brake_medium": (577, 1052),
        "friction_brake_low": (556, 1052),
        "fish_icon": (549, 1024),
        "clip_icon": (1202, 1024),
        "spool_icon": (1237, 1024),
        "reel_burning_icon": (1271, 1023),
        "snag_icon": (1307, 1009),
        "float_camera": (880, 834),
        "bait_icon": (35, 31),
    },
    "2560x1440": {
        "friction_brake_very_high": (982, 1412),
        "friction_brake_high": (939, 1412),
        "friction_brake_medium": (897, 1412),
        "friction_brake_low": (876, 1412),
        "fish_icon": (869, 1384),
        "clip_icon": (1522, 1384),
        "spool_icon": (1557, 1384),
        "reel_burning_icon": (1593, 1383),
        "snag_icon": (1627, 1369),
        "float_camera": (1200, 1194),
        "bait_icon": (35, 31),
    },
}

# ------------------------ Friction brake coordinates ------------------------ #
# ----------------------------- 900p - 1080p - 2k ---------------------------- #
# ------ left - red - yellow - center(left + 424) - yellow - red - right ----- #
# "bases": ((480, 270), (320, 180), (0, 0))
# "absolute": {"x": (855, 960, 1066, 1279, 1491, 1598, 1702, "y": (1146, 1236, 1412)}
# "1600x900": {"x": (375, 480, 586, 799, 1011, 1118, 1222), "y": 876},
# "1920x1080": {"x": (535, 640, 746, 959, 1171, 1278, 1382), "y": 1056},
# "2560x1440": {"x": (855, 960, 1066, 1279, 1491, 1598, 1702), "y": 1412},


class Detection:
    """A class that holds different aliases of locateOnScreen(image).

    This class provides methods for detecting various in-game elements such as fish,
    icons, and UI components using image recognition and pixel color analysis.

    优化特性：
    - capture_frame(): 使用 mss 快速截图一帧，后续所有检测复用
    - 所有 is_xxx() 方法接受 frame= 参数，传入时不再重复截图
    - 像素检测也可从帧数组直接读取

    Attributes:
        cfg (CfgNode): Configuration node for the detection settings.
        window (Window): Game window controller instance.
        image_dir (Path): Directory containing reference images for detection.
        coord_offsets (dict): Dictionary of coordinate offsets for different window sizes.
        bait_icon_reference_img (Image): Reference image for bait icon detection.
    """

    def __init__(self, cfg, window: Window):
        """Initialize the Detection class with configuration and window settings.

        :param cfg: Configuration node for detection settings.
        :type cfg: CfgNode
        :param window: Game window controller instance.
        :type window: Window
        """
        self.cfg = cfg
        self.window = window
        self.image_dir = ROOT / "static" / cfg.LANGUAGE

        # mss 截图器（进程生命周期内复用）
        self._sct = mss.mss()
        # 模板缓存：避免每次 imread
        self._template_cache: dict[str, np.ndarray] = {}
        # 缓存的帧
        self._cached_frame: Optional[np.ndarray] = None
        # 窗口基坐标缓存
        self._base_x = 0
        self._base_y = 0

        if window.is_size_supported():
            self._set_absolute_coords()
            self.is_fish_hooked = self.is_fish_hooked_pixel
        else:
            self.is_fish_hooked = partial(
                self._get_image_box,
                image="fish_icon",
                confidence="0.9",
            )

        self.bait_icon_reference_img = Image.open(self.image_dir / "bait_icon.png")

    # ======================== 帧捕获与缓存 ========================
    def capture_frame(self) -> np.ndarray:
        """使用 mss 截取一帧并缓存，供后续多次匹配/像素读取复用。

        比 GDI (pag.screenshot) 快 3-5 倍。

        :return: BGR 格式的 numpy 数组
        :rtype: np.ndarray
        """
        box = self.window.get_box()
        self._base_x, self._base_y = box[0], box[1]
        monitor = {
            "left": box[0],
            "top": box[1],
            "width": box[2],
            "height": box[3],
        }
        raw = self._sct.grab(monitor)
        # mss 返回 BGRA，去掉 alpha 通道
        self._cached_frame = np.array(raw)[:, :, :3].copy()
        return self._cached_frame

    def _get_pixel_from_frame(
        self, frame: np.ndarray, abs_x: int, abs_y: int
    ) -> tuple[int, int, int]:
        """从帧上读取指定绝对坐标的像素值 (R, G, B)。

        :param frame: BGR numpy 数组
        :param abs_x: 屏幕绝对 X 坐标
        :param abs_y: 屏幕绝对 Y 坐标
        :return: (R, G, B) 元组
        """
        rel_y = abs_y - self._base_y
        rel_x = abs_x - self._base_x
        b, g, r = frame[rel_y, rel_x]
        return (int(r), int(g), int(b))

    def _get_template(self, image: str) -> np.ndarray:
        """读取模板图并缓存。

        :param image: 模板图名称（不含扩展名）
        :return: BGR 格式模板 numpy 数组
        """
        if image not in self._template_cache:
            path = str(self.image_dir / f"{image}.png")
            tpl = cv2.imread(path)
            if tpl is None:
                raise FileNotFoundError(f"模板图不存在: {path}")
            self._template_cache[image] = tpl
        return self._template_cache[image]

    def _locate_in_frame(
        self, frame: np.ndarray, image: str, confidence: float
    ) -> Box | None:
        """在已有帧上做模板匹配（不截图）。

        :param frame: BGR numpy 数组
        :param image: 模板图名称
        :param confidence: 匹配阈值
        :return: 匹配到的 Box，未匹配返回 None
        """
        template = self._get_template(image)
        result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val >= confidence:
            h, w = template.shape[:2]
            # 返回绝对坐标的 Box（与 locateOnScreen 行为一致）
            return Box(
                max_loc[0] + self._base_x,
                max_loc[1] + self._base_y,
                w,
                h,
            )
        return None

    def _locate_all_in_frame(
        self, frame: np.ndarray, image: str, confidence: float
    ) -> Generator[Box, None, None]:
        """在已有帧上查找所有匹配位置。

        :param frame: BGR numpy 数组
        :param image: 模板图名称
        :param confidence: 匹配阈值
        :yields: 匹配到的 Box
        """
        template = self._get_template(image)
        h, w = template.shape[:2]
        result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
        loc = np.where(result >= confidence)
        # 去重（NMS 简易版：同一区域只取一个）
        seen = set()
        for pt_y, pt_x in zip(*loc):
            # 按 20px 网格去重
            grid = (pt_x // 20, pt_y // 20)
            if grid not in seen:
                seen.add(grid)
                yield Box(
                    int(pt_x) + self._base_x,
                    int(pt_y) + self._base_y,
                    w,
                    h,
                )

    # ======================== 核心匹配方法 ========================
    def _get_image_box(
        self,
        image: str,
        confidence: float,
        multiple: bool = False,
        frame: Optional[np.ndarray] = None,
    ) -> Box | Generator[Box, None, None] | None:
        """A wrapper for locateOnScreen method and path resolving.

        当 frame 参数传入时，在帧上做匹配（不截图）；
        否则走原始 locateOnScreen 路径（向后兼容）。

        :param image: Base name of the image.
        :type image: str
        :param confidence: Matching confidence for locateOnScreen.
        :type confidence: float
        :param multiple: Whether to locate all matching images, defaults to False.
        :type multiple: bool, optional
        :param frame: 预截取的帧（BGR numpy 数组），传入时不再截图。
        :type frame: np.ndarray, optional
        :return: Image box, None if not found.
        :rtype: Box | None
        """
        if frame is not None:
            if multiple:
                return self._locate_all_in_frame(frame, image, confidence)
            return self._locate_in_frame(frame, image, confidence)

        # 向后兼容：无 frame 时走原始路径
        image_path = str(self.image_dir / f"{image}.png")
        if multiple:
            return pag.locateAllOnScreen(image_path, confidence=confidence)
        return pag.locateOnScreen(image_path, confidence=confidence)

    def _set_absolute_coords(self) -> None:
        """Add offsets to the base coordinates to get absolute ones."""
        self.coord_offsets = COORD_OFFSETS[self.window.get_resolution_str()]

        for key in self.coord_offsets:
            setattr(self, f"{key}_coord", self._get_absolute_coord(key))

        self.bait_icon_coord = self._get_absolute_coord("bait_icon") + [44, 52]
        if self.cfg.ARGS.FEATURE == "bot":
            sensitivity = self.cfg.BOT.FRICTION_BRAKE.SENSITIVITY
        else:  # friction_brake
            sensitivity = self.cfg.FRICTION_BRAKE.SENSITIVITY
        friction_brake_key = f"friction_brake_{sensitivity}"
        self.friction_brake_coord = self._get_absolute_coord(friction_brake_key)

        bases = self._get_absolute_coord("float_camera")
        if hasattr(self.cfg.PROFILE, "MODE") and self.cfg.PROFILE.MODE in (
            "telescopic",
            "bolognese",
        ):
            match self.cfg.PROFILE.CAMERA_SHAPE:
                case "tall":
                    bases[0] += CAMERA_OFFSET
                    width, height = SIDE_LENGTH_HALF, SIDE_LENGTH
                case "wide":
                    bases[1] += CAMERA_OFFSET
                    width, height = SIDE_LENGTH, SIDE_LENGTH_HALF
                case "square":
                    width, height = SIDE_LENGTH, SIDE_LENGTH
                case _:
                    raise ValueError(self.cfg.PROFILE.CAMERA_SHAPE)
            self.float_camera_rect = (*bases, width, height)  # (left, top, w, h)

    def _get_absolute_coord(self, offset_key: str) -> list[int]:
        """Calculate absolute coordinate based on given key.

        :param offset_key: A key in the offset dictionary.
        :type offset_key: str
        :return: Converted absolute coordinate.
        :rtype: list[int]
        """
        box = self.window.get_box()
        return [box[i] + self.coord_offsets[offset_key][i] for i in range(2)]

    # ----------------------------- Untagged release ----------------------------- #
    # HSV values
    # green: 40, 175, 200
    # yellow: 25, 200, 228
    # pink: 139, 160, 255
    # blue: 104, 165, 251
    # purple: 130, 126, 252

    def is_tag_exist(self, color: TagColor, frame=None):
        return self._get_image_box(color.value, 0.95, frame=frame)

    def is_fish_species_matched(self, species: str, frame=None):
        return self._get_image_box(species, 0.9, frame=frame)

    # -------------------------------- Fish status ------------------------------- #
    def is_fish_hooked(self, frame=None):
        pass  # It's initialized in the constructor

    def is_fish_hooked_pixel(self, frame=None) -> bool:
        if frame is not None:
            pixel = self._get_pixel_from_frame(frame, *self.fish_icon_coord)
            return all(c > MIN_GRAY_SCALE_LEVEL for c in pixel)
        return all(c > MIN_GRAY_SCALE_LEVEL for c in pag.pixel(*self.fish_icon_coord))

    def is_fish_hooked_twice(self, frame=None) -> bool:
        if not self.is_fish_hooked(frame=frame):
            return False

        time.sleep(add_jitter(self.cfg.PROFILE.HOOK_DELAY, self.cfg.BOT.JITTER_SCALE))
        # 第二次检测需要新帧
        if self.is_fish_hooked():
            return True
        return False

    def is_fish_captured(self, frame=None):
        return self._get_image_box("keep", 0.9, frame=frame)

    def is_fish_in_list(self, fish_species_list: tuple | list, frame=None) -> bool:
        """Check if the fish species matches any in the table.

        :param fish_species_list: fish species list
        :type fish_species_list: tuple | list
        :return: True if the fish species matches, False otherwise
        :rtype: bool
        """
        for species in fish_species_list:
            if self.is_fish_species_matched(species, frame=frame):
                return True
        return False

    # ---------------------------- Retrieval detection --------------------------- #
    def is_retrieval_finished(self, frame=None):
        if self.is_tackle_ready(frame=frame):
            return True

        if self.cfg.ARGS.RAINBOW is None:
            return self._get_image_box("wheel", self.cfg.BOT.SPOOL_CONFIDENCE, frame=frame)
        elif self.cfg.ARGS.RAINBOW == 0:
            return self._get_image_box("0m", self.cfg.BOT.SPOOL_CONFIDENCE, frame=frame)
        else:  # self.cfg.ARGS.RAINBOW = 5, detect 0m or 5m
            return self._get_image_box(
                "5m", self.cfg.BOT.SPOOL_CONFIDENCE, frame=frame
            ) or self._get_image_box("0m", self.cfg.BOT.SPOOL_CONFIDENCE, frame=frame)

    def is_line_snagged(self, frame=None) -> bool:
        if frame is not None:
            return self._get_pixel_from_frame(frame, *self.snag_icon_coord) == CRITICAL_COLOR
        return pag.pixel(*self.snag_icon_coord) == CRITICAL_COLOR

    def is_line_at_end(self, frame=None) -> bool:
        if frame is not None:
            pixel = self._get_pixel_from_frame(frame, *self.spool_icon_coord)
            return pixel in (WARNING_COLOR, CRITICAL_COLOR)
        return pag.pixel(*self.spool_icon_coord) in (WARNING_COLOR, CRITICAL_COLOR)

    def is_clip_open(self, frame=None) -> bool:
        if frame is not None:
            pixel = self._get_pixel_from_frame(frame, *self.clip_icon_coord)
            return not all(c > MIN_GRAY_SCALE_LEVEL for c in pixel)
        return not all(
            c > MIN_GRAY_SCALE_LEVEL for c in pag.pixel(*self.clip_icon_coord)
        )

    # ------------------------------ Text detection ------------------------------ #
    def is_tackle_ready(self, frame=None):
        return self._get_image_box("ready", 0.6, frame=frame)

    def is_tackle_broken(self, frame=None):
        return self._get_image_box("broke", 0.8, frame=frame)

    def is_lure_broken(self, frame=None):
        return self._get_image_box("lure_is_broken", 0.8, frame=frame)

    def is_moving_in_bottom_layer(self, frame=None):
        return self._get_image_box("movement", 0.7, frame=frame)

    # ------------------------------ Hint detection ------------------------------ #
    def is_disconnected(self, frame=None):
        return self._get_image_box("disconnected", 0.9, frame=frame)

    def is_ticket_expired(self, frame=None):
        return self._get_image_box("ticket", 0.9, frame=frame)

    def is_keepnet_full(self, frame=None):
        return self._get_image_box("keepnet_is_full", 0.9, frame=frame)

    def is_gift_receieved(self, frame=None):
        return self._get_image_box("gift", 0.9, frame=frame)

    def is_card_receieved(self, frame=None):
        return self._get_image_box("card", 0.9, frame=frame)

    def is_event_triggered(self, frame=None):
        return self._get_image_box("event_ok", 0.95, frame=frame)

    # ------------------------------- Item crafting ------------------------------ #
    def is_operation_failed(self, frame=None):
        return self._get_image_box("warning", 0.8, frame=frame)

    def is_operation_success(self, frame=None):
        return self._get_image_box("ok_black", 0.8, frame=frame) or self._get_image_box(
            "ok_white", 0.8, frame=frame
        )

    def is_material_complete(self, frame=None):
        return not self._get_image_box("material_slot", 0.7, frame=frame)

    def get_make_button_position(self, frame=None):
        return self._get_image_box("make", 0.9, frame=frame)

    def get_discard_yes_position(self, frame=None):
        return self._get_image_box("discard_yes", 0.9, frame=frame)

    # ---------------------- Quiting game from control panel --------------------- #
    def get_quit_position(self, frame=None):
        return self._get_image_box("quit", 0.8, frame=frame)

    def get_yes_position(self, frame=None):
        return self._get_image_box("yes", 0.8, frame=frame)

    # ------------------------ Quiting game from main menu ----------------------- #
    def get_exit_icon_position(self, frame=None):
        return self._get_image_box("exit", 0.8, frame=frame)

    def get_confirm_button_position(self, frame=None):
        return self._get_image_box("confirm", 0.8, frame=frame)

    # ------------------------------- Player stats ------------------------------- #
    def get_food_position(self, food: str, frame=None):
        return self._get_image_box(food, 0.9, frame=frame)

    def is_energy_high(self, frame=None) -> bool:
        box = self._get_image_box("energy", 0.8, frame=frame)
        if not box:
            return False
        x, y = utils.get_box_center_integers(box)
        # default threshold: 0.74,  well done FishSoft
        last_point = int(19 + 152 * self.cfg.STAT.ENERGY_THRESHOLD) - 1
        if frame is not None:
            return self._get_pixel_from_frame(frame, x + 19, y) == self._get_pixel_from_frame(frame, x + last_point, y)
        return pag.pixel(x + 19, y) == pag.pixel(x + last_point, y)

    def is_hunger_low(self, frame=None) -> bool:
        box = self._get_image_box("food", 0.8, frame=frame)
        if not box:
            return False
        x, y = utils.get_box_center_integers(box)
        last_point = int(18 + 152 * self.cfg.STAT.HUNGER_THRESHOLD) - 1
        if frame is not None:
            return not self._get_pixel_from_frame(frame, x + 18, y) == self._get_pixel_from_frame(frame, x + last_point, y)
        return not pag.pixel(x + 18, y) == pag.pixel(x + last_point, y)

    def is_comfort_low(self, frame=None) -> bool:
        box = self._get_image_box("comfort", 0.8, frame=frame)
        if not box:
            return False
        x, y = utils.get_box_center_integers(box)
        last_point = int(18 + 152 * self.cfg.STAT.COMFORT_THRESHOLD) - 1
        if frame is not None:
            return not self._get_pixel_from_frame(frame, x + 18, y) == self._get_pixel_from_frame(frame, x + last_point, y)
        return not pag.pixel(x + 18, y) == pag.pixel(x + last_point, y)

    # ----------------------------- Item replacement ----------------------------- #
    def get_scrollbar_position(self, frame=None):
        return self._get_image_box("scrollbar", 0.97, frame=frame)

    def get_100wear_position(self, frame=None):
        return self._get_image_box("100wear", 0.98, frame=frame)

    def get_favorite_item_positions(self, frame=None):
        return self._get_image_box("favorite", 0.95, multiple=True, frame=frame)

    def is_pva_chosen(self, frame=None):
        return self._get_image_box("pva_icon", 0.6, frame=frame) is None

    def is_dry_mix_chosen(self, frame=None):
        return not self._get_image_box("groundbait_is_not_chosen", 0.8, frame=frame)

    def is_bait_chosen(self, frame=None):
        if self.cfg.PROFILE.MODE in ("spin", "pirk", "elevator"):
            return True

        # Two bait slots, check only the first one
        if self.cfg.PROFILE.MODE in ("telescopic", "bolognese"):
            return (
                pag.locate(
                    pag.screenshot(region=self.bait_icon_coord),
                    self.bait_icon_reference_img,
                    confidence=0.6,
                )
                is None
            )
        return self._get_image_box("bait_icon", 0.6, frame=frame) is None

    def is_groundbait_chosen(self, frame=None):
        return self._get_image_box("groundbait_icon", 0.6, frame=frame) is None

    def get_groundbait_position(self, frame=None):
        return self._get_image_box("classic_feed_mix", 0.95, frame=frame)

    def get_dry_mix_position(self, frame=None):
        return self._get_image_box("dry_feed_mix", 0.95, frame=frame)

    def get_pva_position(self, frame=None):
        return self._get_image_box("pva_stick_or_pva_stringer", 0.95, frame=frame)

    # ------------------------------ Friction brake ------------------------------ #
    def is_friction_brake_high(self, frame=None) -> bool:
        if frame is not None:
            pixel = self._get_pixel_from_frame(frame, *self.friction_brake_coord)
            return all(
                abs(pixel[i] - RED_FRICTION_BRAKE[i]) <= COLOR_TOLERANCE
                for i in range(3)
            )
        return pag.pixelMatchesColor(
            *self.friction_brake_coord, RED_FRICTION_BRAKE, COLOR_TOLERANCE
        )

    def is_reel_burning(self, frame=None) -> bool:
        if frame is not None:
            return self._get_pixel_from_frame(frame, *self.reel_burning_icon_coord) == ORANGE_REEL
        return pag.pixel(*self.reel_burning_icon_coord) == ORANGE_REEL

    def is_float_state_changed(self, reference_img):
        current_img = pag.screenshot(region=self.float_camera_rect)
        return not pag.locate(
            current_img.filter(ImageFilter.GaussianBlur(radius=3)),
            reference_img,
            grayscale=True,
            confidence=self.cfg.PROFILE.FLOAT_SENSITIVITY,
        )

    def get_ticket_position(self, duration: int, frame=None):
        return self._get_image_box(f"ticket_{duration}", 0.95, frame=frame)

    def is_harvest_success(self, frame=None):
        return self._get_image_box("ok_black", 0.8, frame=frame)

    def is_stuck_at_casting(self, frame=None):
        return self._get_image_box("cast", 0.7, frame=frame)
