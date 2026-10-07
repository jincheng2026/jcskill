# Preserve-Source Quality Contract

## Fixed Route

画质保护依靠固定工艺，不依靠成片后主观补救：

1. 原视频或有证据的高质量中间片作为唯一底层。
2. Remotion 只渲染 RGBA 透明 overlay PNG 序列。
3. overlay 的 fps、帧数和最终分辨率必须原生匹配目标，不拉伸低分辨率 overlay。
4. ffmpeg 只把 overlay 合成到底层，并复制未改时序的原音频。
5. 禁止 `-shortest`。
6. 长视频先生成 video-only，再无损 remux 完整源音频，避免编码停止时截掉最后 AAC packet。

## Resolution Profiles

### 源片低于 1080×1920

- 用 `zscale + spline36` 放大到底宽 1080 的等比例竖屏尺寸。
- Remotion 直接按目标尺寸渲染 overlay，例如 720×1280 源片使用 `scale=1.5` 输出 1080×1920 overlay。
- 默认母版：H.264 `libx264 -preset slow -crf 8`。
- 当前固定母版不允许在 manifest 中覆盖 CRF、preset 或缩放算法；体积优化必须作为新的、独立验证过的 profile 另行加入。

### 源片为 1080×1920

- 不缩放底层，Remotion 原生渲染 1080×1920 overlay。
- 默认仍用 `libx264 slow CRF 8` 质量母版。
- 长片确需硬件加速时，可显式改用 `h264_videotoolbox 45M High`；必须保持同一 preserve-source、video-only、audio remux、BT.709 和完整帧数合同。

## Forbidden Routes

- 把源视频放进 Remotion 作为背景重新编码。
- 使用低码率代理或预览片作为最终底层。
- 先渲 720p overlay 再整体拉伸到 1080p。
- 用低码率 H.264 覆盖高质量 HEVC 源片。
- 为对齐音视频使用 `-shortest`。
- 未经授权加入全局压暗、重度调色、磨皮或降噪。

## Terminal Proof

终检只证明固定工艺没有被破坏：

- Remotion overlay provenance 与 RGBA。
- 源片或高质量中间片路径。
- overlay 与最终片的原生尺寸、fps 和帧数。
- `usedShortest=false`。
- 原音频 packet hash 一致。
- BT.709、完整解码、SHA-256。
- 结构化 render evidence 与最终 SHA 能证明 scale、编码、video-only 和 remux 策略；终检同时核对当前合成脚本哈希。
