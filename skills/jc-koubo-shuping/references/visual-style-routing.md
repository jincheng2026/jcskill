# Visual Style Routing

## Canonical Styles

竖屏口播只提供两个已批准风格，必须使用稳定 ID：

| `visualStyleId` | 用户名称 | 视觉基线 |
|---|---|---|
| `assembly-mono` | 黑白 Assembly | `0726-approved-assembly-mono-v1` |
| `google-semantic` | Google 语义配色 | `0721-approved-baseline-v4-multi-mg` |

## Selection Contract

1. 用户明确说「黑白、黑白版、Assembly、苹果黑白」时，解析为 `assembly-mono`，直接执行，不再确认。
2. 用户明确说「Google、谷歌、谷歌配色、彩色、语义配色」时，解析为 `google-semantic`，直接执行，不再确认。
3. 用户没指定，或描述同时命中两种风格时，只问一次：`这条用「黑白 Assembly」还是「Google 语义配色」？`
4. 没得到选择前，不创建 case、不出静态帧、不渲染。
5. 选择必须写入 `case_manifest.json.visualStyleId`，并绑定对应 `workflow.baselineId`。
6. `fast_preview`、`production` 和 `repair` 都继承同一个 `visualStyleId`。局部返修不得静默换风格。
7. 用户明确要求中途换风格时，新建同源 case；旧 case 和旧 attempt 保留。新 case 重新走静态关键帧、样片和全片闸门。

## Shared Rules

两种风格共用以下合同，不因换皮而变化：

- 语义分段、一个 beat 一个 hero、MG 不复述字幕；
- 3–5 个宏观章节、全部标签常驻、当前章节高亮；
- 人脸、主要肢体、字幕安全区和入场 `motion_bbox`；
- 中英字幕单行、独立半透明深色底板；
- 标题先于解释关系，数字和图表必须展示变化过程；
- Remotion 透明 overlay、ffmpeg preserve-source 合成、原音频 stream copy；
- 静态关键帧、10–15 秒样片、全片和发布验收闸门。

## Cross-style Boundary

- 默认禁止在同一条片里混用彩色 Google 卡片和黑白 Assembly 开放式 MG。
- 证据截图、录屏和原始 A-roll 保留原色，不算跨风格混用。
- 用户明确要求混合时，必须先做新的静态关键帧并记录例外范围；不得把混合处理沉淀为默认基线。
