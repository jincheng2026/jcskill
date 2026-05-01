---
name: jc-handoff
description: >
  Generate a structured handoff package for starting a new Claude Code session.
  Extracts tasks, progress, decisions, rejected approaches, file changes, and
  implicit preferences from the current conversation into a copy-paste-ready
  startup document. Use when user says: /handoff, handoff, session handoff,
  pack context, migrate session, new session, or in Chinese: 打包上下文, 交接,
  迁移会话, 开新会话, 会话交接.
---

# Session Handoff

Generate a startup package for a new Claude Code session — not a summary, but a handoff document that lets the next session pick up and execute immediately.

## Trigger Disambiguation

If the trigger keyword appears in a discussion context (e.g. discussing work handoff processes) rather than as an instruction, confirm first: "你是要做会话交接，还是在讨论交接这个话题？"

## Options

- `--quick` or "直接生成" or "不用确认": Skip the confirmation step, generate directly.
- "只打包关于 XX 的部分": Extract only information related to XX.
- "重点是 XX": Prioritize XX in the output.

## Process

### Step 1: Extract Six Layers

Scan the current conversation and extract information across six layers. For detailed extraction rules, read [references/extraction-rules.md](references/extraction-rules.md).

| Layer | What | Required? |
|-------|------|-----------|
| Task | What this session is trying to accomplish (goal, not process) | **Yes** — abort if missing |
| Status | What's done, what's not, what's blocked | **Yes** — abort if missing |
| Decisions | Key decisions made and why | No — skip if none |
| Rejections | Approaches tried and rejected, with reasons | No — skip if none |
| Files | File paths read/written/modified in this session | No — skip if none |
| Intent | Implicit preferences, constraints, style requirements | No — skip if no clear signal |

**Abort rule**: If both Task and Status layers cannot be extracted, do NOT generate an empty package. Instead respond: "当前会话内容较少，建议直接在新会话重新描述你的需求，不需要交接。"

### Step 2: Identify Session Type

Determine the session type to adjust output emphasis. For detailed type definitions, read [references/session-types.md](references/session-types.md).

Types: Coding/Technical | Course Design | Content Creation | Strategy/Planning | Knowledge Management | Mixed

> Knowledge Management = 知识库录入、对标研究、思想画像、wiki 整理等需要带"已建立的知识资产/核心洞察/调用关系"的场景。这类会话上下文密度极高，模板和长度都需要扩展（详见 Step 3 与 Constraints）。

### Step 2.5: Extraction Confirmation (skippable)

Unless `--quick` or equivalent is specified, output a brief extraction summary before generating:

```
我提取到的信息：
- 🎯 任务：[one line]
- 📍 状态：[one line]
- ✅ 决策：[N items] / 无
- ❌ 否决：[N items] / 无
- 📁 文件：[N files] / 无
- 💡 意图：[one line] / 无明显信号

类型判定：[type]

确认无误我就生成启动包，或者告诉我要调整哪里。
```

Wait for user confirmation before proceeding.

### Step 3: Generate Startup Package

Output a structured Markdown block. **Dynamic trimming**: sections with no content are omitted entirely (no empty headings).

```markdown
# 会话交接启动包

## 你需要知道的背景
[1-3 sentences: who I am, what project, current phase]

## 这次会话做了什么
- ✅ [completed item]
- 🔲 [incomplete item, with reason]

## 关键决策（不要推翻，除非我明确说要改）
- [decision]: [reason]

## 踩过的坑（不要再试）
- ❌ [approach]: [failure reason]

## 相关文件
- `path/to/file` — [what it is, current state]

## 已建立的知识资产（Knowledge Management / Strategy / Course Design 类必出，其他类按需）
- [资产名]: `位置` — [核心价值 / 什么时候该调用它]

## 核心洞察（不要重新发现）
- [洞察一句话]: [来源 / 为什么这么判断]
> 这一区是为了避免新会话从零做认知工作。把已经想清楚的结论放这里。

## 触发→引用关系（以后我问什么时该调用什么）
- 当我问 [X 类问题] → 从 [Y 资产] 抽 [Z 角度]
> 这一区让新会话知道"什么时候用什么"，把静态资产变成可调用工具。

## 我的偏好和约束
- [preference/constraint]
> 以上偏好是我从对话中推断的，如有偏差请纠正

## 下一步该做什么
1. [specific next action, not "continue working"]

## 不要做什么（这次会话明确反对的方向）
- ❌ [不要做的事]: [为什么]

---
📋 使用方式：复制以上全部内容，粘贴到新会话的第一条消息
```

**模板裁剪规则**：
- Coding/Technical 类：可只用基础 6 区（背景/做了什么/决策/坑/文件/偏好/下一步），后 3 区（已建立的知识资产/核心洞察/触发引用）通常不需要
- Knowledge Management / Strategy / Course Design / Content Creation 类：**必须**写后 3 区，否则启动包对新会话毫无杠杆
- 「不要做什么」是 Rejections 的强化版，所有类型都建议保留

### Step 4: Project Memory Sync (optional)

If a project-level CLAUDE.md is detected in the current directory, ask: "要同时更新项目日志/全景档案吗？"

## Constraints

- **Length policy** (信息密度优先，不为字数砍掉关键上下文)：长度按会话类型分级
  - Coding/Technical: ≤ 800 字（小上下文足够）
  - Course Design / Content Creation: ≤ 1500 字
  - Strategy/Planning: ≤ 2500 字
  - **Knowledge Management / Research: ≤ 3500 字**（涉及大量已建立资产的引用）
  - Mixed: 取适用类型中较大者
  - 如果该会话沉淀了大量"以后会被反复调用"的资产，宁可超字数也要写完。新会话拿不到关键上下文 = handoff 失败。
- **File paths must be specific**: Write `src/config/auth.ts`, not "the config file".
- **Intent layer must be labeled**: Always mark as inferred with source evidence.
- **Sensitive data**: Auto-redact patterns matching API keys, tokens, passwords, secrets, .env values, connection strings. Replace with `[已脱敏]`.
- **Compacted sessions**: If the session has been compacted, prepend: "⚠️ 本次会话已被压缩，以下信息可能不完整". Supplement from file system where possible.
- **No duplication with CLAUDE.md**: Rules already in CLAUDE.md are not included in the package.
- **Action-oriented**: Every line serves the next session's ability to execute, not to record history.
- **Rejections > Completions**: Prioritize "don't do X" over "already did Y" — preventing repeated mistakes is more valuable.
