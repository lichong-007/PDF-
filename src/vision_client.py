"""
OpenAI 兼容的视觉对话：本地 PNG → base64 → {base}/chat/completions。
默认对接火山方舟 / 豆包；也可用环境变量改回其它兼容服务。
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


def png_to_data_url(path: Path) -> str:
    raw = path.read_bytes()
    b64 = base64.standard_b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{b64}"


def chat_with_images(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system_text: str,
    user_text: str,
    image_paths: list[Path],
    timeout_sec: int = 300,
) -> str:
    if not image_paths:
        raise ValueError("至少需要一张图片")
    content: list[dict] = [{"type": "text", "text": user_text}]
    for p in image_paths:
        if not p.is_file():
            raise FileNotFoundError(f"图片不存在: {p}")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": png_to_data_url(p)},
            }
        )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": content},
        ],
        "max_tokens": 4096,
    }
    return _post_chat(base_url=base_url, api_key=api_key, body=body, timeout_sec=timeout_sec)


def chat_text(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system_text: str,
    user_text: str,
    timeout_sec: int = 300,
) -> str:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 4096,
    }
    return _post_chat(base_url=base_url, api_key=api_key, body=body, timeout_sec=timeout_sec)


def _post_chat(*, base_url: str, api_key: str, body: dict, timeout_sec: int) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API HTTP {e.code}: {err_body}") from e
    try:
        result = payload["choices"][0]["message"]["content"]
        print("--------------------------------")
        print(f"result: {result}")
        print("--------------------------------")
        return result
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"无法解析 API 返回: {payload!r}") from e


# 火山方舟 OpenAI 兼容 chat/completions
DEFAULT_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-1-5-vision-pro-32k-250115"


def load_dotenv_file(path: Path) -> None:
    """
    读取 .env：每行 KEY=VALUE，# 开头为注释。
    已在操作系统环境变量里的键不会被覆盖（方便你临时 export 覆盖）。
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        k, _, v = s.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def env_config() -> tuple[str, str, str]:
    """
    返回 (api_key, base_url, model)。
    密钥优先 ARK_API_KEY，其次 OPENAI_API_KEY。
    地址优先 OPENAI_BASE_URL，其次 ARK_API_BASE，最后 DEFAULT_API_BASE。
    模型优先 OPENAI_MODEL，其次 ARK_MODEL，最后 DEFAULT_MODEL。
    """
    key = (os.environ.get("ARK_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    base = (
        os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("ARK_API_BASE")
        or DEFAULT_API_BASE
    ).strip()
    model = (os.environ.get("OPENAI_MODEL") or os.environ.get("ARK_MODEL") or DEFAULT_MODEL).strip()
    return key, base, model
