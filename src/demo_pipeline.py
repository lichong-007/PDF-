"""演示用交互式总控脚本。

把现有三段流程包装成菜单：
1. run_pipeline.py: PDF -> Markdown
2. cli_step4_summary_struct.py: summary.md -> structured.json
3. import_structured_to_excel.py: structured.json -> Excel
4. 一键运行：PDF -> Excel
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def safe_folder_name(pdf_stem: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "_", pdf_stem)
    return s.strip() or "output"


def print_header(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def ask_path(prompt: str, *, default: Path | None = None) -> Path:
    while True:
        suffix = f"\n直接回车使用默认值：{default}" if default else ""
        raw = input(f"{prompt}{suffix}\n> ").strip().strip('"').strip("'")
        path = default if not raw and default else Path(raw)
        if path and path.exists():
            return path.resolve()
        print(f"路径不存在，请重新输入：{path}")


def ask_yes_no(prompt: str, *, default_yes: bool = True) -> bool:
    hint = "Y/n" if default_yes else "y/N"
    while True:
        raw = input(f"{prompt} ({hint})\n> ").strip().lower()
        if not raw:
            return default_yes
        if raw in {"y", "yes", "是", "继续"}:
            return True
        if raw in {"n", "no", "否", "不"}:
            return False
        print("请输入 y 或 n。")


def run_command(cmd: list[str], *, cwd: Path) -> bool:
    print("\n即将执行：")
    print(" ".join(f'"{x}"' if " " in x else x for x in cmd))
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        print(f"\n命令执行失败，退出码：{result.returncode}")
        return False
    return True


def collect_pdfs(path: Path) -> list[Path]:
    if path.is_file() and path.suffix.lower() == ".pdf":
        return [path]
    if path.is_dir():
        return sorted(p for p in path.glob("*.pdf") if p.is_file())
    return []


def infer_summary_paths(input_path: Path) -> list[Path]:
    root = project_root()
    llm_root = root / "out_test" / "llm_output"
    summaries: list[Path] = []
    for pdf in collect_pdfs(input_path):
        summary = llm_root / safe_folder_name(pdf.stem) / "summary.md"
        if summary.is_file():
            summaries.append(summary)
        else:
            print(f"未找到 summary.md：{summary}")
    return summaries


def collect_summary_paths(path: Path) -> list[Path]:
    if path.is_file() and path.name == "summary.md":
        return [path]
    if path.is_dir():
        return sorted(path.rglob("summary.md"))
    return []


def infer_structured_paths(summary_paths: list[Path]) -> list[Path]:
    root = project_root()
    out_root = root / "out_test" / "structured_output"
    structured: list[Path] = []
    for summary in summary_paths:
        path = out_root / summary.parent.name / "structured.json"
        if path.is_file():
            structured.append(path)
        else:
            print(f"未找到 structured.json：{path}")
    return structured


def collect_structured_paths(path: Path) -> list[Path]:
    if path.is_file() and path.name == "structured.json":
        return [path]
    if path.is_dir():
        return sorted(path.rglob("structured.json"))
    return []


class DemoPipeline:
    def __init__(self, input_path: Path | None = None) -> None:
        self.root = project_root()
        self.python = sys.executable
        self.input_path = input_path
        self.summary_paths: list[Path] = []
        self.structured_paths: list[Path] = []

    def step1_run_pipeline(self) -> bool:
        print_header("第一步：PDF -> Markdown")
        if self.input_path is None or not self.input_path.exists():
            self.input_path = ask_path("请输入 PDF 文件路径，或包含多个 PDF 的目录")

        ok = run_command(
            [
                self.python,
                str(self.root / "src" / "run_pipeline.py"),
                str(self.input_path),
            ],
            cwd=self.root,
        )
        if not ok:
            return False

        self.summary_paths = infer_summary_paths(self.input_path)
        print("\n第一步完成。请人工检查以下文件：")
        if self.summary_paths:
            for path in self.summary_paths:
                print(f"- {path}")
        else:
            print("- 未自动定位到 summary.md，请稍后在第二步手动输入。")
        return True

    def step2_summary_to_structured(self) -> bool:
        print_header("第二步：summary.md -> structured.json")
        if not self.summary_paths:
            default = self.root / "out_test" / "llm_output"
            path = ask_path("请输入 summary.md 文件路径，或包含 summary.md 的目录", default=default)
            self.summary_paths = collect_summary_paths(path)
            if not self.summary_paths:
                print("未找到任何 summary.md。")
                return False

        ok_count = 0
        for summary in self.summary_paths:
            ok = run_command(
                [
                    self.python,
                    str(self.root / "src" / "cli_step4_summary_struct.py"),
                    str(summary),
                ],
                cwd=self.root,
            )
            if ok:
                ok_count += 1

        self.structured_paths = infer_structured_paths(self.summary_paths)
        print("\n第二步完成。请人工检查以下文件：")
        if self.structured_paths:
            for path in self.structured_paths:
                print(f"- {path}")
        else:
            print("- 未自动定位到 structured.json，请稍后在第三步手动输入。")
        return ok_count == len(self.summary_paths)

    def step3_import_excel(self) -> bool:
        print_header("第三步：structured.json -> Excel")
        if not self.structured_paths:
            default = self.root / "out_test" / "structured_output"
            path = ask_path("请输入 structured.json 文件路径，或包含 structured.json 的目录", default=default)
            self.structured_paths = collect_structured_paths(path)
            if not self.structured_paths:
                print("未找到任何 structured.json。")
                return False

        excel_path = self.root / "初建数据库.xlsx"
        print(f"\n即将写入 Excel：{excel_path}")
        print("注意：默认会按“文献名称”替换同名旧行。")

        ok_count = 0
        for structured in self.structured_paths:
            ok = run_command(
                [
                    self.python,
                    str(self.root / "tools" / "import_structured_to_excel.py"),
                    str(structured),
                ],
                cwd=self.root,
            )
            if ok:
                ok_count += 1

        print(f"\n第三步完成：成功写入 {ok_count}/{len(self.structured_paths)} 个 structured.json。")
        return ok_count == len(self.structured_paths)

    def run_pdf_to_excel(self) -> bool:
        print_header("一键运行：PDF -> Excel")
        if not self.step1_run_pipeline():
            return False
        if not self.step2_summary_to_structured():
            return False
        return self.step3_import_excel()

    def show_menu(self) -> None:
        while True:
            print_header("文献抽取演示流程")
            print(f"当前 PDF/目录：{self.input_path or '未设置'}")
            print(f"已定位 summary.md：{len(self.summary_paths)} 个")
            print(f"已定位 structured.json：{len(self.structured_paths)} 个")
            print("\n1. 第一步：运行 run_pipeline.py（PDF -> Markdown）")
            print("2. 第二步：运行 cli_step4_summary_struct.py（summary.md -> structured.json）")
            print("3. 第三步：运行 import_structured_to_excel.py（structured.json -> Excel）")
            print("4. 一键运行：PDF -> Excel")
            print("0. 退出")

            choice = input("\n请输入选项：").strip()
            if choice == "1":
                if self.step1_run_pipeline() and ask_yes_no("是否已经人工检查完毕，并继续第二步？"):
                    if self.step2_summary_to_structured() and ask_yes_no("是否已经人工检查完毕，并继续第三步？"):
                        self.step3_import_excel()
            elif choice == "2":
                if self.step2_summary_to_structured() and ask_yes_no("是否已经人工检查完毕，并继续第三步？"):
                    self.step3_import_excel()
            elif choice == "3":
                self.step3_import_excel()
            elif choice == "4":
                self.run_pdf_to_excel()
            elif choice == "0":
                print("已退出。")
                return
            else:
                print("无效选项，请输入 1、2、3、4 或 0。")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="演示用交互式文献抽取流程。")
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="可选：PDF 文件路径，或包含多个 PDF 的目录",
    )
    args = parser.parse_args(argv)

    input_path = args.input.resolve() if args.input else None
    if input_path is not None and not input_path.exists():
        print(f"输入路径不存在：{input_path}", file=sys.stderr)
        return 2

    DemoPipeline(input_path=input_path).show_menu()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
