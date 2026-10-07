# Error Bank Contract

## Purpose

错题集不是复盘文章，而是让下一次执行自动避错的回归真源。机器数据位于 `evals/error-cases.json`。

## When To Add

同一轮必须新增或更新错题，当出现以下任一情况：

- 用户指出错误、风格漂移或位置不对。
- QA 发现返工项。
- 技术链失败、画质链偏离或交付状态误报。
- 旧错误以新形式再次发生。

## Required Fields

每题至少包含：

- `id`：稳定编号。
- `category`：subtitle、workflow、layout、style、render、quality、audio、release。
- `symptom`：用户或 QA 看见了什么。
- `rootCause`：为什么发生。
- `prevention`：下一次执行前必须做什么。
- `detection`：如何确定没有复发。
- `evidence`：真实案例或规则来源。
- `regression`：可执行或可核查的回归断言。
- `testId`：映射到 `scripts/regression-suite.mjs` 的实际测试；没有注册测试不得通过。
- `status`：`active` 或 `retired`。

## Update Rules

- 按根因去重，不按表面症状堆重复题。
- 用户原话可短摘录，但不保存敏感内容。
- 修复不能只写「注意」；必须落成流程门、脚本断言或明确证据检查。
- 只有替代规则和回归测试均存在时，才能把旧题标为 `retired`。
- 每次重要成片结束前运行 `node scripts/validate-error-bank.mjs`。
- 多 MG 项目还必须检查 KBE-027 的布局预算与 KBE-028 的语义变体选择；只有组件数量增加、没有语义路由和回归断言，不算修复。

## Use Before Editing

开始一个新 case 时，至少筛选与当前输入匹配的 active 错题：

- 有 SRT：subtitle 类。
- 有顶部进度与语义卡：layout、style 类。
- 全片交付：render、quality、audio、release 类。

当前 full render 要求全部 active 错题均在 `errorBank.applied`，并要求 `regressionReport` 显示每个 active ID 实测通过；不是只检查 JSON 外形。
