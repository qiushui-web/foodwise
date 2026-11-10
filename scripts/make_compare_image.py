# -*- coding: utf-8 -*-
"""把参考截图与当前同视口截图拼成上下对比图，便于一眼看出差异。"""
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile

from PIL import Image, ImageDraw, ImageFont

PAIRS = [
    ("经营总览", r"E:\食刻有数\计划书\计划书照片\网站截图\20261014_功能展示\01_经营驾驶舱_展示.png",
     r"E:\食刻有数\项目代码\output\current-1920\dashboard.png", "dashboard"),
    ("备餐计划", r"E:\食刻有数\计划书\计划书照片\网站截图\20261014_功能展示\04_备餐决策中心_展示.png",
     r"E:\食刻有数\项目代码\output\current-1920\prediction.png", "prediction"),
]
OUT = Path(r"E:\食刻有数\项目代码\output\before-after")
OUT.mkdir(parents=True, exist_ok=True)

WIDTH = 1200
LABEL_H = 40
GAP = 16

try:
    font = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 26)
except OSError:
    font = ImageFont.load_default()

def open_reference(path):
    source = Path(path)
    if source.exists():
        return Image.open(source).convert("RGB")
    root = Path(__file__).resolve().parents[2]
    member = source.relative_to(root).as_posix()
    with ZipFile(root / "计划书" / "照片旧版资源_20261109.zip") as archive:
        return Image.open(BytesIO(archive.read(member))).convert("RGB")

for title, old_path, new_path, slug in PAIRS:
    old = open_reference(old_path)
    new = Image.open(new_path).convert("RGB")
    def scaled(img):
        ratio = WIDTH / img.width
        return img.resize((WIDTH, int(img.height * ratio)), Image.LANCZOS)
    old, new = scaled(old), scaled(new)
    canvas = Image.new("RGB", (WIDTH, LABEL_H * 2 + old.height + new.height + GAP * 3), (245, 247, 249))
    draw = ImageDraw.Draw(canvas)
    draw.text((14, 8), f"{title}｜参考截图（2026-10-14）", fill=(40, 60, 75), font=font)
    canvas.paste(old, (0, LABEL_H))
    y = LABEL_H + old.height + GAP
    draw.text((14, y - LABEL_H + 6), f"{title}｜当前站点（同一 1920 视口）", fill=(40, 60, 75), font=font)
    canvas.paste(new, (0, y + 8))
    target = OUT / f"compare-{slug}.png"
    canvas.save(target, optimize=True)
    print(target, canvas.size)