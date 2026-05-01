# jcskill

锦成的 AI 工作流工具箱。从两年深度使用 Claude Code 的实战中提炼，做成 10 个 jc-* skill。

**最新版本：v1.0.0**

**所有 Skill 开放，可以整套装，也可以只拿一个。**

---

## 如何安装

#### Claude Code

```bash
claude plugin marketplace add luozitianyuan/jcskill
claude plugin install jc-clarifier@jincheng-skills
```

把 `jc-clarifier` 换成下面任一 Skill 名即可单独安装。也可以一次装多个：

```bash
claude plugin install jc-write@jincheng-skills
claude plugin install jc-wechat-publish@jincheng-skills
```

#### 通用安装方式（适用于 Codex / Claude Code）

```bash
npx skills add luozitianyuan/jcskill
```

## 如何更新

#### Claude Code 插件市场安装的用户

```bash
claude plugin marketplace update jincheng-skills
claude plugin update jc-clarifier@jincheng-skills
/reload-plugins
```

#### 通过 `npx skills add` 安装的用户

重新运行一次同样的命令即可。安装和更新用的是同一条命令，不需要换成别的写法。

```bash
npx skills add luozitianyuan/jcskill
```

---

## 工具箱

### 思考类（想清楚再动手）

| Skill | 做什么 |
|---|---|
| `/jc-clarifier` | 万能问题澄清器。漏斗追问 + BROK 格式化，输出可直接喂 AI 的提示词 |
| `/jc-ask-anything` | 提问打磨。识别 XY 问题、压缩问题、判断这事该问 AI 还是问人 |

### 规划类（每天该做什么、随手记什么）

| Skill | 做什么 |
|---|---|
| `/jc-plan` | AI 任务管家。自然语言记任务、智能排程、塞飞书日历、到点提醒 |
| `/jc-daily-planning` | 日规划助手。WOOP + 54% 心法 + 砍事原则，5-10 分钟产出当日可执行计划 |

### 学习类（学透一个新领域）

| Skill | 做什么 |
|---|---|
| `/jc-learn-anything` | 通用学习加速器。采集 → 消化 → 检验三阶段，喂材料 / 只给主题名都能用 |

### 内容创作（从找角度到发出去）

| Skill | 做什么 |
|---|---|
| `/jc-write` | AI 辅助原创写作。栋哥五层拆解 + 苏格拉底追问 + 个人文风 DNA，写出只有你能写的版本 |
| `/jc-wechat-publish` | Markdown 一键发公众号。扫图位 → Gemini 生图 → 黄叔风格 HTML → 草稿箱 |
| `/jc-zhuagongzhonghao` | 公众号热文抓取。dajiala + Wilson Score 评分，输出杂志风格 HTML 报告 |

### 工作台基建（横跨所有项目）

| Skill | 做什么 |
|---|---|
| `/jc-handoff` | 会话交接打包。把当前 Claude Code 会话压成下一段对话的启动文档 |
| `/jc-source-of-truth` | 项目级数据权威索引。告诉 AI 和你自己『某个数据在哪份文件、以哪份为准』 |

---

## 工具路径图

#### 主线一：从模糊想法到一篇发出去的文章

```text
想清楚 → /jc-clarifier 或 /jc-ask-anything
   ↓
找角度 + 起草 → /jc-write
   ↓
生图 + 排版 + 发公众号 → /jc-wechat-publish
```

#### 主线二：今天该做什么

```text
随口记事 → /jc-plan（任意时刻）
   ↓
当天聚焦 → /jc-daily-planning（每天早上 5-10 分钟）
```

#### 主线三：学一个新东西

```text
喂材料 / 给主题 → /jc-learn-anything
   ↓
学完之后想写 → /jc-write
```

#### 横向工具（任何阶段都能用）

```text
找选题素材 → /jc-zhuagongzhonghao（看大盘哪些选题在跑）
会话窗口快满了 / 换设备 / 换模型 → /jc-handoff（打包上下文）
项目里数据散落、AI 找不到 → /jc-source-of-truth（建权威索引）
```

#### Skill 之间的自动推荐

- `/jc-clarifier` 想清楚之后要写文章 → 推荐 `/jc-write`
- `/jc-write` 写完之后要发出去 → 推荐 `/jc-wechat-publish`
- `/jc-write` 缺选题灵感 → 推荐 `/jc-zhuagongzhonghao`
- `/jc-learn-anything` 学完想沉淀成原创 → 推荐 `/jc-write`
- 任何对话快达到上下文上限 → 推荐 `/jc-handoff`
- 用户随口记事但没规划 → 推荐 `/jc-plan`；早上没规划当天 → 推荐 `/jc-daily-planning`

---

## 配置

部分 Skill 需要 API key。每个 Skill 自带 `config.example.yaml`：

```bash
cd skills/jc-wechat-publish
cp config.example.yaml config.yaml
# 然后填入自己的 API key（Gemini / imgbb / limyai 微信发布）
```

`config.yaml` 已在 `.gitignore` 中，不会被误提交。

也可以用环境变量代替（推荐，密钥不落盘到项目目录）：

```bash
export GEMINI_API_KEY="..."
export IMGBB_API_KEY="..."
export WECHAT_API_KEY="..."
```

---

## License

MIT © 2026 何锦成（[@luozitianyuan](https://github.com/luozitianyuan)）
