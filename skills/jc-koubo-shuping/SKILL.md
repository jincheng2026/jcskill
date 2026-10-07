---
name: "jc-koubo-shuping"
description: "剪辑竖屏口播 mp4+srt：快速检样、正式成片、局部返修；用 Remotion 与 preserve-source 工艺输出。"
---

# jc-koubo-shuping

## Boundary

只处理 `竖屏口播 mp4 + srt -> Remotion 透明 overlay -> ffmpeg preserve-source 成片`。

不用于横屏、纯转码、拉片、剪映工程或无口播主体。拉片先用本仓库的 `jc-video-analysis`。

## 第一次使用

先确认本机有 Node.js 20 以上、npm、ffmpeg 和 ffprobe（缺什么直接装，有 Homebrew 就 `brew install node ffmpeg`），再运行一次 `node scripts/install-runtime.mjs` 下载 Remotion 运行依赖（几百 MB，开始前告诉用户一句），然后 `node scripts/verify-install.mjs` 检查。字幕 SRT 没有时，先用同仓库的 `jc-zhuanxie` 从口播视频转出来并校正。

本 Skill 的许可证是 CC BY-NC 4.0（见同目录 LICENSE，商用要另外取得作者授权），和仓库里其他 Skill 的 MIT 不同；它用到的 Remotion 有自己的许可证，部分公司用途需要 Remotion 的公司许可。

## Hard Rules

- 先解析 `visualStyleId`：只允许 `assembly-mono` 或 `google-semantic`；已指定直接执行，未指定只问一次，未选定不创建 case。
- 模式：首次检样 `fast_preview`，通过后 `production`，局部修改 `repair`。
- `fast_preview`：一个写入 Agent、4–6 张检样、最多渲染 2 次和自动修复 1 次，然后 `WAIT_USER`。
- `production`：静态图 → 10–15 秒样片 → 全片 → 技术终检 → 人工验收，不跨闸门。
- `repair` 只使受影响的依赖失效，旧产物保留，新产物写入新 attempt；更换源视频必须新建 case。
- SRT 只修明确错误并保留 diff；ASR 仅用于明确疑点片段。
- Remotion 只渲透明包装；ffmpeg preserve-source 合成，禁止 `-shortest`，未改时序则原音频 stream copy。
- 一个 beat 一个 hero；进度限 3–5 个宏观章节同显；MG 按语义选 variant，不随机轮换。
- 中英字幕各单行、独立深色底板；超预算先拆 cue 或改文案，不缩小硬塞。
- motion map 是唯一语义真源；schema v3；新缺陷写入错题集并回归。
- 技术通过不等于发布通过；发布必须有用户明确验收。

## Style Router

- 黑白／Assembly → `assembly-mono`；Google／谷歌配色 → `google-semantic`。
- 未指定或冲突：读 `references/visual-style-routing.md`，只问「这条用「黑白 Assembly」还是「Google 语义配色」？」
- 风格选择写入 manifest；返修继承原风格。中途换风格必须新建同源 case，并重新走静态帧与样片闸门。

## Mode Router

- 用户说「先看看效果、检样、快速出一版」：读 `references/fast-preview.md`。
- 用户确认静态图或样片并要求继续成片：读 `references/production.md` 和既有发布合同。
- 用户说「字太大、卡片挡脸、只改某处」：读 `references/repair.md`，先运行 `repair-case.mjs`。

## Canonical Commands

1. 创建 case：`node scripts/create-case.mjs --video /abs/in.mp4 --srt /abs/in.srt --out /abs/case --style assembly-mono|google-semantic`。
2. 编译 caption plan 和 motion map；到 `motion_map_ready` 后运行 `run-fast-preview.mjs`。
3. 通过后按 `production.md` 成片；返修用 `repair-case.mjs`。
4. 修改 Skill 后运行 `verify-fast-preview.mjs` 和 `verify-install.mjs`。

## Resource Routing

下列 `.md` 均位于 `references/`：

- 输入／流程／模式：`input-contract.md`、`workflow-contract.md`、`fast-preview.md`、`production.md`、`repair.md`
- 双风格：`visual-style-routing.md`、`style-assembly-mono.md`、`style-google-semantic.md`
- 内容／视觉：`semantic-copy-contract.md`、`mg-variant-contract.md`、`visual-contract.md`
- 交付：`preserve-source-quality.md`、`render-contract.md`、`qa-contract.md`、`release-gates.md`
- 错题：`error-bank.md`、`evals/error-cases.json`
- 执行资产：`assets/remotion-template/`、`assets/baselines/`

## Completion Contract

缺 motion map、两次人工闸门、Remotion provenance、QA、preserve-source 证据或用户明确验收，不得报告「剪辑完成」。验收 JSON 不能证明填写者身份。
