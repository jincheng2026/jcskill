---
name: jc-media-research
description: 真实社媒研究：低粉爆款、账号基线、作品对照、演化分析、评论需求、选题判断与口播共创。给方向、链接、原稿或数据时使用。
---

# jc-media-research

用真实作品、账号、评论、逐字稿和本人材料，回答拍什么、为什么值得拍、学谁的什么、怎样写成自己的内容。重要判断保留可核对的来源。

## 默认行为

先读 [任务路由](references/routes-and-gates.md)，只执行本次需要的路径。已有数据能回答时先离线处理，不重复采集。给选题建议前读取已有定位、经历和素材；上下文已有的内容不重复问。

Agent 负责相关性、语义判断、问题聚类和写作；程序负责计算、来源校验、保存和渲染。不用关键词套写充当理解，不编造本人经历或结果。

用户已给明确需求时，完成已授权的工作再交付。计划、费用核对、自动选样、计算和验证在后台进行。只有以下真实阻塞才追问一次：

- required_input_missing：现有材料无法取得不可替代的输入。
- cost_limit_exceeded：同一任务累计将超过 120 次付费请求或 1.00 美元。
- execution_failed：鉴权失败、未知扣费、媒体不可读等问题需要用户采取动作。

3 条或 0 条合格样本都是可完整交付的结果，不降低门槛凑数，不要求用户再次选样或确认执行。

## 首次运行检查

安装首次使用或运行状态未知时先离线执行：

    python3 scripts/validate_and_package.py validate
    python3 scripts/tikhub_guard.py self-test
    python3 scripts/tikhub_guard.py credential-status

分别说明离线能力和凭据是否配置；需要转文字时，确认同仓库的 jc-zhuanxie 装好（和本 Skill 装在同一个地方），它自己会检查火山引擎的 key 和 ffmpeg。凭据已配置不证明端点权限可用；本地依赖齐全不证明媒体完整。不得让用户把 Key 发到聊天框或打印凭据。凭据设置和平台调用见 [报告与安全](references/reporting-and-security.md)。

## 工作目录与采集

任务目录默认建在工作文件夹的 `市场调研/调研报告/YYYY-MM-DD-主题/` 下（工作文件夹和创作工作台 jincheng-workbench 是同一个：按顺序找当前对话打开的文件夹或它往上几层里有 `内容草稿/` 或 `选题库/00_选题总览.md` 的、`~/Library/Application Support/jincheng-workbench/config.json` 的 `workFolder`、`~/Documents/jincheng-workbench/`；都没有就用同仓库总入口 jc 的建文件夹脚本 init_workfolder.py 建好），用户另指定位置时按用户的。任务目录使用 raw、normalized、transcript、reports、feedback 子目录。真实材料不进入 Skill。已有证据文件默认不覆盖；写稿页仅通过版本检查保存当前任务状态。

先从实时 OpenAPI 确认端点、参数与价格。所有付费请求经 scripts/tikhub_guard.py，同一任务始终使用同一份 raw/task-budget.jsonl。预算内由脚本生成与计划哈希绑定的自动授权，直接执行；超限才请求匹配批准。费用不明仍占预算，鉴权失败或超时扣费未知时停止相应采集，不盲目重试。

    python3 scripts/tikhub_guard.py auto-approve \
      --plan TASK/raw/plan.json \
      --budget-ledger TASK/raw/task-budget.jsonl \
      --out TASK/raw/approval.json

随后 run 继续携带同一 --budget-ledger。参数、游标或数量变化必须重新生成计划并累加，不能新建账本重置额度。

## 研究路径

| 路径 | 方法与产物 |
| --- | --- |
| 搜索与选题 | 按 [搜索和筛选](references/search-and-selection.md) 规范化、去重、硬筛选，交付真实候选与排除理由 |
| 账号自身基线 | 同平台、稳定账号 ID、内容类型和采集批次计算中位数与倍率，原始数值同时展示 |
| 高表现与普通作品 | 默认 1 条高表现、2 条接近中位数的普通作品，另有材料时最多 2 条同题其他作者 |
| 多对标演化链 | 按段落作用对齐，识别拆合段、调序、保留、增删、改写和案例替换 |
| 评论需求 | 保留评论层级和回复覆盖；引用真实问题，核对原视频与回复，产出有证据的内容机会 |
| 共同写稿 | 从真实任务起稿、参考改写或局部修改，保留来源、本人事实、批注、锁稿和历史 |

