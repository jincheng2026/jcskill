# Changelog

## 0.8.0-candidate - 2026-07-26

- Dual-style system: promote `assembly-mono`（黑白 Assembly）and `google-semantic`（Google 语义配色）as the only canonical vertical talking-head styles.
- Routing: add stable aliases and a one-question pre-case gate; explicit user choices execute directly, while missing or ambiguous choices stop before case creation.
- Manifest contract: require `visualStyleId` and bind each style to exactly one approved baseline; repair inherits the current style and switching style requires a new same-source case.
- Assembly baseline: lock the user-published 0726-01 full video, SHA-256, typography, monochrome palette, open MG geometry, progress grammar, local feathered contrast and preserve-source boundaries.
- Renderer: add an executable `AssemblyMonoHero` route for all nine semantic variants while retaining the existing Google semantic `MgHero` route.
- Typography: bundle Noto Sans SC, Inter and Archivo Black for the Assembly route.
- Fast Preview: remove the stale single-baseline default and require the selected style's bound baseline before preview.
- Regression: add KBE-030 and KBE-031 for style selection/baseline binding and renderer/palette separation.

## 0.7.2-candidate - 2026-07-26

- Correction: the user's request was to reduce progress nodes, not replace the approved all-label grammar with a current-only chapter label.
- Rendering: keep all 3–5 macro chapter labels visible, highlight the current chapter, brighten completed chapters and mute future chapters.
- Boundary: internal semantic beat labels remain forbidden in progress chrome.
- Regression: update KBE-025 and KBE-029 so a current-only label treatment fails alongside beat-level label dumping.

## 0.7.1-candidate - 2026-07-26

- Progress hierarchy: stop rendering every semantic beat as a visible progress label; internal beats remain MG and QA units only.
- Default chrome: use one continuous whole-video rail with no text when no explicit chapter plan exists.
- Optional chapters: accept only 3–5 contiguous macro chapters covering the full duration, and display only the current chapter plus `current/total`.
- Validation: add workflow checks for chapter count, coverage, continuity, uniqueness and label length.
- Error bank: add KBE-029 from the real 0726-01 full-video feedback and register an executable regression preventing `node.label` from returning to progress chrome.

## 0.7.0-candidate - 2026-07-25

- Multi-MG system: replace the single-card-only renderer with nine semantic variants covering chapter titles, reversals, lists, prompt/fact cards, dual relations, bookmark relations, agent flows and numeric conclusions while retaining `semantic_card` as the backward-compatible default.
- Semantic compiler: add `mg_copy.variant` plus structured `payload` validation so component choice follows the information relationship instead of random visual rotation.
- Layout safety: introduce `mg-layout.json` as the shared renderer/validator budget; enforce border-box sizing, upper safe-zone bounds, prompt bottom padding, 116 px relation panels, an independent bookmark footer and a 234 px numeric-result card verified after the first smoke exposed result-row clipping and insufficient bottom clearance.
- Baseline: promote `0721-approved-baseline-v4-multi-mg`, inheriting the approved Google-color progress and v3 single-line bilingual caption system.
- Error bank: add KBE-027 for fixed-height card/footer overflow and KBE-028 for single-card semantic flattening.
- Audio boundary: keep source speech stream-copy as the production default; this release records `sound_cue` intent but does not import the experiment's mixed-audio implementation.
- Evidence: use the accepted `0721-01-skill-multimg-experiment` attempt 03 and its spacing/bookmark contact sheets as the real-sample basis.

## 0.6.3-candidate - 2026-07-21

- Repeat render safety: rebuild the managed Remotion bundle directory before pilot/full renders so stale `public` symlinks cannot trigger `EEXIST`.
- Regression: add KBE-026 from the 0721-03 pilot rerender failure.

## 0.6.2-candidate - 2026-07-21

- Transition visibility: semantic cards are visible from the exact first frame of each beat while retaining the subtle position/scale entrance; node, caption and progress switching now share the same integer-frame rounding.
- Progress sync: the active progress label switches on the exact beat boundary instead of waiting for non-zero local progress.
- Regression: add KBE-025 from the 0721-03 dynamic pilot boundary contact sheet.

## 0.6.1-candidate - 2026-07-21

- Font texture: replace inherited Noto Sans SC/medium-weight caption rendering with explicit PingFang SC 300 for Chinese and Helvetica Neue 300 for English.
- Plates: reduce opacity, remove visible borders, and soften shadows to match the supplied interview-caption references more closely.
- Human approval: promote cycle 3 attempt 1 to the default accepted caption baseline; future cases inherit v3 instead of the older v2 subtitle style.
- Regression: add KBE-024 so structurally correct but visually heavy caption fonts cannot silently return.
- Verification: actual 0721-03 cycle 3 render, Fast Preview smoke, full preserve-source smoke, Skill validators, TypeScript and 24/24 active regressions pass; all host bridges resolve to the shared truth.

