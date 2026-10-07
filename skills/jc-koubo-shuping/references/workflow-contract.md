# Workflow Contract

## Execution Modes

- `fast_preview`：到 `static_preview_pending` 即停止等待用户；使用极简证据和渲染预算。
- `production`：沿既有状态机走到发布；保留完整证据和人工闸门。
- `repair`：从现有 case 计算依赖失效，只重跑受影响节点；旧 attempt 保留。

模式不能偷换：Fast Preview 不能宣称发布完成，Production 不能跳过静态与样片验收，Repair 更换源视频必须新建 case。

## Visual Style Resolution

- 在 `intake` 之前按 `visual-style-routing.md` 解析风格。
- `case_manifest.json.visualStyleId` 只允许 `assembly-mono` 或 `google-semantic`。
- `workflow.baselineId` 必须与所选风格一一对应；不得选黑白风格却继续引用 Google 基线。
- 风格未指定时必须先问用户，不得把历史默认或当前模板颜色当成用户选择。
- 返修沿用 manifest 已记录的风格；中途明确换风格时新建同源 case，重新走静态帧和样片闸门。

## State Machine

按顺序推进，不跨级：

1. `intake`
2. `subtitle_reviewed`
3. `motion_map_ready`
4. `static_preview_pending`
5. `static_preview_accepted`
6. `pilot_pending`
7. `pilot_accepted`
8. `full_rendered`
9. `technical_pass`
10. `final_release_accepted`

任何阶段被用户否决，都回到造成问题的最早阶段，不在后续阶段打补丁掩盖。

## Intake And Subtitle Review

- 用 ffprobe 记录源分辨率、fps、帧数、时长、编码、码率、音频和色彩标签。
- 逐条检查 SRT 的错别字、专有名词、断句、时间重叠和尾差。
- 原 SRT 保留只读副本；修订稿另存，并生成逐条差异记录。
- 只修正明确错误，不把用户口语改成书面稿。
- SRT 存在重叠时，保留文字真源；显示层把前条结束时间夹到下一条开始，避免双字幕同屏。
- 修订后按语义拆成单行 caption plan；在每条源 cue 内按整数帧连续分配，不丢字、不改顺序、不跨源 cue 偷换时间。
- 每条拆分后的中文 cue 都要提供简洁英文翻译；英文必须与当前中文语义一一对应，不能把整条源句的译文重复到多个短 cue。

## Semantic Planning

- 先读 `semantic-copy-contract.md`。canonical workflow 只接受 schema v3；旧 case 先显式迁移。
- 先写全片 argument map，再按语义变化拆 beat；不得从自动均分草稿生成最终计划。
- 作者只填写 cue 分区、argument 引用、边界理由、语义字段和 MG 文案；时间、timecode 与 spoken_line 必须由编译器从字幕证据生成。
- 3–10 秒是风险参考范围，不是绝对语义真理；异常时长、近似均分、重复或通用文案必须修正或提供明确 override 理由。
- `create-case` 生成的等时长 `draftNodes` 只帮助定位素材，始终不可渲染。motion map 完成后必须运行 `compile-motion-map.mjs`，禁止手改 `manifest.nodes`。
- 每个 beat 只允许一个 hero；字幕、标签和 chips 只能辅助。
- 沿用最近获用户批准的 style baseline。没有明确授权，不重新发明卡片壳、字幕底板或进度条。
- 组件语义 variant 可以共用，但具体皮肤、字体、颜色、卡片壳和对比层必须由 `visualStyleId` 决定，禁止跨风格混搭。

## Static Preview Gate

- 先生成 4–6 张低成本静态预览；字幕预检必须证明全部中英文 cue 均为单行、翻译非空，并使用双层独立黑色圆角底板。
- 必须覆盖：开场结论、最强证明点、最抽象点、高风险同屏、收尾 CTA。
- 检查头顶留白、脸部安全区、字幕安全区、标题完整性和视觉基线一致性。
- 用户未明确通过，不进入动态样片。
- 默认使用 `run-fast-preview.mjs`；一个写入 Agent、最多 2 次渲染和 1 次自动修复。第 2 次后必须 `WAIT_USER`。

## Dynamic Pilot Gate

- 样片默认 10–15 秒，选择最能暴露风险的连续片段。
- 至少覆盖一次卡片入场、字幕接力、进度变化和 hero/讲者同屏。
- 输出样片、overview contact、animation-risk contact 和 caption-risk contact。
- 用户未明确通过，不进入全片。

## Full Build

- 锁定样片通过的 baseline、布局和组件语法，不在全片阶段重新设计。
- 全片使用固定 preserve-source 画质工艺。
- 每个 cue 检查开始、入场、停留中点和结束前；字幕与动画另查风险帧。
- 技术通过后等待用户验收；只有明确接受才能进入 `final_release_accepted`。

## Required Manifest Evidence

```json
{
  "workflow": {
    "stage": "pilot_accepted",
    "subtitleReview": {"revisedSrt": "source/revised.srt", "diff": "reports/subtitle-diff.json"},
    "motionMap": "planning/motion-map.compiled.json",
    "planningMode": "semantic_manual",
    "semanticPlan": {"sourceMotionMap": "planning/motion-map.json", "sourceMotionMapSha256": "...", "compiledMotionMapSha256": "...", "compilerSha256": "...", "semanticCoreSha256": "..."},
    "staticPreview": {"files": [], "contactSheet": "qa/static-preview-contact.jpg", "decision": "accepted", "reviewerType": "human", "evidence": {"source": "external_user_message", "threadId": "...", "messageId": "...", "artifact": "qa/static-preview-contact.jpg", "sha256": "..."}},
    "pilot": {"video": "pilot/pilot.mp4", "contacts": {"overview": "...", "animationRisk": "...", "captionRisk": "...", "safeZone": "..."}, "decision": "accepted", "reviewerType": "human", "evidence": {"source": "external_user_message", "threadId": "...", "messageId": "...", "artifact": "pilot/pilot.mp4", "sha256": "..."}}
  }
}
```

Manifest 顶层还必须包含：

```json
{
  "visualStyleId": "assembly-mono"
}
```

`workflow.history` 必须从 `intake` 开始逐级记录到当前阶段；当前脚本能校验顺序与证据绑定，但文件系统本身不提供不可伪造的历史签名。
