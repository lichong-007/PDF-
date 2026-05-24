"""将 structured.json 导入初建数据库.xlsx（按文献名可替换旧行）。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

MECH_START_COL = "YS(屈服强度)"


def _to_cell_value(v: Any) -> Any:
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v


def load_structured_rows(structured_json: Path) -> tuple[str | None, list[dict[str, Any]]]:
    payload = json.loads(structured_json.read_text(encoding="utf-8"))
    paper_title = payload.get("paper_title")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("structured.json 缺少 rows 数组")
    dict_rows: list[dict[str, Any]] = []
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"rows 第 {i} 行不是对象")
        dict_rows.append(row)
    return paper_title, dict_rows


def collect_extra_element_cols(rows: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for row in rows:
        extra = row.get("额外元素")
        if not isinstance(extra, dict):
            continue
        for k in extra.keys():
            key = str(k).strip()
            if key and key not in seen:
                seen.add(key)
                ordered.append(key)
    return ordered


def main() -> None:
    p = argparse.ArgumentParser(description="将 structured.json 写入 Excel（按文献名可替换旧数据）")
    p.add_argument("structured_json", type=Path, help="structured.json 文件路径")
    p.add_argument(
        "--excel",
        type=Path,
        default=Path(r"E:\new_product\初建数据库.xlsx"),
        help="目标 Excel 路径，默认 E:\\new_product\\初建数据库.xlsx",
    )
    p.add_argument("--sheet", type=str, default=None, help="工作表名，默认第一个 sheet")
    p.add_argument(
        "--append-only",
        action="store_true",
        help="仅追加，不按文献名替换旧行（默认会替换同文献旧行）",
    )
    p.add_argument(
        "--skip-columns",
        type=str,
        default="力学性能状态,浇铸温度_来源",
        help="逗号分隔的不写入列名，例如: 力学性能状态,浇铸温度_来源",
    )
    args = p.parse_args()

    structured_json = args.structured_json.resolve()
    excel_path = args.excel.resolve()
    if not structured_json.is_file():
        raise FileNotFoundError(f"structured.json 不存在: {structured_json}")
    if not excel_path.is_file():
        raise FileNotFoundError(f"Excel 不存在: {excel_path}")

    paper_title, rows = load_structured_rows(structured_json)

    xls = pd.ExcelFile(excel_path)
    sheet_name = args.sheet or xls.sheet_names[0]
    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    excel_cols = list(df.columns)
    extra_cols = collect_extra_element_cols(rows)
    if extra_cols:
        insert_at = excel_cols.index(MECH_START_COL) if MECH_START_COL in excel_cols else len(excel_cols)
        for col in extra_cols:
            if col not in excel_cols:
                df.insert(insert_at, col, None)
                excel_cols.insert(insert_at, col)
                insert_at += 1
    skip_cols = {c.strip() for c in args.skip_columns.split(",") if c.strip()}

    records: list[dict[str, Any]] = []
    for row in rows:
        rec = {c: None for c in excel_cols}
        for c in excel_cols:
            if c in skip_cols:
                continue
            if c in row:
                rec[c] = _to_cell_value(row[c])
        extra = row.get("额外元素")
        if isinstance(extra, dict):
            for k, v in extra.items():
                key = str(k).strip()
                if not key or key in skip_cols:
                    continue
                if key in rec:
                    rec[key] = _to_cell_value(v)
        if "文献名称" in rec and (rec["文献名称"] is None or str(rec["文献名称"]).strip() == ""):
            rec["文献名称"] = paper_title
        records.append(rec)

    if not records:
        print("rows 为空，未写入。")
        return

    incoming_df = pd.DataFrame(records, columns=excel_cols)

    removed = 0
    if not args.append_only and "文献名称" in df.columns:
        titles = {
            str(r.get("文献名称")).strip()
            for r in records
            if r.get("文献名称") is not None and str(r.get("文献名称")).strip()
        }
        if not titles and paper_title:
            titles = {paper_title}
        if titles:
            before = len(df)
            df = df[~df["文献名称"].astype(str).isin(titles)].copy()
            removed = before - len(df)

    out_df = pd.concat([df, incoming_df], ignore_index=True)

    with pd.ExcelWriter(excel_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        out_df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(
        f"写入完成: sheet={sheet_name}, 新增元素列={extra_cols}, 追加={len(incoming_df)}, 替换旧行={removed}, 最终总行数={len(out_df)}"
    )


if __name__ == "__main__":
    main()
