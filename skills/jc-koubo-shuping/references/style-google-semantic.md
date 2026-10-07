# Style: Google Semantic

## Identity

`visualStyleId=google-semantic`。这是原 `jc-koubo-shuping` 已验证的 Google 语义配色、多 MG 卡片系统，不是任意彩虹渐变，也不是每段随机换色。

基线：`0721-approved-baseline-v4-multi-mg`。

## Palette

- Google Blue：`#4285F4`
- Google Red：`#EA4335`
- Google Yellow：`#FBBC05`
- Google Green：`#34A853`
- 主文字：`#F8FAFD`
- 深色玻璃卡：`rgba(8,11,17,0.84)` 到 `rgba(20,25,36,0.78)`
- 辅助线和边框：白色 10%–20% alpha

颜色按语义使用：

- 蓝：结构、工具、信息、连接；
- 红：风险、错误、阻塞、否定；
- 黄：数字、提醒、等待、关键转折；
- 绿：完成、行动、解决方案、正向结果。

同一个 beat 只选一个主强调色。禁止按顺序机械轮播颜色。

## Typography And Cards

- 中文：`Noto Sans SC`；英文标签：`JetBrains Mono` 或等宽 fallback。
- 卡片采用深色玻璃、单侧 10 px 强调轨、22 px 圆角、1 px 轻边框。
- 标题清晰高于摘要；事实、左右关系、数字和列表使用不同组件，但共享圆角、边框、阴影和间距系统。
- 组件几何与字段预算以 `assets/remotion-template/src/mg-layout.json` 为准。

## Progress

- 3–5 个宏观章节标签全部常驻。
- 当前章节高亮；已完成明亮；未来章节弱化。
- 轨道可使用蓝红黄绿连续渐变，但语义 beat 标签不得直接成为可见章节。

## Motion

- 标题或判断先出现，再进入关系信息，最后出现页脚或补充结论。
- 卡片整体入场使用小幅滑入/缩放；内部列表、左右面板、流程节点按信息关系接力。
- 大数字 20–40f 计数或变化；禁止直接跳最终值。
- 音效只绑定标题 hit、关键数字、结论和空间移动，不给每个 chip 加声音。

## Forbidden

- 为了“像 Google”把四种颜色同时塞进一张卡。
- 随机换色、随机换 variant。
- 卡片复述字幕。
- 玻璃卡过暗、过厚，遮住人物环境。
- 圆角、边框、阴影和字体在不同卡片之间漂移。
- 把参考视频原作者的文案、商标、截图或标签照搬进新视频。
