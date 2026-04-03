"""拖钓巡航数字模板校准工具。

使用方式：
    python -m rf4s.controller.calibrate

功能：
    1. 截取游戏窗口中坐标显示区域
    2. 预处理（灰度 + 二值化）
    3. 轮廓分割出各个字符
    4. 交互式让用户标注每个字符
    5. 保存为数字模板文件到 static/digits/
"""

import sys
from pathlib import Path
from time import sleep

import cv2
import mss
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = ROOT / "static" / "digits"


def capture_coord_region(
    sct: mss.mss, region: tuple[int, int, int, int]
) -> np.ndarray:
    """截取坐标显示区域。

    :param sct: mss 截图器
    :param region: (left, top, width, height)
    :return: BGR 图像
    """
    monitor = {
        "left": region[0],
        "top": region[1],
        "width": region[2],
        "height": region[3],
    }
    raw = sct.grab(monitor)
    return np.array(raw)[:, :, :3].copy()


def preprocess(img: np.ndarray) -> np.ndarray:
    """灰度 + 二值化预处理。"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    return binary


def segment_characters(binary: np.ndarray) -> list[np.ndarray]:
    """轮廓分割出各字符图片。"""
    contours, _ = cv2.findContours(
        binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    bboxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w >= 3 and h >= 5:
            bboxes.append((x, y, w, h))

    bboxes.sort(key=lambda b: b[0])

    chars = []
    for x, y, w, h in bboxes:
        chars.append(binary[y : y + h, x : x + w])
    return chars


def main():
    print("=" * 50)
    print("  拖钓巡航 — 数字模板校准工具")
    print("=" * 50)
    print()
    print("请确保游戏窗口已打开，且在有坐标显示的界面。")
    print("默认截取区域: (2380, 1330, 100, 30) [2560x1440]")
    print()

    # 让用户自定义区域
    use_default = input("使用默认截取区域? (y/n, 默认 y): ").strip().lower()
    if use_default == "n":
        try:
            left = int(input("  left: "))
            top = int(input("  top: "))
            width = int(input("  width: "))
            height = int(input("  height: "))
            region = (left, top, width, height)
        except ValueError:
            print("无效输入，使用默认值")
            region = (2380, 1330, 100, 30)
    else:
        region = (2380, 1330, 100, 30)

    print(f"\n截取区域: {region}")
    print("3 秒后开始截图，请切换到游戏窗口...")

    for i in range(3, 0, -1):
        print(f"  {i}...")
        sleep(1)

    # 截图
    with mss.mss() as sct:
        img = capture_coord_region(sct, region)

    print(f"\n截图成功! 图像大小: {img.shape}")

    # 预处理
    binary = preprocess(img)

    # 分割字符
    chars = segment_characters(binary)
    print(f"检测到 {len(chars)} 个字符")

    if not chars:
        print("未检测到任何字符！请检查截取区域是否正确。")
        print("提示: 可以调整区域坐标或游戏窗口位置。")
        # 保存原图和二值化图供调试
        debug_dir = ROOT / "static" / "digits" / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / "original.png"), img)
        cv2.imwrite(str(debug_dir / "binary.png"), binary)
        print(f"调试图片已保存到: {debug_dir}")
        sys.exit(1)

    # 显示并让用户标注
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    saved = {}

    print("\n请为每个检测到的字符输入标签:")
    print("  0-9 = 数字, c = 冒号(:), s = 跳过")
    print()

    for i, char_img in enumerate(chars):
        # 放大显示
        display = cv2.resize(char_img, (80, 120), interpolation=cv2.INTER_NEAREST)
        window_name = f"字符 {i + 1}/{len(chars)}"
        cv2.imshow(window_name, display)
        cv2.waitKey(100)

        label = input(f"  字符 {i + 1}: ").strip()
        cv2.destroyWindow(window_name)

        if label == "s":
            continue
        elif label == "c":
            filename = "colon.png"
        elif label.isdigit() and len(label) == 1:
            filename = f"{label}.png"
        else:
            print(f"  无效标签 '{label}'，跳过")
            continue

        filepath = TEMPLATE_DIR / filename
        # 如果已有同名模板，询问是否覆盖
        if filename in saved:
            print(f"  '{filename}' 已标注过，跳过重复")
            continue

        cv2.imwrite(str(filepath), char_img)
        saved[filename] = True
        print(f"  -> 已保存: {filepath}")

    cv2.destroyAllWindows()

    print(f"\n校准完成! 共保存 {len(saved)} 个模板到: {TEMPLATE_DIR}")
    print("缺少的字符可以下次在不同坐标位置再次运行校准补充。")

    # 检查完整性
    expected = [f"{d}.png" for d in range(10)] + ["colon.png"]
    existing = [f for f in expected if (TEMPLATE_DIR / f).exists()]
    missing = [f for f in expected if f not in existing]

    if missing:
        print(f"\n还缺少以下模板: {', '.join(missing)}")
        print("多次运行校准工具，在不同坐标位置截图来补全所有数字。")
    else:
        print("\n所有模板已就绪，巡航 OCR 可以正常使用!")


if __name__ == "__main__":
    main()
