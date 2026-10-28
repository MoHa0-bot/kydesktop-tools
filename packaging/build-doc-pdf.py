#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
"""把 README.md 渲染成 PDF 使用手册（docs/kylinpkg-manual.pdf）。

流程：markdown -> HTML（python-markdown）-> PDF（weasyprint）。
依赖（均装在运行环境的 Python venv 中即可）：
  pip install markdown weasyprint

用法（仓库根目录）：
  python3 packaging/build-doc-pdf.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
README = PROJECT_DIR / "README.md"
OUT_PDF = PROJECT_DIR / "docs" / "kylinpkg-manual.pdf"

# 页面样式：正文用 Noto Sans CJK SC；A4 页边距由 @page 控制，
# 章节标题避免与正文断页，表格/代码块避免跨页拆断。
CSS = """\
@page {
  size: A4;
  margin: 18mm 16mm 16mm;
  @bottom-center {
    content: "kylinpkg 使用手册 · 第 " counter(page) " 页 / 共 " counter(pages) " 页";
    font-size: 8.5pt; color: #8a919c;
    font-family: "Noto Sans CJK SC", sans-serif;
  }
}
* { box-sizing: border-box; }
body {
  font-family: "Noto Sans CJK SC", "WenQuanYi Micro Hei", sans-serif;
  font-size: 10.5pt; line-height: 1.65; color: #1f2328; margin: 0;
}
h1 { font-size: 19pt; border-bottom: 2px solid #2f6fdb; padding-bottom: 6px; }
h2 { font-size: 14.5pt; border-bottom: 1px solid #d0d7de; padding-bottom: 4px;
     margin-top: 26px; page-break-after: avoid; }
h3 { font-size: 12pt; margin-top: 20px; page-break-after: avoid; }
p, li { orphans: 2; widows: 2; }
code {
  font-family: "Noto Sans Mono CJK SC", "DejaVu Sans Mono", monospace;
  font-size: 9pt; background: #f0f2f5; padding: 1px 4px; border-radius: 3px;
}
pre {
  background: #f6f8fa; border: 1px solid #d8dee4; border-radius: 6px;
  padding: 10px 12px; page-break-inside: avoid;
}
pre code { background: none; padding: 0; white-space: pre-wrap; word-break: break-all; }
table { border-collapse: collapse; width: 100%; margin: 10px 0;
        font-size: 9.5pt; page-break-inside: avoid; }
th, td { border: 1px solid #d0d7de; padding: 5px 8px; text-align: left;
         word-break: break-all; }
th { background: #eef1f5; }
blockquote { margin: 8px 0; padding: 2px 12px; color: #57606a;
             border-left: 4px solid #d0d7de; }
a { color: #2f6fdb; text-decoration: none; }
hr { border: none; border-top: 1px solid #d0d7de; margin: 20px 0; }
"""

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>kylinpkg 使用手册</title>
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>
"""


def render_html() -> str:
    try:
        import markdown
    except ImportError:
        raise SystemExit("缺少 python-markdown：请先 pip install markdown")
    text = README.read_text(encoding="utf-8")
    body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
        output_format="html5",
    )
    return HTML_TEMPLATE.format(css=CSS, body=body)


def main() -> int:
    try:
        from weasyprint import HTML
    except ImportError:
        raise SystemExit("缺少 weasyprint：请先 pip install weasyprint")
    html = render_html()
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=str(PROJECT_DIR)).write_pdf(str(OUT_PDF))
    print("已生成：%s" % OUT_PDF)
    return 0


if __name__ == "__main__":
    sys.exit(main())
