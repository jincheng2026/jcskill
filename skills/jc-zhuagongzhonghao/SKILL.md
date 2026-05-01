---
name: jc-zhuagongzhonghao
description: >
  抓取公众号热文并生成智能评分报告。通过 dajiala.com API 按关键词搜索微信公众号文章，
  用 Wilson Score 算法（流量40%+信任50%+内容信号10%）自动评分排序，生成杂志风格
  HTML 报告（The Signal），支持搜索/排序/筛选/收藏/导出。可选部署到 Cloudflare Pages。
  当用户提到"抓取公众号""公众号热文""搜索公众号文章""公众号监控""抓公众号"
  "跑一下公众号""The Signal"时触发。
---

# 公众号热文抓取系统

## 触发后的工作流（必须严格遵守）

**铁律：每次调 API 都花钱（¥0.40/组），必须先跟用户确认再执行。**

### 第一步：确认搜索需求（必须问清楚再动手）

触发后，先问用户以下问题，不要直接跑脚本：

1. **搜什么？** — 关键词是什么？（如"AI工作流""Claude""留学"）
2. **搜多少？** — 搜几组关键词？（每组 ¥0.40，4组 = ¥1.60）
3. **有没有排除词？** — 哪些内容不想看到？（如"招聘""论文""股票"）
4. **搜索范围？** — 最近几天的？（默认7天，标题最大720天）

如果用户说"跟上次一样"或"用默认的"，读取现有 `config.yaml` 的配置，列出来让用户确认后再跑。

### 第二步：确认费用

告知用户本次预计花费：`关键词组数 × ¥0.40`。用户说"可以"或"跑吧"后才执行。

### 第三步：执行抓取

根据用户确认的参数，更新 `config.yaml` 后运行脚本。

### 第四步：展示结果

报告生成后告知：抓了多少篇、花了多少钱、S/A/B 各多少篇、余额多少。问用户要不要部署到公网。

---

## 首次使用（初始化项目目录）

1. 确认用户的工作目录，将 skill 下的文件复制过去：
   - `scripts/公众号热文抓取.py` → 工作目录
   - `assets/report-template.html` → 工作目录
   - `assets/config-template.yaml` → 工作目录，重命名为 `config.yaml`

2. 让用户填写 `config.yaml` 中的 API Key（从 dajiala.com 注册获取）

3. 安装依赖：`pip3 install requests pyyaml`

4. 运行：`python3 公众号热文抓取.py`

## 日常使用

```bash
python3 公众号热文抓取.py              # 抓取 + 报告 + 自动部署
python3 公众号热文抓取.py --no-deploy   # 只生成报告
```

## 评分算法

Wilson Score + 三维度加权：

```
总分 = 流量分 × 40% + 信任分 × 50% + 内容信号 × 10%

流量分 = log10(阅读量) 归一化到 0-100
信任分 = Wilson Score 下界(互动数, 阅读量) 归一化到 0-100
内容信号 = 原创(+30) + 关键词 + 内容长度
```

- Wilson Score 解决小样本噪音（2次阅读1次点赞≠50%互动率）
- 阅读<50 时信任分归零
- 等级：S(≥55) / A(≥35) / B(20-34) / 过滤(<20)

## config.yaml 关键配置

### 搜索关键词

```yaml
search_groups:
  - name: "分组名"
    kw: "必须包含"     # AND
    any_kw: "词1 词2"  # OR
    ex_kw: "排除词"    # NOT
```

经验："AI"太泛（垃圾率80%），用"AI工作流""Claude"等精准词。每组 ¥0.40。

### 评分权重

```yaml
dimensions:
  weight_traffic: 0.40    # 流量（阅读量）
  weight_trust: 0.50      # 信任（互动率 Wilson Score）
  weight_content: 0.10    # 辅助（原创/关键词/长度）
  original_bonus: 30      # 原创加分（互动率是非原创3.4倍）
```

### 部署

首次：`npx wrangler login` + `npx wrangler pages project create 项目名 --production-branch=main`

之后自动部署（`deploy.auto_deploy: true`）。

## 报告功能

杂志风格 HTML（The Signal）：实时搜索、多维排序、S/A/B筛选、收藏（localStorage）、导出 Markdown、键盘快捷键（/ j k o s）。

## 文件清单

| 文件 | 用途 |
|------|------|
| `scripts/公众号热文抓取.py` | 主脚本 |
| `assets/report-template.html` | 报告模板 |
| `assets/config-template.yaml` | 配置模板（需填 API Key） |
