# MG Variant Contract

## Selection Rule

一个 beat 只选一个可阅读 hero。先判断信息关系，再选择组件；不要按序轮播，不要为了让画面一直动而加 MG。

| variant | 适用语义 | 必需 payload |
|---|---|---|
| `semantic_card` | 普通结论、机制摘要 | 无；沿用 title、sub、chips |
| `chapter_title` | 开场钩子、章节切换、情绪高点 | 无 |
| `contrast_statement` | 否定旧认识并给出真正重点 | `left`、`right`，可选 `footer` |
| `numbered_list` | 2–5 个并列步骤、条件或清单 | `items[]` |
| `prompt_fact` | 口令、引用、事实原文加前后对比 | `quote`、`left`、`right` |
| `dual_relation` | 两个对象相加、对比或组合 | `left`、`right`、可选 `operator` |
| `bookmark_relation` | 先后关系、索引与完整信息的关系 | `left`、`right`、`footer` |
| `agent_flow` | 3–4 个节点的单向流程 | `flow[]` |
| `numeric_conclusion` | 核心数字、比例、数量结论 | `value`、`unit` |

`left` / `right` 结构为 `{label?, title, sub?}`；`items[]` 为 `{label, note?}`。所有长度限制由 `mg-layout.json` 和语义编译器共同执行。

## Hierarchy

- 先出现标题或判断，让观众知道本段讲什么。
- 再出现解释关系：列表项、左右卡、流程节点或事实条。
- 最后出现页脚、补充说明或数字落点。
- 大数字必须有变化过程；列表和流程必须逐项接力，不得所有子元素同帧弹出。
- 元素出现后必须有可读停留；下一 beat 的 +0f 必须切换 hero，旧组件不得残留。

## Layout Budget

- 所有外卡、内卡、标签和页脚使用 `box-sizing: border-box`。
- 720 设计画布上的 hero 底边不得低于 `y=420`，底部字幕从 `y=890` 开始。
- `prompt_fact`：外卡高 220，底部 padding 25。
- `dual_relation`：外卡高 216，内卡高 116。
- `bookmark_relation`：外卡高 252，内卡高 116，页脚高 34，页脚上间距 14。
- `numeric_conclusion`：外卡至少高 234，数字落点、底部结果条和 20 px 底部留白必须同时完整显示。
- 超出字段长度或数量预算时，修改文案或拆 beat；禁止缩到看不清、隐藏溢出或让文字贴住卡片底边。

## Forbidden

- 不同语义全部套同一张通用卡。
- 同一段同时放标题卡、列表、数字和图表。
- 用卡片复述字幕，而不提炼关系。
- 用随机 variant 制造“丰富感”。
- 固定高度卡片没有明确内容区、页脚区和底部留白。
- 只检查最好看的中间帧，不检查入场、最终状态和场景边界。
- 未经单独声音方案批准，自动给每个小元素配音效或重新编码原人声。
