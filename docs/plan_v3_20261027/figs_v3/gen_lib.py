# -*- coding: utf-8 -*-
"""计划书 v3 示意图绘制基础库。

画布单位 = CSS px，1 单位 ≈ 0.264 mm；500 单位 = 13.2 cm 版心宽。
渲染：Chrome headless，device-scale-factor 3.13 → 约 301 dpi。
"""
import os
import re
import subprocess

W = 500  # 版心宽（13.2 cm）
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SCALE = 3.13

# 项目配色（见《图表作图方案》总则）
PRIMARY = "#1F4E79"
SECOND = "#2E75B6"
ACCENT = "#C00000"
GRAY = "#7F7F7F"
INK = "#1A1A1A"
LIGHT = "#F2F5F9"
LIGHT2 = "#EDF3F8"
BORDER = "#C9D3DF"
WHITE = "#FFFFFF"

FONT = "'SimHei','Microsoft YaHei',sans-serif"


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


class Fig:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.parts = []
        self.defs = []
        self._markers = set()

    # ---------------- 基础图元 ----------------
    def raw(self, s):
        self.parts.append(s)

    def marker(self, color):
        key = color.replace("#", "")
        mid = f"ah{key}"
        if mid not in self._markers:
            self._markers.add(mid)
            self.defs.append(
                f'<marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" '
                f'markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">'
                f'<path d="M0,0.8 L9.6,5 L0,9.2 z" fill="{color}"/></marker>'
            )
        return mid

    def text(self, x, y, s, fs=11.0, fill=INK, anchor="middle", bold=False,
             ls=0.0, italic=False):
        st = f'font-family:{FONT};font-size:{fs}px;fill:{fill};letter-spacing:{ls}px;'
        st += f'font-weight:{"700" if bold else "400"};'
        if italic:
            st += "font-style:italic;"
        self.raw(f'<text x="{x}" y="{y}" text-anchor="{anchor}" style="{st}">{esc(s)}</text>')

    def rect(self, x, y, w, h, fill=WHITE, stroke=BORDER, rx=6, lw=1.0, dash=None, op=1.0):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.raw(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" '
                 f'fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="{lw}"{d}/>')

    def box(self, x, y, w, h, title, sub=None, fill=WHITE, stroke=BORDER, tcol=INK,
            fs=11.5, rx=6, lw=1.0, bold=False, dash=None, subcol=GRAY, subfs=9.5,
            align="middle"):
        self.rect(x, y, w, h, fill, stroke, rx, lw, dash)
        cx = x + w / 2 if align == "middle" else x + 9
        anchor = "middle" if align == "middle" else "start"
        if sub:
            self.text(cx, y + h / 2 - 3.5, title, fs, tcol, anchor, bold)
            self.text(cx, y + h / 2 + 11.5, sub, subfs, subcol, anchor)
        else:
            self.text(cx, y + h / 2 + 4, title, fs, tcol, anchor, bold)

    def line(self, x1, y1, x2, y2, color=PRIMARY, lw=1.0, dash=None, head=True):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        m = f' marker-end="url(#{self.marker(color)})"' if head else ""
        self.raw(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
                 f'stroke-width="{lw}"{d}{m}/>')

    def path(self, d, color=PRIMARY, lw=1.0, dash=None, head=True, fill="none"):
        m = f' marker-end="url(#{self.marker(color)})"' if head else ""
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.raw(f'<path d="{d}" fill="{fill}" stroke="{color}" stroke-width="{lw}"{da}{m}/>')

    def arrow(self, x1, y1, x2, y2, color=PRIMARY, lw=1.0, dash=None):
        self.line(x1, y1, x2, y2, color, lw, dash)

    def elbow(self, pts, color=PRIMARY, lw=1.0, dash=None, head=True, r=6):
        """折线路径，转角圆角。pts=[(x,y),...]"""
        d = f"M{pts[0][0]},{pts[0][1]}"
        for i in range(1, len(pts)):
            x0, y0 = pts[i - 1]
            x1, y1 = pts[i]
            if i < len(pts) - 1:
                x2, y2 = pts[i + 1]
                # 圆角：在拐点前 r 处停，再画到下一段起点后 r
                d += f" L{x1},{y1}"
            else:
                d += f" L{x1},{y1}"
        self.path(d, color, lw, dash, head)

    def chip(self, x, y, label, fs=9.2, fg=PRIMARY, bg=LIGHT, stroke=None, padx=8, h=19, rx=9.5):
        w = padx * 2 + sum(1.0 if ord(c) > 127 else 0.52 for c in label) * fs
        self.rect(x, y, w, h, bg, stroke or (fg if stroke is None else stroke), rx, 0.8)
        self.text(x + w / 2, y + h / 2 + 3.4, label, fs, fg)
        return w

    def note(self, x, y, s, fs=9.0, fill=GRAY, anchor="middle"):
        self.text(x, y, s, fs, fill, anchor)

    def text_outlined(self, x, y, s, fs=9.0, fill=INK, anchor="middle", bold=False, halo=3.2):
        """带白色描边的文字，用于压在连线上的标签。"""
        st = (f'font-family:{FONT};font-size:{fs}px;fill:{fill};letter-spacing:0px;'
              f'font-weight:{"700" if bold else "400"};paint-order:stroke;'
              f'stroke:#FFFFFF;stroke-width:{halo}px;stroke-linejoin:round;')
        self.raw(f'<text x="{x}" y="{y}" text-anchor="{anchor}" style="{st}">{esc(s)}</text>')

    def circle_num(self, cx, cy, n, r=9, color=PRIMARY, fs=10.5, bg=WHITE):
        self.raw(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{bg}" stroke="{color}" stroke-width="1.1"/>')
        self.text(cx, cy + 3.6, str(n), fs, color, bold=True)

    # ---------------- 输出 ----------------
    def svg(self):
        defs = f"<defs>{''.join(self.defs)}</defs>" if self.defs else ""
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}">{defs}{"".join(self.parts)}</svg>')

    def html(self):
        return (f'<!doctype html><html><head><meta charset="utf-8">'
                f'<style>html,body{{margin:0;padding:0;background:#fff;}}'
                f'svg{{display:block}}</style></head><body>{self.svg()}</body></html>')


def render(svg_html, out_png, w, h, workdir):
    """写 HTML → Chrome 无头截图 → PNG。"""
    os.makedirs(workdir, exist_ok=True)
    html_path = os.path.join(workdir, "_tmp_fig.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(svg_html)
    if os.path.exists(out_png):
        os.remove(out_png)
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-first-run", "--no-default-browser-check",
        f"--force-device-scale-factor={SCALE}",
        f"--window-size={w},{h}",
        f"--screenshot={out_png}",
        "file:///" + html_path.replace("\\", "/"),
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    if not os.path.exists(out_png):
        raise RuntimeError(f"chrome failed: {r.stderr[-400:]!r}")
    return out_png