## 0.6.0-candidate - 2026-07-21

- Caption contract: replace the incorrect two-line default with semantic single-line Chinese cues; any unsplit overflow now blocks before render.
- Bilingual style: require a concise English translation for every cue and render Chinese and English on separate content-width translucent black rounded plates with white medium-weight text, no thick stroke, no forced lowercase, no yellow highlights.
- Planning: add `compile-caption-plan.mjs` to preserve source words while allocating semantic short cues inside each source cue's integer-frame range and updating existing motion-map cue bindings.
- Baseline: add `0708-0721-approved-baseline-v3-single-line`, incorporating the user's two subtitle reference images and superseding v2 for new cases.
- Regression: update KBE-018 and KBE-022, add KBE-023 for bilingual plate style and missing translation drift.
- Verification: quick validate, meta validation, resource boundary (950/1000 initial-load tokens), JavaScript syntax, Remotion TypeScript, Fast Preview smoke, full preserve-source smoke and 23/23 active regressions all pass; Claude/Codex/NewMax bridges resolve to the shared truth with matching `SKILL.md` SHA-256.

## 0.5.1-candidate - 2026-07-21

- Captions: prevent deterministic two-line layout from breaking continuous ASCII tokens such as `Vibe`, `Coding`, `GitHub`, and `handoff.md` across lines.
- QA: expose `splitAsciiToken` in caption preflight and treat any unresolved token split as P1.
- Regression: add KBE-022 from the real `0721-03` first preview; mixed Chinese-English caption fixtures must keep every ASCII token on one line.

## 0.5.0-candidate - 2026-07-21

- Product modes: route one Skill into `fast_preview`, `production`, and `repair`; preserve the strict production release gates while moving expensive evidence and review work after human preview approval.
- Fast Preview: add one-command runtime refresh, deterministic caption preflight, 4–6 sparse Remotion stills, source-frame composites, contact sheets, minimal provenance, and immutable attempt directories.
- Cost controls: default to one writer before first preview; cap Fast Preview at two renders and one auto-fix; P2/P3 feedback never triggers autonomous rerender; ASR is conditional and snippet-scoped.
- Cache: fingerprint template source plus package lock, reuse the Remotion bundle across cases and attempts, keep one browser session for sparse still rendering, and retain bundle caching for full overlay repair.
- Captions: replace browser auto-wrap with deterministic one/two-line balancing and a shared preflight model; block overflow and orphan lines before render.
- Baseline: freeze the human-approved 0708/0715/0721 geometry as `0708-0721-approved-baseline-v2` with a machine-readable lock.
- Repair: add dependency-specific repair planning for caption, copy, layout, motion, and source changes; every repair opens a new cycle with an independent preview budget and never deletes or overwrites previous attempts.
- Regression: add KBE-018 through KBE-021 for orphan captions, iteration budgets, bundle caching, and premature multi-Agent/ASR work; 21/21 active cases pass.
- Verification: final sparse-preview smoke rendered three four-frame attempts across two cycles in 7.99 seconds after fixture setup, reused the bundle, blocked cycle 1 attempt 3, and opened an independent repair budget; full 180-frame Remotion/preserve-source smoke, exact audio packet hash, release gate, and 8/8 adversarial checks all pass.

## 0.4.1-candidate - 2026-07-18

- Schema: canonical workflow, render, composite and final gates now require schema v3; add an explicit backup-first migration command for legacy cases.
- Evidence: source beats partition subtitle cues; compiler derives timing, timecode and spoken-line evidence instead of trusting authored values.
- Semantics: require a whole-video argument map and per-beat argument/boundary mapping before MG compilation.
- Quality gates: split deterministic hard failures from explainable risk warnings; add Unicode normalization, zero-width removal, meaningful-text checks, all-position ASCII-token checks and legitimate single-letter handling.
- Provenance: bind source map, compiled map, compiler and semantic-core hashes; nodes must exactly match the compiled map.
- Regression: replace the prior overlong-beat proxy with schema downgrade, placeholder, punctuation, Unicode repetition, equal-duration risk, mid-sentence truncation, legitimate Plan A and drift attacks.
- Measurement: add an explicit workflow timing recorder so quality improvements can be evaluated against total editing time.

## 0.4.0-candidate - 2026-07-18

- Semantic quality: make motion map the single source of truth for MG copy; require cue evidence plus explicit `mg_copy` for schema v3.
- Draft safety: move equal-duration `create-case` output to non-renderable `draftNodes`; new cases start with empty render nodes and an explicit semantic block.
- Compiler: add `compile-motion-map.mjs` to validate semantic coverage and copy, derive render nodes, and bind the motion-map SHA-256 without advancing workflow state.
- Gates: reject repeated titles, repeated title/sub, repeated chip sets, obvious clipped ASCII tokens, coverage gaps, missing cue bindings, stale motion-map hashes, and motion-map/node drift.
- Regression: expand KBE-005 to cover the observed fast-path failures while retaining schema-v2 compatibility.

