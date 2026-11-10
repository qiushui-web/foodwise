"""从本地文献 PDF 中抽取可引用的浪费率口径，作为模拟器与报告的数字锚点。"""

from pathlib import Path

import fitz

ROOT = Path(r"E:\食刻有数\数据来源")
TARGETS = [
    "全国高校食堂堂食浪费概况_知网.pdf",
    "中国消费端食物浪费规模_资源科学.pdf",
    "实现食物理性消费_中国农大.pdf",
    "Food_Loss_Waste_in_China_G20.pdf",
]
KEYWORDS = ("浪费率", "浪费量", "kg", "千克", "克/", "人均", "占比", "百分比", "%", "万吨")


def main() -> int:
    for name in TARGETS:
        path = ROOT / name
        if not path.exists():
            print(f"[missing] {name}")
            continue
        document = fitz.open(path)
        print(f"\n===== {name} ({document.page_count} pages) =====")
        for page_index in range(document.page_count):
            text = document.load_page(page_index).get_text("text").replace("\n", " ")
            hits = [sentence.strip() for sentence in text.split("。") if any(key in sentence for key in KEYWORDS)]
            if hits:
                print(f"-- p{page_index + 1}")
                for sentence in hits[:4]:
                    print("   ", sentence[:260])
        document.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())