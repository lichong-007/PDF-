"""
开发阶段：偏「高精度」——少误报，宁可漏掉边缘页，后续可再放宽。
每类规则返回 None 表示本页不算命中；否则返回一小段原文便于你肉眼核对。
"""

from __future__ import annotations

import re
from re import Pattern


def _clip(s: str, max_len: int = 160) -> str:
    s = " ".join(s.split())
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


# 小节标题：2. … Experimental … 或 2. … 实验 …
_RE_SECTION2_EN: Pattern[str] = re.compile(
    r"^\s*2\.\s+[^\n]{0,120}[Ee]xperimental[^\n]{0,80}$",
    re.MULTILINE,
)
_RE_SECTION2_ZH: Pattern[str] = re.compile(
    r"^\s*2\.\s+[^\n]{0,120}实验[^\n]{0,80}$",
    re.MULTILINE,
)
_RE_EXPERIMENTAL_FREE_EN: Pattern[str] = re.compile(
    r"^\s*Experimental(?:\s+Materials\s+and\s+Test\s+Methods|\s+Procedures)?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_RE_EXPERIMENTAL_FREE_ZH: Pattern[str] = re.compile(
    r"^\s*(实验材料与方法|实验材料和方法|材料与方法|实验方法|试验材料与方法|测试方法)\s*$",
    re.MULTILINE,
)


def match_section2_experimental(page_text: str) -> str | None:
    m = (
        _RE_SECTION2_EN.search(page_text)
        or _RE_SECTION2_ZH.search(page_text)
        or _RE_EXPERIMENTAL_FREE_EN.search(page_text)
        or _RE_EXPERIMENTAL_FREE_ZH.search(page_text)
    )
    if not m:
        return None
    return _clip(m.group(0))


# 成分表：同时出现「化学组成/ composition」类表述 + wt%，且出现 Mg/Si 含量表头形态（与旧逻辑一致，减少误报）
_RE_COMP_A: Pattern[str] = re.compile(
    r"(?is)(chemical\s+compositions?|composition\s+of).{0,200}(wt\.?\s*%|mass\s*%)",
)
_RE_COMP_TITLE: Pattern[str] = re.compile(
    r"(?is)(chemical\s+compositions?|elemental\s+composition|alloy\s+elemental\s+composition|compositions?)"
    r".{0,120}(wt\.?\s*%|mass\s*%)",
)
_RE_COMP_B: Pattern[str] = re.compile(r"Mg\s*\(\s*wt", re.I)
_RE_COMP_C: Pattern[str] = re.compile(r"Si\s*\(\s*wt", re.I)
_RE_COMP_TABLE: Pattern[str] = re.compile(r"(?i)\btable\b|表\s*\d")
_RE_WT: Pattern[str] = re.compile(r"(?i)\bwt\.?\s*%")
_RE_COMP_ZH: Pattern[str] = re.compile(r"化学成分|成分", re.I)
_RE_ELEM_WORD: Pattern[str] = re.compile(r"\b(Mg|Si|Cu|Fe|Mn|Cr|Zn|Ti|Ni|Zr|Sc|Sr|Mo|V)\b")
_RE_TABLE_LABEL: Pattern[str] = re.compile(r"(?i)\btable\s*\d+[a-z]?\b|表\s*\d+")


def _windows_around_tables(page_text: str, radius: int = 320) -> list[str]:
    """
    方法 A：只在 Table 标题附近的小窗口里做判断，避免正文讨论段提到 Table/元素导致误报。
    """
    wins: list[str] = []
    for m in _RE_TABLE_LABEL.finditer(page_text):
        start = max(0, m.start() - radius)
        end = min(len(page_text), m.end() + radius)
        wins.append(page_text[start:end])
    return wins


