# jc-benchmark-intake · 对标内容入库

## 是什么

把你已经选中的抖音、小红书、视频号等社媒内容，连同复制的作品信息、图片和本地视频，去重后存进工作文件夹的 `市场调研/对标素材/未参考/<平台>/`，一条作品一个文件夹。有视频时调用 jc-zhuanxie 补齐逐字稿，再用识别时间给校正版生成同名时间码字幕（`.srt`）；验收通过后，正式素材只留校正版逐字稿和字幕，中间版本移进工作文件夹的 `回收站/`。

值不值得对标由你自己判断，这个 Skill 只负责把你选中的内容存完整、存对地方。

## 你可以直接这样说

- 「这是社媒助手复制的内容和下载好的视频，把它作为对标内容入库。」
- 「把这条小红书笔记存进对标素材，图片也一起放进去。」
- 「检查这条内容是不是已经存过，没有就入库。」

## 不做什么

- 不替你寻找或挑选对标内容（找内容、看数据用 jc-media-research）。
- 不分析为什么爆、不生成选题、不总结写法、不写稿（拆解用 jc-video-analysis）。
- 不登录平台、不保存凭据；除了转写用的火山引擎接口，不调用付费接口。
- 只想把音视频转成文字、不需要入库时，用 jc-zhuanxie。

## 依赖

- 同一个地方装好本仓库的 jc-zhuanxie（转写），以及它需要的火山引擎豆包语音 Key 和 ffmpeg。
- Python 3.10 以上，只用标准库。

## 本地验证

在本 Skill 文件夹里运行：

```bash
python3 -m unittest discover -s tests
python3 scripts/validate_workspace.py "<工作文件夹>" --target "市场调研/对标素材/未参考/抖音/目标目录" --strict --require-srt --json
```

## 常见问题

- 提示重复：打开报告指出的现有目录，在原目录补资料，不新建第二份。
- 视频检查失败：先确认原视频能被 `ffprobe` 读取，不把下载残片送去转写。
- 缺少逐字稿：运行 jc-zhuanxie，先在 `.staging/` 保留完整证据并通过验收；正式入库后再清理中间版本，不能提前删。
- 字幕检查报「文字和校正版逐字稿对不上」：逐字稿改过了，用 `python3 scripts/transcript_srt.py build --timing 现有字幕.srt --transcript 逐字稿.md --force` 重建，不用重新转写。

## 借鉴来源

参考了 PostPlus 的 social-media-extractor、benchmark-to-brief 和 video-transcription 的做法，只借鉴了明确分工、证据分层、先暂存再入库和转写验收这几个机制；转写改用火山引擎豆包语音（jc-zhuanxie），没有复制其托管服务、付费确认或平台专用代码。
