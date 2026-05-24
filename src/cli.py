"""命令行：只跑第一步选页。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):
    # 直接运行 python new_way/cli.py 时无包上下文，相对导入会失败；先挂项目根再绝对导入。
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from src.select_pages import analyze_pdf
else:
    from src.select_pages import analyze_pdf


def default_output_dir() -> Path:
    # new_product/new_way/cli.py -> new_product/out_test
    return Path(__file__).resolve().parents[1] / "out_test"


def default_batch_dir() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return default_output_dir() / f"batch_{ts}"


def default_output_path(pdf: Path) -> Path:
    # 每篇一个 json：<stem>.page_candidates.json
    return default_output_dir() / f"{pdf.stem}.page_candidates.json"


def batch_output_path(batch_dir: Path, pdf: Path) -> Path:
    return batch_dir / f"{pdf.stem}.page_candidates.json"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="第一步：用规则标出可能含 Experimental / 成分表 / 力学表的页",
    )
    p.add_argument("pdf", type=Path, help="PDF 文件路径，或包含多个 PDF 的目录")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="可选：输出 JSON 文件路径（单篇）或输出目录（批处理）。省略则写入 out_test/ 或 out_test/batch_*/",
    )
    args = p.parse_args(argv)

    inp = args.pdf.resolve()

    # 单篇
    if inp.is_file():
        if inp.suffix.lower() != ".pdf":
            print(f"请提供存在的 .pdf 文件: {inp}", file=sys.stderr)
            return 2
        result = analyze_pdf(inp)
        text = json.dumps(result, ensure_ascii=False, indent=2)
        out_path = (args.output.resolve() if args.output else default_output_path(inp))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"已写入 {out_path}", file=sys.stderr)
        return 0

    # 批处理目录
    if inp.is_dir():
        pdfs = sorted(p for p in inp.glob("*.pdf") if p.is_file())
        if not pdfs:
            print(f"目录下未找到 .pdf: {inp}", file=sys.stderr)
            return 2
        batch_dir = (args.output.resolve() if args.output else default_batch_dir())
        batch_dir.mkdir(parents=True, exist_ok=True)
        ok = 0
        for pth in pdfs:
            result = analyze_pdf(pth)
            text = json.dumps(result, ensure_ascii=False, indent=2)
            out_path = batch_output_path(batch_dir, pth)
            out_path.write_text(text, encoding="utf-8")
            ok += 1
        print(f"完成：写入 {ok} 个 JSON -> {batch_dir}", file=sys.stderr)
        return 0

    print(f"输入路径不存在: {inp}", file=sys.stderr)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())