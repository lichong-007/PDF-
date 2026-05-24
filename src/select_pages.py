"""
第一步：读 PDF，按页抽取文本，套用 rules，得到「建议送给大模型的页」及命中说明。
"""

from __future__ import annotations

from pathlib import Path

import fitz

from . import page_labels as L
from .rules import (
    match_composition_table,
    match_mechanical_table,
    match_section2_experimental,
)


def iter_page_texts(pdf_path: str | Path) -> list[tuple[int, str]]:
    """返回 (1-based 页码, 该页全文)。"""
    path = Path(pdf_path)
    doc = fitz.open(path)
    try:
        out: list[tuple[int, str]] = []
        for i in range(doc.page_count):
            text = doc.load_page(i).get_text("text") or ""
            out.append((i + 1, text))
        return out
    finally:
        doc.close()


def labels_for_page(page_text: str) -> dict[str, str]:
    """
    对单页文本跑全部规则。
    返回 { 标签常量: 匹配片段 }，只含本页命中的项。
    """
    hits: dict[str, str] = {}
    s = match_section2_experimental(page_text)
    if s:
        hits[L.SECTION2_EXPERIMENTAL] = s
    s = match_composition_table(page_text)
    if s:
        hits[L.COMPOSITION_TABLE] = s
    s = match_mechanical_table(page_text)
    if s:
        hits[L.MECHANICAL_TABLE] = s
    return hits


def analyze_pdf(pdf_path: str | Path) -> dict:
    """
    汇总整本 PDF。
    结构简单，便于你 print(json.dumps(..., ensure_ascii=False, indent=2)) 检查。
    """
    path = str(Path(pdf_path).resolve())
    pages_out: list[dict] = []
    all_pages_with_any_label: list[int] = []

    for page_no, text in iter_page_texts(path):
        hits = labels_for_page(text)
        if not hits:
            continue
        all_pages_with_any_label.append(page_no)
        pages_out.append(
            {
                "page": page_no,
                "labels": list(hits.keys()),
                "snippets": hits,
            }
        )

    return {
        "pdf_path": path,
        "candidate_page_count": len(all_pages_with_any_label),
        "candidate_pages": all_pages_with_any_label,
        "pages": pages_out,
    }