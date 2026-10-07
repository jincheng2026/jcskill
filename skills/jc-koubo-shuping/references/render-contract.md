# Render Contract

Read `preserve-source-quality.md` before rendering.

## Render Boundary

Remotion renders only transparent overlay PNG frames. The source video never enters the Remotion composition for final delivery.

```text
remotion_overlay_frames/element-0000.png
remotion_overlay_frames/element-0001.png
...
```

Overlay requirements:

- exact target fps;
- exact source/target video frame count;
- native final output dimensions;
- RGBA alpha;
- stable contiguous numbering from frame 0.

Fast Preview 例外只针对证据形态：允许用同一缓存 bundle 渲染 4–6 个离散 Remotion still，并以最高 1080 宽和源片合成检样；它不是最终 overlay，也不得进入发布合成。bundle cache key 必须绑定模板源码与 package lock。

## Fixed Composite Route

1. Scale the source only when the quality profile explicitly requires it; use `zscale + spline36`.
2. Composite the native-size overlay onto the source into a high-quality video-only intermediate.
3. Remux the complete source audio into the video-only intermediate with stream copy.
4. Do not use `-shortest`.
5. Preserve BT.709 and `yuv420p` delivery metadata.

Default quality master:

```text
libx264 + preset slow + CRF 8 + High profile + yuv420p + BT.709 + tv range
```

Explicit accelerated long-form alternative:

```text
h264_videotoolbox + 45 Mbps + High profile + yuv420p + BT.709
```

The accelerated path does not relax preserve-source, native overlay, frame-count, audio-copy, or remux requirements.

## Required Manifest Evidence

```json
{
  "visualRenderer": "Remotion",
  "compositor": "ffmpeg",
  "sourcePreservation": {"base": "original", "sourceInRemotion": false},
  "overlayFrames": {"expectedCount": 120, "width": 1080, "height": 1920, "hasAlpha": true},
  "qualityProfile": {"name": "1080p_native_overlay_h264_crf8"},
  "composite": {
    "usedShortest": false,
    "audioPolicy": "copy_original_packets",
    "videoOnlyIntermediate": "output/final.video-only.mp4",
    "renderEvidence": "qa/render-evidence.json",
    "videoArgs": ["-y", "-i", "..."],
    "remuxArgs": ["-y", "-i", "..."]
  }
}
```

## Forbidden

- Remotion full-video rerender as final output.
- Low-bitrate proxy as the base layer.
- Stretched low-resolution overlay.
- `-shortest`.
- Audio re-encode when timing is unchanged.
- Pillow, Python, or ffmpeg-only visual fallback as final delivery.
