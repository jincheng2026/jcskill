# jcskill

锦成的 AI 工作流 Skills——10 个 Claude Code skill，覆盖思考、规划、学习、写作、发布、抓取。

**所有内容开放，可以整套装，也可以只拿一部分。**

---

## 如何安装

#### Claude Code

```bash
claude plugin marketplace add luozitianyuan/jcskill
claude plugin install jc-clarifier@jincheng-skills
```

把 `jc-clarifier` 换成下面任一 Skill 名即可单独安装。也可以一次装多个：

```bash
claude plugin install jc-clarifier@jincheng-skills
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

重新运行一次同样的命令即可。

```bash
npx skills add luozitianyuan/jcskill
```

---

## 工具箱

### 思考类

| Skill | 做什么 |
|---|---|
| `jc-clarifier` | 万能问题澄清器。把模糊需求转成清晰提示词。BROK 框架 + 澄清漏斗 |
| `jc-ask-anything` | 提问打磨。识别 XY 问题、压缩问题、判断该问 AI 还是问人 |

### 规划类

| Skill | 做什么 |
|---|---|
| `jc-plan` | AI 任务管家。自然语言记任务、排程、塞飞书日历、到点提醒 |
| `jc-daily-planning` | 日规划助手。WOOP + 54% 心法 + 砍事原则，5-10 分钟产出当日可执行计划 |

### 项目类

| Skill | 做什么 |
|---|---|
| `jc-handoff` | 把当前会话打包成下次开新会话的启动文档 |
| `jc-source-of-truth` | 项目级 SOURCE_OF_TRUTH.md 数据权威索引管理 |

### 学习与写作

| Skill | 做什么 |
|---|---|
| `jc-learn-anything` | 通用学习加速器。三阶段（采集 / 消化 / 检验）学透任何领域 |
| `jc-write` | AI 辅助原创写作。栋哥五层拆解 + 苏格拉底追问 + 个人文风 DNA |

### 内容发布

| Skill | 做什么 |
|---|---|
| `jc-wechat-publish` | Markdown 一键发公众号。扫图位 → Gemini 生图 → 黄叔风格 HTML → 公众号草稿 |
| `jc-zhuagongzhonghao` | 抓公众号热文。dajiala API + Wilson Score，输出杂志风格 HTML 报告 |

---

## 配置

某些 Skill 需要 API key（例如 `jc-wechat-publish` 需要 Gemini / imgbb / 微信发布 API）。在对应 Skill 目录下：

```bash
cp config.example.yaml config.yaml
# 然后填入自己的 API key
```

`config.yaml` 已在 `.gitignore` 中，不会被误提交。

---

## License

MIT © 2026 何锦成
