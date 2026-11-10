# -*- coding: utf-8 -*-
"""按 Microsoft Word 实际分页信息回填目录，不生成 PDF。"""
import json
import os
import re
import sys

import win32com.client
from docx import Document

HERE = os.path.dirname(os.path.abspath(__file__))
DOCX = r"E:\食刻有数\计划书\计划书版本\食刻有数_商业计划书_20261104.docx"
TOC_JSON = os.path.join(HERE, "toc_entries.json")
WD_ACTIVE_END_PAGE_NUMBER = 3


def norm(text):
    return re.sub(r"\s+", "", str(text)).replace("\u3000", "")


def main():
    entries = json.load(open(TOC_JSON, encoding="utf-8"))
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = None
    try:
        doc = word.Documents.Open(os.path.abspath(DOCX), ReadOnly=False, AddToRecentFiles=False)
        doc.Repaginate()
        headings = []
        for paragraph in doc.Paragraphs:
            style = str(paragraph.Style.NameLocal)
            if style not in ("标题 1", "标题 2", "Heading 1", "Heading 2"):
                continue
            title = norm(paragraph.Range.Text.rstrip("\r\x07"))
            page = int(paragraph.Range.Information(WD_ACTIVE_END_PAGE_NUMBER))
            headings.append((title, page))

        pages, cursor = [], 0
        for _, title in entries:
            key = norm(title)
            hit = None
            for i in range(cursor, len(headings)):
                if headings[i][0] == key:
                    hit = headings[i][1]
                    cursor = i + 1
                    break
            if hit is None:
                raise RuntimeError(f"目录标题未匹配到 Word 标题：{title}")
            pages.append(hit)

        static_entries = [p for p in doc.Paragraphs if str(p.Style.NameLocal) == "目录条目"]
        if len(static_entries) != len(entries):
            raise RuntimeError(f"目录条目数不一致：文档 {len(static_entries)}，索引 {len(entries)}")
        for paragraph, entry, page in zip(static_entries, entries, pages):
            paragraph.Range.Text = f"{entry[1]}\t{page}\r"
        doc.Save()
        print(f"回填目录 {len(entries)} 项；Word 分页 {doc.ComputeStatistics(2)} 页")
        print("目录页码单调检查：", all(a <= b for a, b in zip(pages, pages[1:])))
    finally:
        if doc is not None:
            doc.Close(SaveChanges=False)
        word.Quit()


if __name__ == "__main__":
    main()
