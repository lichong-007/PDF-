"""第三步：读 page_candidates.json + 已渲染 PNG；每类结果一个 .md，并生成 summary.md。支持单文件或目录批处理。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from src.llm_step3 import run_extractions
    from src.vision_client import env_config, load_dotenv_file
else:
    from .llm_step3 import run_extractions
    from .vision_client import env_config, load_dotenv_file


def default_render_root() -> Path:
    return Path(__file__).resolve().parents[1] / "out_test" / "rendered"


def default_llm_out_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "out_test" / "llm_output"


def safe_folder_name(pdf_stem: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "_", pdf_stem)
    return s.strip() or "output"


SKIP_PLACEHOLDER = "（本次未调用大模型：无对应标签页面，或缺少第二步渲染的 PNG。）\n"

MD_FILES = (
    ("composition.md", "composition", "化学成分"),
    ("mechanical.md", "mechanical", "力学性能"),
    ("process.md", "process", "工艺与测试"),
)


def collect_candidate_jsons(path: Path) -> list[Path]:
    """单个 .page_candidates.json，或目录下所有该文件（不递归）。"""
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


def process_one_paper(
    jp: Path,
    *,
    render_root: Path,
    out_root: Path,
    api_key: str,
    base_url: str,
    model: str,
) -> str:
    """
    处理一篇。返回 'ok' | 'skipped_all'。
    发生异常时由调用方捕获。
    """
    data = json.loads(jp.read_text(encoding="utf-8"))
    pdf_stem_raw = Path(data["pdf_path"]).stem
    folder = safe_folder_name(pdf_stem_raw)

    results = run_extractions(
        candidates_data=data,
        render_root=render_root,
        api_key=api_key,
        base_url=base_url,
        model=model,
    )
    if not any(results.values()):
        print(f"[跳过全文] {jp.name}：三类均未调用模型。", file=sys.stderr)
        return "skipped_all"

    paper_dir = out_root / folder
    paper_dir.mkdir(parents=True, exist_ok=True)

    summary_parts: list[str] = [
        "# 提取汇总\n\n",
        f"文献：`{pdf_stem_raw}`\n\n",
    ]

    for md_name, key, title_zh in MD_FILES:
        body = results[key]
        text = (body.strip() + "\n") if body else SKIP_PLACEHOLDER
        (paper_dir / md_name).write_text(text, encoding="utf-8")
        summary_parts.append(f"## {title_zh}\n\n")
        summary_parts.append(text if body else SKIP_PLACEHOLDER)
        summary_parts.append("\n")

    (paper_dir / "summary.md").write_text("".join(summary_parts), encoding="utf-8")

    print(f"已写入 {paper_dir}", file=sys.stderr)
    return "ok"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="第三步：单篇 json 或批处理目录（仅当前层 *.page_candidates.json）",
    )
    p.add_argument(
        "candidates_json",
        type=Path,
        help="一个 .page_candidates.json，或包含多篇该文件的目录",
    )
    p.add_argument(
        "--render-dir",
        type=Path,
        default=None,
        help=f"第二步 PNG 根目录，默认 {default_render_root()}",
    )
    p.add_argument(
        "--model",
        type=str,
        default=None,
        help="覆盖模型名（默认豆包视觉，见 vision_client.DEFAULT_MODEL）",
    )
    p.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="覆盖 API 根地址（默认火山方舟 api/v3）",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help=f"输出根目录，默认 {default_llm_out_dir()}",
    )
    args = p.parse_args(argv)

    load_dotenv_file(Path(__file__).resolve().parent / ".env")

    key, base, model = env_config()
    if args.model:
        model = args.model.strip()
    if args.base_url:
        base = args.base_url.strip()
    if not key:
        print(
            "未找到密钥：请在 src/.env 中设置 ARK_API_KEY=...，"
            "或导出环境变量 ARK_API_KEY / OPENAI_API_KEY",
            file=sys.stderr,
        )
        return 2

    inp = args.candidates_json.resolve()
    try:
        json_files = collect_candidate_jsons(inp)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    render_root = args.render_dir.resolve() if args.render_dir else default_render_root()
    out_root = args.out_dir.resolve() if args.out_dir else default_llm_out_dir()
    out_root.mkdir(parents=True, exist_ok=True)

    ok_n = skip_n = err_n = 0
    for jp in json_files:
        try:
            status = process_one_paper(
                jp,
                render_root=render_root,
                out_root=out_root,
                api_key=key,
                base_url=base,
                model=model,
            )
            if status == "ok":
                ok_n += 1
            else:
                skip_n += 1
        except Exception as e:
            err_n += 1
            print(f"[失败] {jp.name}: {e}", file=sys.stderr)

    print(
        f"批处理结束：成功 {ok_n}，跳过 {skip_n}，失败 {err_n}，共 {len(json_files)} 个 json。",
        file=sys.stderr,
    )
    if err_n:
        return 1
    if ok_n == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
