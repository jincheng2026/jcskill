# Semantic Copy Contract

## First Principle

MG 文案必须降低当前语义时刻的理解成本。字段齐全、时间均分、截取字幕和复用通用短语都不能证明完成了语义分析。

schema v3 把数据分成三层：作者写 source motion map；编译器从 cue 证据生成 compiled motion map；`manifest.nodes` 只由 compiled motion map 生成。

语义 beat 只服务 MG、字幕、声音和 QA，不等于观众可见章节。顶部进度默认只显示全片时间进度；确有结构性章节时，另写 `manifest.progressChapters`，只允许 3–5 个连续、完整覆盖全片的宏观章节。禁止把 `beats[].mg_copy.label` 批量复制成进度条标签。

## Whole-video Argument Map

source motion map 顶层必须包含：

- `argument_map.core_claim`：全片唯一核心结论。
- `argument_map.audience_problem`：观众原有困惑或错误认识。
- `argument_map.ending_action`：看完后的具体行动。
- `argument_map.progression[]`：论证节点；每项包含唯一 `id`、`type` 和本片独有的 `claim`。

`type` 只能是 `hook`、`claim`、`mechanism`、`evidence`、`contrast`、`action`、`cta`。

## Source Beat Schema

每个 beat 由作者填写：

- `id`：唯一稳定 ID。
- `cue_ids`：按字幕顺序组成完整且不重不漏的分区。
- `argument_id`：引用 argument map 中的论证节点。
- `boundary.type`：语义变化类型。
- `boundary.change`：前后两段究竟新增了什么，不能写占位词。
- `semantic_function`、`viewer_need`、`trigger_rule`、`hero_visual`、`caption_policy`、`sound_cue`、`layout_risk`。
- `mg_copy.label`、`eyebrow`、`title`、`sub`、`chips`、`accent`。
- 可选 `mg_copy.variant` 和对应的 `mg_copy.payload`；未声明 `variant` 时按 `semantic_card` 兼容。字段合同见 `mg-variant-contract.md`。

作者不填写 `start`、`end`、`timecode`、`spoken_line`。编译器从 `cue_ids` 和 manifest 字幕真源自动生成，防止伪造逐字证据。

## Copy Rules

- title 回答「这一段必须记住什么」，sub 回答「为什么、如何或下一步是什么」。
- MG 文案必须包含字母或数字意义字符；纯标点、零宽字符和 `x/TODO/待补充` 等占位内容硬失败。
- title 不超过 20 个可见字符，sub 不超过 28 个，label 不超过 8 个，eyebrow 不超过 24 个，每个 chip 不超过 10 个。
- 英文 token 在 title、sub、chips 的任何位置都不能截断。证据中同时真实存在独立 `A` 和 `AI` 时，合法的「方案 A」不得误杀。
- 一个 beat 只允许一个 hero。
- `variant` 必须回答当前信息是什么关系；禁止为了避免重复而随机换卡片。
- 列表、左右关系、流程和数字结论的可见文案必须写入结构化 payload，不能继续塞进一个长 `sub`。

## Hard Failures And Risk Warnings

硬失败包括：schema 非 v3、cue 不重不漏分区失败、argument 引用无效、证据或 timing 非编译生成、无效文字、明确英文 token 截断、nodes 漂移和 provenance hash 漂移。

风险警告包括：3–10 秒之外的 beat、三个以上 beat 时长近似均分、重复或高度相似 MG、整组 chips 重复、通用套话和未使用 argument。风险不是自动判错；只有修正文案或在顶层 `risk_overrides` 中对精确 warning ID 写至少 6 个可见字符的具体理由，才会解除渲染阻断。

```json
{
  "risk_overrides": [
    {"id": "repeated_title:n12", "reason": "结尾刻意回扣开场原句，形成首尾呼应"}
  ]
}
```

## Compile And Timing

```bash
node scripts/record-workflow-timing.mjs /abs/case/case_manifest.json --phase semantic_analysis --start
node scripts/compile-motion-map.mjs /abs/case/case_manifest.json --motion-map planning/motion-map.json
node scripts/record-workflow-timing.mjs /abs/case/case_manifest.json --phase semantic_analysis --stop
```

编译器默认写 `planning/motion-map.compiled.json`，记录 source map、compiled map、compiler 和 semantic core 的 SHA-256。任何一个发生变化都必须重新编译。

机器门只能阻止可证伪的结构问题，不能证明文案深刻。正式全片前仍必须审查完整 motion map，并用 10–15 秒高风险样片验证真实理解效果。
