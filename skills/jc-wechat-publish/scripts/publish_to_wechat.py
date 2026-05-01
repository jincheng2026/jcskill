#!/usr/bin/env python3
"""
publish_to_wechat.py
发布到微信公众号草稿箱。

流程：
  1. 读取 HTML，扫描 base64 图片 → 逐张上传 ImgBB，替换为公网 URL
  2. 上传封面图到 ImgBB
  3. 获取公众号 appid
  4. 调用 /wechat-publish 推送草稿

用法：
  python3 publish_to_wechat.py \
    --html outputs/wechat/slug_article.html \
    --cover outputs/slug_cover_main.png \
    --title "文章标题" \
    --summary "摘要" \
    --slug "slug"
"""

import os
import sys
import re
import json
import base64
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
SKILL_DIR = SCRIPTS_DIR.parent


def load_config():
    config_path = SKILL_DIR / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        config = {}
        current_section = None
        with open(config_path) as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped.endswith(":") and not line.startswith(" "):
                    current_section = stripped[:-1]
                    config[current_section] = {}
                elif ":" in stripped and current_section:
                    key, _, val = stripped.partition(":")
                    if isinstance(config.get(current_section), dict):
                        config[current_section][key.strip()] = val.strip()
                elif ":" in stripped:
                    key, _, val = stripped.partition(":")
                    config[key.strip()] = val.strip()
        return config


def get_cfg_value(cfg, section, key, env_var=None):
    if env_var:
        val = os.environ.get(env_var)
        if val:
            return val
    if isinstance(cfg.get(section), dict):
        return cfg[section].get(key, "")
    return ""


