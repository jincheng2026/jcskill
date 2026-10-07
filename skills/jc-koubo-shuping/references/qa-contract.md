# QA Contract

## Severity And Auto-Fix Budget

- P0：错素材、黑屏、缺帧、字幕事实错误。必须阻断。
- P1：中文或英文缺失、任一字幕不是单行、文字裁切、字号跌出批准区间、双底板样式漂移或脸部遮挡。Fast Preview 最多自动修一次。
- P2：卡片略大、动效强弱、轻微安全区风险。展示给用户决定。
- P3：纯主观的「可能更高级」。不得触发自动返工。

Fast Preview 最多渲染 2 次；预算耗尽后必须返回 `AUTO_FIX_LIMIT_REACHED / WAIT_USER`。Production 的发布硬门不受该预算削弱。

## Preview Gates

Before full render, require:

- 4–6 static previews plus one contact sheet;
- explicit human decision for static previews;
- 10–15 second representative pilot;
- pilot overview, animation-risk, caption-risk, and safe-zone contacts;
- explicit human decision for the pilot.

## Full Render Evidence

Generate and inspect:

- overview、scene-boundary、animation-risk、caption-risk、cue-coverage、safe-zone、publish-safe-top 分页联系表；
- `qa/contact-sheet-coverage.json`，记录每组真实抽查帧与对应页；
- overlap-specific contact sheets when SRT timings overlap
- source/final ffprobe, overlay alpha/frame count, full decode result, audio packet hash, and final SHA-256

Check every cue at start + 0.2s, start + 1s, hold midpoint, and end - 0.2s. Check entry motion at +0f, +6f, +12f, +18f, and +30f. Check captions at start +2f, midpoint, and end -2f.

For multi-MG timelines also require:

- one final-state frame for every active `mg_copy.variant`;
- every scene boundary at -1f, +0f, +6f, and the hold midpoint;
- explicit parent/child containment checks for inner panels, prompt comparison rows, list rows, and bookmark footers;
- no text touching the outer card bottom padding or crossing its rounded clip;
- no stale hero retained after the next semantic beat begins.

## Fixed-Route Proof

Technical validation must prove:

- source is not inside Remotion;
- overlay is native-size RGBA and contiguous;
- preserve-source video-only composite exists;
- complete original audio was remuxed with packet hash equality;
- no `-shortest`;
- final frame count and fps match the declared target;
- final color tags match the quality profile;
- final file fully decodes;
- required QA images and SHA exist.

The checks verify compliance with the fixed route; they are not a substitute for that route.

## Human Acceptance

Technical pass is `technical_pass_pending_acceptance`, not final release.

Release requires `qa/acceptance.json` with:

- matching case ID and final artifact;
- `decision` equal to `accepted` or `accepted_with_risks`;
- `reviewer.type = human`;
- user statement or equivalent human evidence;
- final SHA-256 and technical report path.

验收记录还必须包含 `evidence.source=external_user_message`、thread/message ID、记录时间、技术报告路径和最终成片实际 SHA。artifact 必须严格等于 `manifest.finalVideo`。

边界：脚本只能校验这些外部消息元数据与文件 SHA 的结构一致性，不能在同一文件权限域内鉴别人类或 AI 作者。执行者不得自己生成用户验收；最终判断仍以真实对话中的用户消息为准。
