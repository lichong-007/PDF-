"""
第三步：根据 page_candidates.json 的 labels 选图，分三次调用视觉模型。
- 成分：仅 composition_table 页
- 力学：仅 mechanical_table 页
- 处理过程：实验小节页 + 成分页（去重；成分页在前便于模型对照）
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import page_labels as L
from .vision_client import chat_with_images

DEFAULT_SYSTEM = (
    "你是严谨的学术文献阅读助手。"
    "请根据用户文字说明，结合用户消息中附带的图片作答，遵守用户要求的输出格式。"
)


def _prompt_dir() -> Path:
    return Path(__file__).resolve().parent / "prompts"


def load_prompt_file(name: str) -> str:
    return (_prompt_dir() / f"{name}.txt").read_text(encoding="utf-8")


def groups_from_candidates(data: dict) -> tuple[list[int], list[int], list[int]]:
    """
    返回 (成分页, 力学页, 工艺/实验页含成分)。
    工艺组 = 所有带 composition_table 的页（去重排序）+ 仅带 section2 而不在成分集合中的页。
    同一页若同时有 section2 与 composition，在工艺组只出现一次（排在成分顺序里）。
    """
    rows = data.get("pages") or []
    comp: list[int] = []
    mech: list[int] = []
    exp: list[int] = []
    for row in rows:
        p = int(row["page"])
        labels = set(row.get("labels") or [])
        if L.COMPOSITION_TABLE in labels:
            comp.append(p)
        if L.MECHANICAL_TABLE in labels:
            mech.append(p)
        if L.SECTION2_EXPERIMENTAL in labels:
            exp.append(p)
    comp_u = sorted(set(comp))
    mech_u = sorted(set(mech))
    exp_u = sorted(set(exp))
    seen: set[int] = set()
    process: list[int] = []
    for p in comp_u:
        if p not in seen:
            process.append(p)
            seen.add(p)
    for p in exp_u:
        if p not in seen:
            process.append(p)
            seen.add(p)
    return comp_u, mech_u, process


def png_paths(render_root: Path, pdf_stem: str, pages: list[int]) -> list[Path]:
    root = render_root.resolve() / pdf_stem
    return [root / f"page_{p:03d}.png" for p in pages]


def run_extractions(
    *,
    candidates_data: dict,
    render_root: Path,
    api_key: str,
    base_url: str,
    model: str,
) -> dict[str, str | None]:
    """
    三次调用模型。键：composition / mechanical / process；
    未调用或跳过为 None。
    """
    pdf_path = Path(candidates_data["pdf_path"])
    stem = pdf_path.stem
    comp_pages, mech_pages, proc_pages = groups_from_candidates(candidates_data)
    comp_user = load_prompt_file("composition")
    mech_user = load_prompt_file("mechanical")
    proc_user = load_prompt_file("process")
    out: dict[str, str | None] = {
        "composition": None,
        "mechanical": None,
        "process": None,
    }

    def run_one(
        key: str,
        pages: list[int],
        user_text: str,
        label: str,
    ) -> None:
        paths = png_paths(render_root, stem, pages)
        if not pages:
            print(f"[跳过 {label}] 没有对应标签的页面", file=sys.stderr)
            return
        if not all(p.is_file() for p in paths):
            print(f"[跳过 {label}] 缺少 PNG，请先运行第二步渲染", file=sys.stderr)
            return
        text = chat_with_images(
            base_url=base_url,
            api_key=api_key,
            model=model,
            system_text=DEFAULT_SYSTEM,
            user_text=user_text.strip(),
            image_paths=paths,
        )
        out[key] = text

    run_one("composition", comp_pages, comp_user, "成分")
    run_one("mechanical", mech_pages, mech_user, "力学")
    run_one("process", proc_pages, proc_user, "工艺")
    return out
