#!/usr/bin/env python3
"""
image_generator.py
使用 Gemini 官方 API 生成图片，保存为 PNG 文件。

用法：
  python3 image_generator.py --prompt "a cat" --output out.png
  IMAGE_API_KEY=xxx python3 image_generator.py ...

配置（优先级从高到低）：
  1. 环境变量 IMAGE_API_KEY
  2. config.yaml 中 image_api.api_key
"""

import os
import sys
import argparse
import base64
import json
import time
from pathlib import Path

def load_config():
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # 不依赖 yaml，手动解析简单格式
        config = {}
        with open(config_path) as f:
            for line in f:
                line = line.strip()
                if ":" in line and not line.startswith("#"):
                    key, _, val = line.partition(":")
                    config[key.strip()] = val.strip()
        return config

def get_api_key(cfg):
    key = os.environ.get("IMAGE_API_KEY")
    if key:
        return key
    # 嵌套 yaml 结构
    if isinstance(cfg.get("image_api"), dict):
        return cfg["image_api"].get("api_key", "")
    return cfg.get("IMAGE_API_KEY", "")

def get_model(cfg):
    model = os.environ.get("IMAGE_MODEL")
    if model:
        return model
    if isinstance(cfg.get("image_api"), dict):
        return cfg["image_api"].get("model", "gemini-2.0-flash-preview-image-generation")
    return cfg.get("IMAGE_MODEL", "gemini-2.0-flash-preview-image-generation")

def generate_image(prompt: str, output_path: str, api_key: str, model: str) -> bool:
    """
    调用 Gemini 官方 API 生成图片。
    端点：https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
    认证：x-goog-api-key header
    返回格式：inlineData.data（base64）
    """
    import urllib.request
    import urllib.error

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"]
        }
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"[image_generator] HTTP {e.code}: {err_body}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[image_generator] 请求失败: {e}", file=sys.stderr)
        return False

    # 解析 base64 图片数据
    try:
        candidates = data.get("candidates", [])
        for candidate in candidates:
            parts = candidate.get("content", {}).get("parts", [])
            for part in parts:
                inline_data = part.get("inlineData") or part.get("inline_data")
                if inline_data:
                    img_data = base64.b64decode(inline_data["data"])
                    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(img_data)
                    print(f"[image_generator] 图片已保存: {output_path}", file=sys.stderr)
                    return True
    except Exception as e:
        print(f"[image_generator] 解析响应失败: {e}", file=sys.stderr)
        print(f"[image_generator] 原始响应: {json.dumps(data)[:500]}", file=sys.stderr)
        return False

    print(f"[image_generator] 响应中未找到图片数据", file=sys.stderr)
    print(f"[image_generator] 候选项: {json.dumps(data.get('candidates', []))[:300]}", file=sys.stderr)
    return False


def main():
    parser = argparse.ArgumentParser(description="Gemini 官方 API 生图")
    parser.add_argument("--prompt", required=True, help="英文图片描述")
    parser.add_argument("--output", required=True, help="输出 PNG 文件路径")
    parser.add_argument("--retry", type=int, default=2, help="失败重试次数")
    args = parser.parse_args()

    cfg = load_config()
    api_key = get_api_key(cfg)
    model = get_model(cfg)

    if not api_key:
        print("[image_generator] 错误：未找到 IMAGE_API_KEY", file=sys.stderr)
        sys.exit(1)

    for attempt in range(args.retry + 1):
        if attempt > 0:
            wait = 2 ** attempt
            print(f"[image_generator] 第 {attempt+1} 次重试，等待 {wait}s...", file=sys.stderr)
            time.sleep(wait)
        if generate_image(args.prompt, args.output, api_key, model):
            sys.exit(0)

    print(f"[image_generator] 全部重试失败: {args.output}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