def match_composition_table(page_text: str) -> str | None:
    # 成分表（尽量稳，不依赖某个期刊表头格式）：
    # Table + compositions/成分 + wt.% + 若干元素符号
    wins = _windows_around_tables(page_text)
    if not wins:
        return None
    for w in wins:
        if not _RE_WT.search(w):
            continue
        # 英文表题常见写法：Elemental Composition / Chemical compositions / Compositions (wt.%)
        if not (_RE_COMP_TITLE.search(w) or _RE_COMP_ZH.search(w)):
            continue
        elems = set(m.group(1) for m in _RE_ELEM_WORD.finditer(w))
        if len(elems) < 3:
            continue
        # snippet 返回更像“表标题附近”的窗口内容
        mt = _RE_COMP_TITLE.search(w)
        if mt:
            return _clip(mt.group(0))
        return _clip(w)
    return None


# 力学表：同时出现 YS (MPa) / UTS (MPa) 类表头，减少正文单独出现 MPa 的误报
_RE_YS: Pattern[str] = re.compile(r"\bYS\s*\(\s*MPa\s*\)", re.I)
_RE_UTS: Pattern[str] = re.compile(r"\bUTS\s*\(\s*MPa\s*\)", re.I)
_RE_SIGMA_MPA: Pattern[str] = re.compile(r"[σ\u03c3]\s*[a-z0-9]?\s*/\s*MPa", re.I)
_RE_DELTA_PERCENT: Pattern[str] = re.compile(r"(?:\bEl\b|elongation|[δ\u03b4])\s*/\s*%|%\s*$", re.I)
_RE_MECH_WORD: Pattern[str] = re.compile(r"(?i)mechanical\s+properties")
_RE_YIELD_WORD: Pattern[str] = re.compile(r"(?i)\byield\s+strength\b")
_RE_TENSILE_WORD: Pattern[str] = re.compile(r"(?i)\btensile\s+strength\b|ultimate\s+tensile\s+strength")
_RE_ELONG_WORD: Pattern[str] = re.compile(r"(?i)\belongation\b")
_RE_ZH_YIELD: Pattern[str] = re.compile(r"屈服强度")
_RE_ZH_TENSILE: Pattern[str] = re.compile(r"抗拉强度|拉伸强度")
_RE_ZH_ELONG: Pattern[str] = re.compile(r"伸长率")
def match_mechanical_table(page_text: str) -> str | None:
    # 方法 A：仅在 Table X 附近窗口里识别“像力学表”的表头
    for w in _windows_around_tables(page_text):
        # 规则 1：传统 YS/UTS 表头
        if _RE_YS.search(w) and _RE_UTS.search(w):
            a = _RE_YS.search(w)
            b = _RE_UTS.search(w)
            assert a and b
            lo = min(a.start(), b.start())
            hi = max(a.end(), b.end())
            return _clip(w[max(0, lo - 30) : min(len(w), hi + 60)])

        # 规则 2：σ?/MPa + δ/% 这种表头（你这篇就是 σb/MPa + δ/%）
        if _RE_SIGMA_MPA.search(w) and _RE_DELTA_PERCENT.search(w):
            # 为了高精度，再要求窗口里出现 “mechanical properties” 或至少出现 MPa 和 % 多次
            if not _RE_MECH_WORD.search(w):
                if w.count("MPa") < 1 or w.count("%") < 1:
                    continue
            return _clip(w)

        # 规则 3：全称表头（不写 YS/UTS 缩写）
        if (
            (_RE_YIELD_WORD.search(w) and _RE_TENSILE_WORD.search(w) and "MPa" in w)
            and (_RE_ELONG_WORD.search(w) or "%" in w)
        ):
            return _clip(w)

        # 规则 4：中文表头
        if (
            (_RE_ZH_YIELD.search(w) and _RE_ZH_TENSILE.search(w))
            and ("MPa" in w or "兆帕" in w)
            and (_RE_ZH_ELONG.search(w) or "%" in w)
        ):
            return _clip(w)

    return None