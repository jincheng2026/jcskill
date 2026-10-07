# jcskill

何锦成的 AI 工作流 Skill。主体是一套 **JC 内容创作系列**：做 AI 自媒体视频时，从调研对标、拆解对标、生成内容、发布到复盘，每个阶段一个 Skill，加一个总入口 `jc`。另外还有 10 个通用 Skill（思考、规划、学习、写作、公众号）。

这套方法的核心一句话：

> 每一个环节，能用 AI 参与的，我就尽量用 AI 参与……但是我们人类该把控哪些环节，这个地方我们要时刻清楚。

所以每个 Skill 都会在固定的地方停下来等你：叙事你说「确认」才写全稿，修改建议你点「采纳」才算，复盘你说「行」才写入，记进你的判断库要你逐条同意。AI 做功课、出初稿、算数据，拍板的是你。

支持 Codex 和 Claude Code，在 Apple 芯片的 Mac 上测过。

---

## 安装

把下面这句复制给 Codex 或 Claude Code 发出去（在哪个对话里发都可以）：

> 照 https://github.com/jincheng2026/jcskill 里的 docs/给AI的安装说明.md，把 JC 内容创作系列 Skill 装进这台电脑上的 AI 工具，然后用 jc 带我走一遍新手引导。已经装过的话，就更新到最新。缺什么直接装，要我输密码或者点允许的时候提醒我。

AI 会自己查你用的是 Codex 还是 Claude Code、缺什么工具，装好 12 个 Skill，在 `~/Documents/jincheng-workbench/` 建好你的工作文件夹，然后用总入口 `jc` 给你讲清楚五个阶段各用哪个 Skill、每一步你要判断什么。以后想更新，把同一句话再发一次。

安装说明是写给 AI 的，也可以自己照着做：[docs/给AI的安装说明.md](docs/给AI的安装说明.md)。

## 开始做第一条

装好以后，想直接从一条参考视频开始，复制这句，把链接贴在最后：

> 用 jc 内容创作系列，帮我拆这条参考视频，拆完和我定叙事，叙事我确认后写第一版逐字稿并做成创作页。没装就先照 https://github.com/jincheng2026/jcskill 的安装说明装好。需要我判断、输密码或者点允许的时候提醒我。参考视频：

不知道从哪开始，就跟 AI 说一句「用 jc 看看我下一步该做什么」。

---

## 五个阶段

| 阶段 | Skill | AI 做什么 | 你判断什么 |
| --- | --- | --- | --- |
| 总入口 | `jc` | 新手引导、帮你选 Skill、提醒到点没抓的发布数据、更新本系列 | 现在做哪件事 |
| 一、调研对标 | `jc-media-research` | 找低粉爆款、算博主自己的平均水平和爆款倍数、读评论区找需求，出带图表的报告 | 哪条值得学、哪个选题值得拍 |
| | `jc-benchmark-intake` | 你选中的作品去重入库：原文、图片视频、校正版逐字稿、时间码字幕 | 哪条值得入库（它不替你判断） |
| 二、拆解对标 | `jc-video-analysis` | 拆清参考视频讲给谁、怎么让人停下、继续看、相信，哪些能学哪些不能照搬 | 学它的什么 |
| 三、生成内容 | `jc-jiaocheng-video` | 先和你定叙事，再写逐字稿（教程和观点口播两种），教程另规划画面，发布前轻量评审 | 叙事、开头结尾的方向、定稿 |
| | `jc-gongzuotai-write` | 把稿子做成「创作页」网页：左边参考原话，右边你的稿，AI 的修改建议贴在原句旁边，你改的字自动存回文件 | 每条建议采纳不采纳、标题封面文字简介选哪个 |
| | `jc-zhuanxie` | 音视频转文字，保留原始识别，只修确定的错字 | 拿不准的词 |
| | `jc-jianjie` | 写一段像你本人发的发布配文和标签 | 发哪一版 |
| | `jc-koubo-shuping` | 竖屏口播加字幕和动效：静态检样 → 样片 → 全片 | 三道样都要你说通过 |
| 四、发布 | `jc-publish-closeout` | 你发完说一声：建档、找到各平台的作品、在 12 小时和 7 天抓数据 | 作品认不准时确认，花钱超上限时点头 |
| 五、复盘 | `jc-media-review` | 拿数据、评论原话和对照视频写复盘，先给你看 | 复盘对不对、下一条改哪一项 |
| 迭代 | `jc-skill-writer` | 把复盘结论整理成判断库条目；反复成立的才提议改 Skill；也能写新 Skill、审 Skill | 每条记不记、Skill 改不改 |

**封面**不在这个仓库：用开源的创作工作台里的封面 Skill（`skills/jincheng-workbench-cover`），见 https://github.com/jincheng2026/jincheng-workbench 。创作页也用这个工作台的页面和保存服务，第一次用 `jc-gongzuotai-write` 时 AI 会自动装好。

### 越用越像你

Skill 里不带任何人的私人判断和口气。你的东西放在你自己的工作文件夹里：

