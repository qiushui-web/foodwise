# -*- coding: utf-8 -*-
"""一次性重绘全部示意图：输出 PNG（约 307 dpi）与同名 SVG，并写 index.json。

用法：python render_all.py [图号 ...]   # 不带参数则全画
"""
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gen_lib
from gen_lib import W, render

MODULES = ["fig_1_1", "fig_2", "fig_3", "fig_4", "fig_charts", "fig_6"]
OUT = os.path.join(HERE, "out")


def collect():
    items = []
    for m in MODULES:
        mod = importlib.import_module(m)
        for name in dir(mod):
            if name.startswith("fig_") and callable(getattr(mod, name)):
                fig_id = name.replace("fig_", "").replace("_", "-")
                items.append((fig_id, getattr(mod, name)))
    return items


def main(argv):
    only = set(argv[1:])
    os.makedirs(OUT, exist_ok=True)
    index = {}
    for fig_id, fn in collect():
        if only and fig_id not in only:
            continue
        f, h = fn()
        svg_path = os.path.join(OUT, f"图{fig_id}.svg")
        png_path = os.path.join(OUT, f"图{fig_id}.png")
        with open(svg_path, "w", encoding="utf-8") as fp:
            fp.write(f.svg())
        render(f.html(), png_path, W, h, OUT)
        index[f"图{fig_id}"] = {"canvas": [W, h], "png": os.path.basename(png_path),
                                "svg": os.path.basename(svg_path)}
        print("ok", fig_id, f"{W}x{h}")
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as fp:
        json.dump(index, fp, ensure_ascii=False, indent=1)
    print("total", len(index))


if __name__ == "__main__":
    main(sys.argv)