## 0.3.0-candidate - 2026-07-16

- Security: constrain every recursive-delete target to a managed child of the case or fixed runtime cache; reject absolute and symlink escapes before deletion.
- Workflow: share one validator across preview, render, composite and final gates; require ordered history, real decodable artifacts, 10–15 second pilot, artifact SHA, stable baseline, semantic motion-map schema, caption overlap clamps, and full active error-bank coverage.
- Quality: derive an immutable canonical profile from the measured source; reject profile-name spoofing, CRF/preset/filter overrides, missing audio, incomplete SDR BT.709 metadata, wrong dimensions, wrong codec/pixel format, frame drift, and audio packet-hash drift.
- Provenance: bind renderer/component/root/theme/lockfile hashes, structured ffmpeg argv, compositor hash, source/final SHA, full decode and paginated QA coverage to the final artifact.
- Captions: implement display-end clamping for overlapping SRT cues and use the clamped duration inside the caption component; cap highlights at two.
- Error bank: convert all 16 active cases from schema-only records into registered executable regressions.
- Acceptance: bind declared external message metadata to the exact final artifact, technical report and actual SHA; explicitly stop claiming that filesystem JSON can authenticate a human author.
- Verification: real 6-second 720x1280 -> 1080x1920 Remotion/preserve-source smoke passed with 180/180 frames and exact source-audio packet hash; eight adversarial cases were blocked, including late full rerender, and the deletion sentinel survived.

## 0.2.0-candidate - 2026-07-16

- Workflow: add the ordered `subtitle review -> semantic motion map -> 4-6 static previews -> 10-15 second pilot -> full render -> technical gate -> human release acceptance` state machine.
- Quality route: make Remotion RGBA overlay plus ffmpeg preserve-source composite mandatory; full delivery now uses video-only encoding followed by complete source-audio stream-copy remux, with no `-shortest`.
- Resolution: keep 1080x1920 sources native; upscale sub-1080 vertical sources with `spline36` while rendering the overlay natively at the final size.
- Encoding: keep `libx264 slow CRF 8` as the default quality master and support an explicit `h264_videotoolbox 45M` long-form profile without relaxing preserve-source rules.
- Visual safety: move 720 design defaults to `progressTop=96` and `cardTop=150`, remove the global dark-room overlay, and stop masking long titles with ellipsis.
- Error bank: add 16 active, evidence-backed regression cases and deterministic schema validation.
- Gates: add workflow fixtures proving accepted and blocked paths, expanded full-render QA evidence, overlay-only source checks, publish-safe geometry, complete decode, packet-hash audio proof, and human-only release mode.
- Verification: `quick_validate`, meta-skill validation, JavaScript syntax, error-bank validation, workflow fixtures, and the complete 4-second 720-to-1080 Remotion preserve-source smoke passed; release mode correctly returns non-zero pending status without acceptance.
- Trigger eval: 9/9 positive, negative, and near-neighbor cases passed with precision 1.0 and recall 1.0.

## 0.1.2-candidate - 2026-07-16

- Canonical rename: `jc-koubo-packager` -> `jc-koubo-shuping`.
- Scope is now explicit: this skill is dedicated to vertical talking-head editing, not generic video packaging.
- Runtime cache and logs use the new identifier; `JC_KOUBO_PACKAGER_RUNTIME_DIR` remains a compatibility alias.
- Historical reports and release artifacts keep their original names as verification evidence.
- Verification: `quick_validate`, meta-skill validation, resource-boundary validation, JavaScript syntax checks, three-host bridge/hash checks, and the renamed 4-second Remotion preserve-source smoke all passed.

## 0.1.1-candidate - 2026-06-29

- Problem: 720p preserve-size finals remained visually soft on phone screens even with high H.264 bitrate.
- Decision: default publish delivery is now `1080p_native_overlay_h264_crf8` for sub-1080 vertical sources.
- Render change: Remotion overlay renders with manifest-controlled `renderScale` so 720x1280 sources produce native 1080x1920 overlay frames.
- Composite change: ffmpeg upscales source with `zscale` + `spline36`, composites native overlay, uses `libx264 preset=slow crf=8`, `yuv420p`, `bt709`, `tv range`, and audio copy.
- Validation change: final dimensions are checked against `qualityProfile.output`; overlay dimensions are checked against final output dimensions; color metadata is checked.
- Boundary: 720p output remains allowed only as quick preview or explicit compatibility fallback.
- Verification: `verify-install.mjs` smoke now proves 720x1280 input -> 1080x1920 final, 1080x1920 overlay frames, frame/audio preservation, SHA evidence, and clean `technical_pass`.
