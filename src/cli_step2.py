"""第二步：读 page_candidates.json → 按 candidate_pages 渲染 PNG。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from src.from_candidates import load_pages_plan
    from src.render_png import render_pages_to_png
else:
    from .from_candidates import load_pages_plan
    from .render_png import render_pages_to_png


def default_render_root() -> Path:
    return Path(__file__).resolve().parents[1] / "out_test" / "rendered"


def collect_json_inputs(path: Path) -> list[Path]:
    """单个 json 文件，或目录下所有 *.page_candidates.json（不递归）。"""
    if path.is_file():
        if not path.name.endswith(".page_candidates.json"):
            raise ValueError(f"需要 .page_candidates.json 文件: {path}")
        return [path.resolve()]
    if path.is_dir():
        found = sorted(path.glob("*.page_candidates.json"))
        if not found:
            raise ValueError(f"目录下没有 *.page_candidates.json: {path}")
        return found
    raise ValueError(f"路径不存在: {path}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="第二步：根据 candidate_pages 把 PDF 对应页渲染成 PNG",
    )
    p.add_argument(
        "input",
        type=Path,
        help="一个 .page_candidates.json，或包含多个该文件的目录（不扫子目录）",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help=f"PNG 根目录，下面按 PDF 文件名分子文件夹。默认: {default_render_root()}",
    )
    p.add_argument("--dpi", type=int, default=200, help="渲染 DPI，默认 200")
    args = p.parse_args(argv)

    out_root = (args.output_dir.resolve() if args.output_dir else default_render_root())
    out_root.mkdir(parents=True, exist_ok=True)

    try:
        json_files = collect_json_inputs(args.input.resolve())
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    ok = 0
    for jp in json_files:
        try:
            pdf, pages = load_pages_plan(jp)
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"跳过 {jp.name}: {e}", file=sys.stderr)
            continue
        if not pdf.is_file():
            print(f"跳过 {jp.name}: PDF 不存在 {pdf}", file=sys.stderr)
            continue
        if not pages:
            print(f"跳过 {jp.name}: candidate_pages 为空", file=sys.stderr)
            continue
        sub = out_root / pdf.stem
        sub.mkdir(parents=True, exist_ok=True)
        written = render_pages_to_png(pdf, pages, sub, dpi=args.dpi)
        print(f"{pdf.name} -> {len(written)} 张 -> {sub}", file=sys.stderr)
        ok += 1

    print(f"完成 {ok}/{len(json_files)} 篇", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
