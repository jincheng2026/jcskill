# Visual Contract

## Approved Baseline

Reuse the latest human-approved baseline for the case family. Do not invent a new card shell, subtitle background, progress grammar, or global grade after static preview approval.

The selected baseline is resolved from `manifest.visualStyleId`; there is no silent default:

- `assembly-mono` → `0726-approved-assembly-mono-v1`, with open black/white/silver MG, bundled Noto Sans SC / Inter / Archivo Black typography, hairlines and local feathered contrast;
- `google-semantic` → `0721-approved-baseline-v4-multi-mg`, with semantic Google accents and the approved multi-MG card system.

Both styles preserve one upper hero, high-contrast follow-read captions and the real source lighting without a global dark-room overlay. Read the matching style reference before authoring.

## Components

The fixed overlay has three readable layers:

1. Top whole-video progress or 3–5 macro chapters.
2. One semantic hero: card, statement, list, relation, flow, or numeric conclusion.
3. Bilingual captions.

The progress layer is navigation chrome, not a transcript outline. Internal semantic beats remain available to MG routing and QA, but never become one visible label per beat.

## Progress Timeline

- On a 720x1280 design canvas, `progressTop` must stay in `90-110`.
- On a 1080x1920 final canvas, the scaled rail must stay in `135-165`.
- `google-semantic` uses the restrained blue/red/yellow/green gradient.
- `assembly-mono` uses white/silver/grey rails with the current chapter in pure white.
- Default to one continuous elapsed-time rail with no text labels.
- When the story genuinely has macro chapters, author `manifest.progressChapters` with 3–5 contiguous chapters covering the full duration.
- Keep all 3–5 macro chapter labels visible, matching the original segmented-progress grammar; highlight the current chapter, brighten completed chapters, and mute future chapters.
- Never map `manifest.nodes[].label` directly to visible progress labels. Semantic beats and audience-facing chapters are different layers.
- Chapter labels should be short, unique, and no longer than 6 visible characters so the full macro set remains readable.
- No separate dot markers.
- Motion must be smooth: animate clip width/background position, not layout dimensions.

## Semantic Hero

- Variant geometry is locked in `mg-layout.json`; the total hero bottom must stay at or above `y=420` on the 720 design canvas.
- `cardTop` must stay in `140-210` on 720x1280, or `210-315` on 1080x1920.
- Prefer the speaker's upper whitespace. Do not move the hero card onto the mouth, chin, or chest merely because lower space looks empty.
- One readable hero per active node. Variants are selected by information relationship, not rotated for decoration.
- Card title must be short enough to read on phone.
- `google-semantic` card variants use dark glass, one semantic accent rail, consistent rounded corners and thin borders.
- `assembly-mono` uses open typography, hairlines, axes, nodes and 2D mechanism diagrams; no visible thick card shell.
- `chapter_title` and `contrast_statement` may omit the glass shell but still occupy the same upper safe zone.
- Every outer and inner card uses `box-sizing: border-box`.
- `prompt_fact` reserves at least 25 px bottom padding; `dual_relation` and `bookmark_relation` use 116 px inner panels; bookmark footer has an independent 34 px height plus 14 px gap.
- Do not stack another hero visual with the card.

## Captions

- Chinese is primary, light-weight, high-contrast, and exactly one line per cue.
- Split long source cues semantically before render; do not shrink below the approved size band and do not use browser wrapping.
- Use a separate near-black translucent rounded rectangle behind the Chinese line. Use PingFang SC Light-style white text around weight 300 without a thick stroke; keep only a subtle shadow and no visible plate border.
- English is required, smaller, and exactly one line below Chinese. Give it a separate content-width near-black translucent rounded rectangle; use Helvetica Neue Light-style proportional sans around weight 300 and do not merge both languages into one large subtitle box.
- Preserve natural English capitalization. Do not force lowercase and do not use yellow keyword highlighting in this baseline.
- English style should feel like clean interview subtitles, not code or monospace text.
- Default caption box on 720x1280: `left=42 top=890 width=636 height=264`.
- Highlight only meaningful tokens. Over-highlighting makes the line noisy.
- Captions follow the spoken sentence; never render beat summaries as subtitles.
- If two SRT cues overlap, visually hand off at the next cue start instead of showing two captions together.

## Collision Rules

- One beat has at most one readable hero.
- Semantic card + large title, semantic card + proof screenshot, or large number + split comparison are blocked unless one component is reduced to non-readable support.
- Check motion bboxes during entry, not only the resting frame.
- Check every active variant at its final hold state. Child panels and footers must remain fully inside the parent card.
- Titles must fit without ellipsis; shorten judgment text or reduce within approved size bands before rendering full length.

## Fonts

Do not rely on private system fonts for distribution. v0 template uses safe fallbacks and is designed for bundled fonts later:

- Chinese: `Noto Sans SC` preferred when bundled; fallback to system sans.
- English: `JetBrains Mono` preferred when bundled; fallback to monospace.

If exact typography matters, bundle the font files and license evidence before release.
