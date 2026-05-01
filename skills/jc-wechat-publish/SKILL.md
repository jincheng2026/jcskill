---
name: jc-wechat-publish
description: >
  Markdown to WeChat public account publisher. Use when user wants to
  publish an article to WeChat (微信公众号), convert Markdown to styled HTML,
  or mentions "发公众号", "公众号排版", "微信文章", "发布文章", "上传公众号".
  Pipeline: scan image placeholders, generate images via Gemini API,
  render styled HTML (黄叔 design system), publish to WeChat draft via API.
---

# 微信公众号发布 Skill

Markdown → AI配图 → 精排版HTML → 发布到公众号草稿箱。全自动。

## Markdown 格式要求

```markdown
---
title: "文章标题"
subtitle: "副标题（可选）"
---

正文段落...

## 章节标题（自动生成 01 PART 编号结构）

### 子标题

正文中支持：
- **粗体** / *斜体*
- ==高亮文字==（黄底加粗）
- `代码术语`（灰底橙字）
- ![详细的图片场景描述，越详细生图越好](slug_img1_keyword.png)

:::highlight
深蓝底白字高亮块
:::

:::question
浅蓝底问题块
:::

▎ 引用行（深蓝底橙边框）
```

图片占位符规则：
- 格式：`![图注](slug_imgN_keyword.png)`
- alt 文本写详细的场景描述（中英文均可），这是 Gemini 生图的主要输入
- 文件名用英文，包含 slug + 编号 + 关键词
- 一般放 2-4 张图，分布在文章的 1/3、2/3 和结尾处

## 执行流程

### Step 1：准备 Markdown

确认用户提供的 Markdown 文件路径，检查：
- frontmatter 包含 title 字段
- 图片占位符格式正确

### Step 2：运行 Pipeline（生图 + 排版）

```bash
python3 SKILL_DIR/scripts/run_pipeline.py \
  --input <markdown_file> \
  --output <output_dir> \
  --filename <slug>_article.html
```

可选参数：
- `--style warm-flat` — 指定图片风格（不传则根据文章内容自动检测）

4 种预设风格：
| 风格 | 适用场景 |
|------|---------|
| `warm-flat` | 教程、个人成长、AI实战（默认） |
| `dark-tech` | AI/技术深度、商业分析 |
| `cool-editorial` | 系统设计、方法论、数据分析 |
| `sketch-warm` | 个人故事、认知变化、情感 |

脚本自动执行：
1. 扫描 `![alt](file.png)` 占位符
2. 根据文章内容自动选择配图风格（如果没指定 --style）
3. 为每个占位符调用 Gemini Pro 生图（已有图片自动跳过）
4. 调用 convert.js 渲染 HTML（inline style，黄叔设计系统）
5. 在浏览器中自动打开 HTML 预览

### Step 3：发布到公众号草稿箱（API 模式）

```bash
python3 SKILL_DIR/scripts/publish_to_wechat.py --api \
  --html <output_dir>/<slug>_article.html \
  --cover <output_dir>/images/<slug>_img1_keyword.png \
  --title "文章标题" \
  --summary "文章摘要" \
  --slug "<slug>"
```

**必须使用 `--api` 参数**，这样通过 limyai API 直接推送到草稿箱，排版完整保留（contentFormat=html）。

脚本内部自动完成：
1. 扫描 HTML 中 base64 图片 → 逐张上传 ImgBB 图床
2. 替换 base64 为公网 URL（HTML 从 2-5MB 压缩到 20-30KB）
3. 上传封面图到 ImgBB
4. 获取公众号 appid
5. 调用 /wechat-publish 推送草稿

封面图建议用文章中的第一张配图。

## 注意事项

- 图片生成需要时间，3 张图大约 1-2 分钟
- 已生成的图片不会重复生成（按文件名跳过），如需重新生成先删除对应文件
- 发布时 **必须加 `--api`**，不加的话走剪贴板模式（需手动粘贴）
- Markdown 中的 `==文字==` 会渲染为黄底高亮
- 支持代码块、引用块、有序/无序列表等标准 Markdown 语法

## 配置

编辑 `SKILL_DIR/config.yaml`：

```yaml
image_api:
  api_key: <Gemini API Key>
  model: gemini-3-pro-image-preview
  default_style: warm-flat

imgbb:
  api_key: <ImgBB API Key>
  upload_url: https://api.imgbb.com/1/upload

wechat_api:
  api_base: https://wx.limyai.com/api/openapi
  api_key: <limyai API Key>
```

## 设计系统（黄叔风格）

convert.js 内置的排版风格：
- **标题区**：深蓝底 `#1a1a2e` + 白字，居中
- **章节标题**：三层结构（36px 淡粉编号 + 11px 橙色 PART + 20px 深色标题）
- **正文**：16px、行高 2、两端对齐、`#333` 主色
- **高亮**：黄底 `rgb(255,243,176)` 加粗
- **代码**：灰底 `rgb(243,244,246)` 橙字 `#e76f51`
- **引用块**：深蓝底白字、左侧 4px 橙色边框
- **强调色**：橙色 `#e76f51`

## 微信 HTML 约束

- 禁止 `<style>` 标签 → 全部 inline style
- 禁止 `<div>` → 用 `<section>`
- 禁止 `linear-gradient`
- 图片必须先上传图床转为公网 URL（base64 会超体积限制）

## 脚本说明

| 脚本 | 用途 |
|------|------|
| `run_pipeline.py` | 总控：占位符扫描→风格检测→生图→HTML渲染→打开浏览器 |
| `convert.js` | Markdown→HTML 排版（黄叔设计系统） |
| `image_generator.py` | Gemini 官方 API 生图 |
| `publish_to_wechat.py` | ImgBB 图床上传 + limyai API 发布到草稿箱 |