def upload_to_imgbb(image_data: bytes, api_key: str, upload_url: str, name: str = "image", retries: int = 3) -> str:
    """上传图片到 ImgBB，返回公网 URL。失败返回空字符串。"""
    b64 = base64.b64encode(image_data).decode("utf-8")

    for attempt in range(retries):
        if attempt > 0:
            wait = 2 ** attempt
            print(f"[publish] ImgBB 上传重试 {attempt+1}/{retries}，等待 {wait}s...")
            time.sleep(wait)

        try:
            body = f"key={api_key}&image={urllib.request.quote(b64)}&name={name}"
            req = urllib.request.Request(
                upload_url,
                data=body.encode("utf-8"),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("success"):
                    url = data["data"]["url"]
                    print(f"[publish]   ✅ ImgBB 上传成功: {url[:60]}...")
                    return url
                else:
                    print(f"[publish]   ImgBB 返回失败: {data}", file=sys.stderr)
        except Exception as e:
            print(f"[publish]   ImgBB 上传异常: {e}", file=sys.stderr)

    return ""


def replace_base64_images(html: str, imgbb_api_key: str, imgbb_upload_url: str) -> tuple[str, bool]:
    """
    扫描 HTML 中所有 base64 图片，上传到 ImgBB，替换为公网 URL。
    返回 (新HTML, 是否全部成功)
    """
    pattern = r'src="(data:image/[^;]+;base64,[^"]+)"'
    matches = list(re.finditer(pattern, html))
    print(f"[publish] 发现 {len(matches)} 张 base64 图片，开始上传...")

    all_success = True
    for i, m in enumerate(matches):
        data_uri = m.group(1)
        # 解析 mime type 和 base64 数据
        header, b64_data = data_uri.split(",", 1)
        ext = "png"
        if "jpeg" in header or "jpg" in header:
            ext = "jpg"
        elif "webp" in header:
            ext = "webp"
        image_data = base64.b64decode(b64_data)
        name = f"img_{i+1}.{ext}"
        print(f"[publish] 上传图片 {i+1}/{len(matches)}: {name} ({len(image_data)//1024}KB)")

        url = upload_to_imgbb(image_data, imgbb_api_key, imgbb_upload_url, name=name)
        if url:
            html = html.replace(data_uri, url, 1)
        else:
            print(f"[publish] ❌ 图片 {name} 上传失败，停止", file=sys.stderr)
            all_success = False
            return html, False

    return html, all_success


def get_wechat_appid(api_base: str, api_key: str) -> str:
    """获取已绑定公众号的第一个 appid。"""
    url = f"{api_base}/wechat-accounts"
    body = json.dumps({}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            accounts = (data.get("data") or {}).get("accounts") or data.get("accounts") or []
            if accounts:
                appid = accounts[0].get("wechatAppid") or accounts[0].get("appid") or accounts[0].get("id", "")
                name = accounts[0].get("name", "")
                print(f"[publish] 公众号: 「{name}」appid: {appid}")
                return appid
            print(f"[publish] ⚠️ 未找到已绑定公众号，响应: {json.dumps(data)[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"[publish] 获取公众号 appid 失败: {e}", file=sys.stderr)
    return ""


def publish_draft(api_base: str, api_key: str, appid: str, title: str, summary: str,
                  html_content: str, cover_url: str) -> str:
    """推送草稿，返回 publicationId。"""
    url = f"{api_base}/wechat-publish"
    payload = {
        "wechatAppid": appid,
        "title": title,
        "digest": summary,
        "content": html_content,
        "contentFormat": "html",
        "thumb_media_url": cover_url,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[publish] 发布响应: {json.dumps(data)[:300]}")
            pub_id = (data.get("data") or {}).get("id") or data.get("id") or data.get("media_id", "")
            return str(pub_id) if pub_id else "ok"
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8")
        print(f"[publish] ❌ 发布 HTTP {e.code}: {err}", file=sys.stderr)
    except Exception as e:
        print(f"[publish] ❌ 发布失败: {e}", file=sys.stderr)
    return ""


def main():
    parser = argparse.ArgumentParser(description="推送公众号草稿箱")
    parser.add_argument("--html", required=True, help="排版后的 HTML 文件路径")
    parser.add_argument("--cover", required=True, help="封面图 PNG 路径")
    parser.add_argument("--title", required=True, help="文章标题")
    parser.add_argument("--summary", required=True, help="文章摘要")
    parser.add_argument("--slug", required=True, help="文章 slug（用于命名）")
    args = parser.parse_args()

    html_file = Path(args.html)
    cover_file = Path(args.cover)

    if not html_file.exists():
        print(f"[publish] ❌ HTML 文件不存在: {html_file}", file=sys.stderr)
        sys.exit(1)
    if not cover_file.exists():
        print(f"[publish] ❌ 封面图不存在: {cover_file}", file=sys.stderr)
        sys.exit(1)

    cfg = load_config()
    imgbb_key = get_cfg_value(cfg, "imgbb", "api_key", "IMGBB_API_KEY")
    imgbb_url = get_cfg_value(cfg, "imgbb", "upload_url", "IMGBB_UPLOAD_URL") or "https://api.imgbb.com/1/upload"
    wechat_base = get_cfg_value(cfg, "wechat_api", "api_base", "WECHAT_API_BASE") or "https://wx.limyai.com/api/openapi"
    wechat_key = get_cfg_value(cfg, "wechat_api", "api_key", "WECHAT_API_KEY")

    for name, val in [("ImgBB API Key", imgbb_key), ("微信 API Key", wechat_key)]:
        if not val:
            print(f"[publish] ❌ 缺少 {name}，检查 config.yaml", file=sys.stderr)
            sys.exit(1)

    # 读取 HTML
    html_content = html_file.read_text(encoding="utf-8")

    # 替换 base64 图片为 ImgBB URL
    html_content, ok = replace_base64_images(html_content, imgbb_key, imgbb_url)
    if not ok:
        sys.exit(1)

    # 上传封面图
    print(f"[publish] 上传封面图: {cover_file.name}")
    cover_data = cover_file.read_bytes()
    cover_url = upload_to_imgbb(cover_data, imgbb_key, imgbb_url, name=f"{args.slug}_cover.png")
    if not cover_url:
        print("[publish] ❌ 封面图上传失败，停止", file=sys.stderr)
        sys.exit(1)

    # 获取公众号 appid
    appid = get_wechat_appid(wechat_base, wechat_key)
    if not appid:
        print("[publish] ❌ 无法获取公众号 appid，停止", file=sys.stderr)
        sys.exit(1)

    # 推送草稿
    print(f"[publish] 推送草稿：《{args.title}》")
    pub_id = publish_draft(wechat_base, wechat_key, appid, args.title, args.summary, html_content, cover_url)

    if pub_id:
        print(f"\n✅ 公众号文章已推送草稿箱")
        print(f"   publicationId：{pub_id}")
        print(f"   查看路径：公众号后台 → 内容管理 → 草稿箱")
    else:
        print("\n❌ 发布失败，请检查上方错误信息", file=sys.stderr)
        print("   备选方案：手动将 HTML 文件内容粘贴到公众号后台", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
