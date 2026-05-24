# `src` 脚本说明与执行指南

本目录实现「读 PDF → 规则选页 → 渲染图片 → 调用火山方舟（豆包视觉）提取信息」的流程。项目根目录为 `new_product`，下文路径均相对该根目录举例。

---

## 一、环境与依赖

1. **Python**：建议 3.10 及以上（已安装并加入 `PATH`）。
2. **第三方包**：仅需 **PyMuPDF**（代码中 `import fitz`）。在项目根执行：

   ```powershell
   pip install -r requirements.txt
   ```

   或：`pip install pymupdf`

---

## 二、数据流概览

```text
力学性能/*.pdf
    → [第一步] *.page_candidates.json（out_test/batch_* 或指定目录）
    → [第二步] out_test/rendered/<PDF 文件名>/page_XXX.png
    → [第三步] out_test/llm_output/<PDF 文件名>/*.md
```

---

## 三、入口脚本（如何执行）

在 **PowerShell** 中，先将工作目录切到含 `src` 的项目根（示例 `E:\new_product`），并激活 venv（若使用）。

### 方式 A：一键跑完全部三步（推荐）

对**整个 PDF 目录**（仅扫描该目录**一层**的 `*.pdf`，不递归子文件夹）：

```powershell
cd E:\new_product
.\venv\Scripts\Activate.ps1
python src\run_pipeline.py "E:\new_product\力学性能"
```

对**单篇 PDF**：

```powershell
python src\run_pipeline.py "E:\new_product\力学性能\某篇.pdf"
```

- 第一步的 JSON 默认写入：`out_test\batch_pipeline_年月日_时分秒\`
- 可选：`python src\run_pipeline.py "路径" --batch-dir E:\new_product\out_test\my_batch`

任一步失败会中止后续步骤。

### 方式 B：分步执行

| 步骤 | 脚本 | 作用 | 示例 |
|------|------|------|------|
| 1 | `cli.py` | 按规则分析 PDF，生成候选页 JSON | `python src\cli.py "E:\new_product\力学性能"` |
| 2 | `cli_step2.py` | 根据 JSON 的 `candidate_pages` 渲染 PNG | `python src\cli_step2.py "E:\new_product\out_test\batch_xxx"` |
| 3 | `cli_step3.py` | 按标签选图调用大模型，写入 Markdown | `python src\cli_step3.py "E:\new_product\out_test\batch_xxx"` |

说明：

- 第一步若输入**目录**且未指定 `-o`，会生成 `out_test\batch_时间戳\`；若输入**单个 PDF**，默认写到 `out_test\<篇名>.page_candidates.json`。
- 第二步、第三步的输入可以是**一个** `.page_candidates.json` 文件，或**目录**下所有 `*.page_candidates.json`（同样**不递归**子目录）。
- 第二步可选：`--render-dir`、`--dpi`。
- 第三步可选：`--render-dir`（PNG 根目录，默认 `out_test\rendered`）、`--out-dir`（Markdown 根目录，默认 `out_test\llm_output`）、`--model`、`--base-url`。

**注意**：运行脚本时请写 **`python src\cli.py`**（带 **`.py`**），不要写成 `python cli`。

---

## 四、模块分工（便于维护）

| 文件 | 说明 |
|------|------|
| `cli.py` | 第一步命令行入口 |
| `select_pages.py` | 读 PDF 文本、按页打标签、汇总 `analyze_pdf` |
| `rules.py` | 实验小节 / 成分表 / 力学表 等匹配规则 |
| `page_labels.py` | 标签常量 |
| `cli_step2.py` | 第二步命令行入口 |
| `from_candidates.py` | 从 JSON 读取 `candidate_pages` 与 `pdf_path` |
| `render_png.py` | 将指定页渲染为 PNG |
| `cli_step3.py` | 第三步命令行入口（支持单文件或目录批处理） |
| `llm_step3.py` | 按标签分组、加载 `prompts/*.txt`、调用视觉 API |
| `vision_client.py` | 火山方舟 OpenAI 兼容接口、可选加载 `src\.env` |
| `run_pipeline.py` | 串联调用上述三个 CLI |
| `prompts/composition.txt` | 成分提取：用户提示词 |
| `prompts/mechanical.txt` | 力学表提取：用户提示词 |
| `prompts/process.txt` | 工艺与实验：用户提示词 |

---

## 五、输出目录约定

| 路径 | 内容 |
|------|------|
| `out_test\batch_*` / `batch_pipeline_*` | 第一步生成的 `*.page_candidates.json` |
| `out_test\rendered\<PDF stem>\` | 第二步的 `page_001.png` 等 |
| `out_test\llm_output\<PDF stem>\` | 第三步：`composition.md`、`mechanical.md`、`process.md`、`summary.md` |

JSON 中的 `pdf_path` 须仍指向真实 PDF，第二步、第三步才能找到文件与渲染目录名。

---

## 六、常见问题

1. **`ModuleNotFoundError: fitz`**：未安装 PyMuPDF，执行 `pip install pymupdf`。
2. **第三步提示未找到密钥**：检查 `src\.env` 是否含 `ARK_API_KEY=`，或是否在系统中导出该变量。
3. **第三步跳过或缺图**：先对该篇所在批次跑第二步；`rendered` 下子文件夹名须与 PDF **文件名（不含扩展名）** 一致（由第二步按 `pdf_path` 生成）。
4. **路径含中文**：请使用引号包裹路径，例如 `"E:\new_product\力学性能"`。

---

