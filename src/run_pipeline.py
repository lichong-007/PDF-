"""
一键流水线：第一步选页 → 第二步渲染 PNG → 第三步调用大模型。

用法（在项目根或 src 下均可，路径建议写绝对路径）：
  python src/run_pipeline.py "E:\\new_product\\力学性能"
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="对 PDF 目录（或单篇 PDF）依次执行 cli.py → cli_step2.py → cli_step3.py",
    )
    p.add_argument(
        "pdf_path",
        type=Path,
        help="含 .pdf 的目录，或单个 .pdf 文件",
    )
    p.add_argument(
        "--batch-dir",
        type=Path,
        default=None,
        help="第一步 JSON 输出目录；默认 out_test/batch_pipeline_时间戳",
    )
    args = p.parse_args(argv)

    root = project_root()
    src = root / "src"
    py = sys.executable
    inp = args.pdf_path.resolve()
    if not inp.exists():
        print(f"路径不存在: {inp}", file=sys.stderr)
        return 2

    if args.batch_dir:
        batch_dir = args.batch_dir.resolve()
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        batch_dir = root / "out_test" / f"batch_pipeline_{ts}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    if inp.is_dir():
        step1_out: str = str(batch_dir)
    elif inp.is_file() and inp.suffix.lower() == ".pdf":
        step1_out = str(batch_dir / f"{inp.stem}.page_candidates.json")
    else:
        print(f"需要目录（内含 .pdf）或单个 .pdf 文件: {inp}", file=sys.stderr)
        return 2

    steps: list[tuple[str, list[str]]] = [
        ("第一步：选页 JSON", [py, str(src / "cli.py"), str(inp), "-o", step1_out]),
        ("第二步：渲染 PNG", [py, str(src / "cli_step2.py"), str(batch_dir)]),
        ("第三步：大模型提取", [py, str(src / "cli_step3.py"), str(batch_dir)]),
    ]

    for title, cmd in steps:
        print(f"\n=== {title} ===", file=sys.stderr)
        r = subprocess.run(cmd, cwd=str(root))
        if r.returncode != 0:
            print(f"失败（退出码 {r.returncode}），已中止后续步骤。", file=sys.stderr)
            return r.returncode

    print(f"\n流水线完成。\n  JSON：{batch_dir}\n  PNG：{root / 'out_test' / 'rendered'}\n  MD：{root / 'out_test' / 'llm_output'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
