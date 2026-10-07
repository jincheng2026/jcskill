# Fast Preview

## 目标

在用户投入正式制作成本前尽快交付可判断的视觉样本。目标值不是发布承诺：暖缓存 5–8 分钟，冷启动不超过 12 分钟；实测数据优先。

## 前置条件

- 输入视频、SRT 和 take 已锁定。
- 字幕完成最小校对和单行语义拆分，motion map 已编译，workflow 为 `motion_map_ready`。
- `visualStyleId` 必须在创建 case 前确定，并绑定 `assembly-mono` 或 `google-semantic` 各自的已批准 baseline；不得静默回退到旧的单一默认 baseline。

## 执行

1. 默认只用一个写入 Agent，不在第一次检样前派多 Agent 做语义复核和审美 QA。
2. 运行 `node scripts/run-fast-preview.mjs /abs/case/case_manifest.json`。
3. 脚本执行中英双语单行预检、runtime 增量刷新、bundle 指纹缓存、4–6 个离散 Remotion still、源帧合成、总览和顶部安全区联系表。
4. 第一次出现 P1 时最多自动修一次；第 2 次渲染后无论是否仍有 P2/P3，都停止并输出 `WAIT_USER`。
5. 只向用户展示联系表、P0/P1 结果和 P2 Warning。默认不做双模型 ASR，也不先做动态样片、4K 全片、最终 manifest 或多轮独立审核。

## 极简证据

每次 attempt 必须保留 `preview-manifest.json`，至少绑定输入 SHA、字幕 SHA、baseline lock、motion map SHA、template cache key、时间点、联系表、cycle 和 attempt 计数。Repair 开新 cycle，旧 attempt 不覆盖。

## 停止条件

- P0：错素材、黑屏、渲染失败、字幕内容确认错误，阻断并修复。
- P1：中英文任一缺失、不是单行、溢出、底板样式漂移或挡脸，最多自动修一次。
- P2：卡片大小、动效强弱、颜色偏好，展示给用户。
- P3：「还能更高级」等主观想法，不自动返工。
