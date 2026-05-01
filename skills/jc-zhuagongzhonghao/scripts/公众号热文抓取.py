#!/usr/bin/env python3
"""
公众号热文抓取 + 自动评分 + 杂志风格报告 + 自动部署
配置文件: config.yaml（修改关键词/评分规则无需改代码）
用法: python3 公众号热文抓取.py [--no-deploy]
"""

import json
import requests
import time
import os
import sys
import subprocess
import yaml
from datetime import datetime

# ============ 加载配置 ============

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.yaml")

def load_config():
    """从 config.yaml 加载所有配置"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

CFG = load_config()

# ============ 核心逻辑 ============

def search_articles(group, cfg):
    """调用API搜索文章"""
    payload = {
        "kw": group["kw"],
        "sort_type": cfg["search"]["sort_type"],
        "mode": cfg["search"]["mode"],
        "period": cfg["search"]["period"],
        "page": 1,
        "key": cfg["api"]["key"],
        "any_kw": group.get("any_kw", ""),
        "ex_kw": group.get("ex_kw", ""),
    }
    try:
        resp = requests.post(cfg["api"]["url"], json=payload, timeout=30)
        data = resp.json()
        if data.get("code") == 0:
            return data
        else:
            print(f"  ⚠️ API错误: {data.get('msg', '未知错误')}")
            return None
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        return None


def wilson_lower_bound(positive, total, z=1.96):
    """Wilson Score 下界（95%置信区间）
    解决小样本噪音问题：2次阅读1次点赞不应该比1万阅读500互动分数高
    Amazon/Reddit/Steam 都用这个算法"""
    import math
    if total == 0:
        return 0
    p = positive / total
    denominator = 1 + z * z / total
    center = p + z * z / (2 * total)
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (center - spread) / denominator


def score_article(article, cfg):
    """数据驱动评分（0-100）

    三维度权重分配：
    - 流量分（40%）：阅读量 log10 归一化，衡量选题的流量潜力
    - 信任分（50%）：Wilson Score 下界，衡量内容的信任价值
    - 内容信号（10%）：原创 + 关键词 + 内容长度，辅助判断

    参考：HN/Reddit 排名算法 + Wilson Score（Amazon/Steam 评分）
    """
    import math

    scoring = cfg["scoring"]
    dim = scoring["dimensions"]

    read = article.get("read", 0)
    praise = article.get("praise", 0)
    looking = article.get("looking", 0)
    title = article.get("title", "")
    content = article.get("content", "")[:500]
    text = (title + " " + content).lower()

    # ═══ 维度1：流量分（阅读量 log10 归一化）═══
    # log10(100)=2, log10(1000)=3, log10(10000)=4, log10(100000)=5
    # 归一化到 0-100：以 log10(100000)=5 为满分
    if read > 0:
        traffic_raw = math.log10(max(read, 1))
        traffic_score = min(traffic_raw / 5.0, 1.0) * 100
    else:
        traffic_score = 0

    # ═══ 维度2：信任分（Wilson Score 下界）═══
    # 把互动（点赞+在看）视为正面投票，阅读量视为总投票
    # Wilson 自动处理小样本问题：低阅读量的高互动率会被打折
    if read >= dim.get("min_reads_for_trust", 50):
        interactions = praise + looking
        wilson = wilson_lower_bound(interactions, read)
        # 归一化：wilson 值通常在 0-0.05 之间，以 0.05 为满分
        trust_score = min(wilson / 0.05, 1.0) * 100
    else:
        trust_score = 0  # 阅读量太低，信任分不可信

    # ═══ 维度3：内容信号（辅助）═══
    content_score = 0

    # 原创加分
    if article.get("is_original") == 1:
        content_score += dim.get("original_bonus", 30)

    # 正面关键词（+3/个，上限20）
    pos_each = dim.get("positive_keyword_each", 3)
    pos_cap = dim.get("positive_keyword_cap", 20)
    pos_hits = sum(1 for kw in scoring.get("positive_keywords", []) if kw.lower() in text)
    content_score += min(pos_hits * pos_each, pos_cap)

    # 负面关键词（-10/个，上限-40）
    neg_each = dim.get("negative_keyword_each", 10)
    neg_cap = dim.get("negative_keyword_cap", 40)
    neg_hits = sum(1 for kw in scoring.get("negative_keywords", []) if kw.lower() in text)
    content_score -= min(neg_hits * neg_each, neg_cap)

    # 内容长度
    if len(content) > 500:
        content_score += dim.get("long_content_bonus", 10)
    elif len(content) < 50:
        content_score -= 15

    content_score = max(0, min(100, content_score))

    # ═══ 加权合成 ═══
    w_traffic = dim.get("weight_traffic", 0.4)
    w_trust = dim.get("weight_trust", 0.5)
    w_content = dim.get("weight_content", 0.1)

    final = traffic_score * w_traffic + trust_score * w_trust + content_score * w_content

    return max(0, min(100, round(final)))


def generate_html_report(all_results, total_cost, remain_money, cfg):
    """生成杂志风格HTML报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    scoring = cfg["scoring"]

    # 合并所有文章并去重（按URL）
    seen_urls = set()
    all_articles = []
    for group_name, articles in all_results:
        for art in articles:
            url = art.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                art["_group"] = group_name
                art["_score"] = score_article(art, cfg)
                all_articles.append(art)

    # 按分数排序，过滤低分
    all_articles.sort(key=lambda x: x["_score"], reverse=True)
    min_score = scoring["min_score"]
    all_articles = [a for a in all_articles if a["_score"] >= min_score]

    # 统计
    total_articles = len(all_articles)
    high_quality = len([a for a in all_articles if a["_score"] >= scoring["tiers"]["a"]])

    # 构建 JSON 数据给前端
    articles_json = []
    for art in all_articles:
        sc = art["_score"]
        tier = "s" if sc >= scoring["tiers"]["s"] else ("a" if sc >= scoring["tiers"]["a"] else "b")
        title = art.get("title", "").replace("\n", " ").strip()
        if len(title) > 120:
            title = title[:120] + "..."
        content_preview = art.get("content", "").replace("\n", " ").strip()[:300]
        url = art.get("short_link") or art.get("url", "")

        articles_json.append({
            "title": title,
            "url": url,
            "content_preview": content_preview,
            "wx_name": art.get("wx_name", ""),
            "pub_time": art.get("publish_time_str", "")[:10],
            "read": art.get("read", 0),
            "praise": art.get("praise", 0),
            "looking": art.get("looking", 0),
            "is_original": art.get("is_original", 0) == 1,
            "group": art["_group"],
            "score": sc,
            "tier": tier,
        })

    # 读取模板
    template_path = os.path.join(SCRIPT_DIR, "report-template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    # 注入数据
    html = html.replace("{{ARTICLES_JSON}}", json.dumps(articles_json, ensure_ascii=False))
    html = html.replace("{{TOTAL_ARTICLES}}", str(total_articles))
    html = html.replace("{{HIGH_QUALITY}}", str(high_quality))
    html = html.replace("{{TOTAL_COST}}", f"{total_cost:.2f}")
    html = html.replace("{{REMAIN_MONEY}}", f"{remain_money:.2f}")
    html = html.replace("{{NOW}}", now)
    html = html.replace("{{PERIOD}}", str(cfg["search"]["period"]))

    return html


def deploy_to_cloudflare(report_path, cfg):
    """将报告部署到 Cloudflare Pages"""
    deploy_dir = os.path.join(SCRIPT_DIR, cfg["deploy"]["project_dir"])
    os.makedirs(deploy_dir, exist_ok=True)

    # 复制报告为 index.html
    import shutil
    dest = os.path.join(deploy_dir, "index.html")
    shutil.copy2(report_path, dest)

    print(f"\n🚀 部署到 Cloudflare Pages...")
    try:
        result = subprocess.run(
            ["npx", "wrangler", "pages", "deploy", ".", "--project-name=the-signal", "--branch=main", "--commit-dirty=true"],
            cwd=deploy_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            # wrangler 输出格式: "✨ Deployment complete! Take a peek over at https://xxx.pages.dev"
            for line in result.stderr.split("\n") + result.stdout.split("\n"):
                if "pages.dev" in line:
                    import re
                    urls = re.findall(r'https://[^\s]+pages\.dev', line)
                    if urls:
                        print(f"✅ 部署成功: {urls[0]}")
            print(f"✅ 生产地址: https://the-signal-7s5.pages.dev")
        else:
            print(f"⚠️ 部署可能失败: {result.stderr[-300:]}")
    except subprocess.TimeoutExpired:
        print(f"⚠️ 部署超时，请手动运行: cd {deploy_dir} && npx wrangler pages deploy . --project-name=the-signal --branch=main --commit-dirty=true")
    except FileNotFoundError:
        print(f"⚠️ 未找到 npx，请先安装 Node.js")


def main():
    no_deploy = "--no-deploy" in sys.argv

    print("🚀 公众号热文抓取开始...\n")
    print(f"📋 配置: {len(CFG['search_groups'])}组关键词, {CFG['search']['period']}天, "
          f"最低{CFG['scoring']['min_score']}分\n")

    all_results = []
    total_cost = 0
    remain_money = 0

    groups = CFG["search_groups"]
    for i, group in enumerate(groups):
        print(f"[{i+1}/{len(groups)}] 搜索: {group['name']}")
        data = search_articles(group, CFG)
        if data:
            articles = data.get("data", [])
            cost = data.get("cost_money", 0)
            remain_money = data.get("remain_money", 0)
            total_cost += cost
            all_results.append((group["name"], articles))
            print(f"  ✅ 获取 {len(articles)} 篇, 花费 ¥{cost:.2f}, 余额 ¥{remain_money:.2f}")
        else:
            all_results.append((group["name"], []))
            print(f"  ❌ 获取失败")

        if i < len(groups) - 1:
            time.sleep(2)

    print(f"\n📊 生成报告...")
    html = generate_html_report(all_results, total_cost, remain_money, CFG)

    # 保存报告
    report_name = f"公众号热文报告_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    report_path = os.path.join(SCRIPT_DIR, report_name)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ 报告已生成: {report_path}")
    print(f"💰 总花费: ¥{total_cost:.2f}, 余额: ¥{remain_money:.2f}")

    # 自动部署
    if not no_deploy and CFG.get("deploy", {}).get("auto_deploy", False):
        deploy_to_cloudflare(report_path, CFG)
    elif no_deploy:
        print(f"\n⏭️ 跳过部署（--no-deploy）")
    else:
        print(f"\n👉 用浏览器打开报告查看结果")


if __name__ == "__main__":
    main()
