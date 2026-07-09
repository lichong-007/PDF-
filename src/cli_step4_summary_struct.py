"""从 summary.md 生成结构化 JSON（不写入 Excel）。"""

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
    from src.vision_client import chat_text, env_config, load_dotenv_file
else:
    from .vision_client import chat_text, env_config, load_dotenv_file

DEFAULT_SYSTEM = (
    "你是严谨的材料文献信息抽取助手。"
    "请严格按用户给定 schema 输出可解析 JSON，不要输出额外文本。"
)

FIELD_ORDER = [
    "alloy_id",
    "文献名称",
    "Mg",
    "Si",
    "Fe",
    "Cu",
    "Mn",
    "Cr",
    "Zr",
    "Sc",
    "Sr",
    "额外元素",
    "YS(屈服强度)",
    "UTS(抗拉强度)",
    "延伸率",
    "力学性能状态",
    "浇铸温度",
    "浇铸温度_来源",
    "第一次均匀化温度/T",
    "第一次均匀化时间/h",
    "第二次均匀化温度/T",
    "第二次均匀化时间/h",
    "第三次均匀化温度/T",
    "第三次均匀化时间/h",
    "轧制温度",
    "轧制起始尺寸",
    "轧制最终尺寸",
    "固溶温度",
    "固溶时间/min",
    "第一级时效温度/T",
    "第一级时效时间/min",
    "第二级时效温度/T",
    "第二级时效时间/min",
    "evidence",
]


def _prompt_dir() -> Path:
    return Path(__file__).resolve().parent / "prompts"


def load_prompt_file(name: str) -> str:
    return (_prompt_dir() / f"{name}.txt").read_text(encoding="utf-8")


def default_out_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "out_test" / "structured_output"


def collect_summary_files(path: Path) -> list[Path]:
    if path.is_file():
        if path.name != "summary.md":
            raise ValueError(f"请提供 summary.md 文件，当前: {path}")
        return [path.resolve()]
    if path.is_dir():
        found = sorted(path.rglob("summary.md"))
        if not found:
            raise ValueError(f"目录下未找到 summary.md: {path}")
        return found
    raise ValueError(f"路径不存在: {path}")


