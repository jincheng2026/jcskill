---
name: jc-zhuanxie
description: "把本地音视频批量转成逐字稿：火山引擎豆包语音识别（没有 Key 或额度用完时可用本机 Qwen3-ASR 备用），保留原始识别、分段复核、校正错别字并验收，也能单独出句级字幕和字级时间戳。用户会说：转文字、转写、出逐字稿、把这个视频转成文字、校正错别字、要字幕时间戳。不触发：下载平台视频（先用下载工具拿到文件）、把对标作品整理入库（用 jc-benchmark-intake，它会调用本 Skill）、拆解视频内容（用 jc-video-analysis）、写稿（用 jc-jiaocheng-video）。"
---

# 转文字

把本地中文音视频稳定转成完整逐字稿。主引擎是火山引擎豆包语音「录音文件识别标准版 2.0」；本机装了备用引擎时，火山不可用会自动改用本地。不打开任何 App。

下面的 `<本 Skill 目录>` 指这份 SKILL.md 所在的文件夹，运行脚本前先确定它的绝对路径。

## 开工前检查

先运行一次检查，它不调用接口、不打印 Key：

```bash
python3 <本 Skill 目录>/scripts/volc_asr.py --check
```

输出会说清四件事：火山的 Key 读到没有、从哪读到的（环境变量还是 macOS 钥匙串）、ffmpeg 和 ffprobe 在不在、本地备用引擎装没装。按结果处理：

- **Key 没读到，本地备用也没装**：AI 停下，用一句话告诉用户怎么申请和保存 Key，然后等用户说好了再继续。申请：登录火山引擎控制台，进入「豆包语音」，开通「录音文件识别标准版 2.0」，在「API Key 管理」里创建一个 Key（`ark-` 开头的是火山方舟的 Key，不能用在这里）。保存：请用户**自己在「终端」里**运行 `security add-generic-password -a volc -s volc-speech-api -U -w`，在密码提示处粘贴 Key 后回车（这里要的不是开机密码）。不让用户把 Key 发进聊天，AI 也不读、不打印 Key。不想用钥匙串的，可以改设环境变量 `VOLC_SPEECH_API_KEY`。
- **ffmpeg 或 ffprobe 没找到**：装了 Homebrew 的 Mac 让用户运行 `brew install ffmpeg`（ffprobe 一起装上）；其他系统按 ffmpeg 官网安装。
- **本地备用没装**：不影响用火山转写，不用提。只有下面「本地备用引擎」里说的情况才建议装。

Key 的读取顺序：环境变量 `VOLC_SPEECH_API_KEY` → macOS 钥匙串（service `volc-speech-api`，account `volc`）。环境变量 `JC_VOLC_KEYCHAIN_SERVICE` 可以把钥匙串的 service 名换掉，只用于测试。

## 引擎说明

- 火山引擎：`scripts/volc_asr.py`，接口 `https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit`（提交）和 `/query`（轮询结果），资源 ID `volc.seedasr.auc`。按识别时长计费，价格以火山控制台为准。其他需要转文字的 Skill（例如 jc-benchmark-intake）都调用这个脚本。
- 媒体先用 ffmpeg 抽成 16kHz 单声道 MP3 再上传；超过 30 分钟在静音处自动切段，最多 3 段并发请求，时间戳自动加回偏移。
- 不开启顺滑（会删掉口语重复的功能），保留口语和重复；开启标点和数字规整（把「三点五」写成「3.5」这类）。
- 结果里的 `engine` 和复核稿头部写明实际用了哪个引擎；自动切换时 `fallback_reason` 记录火山的失败原因，交付时告诉用户。
- 强制指定：`--engine volc`（只用火山，失败就报错）、`--engine local`（只用本地、不花钱），或环境变量 `JC_ASR_ENGINE`。
- 测试脚本改动时只截几十秒到两分钟的片段；需要反复试时用 `--engine local`。

## 本地备用引擎（可选，只适用 Apple 芯片 Mac）

本机的 `Qwen/Qwen3-ASR-1.7B`（用苹果的 MLX 框架运行），字级时间来自 `Qwen3-ForcedAligner-0.6B`。火山因额度用完、没开通、Key 不对、服务繁忙或网络原因失败时自动改用它；空音频、格式错误、参数错误不切换。两者准确度接近，英文产品名多的内容本地略好。速度约 4 倍实时，也就是 1 小时的音频大约 15 分钟。

什么时候建议装：用户没有火山的 Key 又想马上用，或者想不花钱反复测试。装之前先跟用户说一句要装什么、多大，等用户同意：Python 环境约 250 MB，第一次运行会从 Hugging Face 下载两个模型，合计约 6 GB，存在 `~/.cache/huggingface/hub`。需要 Python 3.10 以上。

安装（用户同意后 AI 可以代为运行）：

```bash
python3 -m venv ~/.local/share/qwen3-asr/venv && ~/.local/share/qwen3-asr/venv/bin/pip install mlx-qwen3-asr
```

脚本默认找 `~/.local/share/qwen3-asr/venv/bin/python`；装在别处时用环境变量 `JC_QWEN3_ASR_PYTHON` 指向那个 Python。装完再跑一次 `--check`，`local_fallback` 应为 `true`。

## 边界