抖音 AI 教程保留原门槛：100–20,000 粉丝、至少 1,000 点赞、直接相关；近 90 天优先。相对基线不改写低粉爆款定义，不跨平台套门槛，不把当前粉丝数当发布时粉丝数。

    python3 scripts/prepare_research.py content INPUT --output TASK/normalized/content.json
    python3 scripts/research_decisions.py baselines --input TASK/normalized/content.json --output TASK/normalized/baselines.json
    python3 scripts/research_decisions.py select --input TASK/normalized/baselines.json --output TASK/normalized/selection.json
    python3 scripts/prepare_research.py comments INPUT --output TASK/normalized/comments.json

数据合同为 schema_version: 2，兼容读取旧版；旧版缺失的新增字段保持未知。具体字段、分析 JSON 和命令见 [数据合同](references/data-contract.md)。

## 先读真实内容，再作判断

优先可靠字幕或已复核逐字稿。缺少可靠字幕时，统一用同仓库的 `jc-zhuanxie` 转写（火山引擎豆包语音，失败时自动改用本机 Qwen3-ASR），本 Skill 不自带转写模型，也不换别的模型。jc-zhuanxie 验收通过后，把它的输出接进任务的 transcript 目录，再做就绪检查：

    python3 scripts/import_zhuanxie.py --source ZHUANXIE_OUTPUT --output TASK/transcript --media MEDIA
    python3 scripts/validate_transcript_ready.py --transcript-dir TASK/transcript --require text

文字结构分析要求 capabilities.text_structure。涉及前 5 秒、精确转折点或视频时间轴时改用 --require timing，要求已复核的句子或词级对齐；约 28 秒转写块不代表精确句子时间。短稿可用，局部疑问只限制相应判断。媒体校验可附 --media MEDIA。

按 [证据分析](references/evidence-analysis.md) 完成语义工作，输出观察、引用、其他解释和可测试改法。两条独立内容以上才支持重复规律；没有对照或实验数据不声称因果。演化顺序不证明作者之间借鉴关系。

    python3 scripts/research_decisions.py validate-analysis --input TASK/normalized/analysis.json --sources TASK/normalized/sources.json --output TASK/reports/analysis-validation.json
    python3 scripts/research_decisions.py questions --input TASK/normalized/comments.json --analysis TASK/normalized/question-analysis.json --sources TASK/normalized/sources.json --output TASK/normalized/questions.json

## 写稿与交付

按 [写稿与反馈](references/writing-and-feedback.md) 读取本人材料并起草。一条视频保留一个主要收获，完整稿先于过程说明；不能说的数字不用，非核心缺口标 [待补]。每段引用来源、借用逻辑、本人事实和表达变化。用户确认或锁定的文字保持原文。

通用页支持段落导航、来源筛选、语义颜色、连续字词重合、编辑、批注和导出。语义由 Agent 复核，重合不是原创性或效果评分。直接打开 HTML 时暂存到浏览器并可下载；服务模式写入独立任务目录：

    python3 scripts/research_decisions.py render-writing --input TASK/writing/state.json --output TASK/writing/writing.html
    python3 scripts/serve_workbench.py --task-dir TASK/writing --port 8767

保存版本冲突返回 409，并保留本地输入；改稿自动重算字词重合，相关语义标记待复核。批注、反馈和历史仅在任务内保存，不自动改全局记忆或规则。

主报告由 scripts/render_report.py 使用 assets/page-template.html 的样式与内联 ECharts，按任务生成图表。不能用数字卡片或长表替代应有图表；无数据的图位说明缺失，不造点。

    python3 scripts/render_report.py --input TASK/normalized/report.json --output TASK/reports/research_report.html
    python3 scripts/render_report_preview.py --input TASK/reports/research_report.html --output TASK/reports/research_report_preview.png
    python3 scripts/qa_page.py TASK/reports/research_report.html --outdir TASK/reports/qa

按 [报告与安全](references/reporting-and-security.md) 检查范围、时间、分母、图表与来源。必须逐屏目检并确认桌面和手机布局可用。最终回复先展示 PNG，再给 HTML 和证据路径；预览失败如实说明，不把文件存在当作视觉通过。

## 完成与公开分享

只检查本次涉及的内容，不追加无关采集。交付需满足：证据可追溯、计算可复算、推断与事实分开、本人事实有出处、锁稿保留、预算未越界、图表和页面验证通过。合格数量为零也直接交付。

    python3 -B -m unittest discover -s tests
    python3 scripts/validate_and_package.py validate
    python3 scripts/validate_and_package.py package --out PUBLIC.zip

公开 ZIP 仅含工具、说明、必要的 ECharts 及许可证、合成案例。真实评论、原始响应、本人资料、密钥、签名链接、本机路径、模型与缓存不得进入；扫描命中必须失败。解压包再次检查依赖和离线报告，不能仅验证源码目录。