- `写稿方法/07_我的判断库.md`：你同意过的写稿判断（遇到什么情况 → 你怎么判断、为什么、什么时候不适用）。每条内容定稿、每次复盘后，AI 整理几条给你过目，你同意的才记进去。
- `写稿方法/08_我的口气样本.md`：你满意的旧稿，和你亲手改过的句子（改前 → 改后）。AI 写第一版之前会读。

一开始都是空的也能用：各个 Skill 照自带的基本做法写，并告诉你一次。

### 工作文件夹

默认在 `~/Documents/jincheng-workbench/`，和创作工作台共用同一个，两边可以一起用。

| 放什么 | 在哪 |
| --- | --- |
| 选题总览和选题卡 | `选题库/` |
| 一条内容发出去之前的全部东西（参考拆解、工作稿、改稿日志、定稿、创作页） | `内容草稿/T001_选题名/` |
| 你的写稿方法、判断库、口气样本、反馈记录 | `写稿方法/` |
| 对标素材、对标账号、调研报告、导入的评论 | `市场调研/` |
| 发布后的档案（发布事实、平台链接、12 小时和 7 天数据、完整逐字稿、复盘） | `已发布/YYYY-MM-DD-标题/` |
| 不要了的文件 | `回收站/` |

都是普通的 Markdown 文件，不用注册账号，不上传你的数据。

### 要用到的第三方服务

按需配，用到时 AI 会告诉你去哪申请、怎么放进这台 Mac 的钥匙串（不用把 key 发进对话）：

| 服务 | 谁用 | 费用 |
| --- | --- | --- |
| [火山引擎豆包语音](https://console.volcengine.com/speech/app)「录音文件识别标准版 2.0」 | 转文字（jc-zhuanxie，以及入库、拆视频、建档时转逐字稿） | 按识别时长付费；没有 key 时可以装本机的 Qwen3-ASR 模型（只支持 Apple 芯片，约 6 GB，不花钱） |
| [TikHub](https://tikhub.io) | 调研采集、发布后抓数据和评论 | 按次付费，抖音一次约 0.001 美元，小红书约 0.01 美元；超过默认上限先问你 |

抖音、小红书的用户协议都限制自动抓取，用第三方数据服务的风险由使用者自己评估。

---

## 通用 Skill

和内容创作系列放在同一个仓库，按需装（安装时跟 AI 说「通用的也要」）。

| 类别 | Skill | 做什么 |
| --- | --- | --- |
| 思考 | `jc-clarifier` | 万能问题澄清器。漏斗追问 + BROK 格式化，输出可直接喂 AI 的提示词 |
| | `jc-ask-anything` | 提问打磨。识别 XY 问题、压缩问题、判断这事该问 AI 还是问人 |
| 规划 | `jc-plan` | AI 任务管家。自然语言记任务、智能排程、塞飞书日历、到点提醒 |
| | `jc-daily-planning` | 日规划助手。WOOP + 54% 心法 + 砍事原则，5-10 分钟产出当日可执行计划 |
| 学习 | `jc-learn-anything` | 通用学习加速器。采集 → 消化 → 检验三阶段，喂材料或只给主题名都能用 |
| 写作与公众号 | `jc-write` | AI 辅助原创写作。五层拆解 + 苏格拉底追问 + 个人文风 DNA |
| | `jc-wechat-publish` | Markdown 一键发公众号。扫图位 → Gemini 生图 → HTML 排版 → 草稿箱 |
| | `jc-zhuagongzhonghao` | 公众号热文抓取。dajiala + Wilson Score 评分，输出杂志风格 HTML 报告 |
| 项目基建 | `jc-handoff` | 会话交接打包。把当前会话压成下一段对话的启动文档 |
| | `jc-source-of-truth` | 项目级数据权威索引。告诉 AI 某个数据在哪份文件、以哪份为准 |

部分通用 Skill 需要 API key（例如 `jc-wechat-publish` 要 Gemini、imgbb、微信发布 API）：在对应 Skill 目录下 `cp config.example.yaml config.yaml` 再填，`config.yaml` 已在 `.gitignore` 里；也可以用环境变量。

---

## 手动安装

不想让 AI 代装，也可以用命令：

```bash
# 通用方式（Codex / Claude Code），会把仓库里的 Skill 复制进去
npx skills add jincheng2026/jcskill

# Claude Code 插件市场：内容创作系列一次装齐
claude plugin marketplace add jincheng2026/jcskill
claude plugin install jc-content@jincheng-skills
```

通用 Skill 可以单独装，比如 `claude plugin install jc-clarifier@jincheng-skills`。

更新：AI 代装的，把安装那句话再发一次；`npx` 装的重新运行同一条命令；插件市场装的运行 `claude plugin marketplace update jincheng-skills` 再 `claude plugin update jc-content@jincheng-skills`。

想改某个 Skill 的做法：优先把你的规矩写进 `写稿方法/07_我的判断库.md`（Skill 每次都会读）；确实要改 Skill 本身，复制一份、换个名字再改，这样以后更新不会冲突。

---

## License

MIT © 2026 何锦成（[@jincheng2026](https://github.com/jincheng2026)）。例外：`skills/jc-koubo-shuping` 是 CC BY-NC 4.0（商用需另外取得作者授权），见它目录里的 LICENSE；它用到的 Remotion 有自己的许可证。
