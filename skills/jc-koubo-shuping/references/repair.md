# Repair

## 路由

先运行：

```text
node scripts/repair-case.mjs /abs/case/case_manifest.json --target caption|copy|layout|motion|source
```

确认计划后加 `--apply` 写入 case。脚本开启新的 repair cycle 和独立的 2 次检样预算，只登记依赖失效，不删除旧证据或覆盖旧 cycle。

- `caption`：重跑字幕预检、overlay、合成和字幕 QA。
- `copy`：重编 motion map，再跑字幕预检、overlay、合成和视觉 QA。
- `layout`：只重跑 overlay、合成和布局 QA。
- `motion`：重编 motion map，再跑 overlay、合成和动画 QA。
- `source`：新建 case；不得在旧 case 内偷换素材。

所有修复产物写入新的 attempt 目录。没有变化的 source probe、字幕、motion map、baseline 或 bundle 必须复用对应指纹缓存。

`repair` 必须继承 `case_manifest.json.visualStyleId`，不得因为改字幕、间距或动效而切换视觉风格。用户明确要求换风格时，新建同源 case 并记录新的 `visualStyleId`；新 case 重新走静态关键帧、样片和全片闸门。
