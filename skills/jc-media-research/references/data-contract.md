# 数据字段合同

## 目录

- 通用规则
- 作品记录
- 评论记录与统计
- 证据索引
- 搜索计划和请求账本
- 图表 manifest
- 公开字段白名单

## 通用规则

输出 schema_version 为整数 2；兼容读取 1、1.0、2。旧数据新增字段未知时使用 null 或 unknown，不推定账号身份、批次或评论层级。

- 时间使用带时区的 ISO 8601。
- 计数字段使用非负整数；缺失时使用 `null`，不要猜成 0。
- 每条 normalized 记录同时保存 `source_url`、`source_file` 和真实 `collected_at`。
- 平台内容 ID、评论 ID 和请求指纹按字符串保存。
- 新字段先写入版本化合同，再进入公开 normalized 数据。

## 作品记录

必填字段：

```text
schema_version
platform
content_id
title
caption
author_name
author_id
content_type
collection_batch_id
follower_snapshot_at
view_count
view_count_reliable
topic_id
follower_count
like_count
comment_count
collect_count
share_count
published_at
collected_at
source_url
source_file
relevance
relevance_reason
direct_related
age_days_at_research
within_preferred_90_days
qualified
eligibility
exclusion_reasons
evidence_issues
```

`eligibility` 使用：

- `eligible_low_follower_viral`
- `anomaly_low_followers`
- `regular_viral_reference`
- `unverified_low_likes`
- `adjacent`
- `off_topic`
- `missing_evidence`

`exclusion_reasons` 是字符串数组，明确列出每个未过门槛的字段。最近 90 天优先状态单独保存为 `within_preferred_90_days`，不能覆盖硬门槛结果。

`evidence_issues` 单独记录缺少来源文件、来源链接或真实采集时间等证据问题。它不改变内容门槛结果，但报告不能把证据不完整的记录写成已充分核验。

## 评论记录

必填字段：

```text
schema_version
platform
content_id
comment_id
parent_comment_id
root_comment_id
is_reply
commenter_id
content_author_id
is_content_author
reply_count_reported
replies_fetched
reply_coverage
collection_batch_id
comment_text
commented_at
digg_count
source_url
source_file
collected_at
primary_category
secondary_categories
category_reason
classification_status
is_noise
noise_reason
```

`primary_category` 只能有一个；无法判断时使用 `未分类`。`secondary_categories` 可以为空。`classification_status` 使用 `ai_proposed`、`user_confirmed` 或 `unclassified`。

## 评论统计

```json
{
  "schema_version": 2,
  "record_type": "comment_research",
  "summary": {
    "input_rows": 0, "deduplicated_rows": 0, "duplicates_removed": 0,
    "noise_rows": 0, "non_noise_rows": 0, "top_level_rows": 0,
    "reply_rows": 0, "hierarchy_unknown_rows": 0,
    "reply_coverage_counts": {},
    "denominator_policy": "top-level-non-noise", "denominator": 0,
    "category_statistics": []
  },
  "records": []
}
```

category_statistics 每项为 primary_category、count、percentage（0 到 100）。默认分母为已知顶层的非噪声评论；旧版扁平数据可显式使用 --denominator non-noise 或 all，但不能称为顶层比例。reply_coverage 使用 complete、partial、not_fetched、unknown；只有显式完整且实际回复数不少于报告数，才能据此统计回答状态。

比例用未四舍五入的行数计算，展示时再格式化。所有分类行数之和应等于分母；如果「未分类」也在分母中，必须作为一个类别显示。

## 证据索引

```text
evidence_id
evidence_type
claim_type
content_id
time_range
text_or_summary
source_url
source_file
collected_at
```

`claim_type` 使用 `fact`、`computed`、`inference`、`user_judgment`、`to_validate`。

## 搜索计划和请求账本

搜索计划保存关键词、排序、时间、分页、请求数、实时价格、最高费用、停止条件和计划哈希。请求账本只保存请求指纹、端点、时间、状态、缓存、已知费用和对应输出文件，不保存凭据。

## 图表 manifest

每张图保存：

```text
chart_id
chart_type
title
file
data_file
filters
columns
denominator
source
collected_at
evidence_issues
fallback
```

`collected_at` 缺失时必须为 `null`，并在 `evidence_issues` 写 `missing_collected_at`，不得拿研究时间代替采集时间。`fallback` 不为空时，报告必须展示对应表格或解释，不能声称图表已经生成。

## 公开字段白名单

公开研究结果只允许使用本合同中的 normalized 字段和显式的报告字段。平台原始响应中的未知字段默认删除；不是看起来无害就保留。