- 处理本地 MP4、MOV、MKV、WebM、MP3、M4A、AAC、WAV、FLAC、OGG、Opus。
- 普通网页或平台分享链接先交给对应下载工具；拿到真实媒体文件后再转写。不要把下载成功当作转写完成。
- 只做下载后校验、识别、错字校正和交付验收，不自动分析观点、提炼金句、写稿或整理进素材库。
- 保留口语、重复和原意；只修确定的识别错误。完整标准见 [references/correction-standard.md](references/correction-standard.md)。

## 这一步人要判断什么

| 时候 | 人判断什么 | AI 怎么做 |
| --- | --- | --- |
| 缺 Key 时 | 要不要申请火山的 Key、要不要装本地备用 | 说清去哪申请、怎么存、本地备用多大，等用户回复；Key 由用户自己在终端里存 |
| 校正时拿不准的专有名词、人名、数字 | 到底是哪个词 | 不猜，标 `【疑似：…】` 或 `【听不清】`，交付时列出来请用户看 |
| 用户只要最终稿、想清理中间材料 | 删不删中间材料 | 默认全保留；用户要求瘦身时移进回收站，不永久删除 |

## 工作流

1. 确认输入目录和交付目录。用户没要求清理时，保留全部中间证据。
2. 跑「开工前检查」，再用一个样本验证媒体、引擎、ffmpeg 和输出路径。
3. 批量转写（逐个文件处理，单个长文件内部分段并发）：

```bash
python3 <本 Skill 目录>/scripts/transcribe_batch.py \
  "/绝对路径/输入目录" \
  "/绝对路径/输出目录"
```

只想盘点和检查媒体、不启动识别时加 `--dry-run`。`--dry-run` 仍会创建输出子目录并写入 `manifest.json`，所以用一个独立的检查输出目录，不指向已有的正式交付目录。用户明确要求只读、不允许写文件时，不运行这条命令，改用不落盘的 `ffprobe` 检查媒体。

```bash
python3 <本 Skill 目录>/scripts/transcribe_batch.py \
  "/绝对路径/输入目录" \
  "/绝对路径/输出目录" \
  --dry-run
```

4. 逐项读取 `原始识别/<id>.txt`。长音视频按约 28 秒切片复核，把带时间戳的复核稿写入 `分段复核/<id>.md`。
5. 按 [references/correction-standard.md](references/correction-standard.md) 校正，把最终稿写入 `校正版逐字稿/<id>.md`。不能覆盖原始识别。
6. 运行最终验收：

```bash
python3 <本 Skill 目录>/scripts/validate_delivery.py \
  "/绝对路径/输出目录"
```

7. 交付完整逐项文本和验收结果。作者、日期、主题只从可验证的来源信息取得；不确定就保留编号或标 `【疑似：…】`。

## 单文件与字级时间戳（切片、剪辑用）

`transcribe_batch.py` 已在 `原始识别/` 为每项同时写出 `<id>.srt`（句级字幕）、`<id>.json`（小句加每个字的起点时间）和 `<id>.volc.json`（接口原始返回）。只处理单个文件时直接运行：

```bash
python3 <本 Skill 目录>/scripts/volc_asr.py /绝对路径/媒体.mp4 --out-prefix /绝对路径/输出前缀 --review-md
```

句子带 `approx: true` 表示接口给的词和句子文本对不上，字级时间是按句内平均分配估出来的，定切点前必须回原声核对。抽音频必须带 `-af aresample=async=1:first_pts=0`（脚本已内置）：不加的话，AAC 音频顺序解码出来会比视频时间轴短几秒、中段还会浮动，成片音画对不上。转完随机抽一句，按时间戳回原片核对。

## 标准目录

```text
输出目录/
├── manifest.json
├── 原始识别/
├── 分段复核/
├── 校正版逐字稿/
└── validation.json
```

## 完成条件

以下清单适用于完整校正版逐字稿交付。用户这次只要切片或剪辑用的字级时间戳时，交付对应媒体的句级 SRT 和字级 JSON，保留原始识别；核对文件非空、时间戳有效且不超出媒体时长，并按上一节要求抽句回原片核对。单文件命令不生成下面的 manifest、校正稿和 validation，不能把时间戳交付说成完整逐字稿校正完成；这次也要校正版逐字稿时，仍须走完校正流程和下面的验收。

- `manifest.json` 中每个输入都有明确状态。
- 成功项的原始识别和校正版逐字稿数量一致、内容非空。
- 长音视频有分段复核稿；没有空分段和明显的时间缺口。
- 没有 `.part`、`.tmp` 或零字节交付文件。
- 失败项不计入完成数，可单项重跑；不能用进程退出或文件出现代替交付验收。

## 失败处理

- 媒体不可读：先看 `ffprobe`，不要把下载残片送去识别。
- 接口报 `45000030 requested resource not granted`：豆包语音控制台还没开通录音文件识别标准版 2.0。报 `Invalid X-Api-Key`：Key 不是豆包语音的 API Key（`ark-` 开头的是火山方舟的，不能用）；请用户重新创建，再用上面的终端命令覆盖保存（`-U` 会覆盖旧的）。
- 接口报 `55000031` 服务器繁忙：脚本已自动重试 3 次；仍失败就单项重跑。
- 分段边界附近的字可能被切断：复核时重点看 `volc.json` 里 `chunks` 的边界时间。
- 专有名词不确定：对照分段和上下文；仍不确定就标 `【疑似：…】`，不猜。
- 用户只要最终稿：仍保留原始识别和校正层；需要瘦身时，把中间材料移进 `回收站/YYYY-MM-DD_原文件名`（在工作文件夹或输出目录旁），不永久删除。
