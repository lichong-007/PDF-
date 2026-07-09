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
    if dpi <= 0:
        raise ValueError(f"dpi 必须为正数，当前: {dpi}")

    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    doc = fitz.open(str(pdf_path))
    try:
        invalid_pages = [pno for pno in pages if pno < 1 or pno > doc.page_count]
        if invalid_pages:
            raise ValueError(
                f"页码超出范围: {invalid_pages}; PDF 总页数: {doc.page_count}"
            )
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