## 基线计算输出

作品的 baseline 包含 metric、median、ratio、reason、candidate_count、sample_count、missing_metric_count、sample_ids、sample_values、sample_published_at、as_of、group。ratio 只有计算条件满足时有数值。reason 为 missing_group_identity、insufficient_samples、zero_baseline、missing_target_metric 或 null。baseline_policy 保留分组字段、年龄窗、样本上下限、研究时点和排除自身规则。

select 输出 selections：group、status、high_id、ordinary_ids、other_author_ids、metric、ordinary_target_median、selection_reason、relevance_condition、time_condition、causal_status。source ID 的详细材料在 sources 文件中，不能仅拿选样清单当作分析。

## 来源与 Agent 分析

sources.json 顶层是数组，每个来源包含 source_id、title、text，可附 paragraphs: [{id, text}]、platform、content_id、source_url、published_at。time_precision 默认为 unknown；只有已复核的 sentence 或 word 对齐才设 alignment_reviewed: true，并保存 duration_seconds 与 alignments: [{start_seconds, end_seconds, text}]。

引用统一为 {source_id, paragraph_id, quote}；整份材料引用可省 paragraph_id。quote 必须逐字存在。涉及视频秒数时再加 start_seconds、end_seconds，必须对应来源 alignments 中已经复核的同一片段。原文不可被引用中的说明文字替代。

analysis.json 可包含：

- comparisons：[{id, title, dimensions}]。dimensions 包含 topic、hook、progression、proof、visual、comments 六项。每项有 observation、citations、alternative_explanations、testable_change、pattern_type、status；缺材料时 status: unknown，说明观察范围。
- evolution：[{id, operation, from, to, logic, expression, fact_change, recommendation}]。from 和 to 是引用数组，支持跨段、拆合段与调序；语义由 Agent 提供。
- draft_sections：[{id, text, references, borrowed_logic, own_facts, expression_change, material_gap}]。references 与 own_facts 均为引用数组。缺材料不能用对标经历顶替。

validate-analysis 返回 citations_checked、analysis_hash、sources_hash 和 semantic_judgment；valid 表示结构与引用通过，不表示程序证明了语义正确。

## 问题聚合输入与输出

问题分析 JSON 为 {questions: [...]}。每组包含 id、question、kind、members、thread_reviews、video_addressed、video_citations、opportunity。

- kind 为 genuine_question 或 claim_keyword，后者不计需求。
- members 每项为 {platform, content_id, comment_id}，应引用已知顶层、非噪声的评论。
- thread_reviews 每项使用同一组定位字段，并附 status、evidence_comment_ids、reason。status 为 answered、partial、unanswered_in_sample、unknown。
- video_addressed 为 addressed、partial、not_addressed、unknown；非 unknown 需要 video_citations，not_addressed 还须提供 video_review: {full_transcript_reviewed: true, reason}，引用来源需声明 text_coverage: full。完整口播未讲到不能扩展为未核对的画面也没讲到。
- opportunity 为 {audience, angle, evidence, material_gaps}，没有机会可用 null。

questions 命令输出每组 occurrences、video_count、answer_counts、representatives（含 evidence_comments、回复数和判断理由）和 opportunity；回复未完整抓取时强制 unknown。输出中的 coverage 保留原评论 summary，而 denominator 文本写明计数口径。

## 写稿状态

state.json 使用 schema_version: 2、record_type: writing_workbench、task_id、title、revision（整数）、updated_at、sources、sections、history，可附 profile 和 import_provenance。

sections 每项包含 id（唯一字符串）、title、mine、note、locked（布尔）、references、reviewed_text、analysis_status、semantic_groups、history、borrowed_logic、own_facts、expression_change。analysis_status 为 reviewed 或 needs_review。semantic_groups 每项包含 id、label、mine（本段原句锚点）、sources（引用数组）、comment，可保留 color。程序检验 source 引用与已复核 mine 锚点。

保存请求只包含 {revision, sections: [{id, mine, note}]}。段落集合不能改变，locked 段的 mine 不能改；来源、标题、分析和用户事实不经普通编辑接口写入。来源补充与 Agent 复核在离线任务数据编辑中按当前 revision 进行，避免覆盖用户最新输入。

## 可运行的合成案例

tests/fixtures/synthetic_decisions.json 只含合成来源、两份含义不同的本人材料和对应写稿分析。该案例用于核对材料是否进入实际判断，以及引用是否能回读。它不是通用写稿的固定文案。
