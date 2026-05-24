"""
从第一步生成的 *.page_candidates.json 里取出要渲染的页码。
策略 A：使用 candidate_pages 全部页码（去重、排序）。
"""

from __future__ import annotations

import json
from pathlib import Path


def load_pages_plan(json_path: str | Path) -> tuple[Path, list[int]]:
    """
    读取 JSON，返回 (PDF 绝对路径, 页码列表 1-based)。
    """
    path = Path(json_path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    pdf = Path(data["pdf_path"]).resolve()
    raw = data.get("candidate_pages") or []
    pages = sorted({int(p) for p in raw})
    return pdf, pages
