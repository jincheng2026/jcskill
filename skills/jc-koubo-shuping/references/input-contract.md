# Input Contract

## v0 Supported

- Vertical talking-head mp4.
- 9:16 canvas or source that is already intended for 9:16 publish.
- SDR video.
- Stable duration and readable frame count from `ffprobe -count_frames`.
- Exactly one audio track and tagged SDR BT.709 limited-range color metadata.
- Existing `.srt` subtitle file.
- No retiming, trimming, denoise, stabilization, or multi-track audio edits.

## Subtitle Review

- Keep the received SRT as an immutable source copy.
- Save corrections as a separate revised SRT and emit a structured diff.
- Check typos, proper nouns, punctuation, sentence boundaries, overlaps, and end-of-video drift.
- Correct explicit mistakes such as homophone substitutions; do not rewrite the speaker's meaning or tone.
- When cue times overlap, preserve transcript text and clamp display timing in the Remotion layer so only one follow-read caption is visible.
- Before motion-map compilation, split long received cues into semantic single-line caption units. Preserve every source word and the source cue's total frame range; record the split plan, highlight tokens, and generated single-line SRT.

## Stop Or Normalize First

Stop before rendering when input is:

- HDR, Dolby Vision, or unclear color metadata.
- VFR that cannot produce reliable frame counts.
- Missing srt.
- Not vertical talking-head.
- Screen recording or horizontal explainer.
- Source where face/safe zones are unknown and must be manually redesigned.

## Case Layout

Use a dedicated case folder:

```text
case/
  case_manifest.json
  source/
  remotion_overlay_frames/
  remotion_bundle/
  output/
  qa/
  reports/
  planning/
  pilot/
```

Do not write next to the user's original source video except when the user explicitly requests it.
