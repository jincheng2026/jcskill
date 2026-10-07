# 分 genre 范例索引（活读层）

> 用法：定下要写的 skill 属于哪个 genre 后，**现场去读对应范例的原文**，学它的判断逻辑和话术手感，不要凭本索引的摘要写。摘要管「去哪看、看什么」，手感在原文里。
> 去哪读范例原文：
> - dbskill 范例：先把仓库克隆到临时目录再读，例如 `git clone --depth 1 https://github.com/dontbesilent2025/dbskill /tmp/dbskill`。下表的 `dbskill/skills/...` 指克隆下来的这个文件夹。作者的 fork 在 https://github.com/jincheng2026/dbskill ，原仓库拿不到时用它。本索引的拆解基于 dbskill v2.14.2，之后的版本行数和细节可能变了，以原文为准。
> - jc 系列范例：在本仓库 https://github.com/jincheng2026/jcskill 的 `skills/` 下（例如 `skills/jc-clarifier/`）；装过的话也在本机 skills 文件夹里（Claude Code 是 `~/.claude/skills/`）。
> 一个 skill 可以跨 genre（如「澄清 + 状态管理」），把涉及的几类范例都读。

## genre 速判

先问两个问题定位：
1. 这个 skill 的主体是**对话**（问答推进）还是**流程**（步骤产出）还是**状态**（跨会话记忆）？
2. 它的判断力长什么形态——公理推导？公式匹配？特征检测？路由分发？

| Genre | 代表范例（读这个） | 去原文看什么 |
|-------|------------------|-------------|
| 路由型 | `dbskill/skills/dbs/SKILL.md` | 自我阉割开场（「你不做诊断，只做路由」）；意图信号表三列：用户原话 → 路由到 → 一句话说明；确认后一句话交接立即执行 |
| 澄清漏斗型 | `jcskill/skills/jc-clarifier/SKILL.md` | 行动锁（确认前禁产出 + 两次「直接做」才放行）；四轮漏斗（合并问→反向排除→显隐分离→镜像确认）；每问附猜测（「我猜是X，对吗」）；references 分文件存放并配读取时机表 |
| 诊断对话型 | `dbskill/skills/dbs-diagnosis/`、`dbs-goal/` | 逐题问（每问依赖上答）；消解漏斗逐层停顿；空转词现场测试（去掉该词句子还成立=空转）；拒绝权（三问全答不上→不硬产出）；终点是「放回生活验证」 |
| 状态管理型 | `dbskill/skills/dbs-save/`、`dbs-restore/`、`dbs-report/`、`dbs-decision/` | 路径 schema 与项目隔离（slug 取 basename $(pwd)）；frontmatter 六字段 + status 三态机；永不覆盖、追加修正；来源标签 `[本人]`/`[AI 推测]`；report 三条可信度基石（不凭空总结、永不覆盖、只搬运字段）；找不到存档的三级降级 |
| 工程脚手架型 | `dbskill/skills/dbs-content-system/`（篇幅长，带 docs/templates/scaffold/脚本） | 四档运行模式 + 硬升档闸门（可检验条件清单，少一条不升档）；「可用态」= 8 项可检查条件；scaffold 只建骨架不造内容；验收命令逐条可跑；.trash 回收站 |
| 跨端迁移型 | `dbskill/skills/dbs-agent-migration/` | 真源 + 薄 bridge 架构（bridge 文件 frontmatter 带 source_of_truth 路径）；候选发现模式（扫描生成清单等用户确认，不直接动）；平台专属字段单独立禁令（Grok 漏 user_invocable 用户就搜不到） |
| 人格模拟型 | `dbskill/skills/dbs-chatroom*/` | 人格三层定义（3 个思考方法 + 诚实规则 + 一句话说话风格）；选人规则=先判断话题缺什么视角；推荐前三条自检；多轮上下文保 3 轮全量、超出压缩 |
| 连续生成型 | `dbskill/skills/dbs-learning/` | 反馈→梯度表（没看懂→降抽象；懂但没意思→换切入；问应用→加案例）；状态容器文件 + 全局 INDEX；模板行与用户输入硬区分。注意它的缺陷：没定义完成态——你写时要补 |
| 公式库型 | `dbskill/skills/dbs-xhs-title/`（篇幅长） | 「你是公式匹配器，不是生成器」；触发器 × 公式连续编号，输出溯源公式号；跳过规则明示；大体量靠速查表 + 分章组织 |
| 检测型 | `dbskill/skills/dbs-ai-check/` | 只诊断不改的哲学；特征 × 三级严重度；按文本顺序报告（不按特征分类）每处引用原文；追问映射表替代直接改写；检测前先问体裁；自检递归（追问本身不得犯 22 个 AI 特征） |
| 问题工程型 | `dbskill/skills/dbs-good-question/` | 五项检查计分 0-10 → 三条处理路径；Agent 可解性 6 维 → 自动化 A/B/C/D 四档；低置信候选解释（信息不足时给带条件的部分答案：「如果它成立应该看到什么」） |

## 风格基准（与 genre 无关，所有产出对齐）

默认对齐 jc 系列风格（用户有自己的风格要求时以用户为准），读 `jcskill/skills/jc-clarifier/SKILL.md` 找手感：
- 简体中文，不用「您」；选项用 A/B/C/D 降回答成本
- ❌/✅ 正反对照写规则；「好的：…/差的：…」写示例
- 猜测大胆但标注「我猜的，你看对不对」
- 中文引号「」；不用 emoji 堆砌（流程标记 ✅❓🔴 除外）

## 架构对照速记

| 场景 | 架构 | 出处 |
|------|------|------|
| 只跑 Claude Code | 极简 SKILL.md 路由 + references/ 渐进披露 | jc 系列 |
| 跨平台分发（Codex/Cursor/Trae） | SKILL.md 自包含、内联案例，长就长 | dbskill（A3） |
| Claude Code + Codex 双端 | 真源放项目目录，两端 skills/ 只放薄指针 | dbs-agent-migration（A4） |
| skill 家族 ≥5 个 | 加一个自我阉割的路由入口 skill | dbs（A2） |
