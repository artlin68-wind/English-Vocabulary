#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_icons.py — 產生 PWA / iOS 圖示(純程式繪製,不依賴外部素材)。
輸出:icons/icon-192.png, icon-512.png, icon-512-maskable.png, apple-touch-icon-180.png,
      icons/favicon-32.png
風格:深色圓角底 + 亮色「背」字(App 標題「背單字」)。"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "icons")
os.makedirs(OUT, exist_ok=True)

BG = (14, 18, 32)        # 深藍黑
ACCENT = (109, 214, 168)  # 薄荷綠(與 App 主色一致)
FG = (240, 244, 255)


def find_font(size):
    # 找一個含中文字形的字型;找不到就用預設(可能無「背」字,退而顯示 ABC)
    candidates = [
        r"C:\Windows\Fonts\msjhbd.ttc",   # 微軟正黑 Bold
        r"C:\Windows\Fonts\msjh.ttc",     # 微軟正黑
        r"C:\Windows\Fonts\msyhbd.ttc",   # 微軟雅黑
        r"C:\Windows\Fonts\arialbd.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size), os.path.basename(c)
            except OSError:
                continue
    return ImageFont.load_default(), "default"


def draw_icon(size, maskable=False):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 底:圓角矩形(maskable 需留安全邊,底鋪滿整塊)
    if maskable:
        d.rectangle([0, 0, size, size], fill=BG)
        pad = int(size * 0.18)
    else:
        r = int(size * 0.22)
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=BG)
        pad = int(size * 0.1)
    # 底部強調條
    bar_h = max(2, int(size * 0.06))
    d.rounded_rectangle(
        [pad, size - pad - bar_h, size - pad, size - pad],
        radius=bar_h // 2, fill=ACCENT)
    # 主字
    ch = "背"
    font, name = find_font(int(size * 0.62))
    if name == "default":
        ch = "A"
        font, _ = find_font(int(size * 0.5))
    # 置中(略上移,讓下方留給強調條)
    try:
        bbox = d.textbbox((0, 0), ch, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (size - tw) / 2 - bbox[0]
        y = (size - th) / 2 - bbox[1] - int(size * 0.04)
    except Exception:
        x = y = size * 0.2
    d.text((x, y), ch, font=font, fill=FG)
    return img


def save(img, name):
    p = os.path.join(OUT, name)
    img.save(p)
    print("wrote", os.path.relpath(p, ROOT), img.size)


save(draw_icon(192), "icon-192.png")
save(draw_icon(512), "icon-512.png")
save(draw_icon(512, maskable=True), "icon-512-maskable.png")
save(draw_icon(180), "apple-touch-icon-180.png")
save(draw_icon(32), "favicon-32.png")
print("done.")
