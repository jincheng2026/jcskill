# Production

只有用户明确通过静态检样后进入本模式。

1. 锁定已通过的 baseline、motion map、MG variant 和字幕；不得在生产阶段重新设计视觉语法。
2. 生成 10–15 秒高风险动态样片以及 overview、animation-risk、caption-risk、safe-zone 联系表。
3. 用户明确通过样片后，运行完整错题回归，再渲染全片 Remotion RGBA overlay。
4. 按 `preserve-source-quality.md` 先合成 video-only，再 stream copy 原音频；禁止 `-shortest`。
5. 运行 `validate-final.mjs --record-technical`。技术通过只报告 `technical_pass_pending_acceptance`。
6. 用户验收后记录外部消息证据，再运行 `validate-final.mjs --require-acceptance`。

Production 保留完整 provenance、QA、manifest、hash 和发布门；Fast Preview 的轻量规则不得用来绕过正式交付红线。

默认声音政策仍是 preserve-source：未改时序时原人声 stream copy。`sound_cue` 只用于记录关键动作的声音意图；本版本不自动混入实验音效，不允许为了 MG 声音损伤原始人声。