def parse_json_text(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise
        return json.loads(m.group(0))


def normalize_rows(payload: dict) -> dict:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("模型返回 JSON 缺少 rows 数组")

    normalized: list[dict] = []
    for i, row in enumerate(rows):
        if isinstance(row, dict):
            norm = {k: row.get(k) for k in FIELD_ORDER}
            extra = norm.get("额外元素")
            if not isinstance(extra, dict):
                extra = {}
            # 兼容模型把未知元素直接作为顶层键输出的情况（例如 Ti/Ni/V）。
            for k, v in row.items():
                if k not in FIELD_ORDER and k != "evidence":
                    extra[k] = v
            norm["额外元素"] = extra if extra else {}
            if not isinstance(norm.get("evidence"), dict):
                norm["evidence"] = {}
            normalized.append(norm)
            continue
        if isinstance(row, list):
            if len(row) > len(FIELD_ORDER):
                raise ValueError(f"第 {i+1} 行字段数超过预期: {len(row)} > {len(FIELD_ORDER)}")
            norm = {k: None for k in FIELD_ORDER}
            for idx, val in enumerate(row):
                norm[FIELD_ORDER[idx]] = val
            if not isinstance(norm.get("额外元素"), dict):
                norm["额外元素"] = {}
            if not isinstance(norm.get("evidence"), dict):
                norm["evidence"] = {}
            normalized.append(norm)
            continue
        raise ValueError(f"第 {i+1} 行类型非法: {type(row).__name__}")

    payload["rows"] = normalized
    return payload


def build_user_text(prompt_text: str, summary_md: str) -> str:
    return (
        f"{prompt_text.strip()}\n\n"
        "# 待解析 summary.md\n"
        "```markdown\n"
        f"{summary_md.strip()}\n"
        "```"
    )


def extract_cold_rolling_final_mm(summary_text: str) -> float | None:
    text = summary_text
    patterns = [
        r"冷轧[^。\n]{0,120}?至\s*~?\s*(\d+(?:\.\d+)?)\s*mm",
        r"冷轧[^。\n]{0,120}?(\d+(?:\.\d+)?)\s*mm\s*厚",
        r"cold[\s-]*rolled[^.\n]{0,160}?to\s*~?\s*(\d+(?:\.\d+)?)\s*mm",
        r"cold[\s-]*rolled[^.\n]{0,160}?(\d+(?:\.\d+)?)\s*mm\s*thick",
    ]
    for pat in patterns:
        ms = re.findall(pat, text, flags=re.IGNORECASE)
        if ms:
            try:
                return float(ms[-1])
            except ValueError:
                continue
    return None


def apply_post_rules(payload: dict, summary_text: str) -> dict:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return payload

    cold_final_mm = extract_cold_rolling_final_mm(summary_text)
    if cold_final_mm is None:
        return payload

    for row in rows:
        if not isinstance(row, dict):
            continue
        row["轧制最终尺寸"] = cold_final_mm
        ev = row.get("evidence")
        if not isinstance(ev, dict):
            ev = {}
        ev["轧制最终尺寸"] = (
            f"后处理规则: 从 summary 识别到冷轧最终厚度为 {cold_final_mm:g} mm"
        )
        row["evidence"] = ev

    return payload


def process_one_summary(
    summary_path: Path,
    *,
    out_root: Path,
    api_key: str,
    base_url: str,
    model: str,
) -> None:
    summary_text = summary_path.read_text(encoding="utf-8")
    prompt_text = load_prompt_file("summary_to_structured")
    user_text = build_user_text(prompt_text, summary_text)

    raw = chat_text(
        base_url=base_url,
        api_key=api_key,
        model=model,
        system_text=DEFAULT_SYSTEM,
        user_text=user_text,
    )
    parsed = parse_json_text(raw)
    parsed = normalize_rows(parsed)
    parsed = apply_post_rules(parsed, summary_text)

    paper_dir = out_root / summary_path.parent.name
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "structured.raw.txt").write_text(raw, encoding="utf-8")
    (paper_dir / "structured.json").write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[完成] {summary_path} -> {paper_dir / 'structured.json'}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="读取 summary.md，用大模型生成结构化 JSON。")
    p.add_argument("summary", type=Path, help="summary.md 文件，或包含多个 summary.md 的目录")
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help=f"输出根目录，默认 {default_out_dir()}",
    )
    p.add_argument(
        "--model",
        type=str,
        default=None,
        help="覆盖模型名（默认读取 ARK_MODEL / OPENAI_MODEL）",
    )
    p.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="覆盖 API 地址（默认读取 ARK_API_BASE / OPENAI_BASE_URL）",
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
            "未找到密钥：请在 src/.env 中设置 ARK_API_KEY，"
            "或导出 ARK_API_KEY / OPENAI_API_KEY",
            file=sys.stderr,
        )
        return 2

    out_root = args.out_dir.resolve() if args.out_dir else default_out_dir()
    out_root.mkdir(parents=True, exist_ok=True)

    try:
        summaries = collect_summary_files(args.summary.resolve())
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    ok_n = 0
    err_n = 0
    for sp in summaries:
        try:
            process_one_summary(
                sp,
                out_root=out_root,
                api_key=key,
                base_url=base,
                model=model,
            )
            ok_n += 1
        except Exception as e:
            err_n += 1
            print(f"[失败] {sp}: {e}", file=sys.stderr)

    print(f"处理结束：成功 {ok_n}，失败 {err_n}，共 {len(summaries)} 篇。", file=sys.stderr)
    return 0 if ok_n > 0 and err_n == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
