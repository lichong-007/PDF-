from __future__ import annotations

from pathlib import Path

import fitz


def render_pages_to_png(
    pdf_path: str | Path,
    pages: list[int],
    out_dir: str | Path,
    *,
    dpi: int = 200,
) -> list[Path]:
    """
    将指定页码（1-based）渲染为 PNG。
    返回生成文件路径列表（与 pages 顺序一致）。
    """
    pdf_path = Path(pdf_path).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    doc = fitz.open(str(pdf_path))
    try:
        written: list[Path] = []
        for pno in pages:
            page = doc.load_page(pno - 1)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            out = out_dir / f"page_{pno:03d}.png"
            pix.save(str(out))
            written.append(out)
        return written
    finally:
        doc.close()
