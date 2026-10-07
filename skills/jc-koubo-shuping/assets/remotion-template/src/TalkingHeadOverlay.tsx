import React from 'react';
import {AbsoluteFill, Sequence, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, FONT, LAYOUT, googleGradient} from './theme';
import type {CaptionCue, NodeBeat, OverlayProps, ProgressChapter, VisualStyleId} from './types';
import {MgHero} from './MgHero';
import {AssemblyMonoContrastLayer, AssemblyMonoHero} from './AssemblyMonoHero';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const fallbackNodes: NodeBeat[] = [
  {
    id: 'n01',
    start: 0,
    end: 1.6,
    label: '开场',
    eyebrow: 'FIRST CHECK',
    title: '先看环境',
    sub: '别急着怀疑能力',
    chips: ['环境先查', '别急否定', '真实素材'],
    accent: 'blue',
  },
  {
    id: 'n02',
    start: 1.6,
    end: 3,
    label: '误区',
    eyebrow: 'TRAP',
    title: '别等成熟',
    sub: '等本身就在掉队',
    chips: ['别等', '马上练', '判断力'],
    accent: 'yellow',
  },
  {
    id: 'n03',
    start: 3,
    end: 4,
    label: '行动',
    eyebrow: 'FINAL MOVE',
    title: '直接开干',
    sub: '动手才不会过期',
    chips: ['开干', '不会过期', '行动'],
    accent: 'green',
  },
];

function cueFrom(seconds: number, fps: number) {
  return Math.max(0, Math.round(seconds * fps));
}

function cueDuration(start: number, end: number, fps: number) {
  return Math.max(1, cueFrom(end, fps) - cueFrom(start, fps));
}

function activeNodeAt(frame: number, fps: number, nodes: NodeBeat[]) {
  return nodes.find((node) => frame >= cueFrom(node.start, fps) && frame < cueFrom(node.end, fps)) || nodes[nodes.length - 1];
}

const ZH_CAPTION_FONT_SIZES = [54, 48, 42, 38] as const;
const EN_CAPTION_FONT_SIZES = [25, 23, 21, 19] as const;

function captionUnit(character: string) {
  if (/\s/u.test(character)) return 0.3;
  if (/[\u0000-\u00ff]/u.test(character)) return 0.58;
  if (/[，。！？；：、,.!?;:（）()《》「」『』【】]/u.test(character)) return 0.56;
  return 1;
}

function units(text: string) {
  return Array.from(text).reduce((total, character) => total + captionUnit(character), 0);
}

function fitSingleLine(text: string, fontSizes: readonly number[]) {
  const normalized = text.trim();
  for (const fontSize of fontSizes) {
    const maxUnits = LAYOUT.captionWidth / fontSize / 1.08;
    if (normalized && units(normalized) <= maxUnits) return {fontSize, overflow: false};
  }
  return {fontSize: fontSizes[fontSizes.length - 1], overflow: true};
}

export const TalkingHeadOverlay: React.FC<OverlayProps> = ({manifest}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const nodes = manifest?.nodes?.length ? manifest.nodes : fallbackNodes;
  const captions = manifest?.captionTrack || [];
  const displayCaptions = captions
    .map((caption, index) => ({
      ...caption,
      displayEnd: Math.min(caption.displayEnd ?? caption.end, captions[index + 1]?.start ?? caption.end),
    }))
    .filter((caption) => caption.displayEnd > caption.start);
  const activeNode = activeNodeAt(frame, fps, nodes);
  const designScale = width / 720;
  const visualStyleId: VisualStyleId = manifest?.visualStyleId || 'google-semantic';

  return (
    <AbsoluteFill style={{fontFamily: FONT.zh, letterSpacing: 0, overflow: 'hidden'}}>
      <div
        style={{
          position: 'absolute',
          width: 720,
          height: height / designScale,
          transform: `scale(${designScale})`,
          transformOrigin: 'top left',
        }}
      >
        {visualStyleId === 'assembly-mono' ? <AssemblyMonoContrastLayer /> : null}
        <ProgressTimeline duration={Number(manifest?.video?.duration || nodes[nodes.length - 1]?.end || 1)} chapters={manifest?.progressChapters} visualStyleId={visualStyleId} />
        {visualStyleId === 'assembly-mono' ? <AssemblyMonoHero beat={activeNode} /> : <MgHero beat={activeNode} />}
        {displayCaptions.map((caption) => (
          <Sequence key={caption.id} from={cueFrom(caption.start, fps)} durationInFrames={cueDuration(caption.start, caption.displayEnd, fps)}>
            <PrimaryCaption cue={caption} />
          </Sequence>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const ProgressTimeline: React.FC<{duration: number; chapters?: ProgressChapter[]; visualStyleId: VisualStyleId}> = ({duration, chapters, visualStyleId}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const hasChapters = Boolean(chapters?.length);
  const timeline: ProgressChapter[] = hasChapters
    ? chapters!
    : [{id: 'whole-video', start: 0, end: Math.max(duration, 1 / fps), label: ''}];
  const activeIndex = timeline.findIndex(
    (chapter) => frame >= cueFrom(chapter.start, fps) && frame < cueFrom(chapter.end, fps),
  );
  const resolvedIndex = activeIndex === -1
    ? (frame >= cueFrom(timeline[timeline.length - 1].end, fps) ? timeline.length : 0)
    : activeIndex;
  const activeChapter = timeline[Math.min(resolvedIndex, timeline.length - 1)];
  const partial = activeChapter
    ? interpolate(frame, [cueFrom(activeChapter.start, fps), cueFrom(activeChapter.end, fps)], [0, 1], clamp)
    : 1;
  const progressIndex = resolvedIndex >= timeline.length ? timeline.length : resolvedIndex + partial;
  const filledSegments = Math.floor(progressIndex);
  const localPartial = progressIndex - filledSegments;
  const gap = hasChapters ? 10 : 0;
  const segmentWidth = `((100% - ${gap * (timeline.length - 1)}px) / ${timeline.length})`;
  const fillWidth =
    filledSegments <= 0
      ? `calc(${segmentWidth} * ${localPartial})`
      : `calc(${segmentWidth} * ${filledSegments} + ${gap * Math.max(0, filledSegments - 1)}px + ${segmentWidth} * ${localPartial})`;
  const clipRight = `calc(100% - ${fillWidth})`;
  const colorShift = interpolate(Math.sin(frame / 84), [-1, 1], [12, -42], clamp);
  const shimmer = interpolate(Math.sin(frame / 56), [-1, 1], [-28, 126], clamp);
  const assemblyMono = visualStyleId === 'assembly-mono';

  return (
    <div style={{position: 'absolute', left: 20, right: 20, top: LAYOUT.progressTop, height: 50}}>
      {hasChapters ? (
        <div
          style={{
            height: 21,
            display: 'grid',
            gridTemplateColumns: `repeat(${timeline.length}, 1fr)`,
            columnGap: gap,
          }}
        >
          {timeline.map((chapter, index) => {
            const isDone = index < resolvedIndex;
            const isActive = index === resolvedIndex && resolvedIndex < timeline.length;
            return (
              <div
                key={`${chapter.id}-label`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: isActive ? 15 : 13,
                  fontWeight: isActive ? 950 : isDone ? 880 : 780,
                  color: assemblyMono
                    ? isActive ? '#FFFFFF' : isDone ? 'rgba(245,245,247,0.72)' : 'rgba(199,199,204,0.34)'
                    : isActive ? COLORS.yellow : isDone ? 'rgba(248,250,253,0.88)' : 'rgba(248,250,253,0.42)',
                  whiteSpace: 'nowrap',
                  textShadow: '0 2px 8px rgba(0,0,0,0.82)',
                }}
              >
                {chapter.label}
              </div>
            );
          })}
        </div>
      ) : null}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 28,
          height: 8,
          display: 'grid',
          gridTemplateColumns: `repeat(${timeline.length}, 1fr)`,
          columnGap: gap,
        }}
      >
        {timeline.map((chapter) => (
          <div
            key={`${chapter.id}-rail`}
            style={{
              height: 8,
              borderRadius: 999,
            background: assemblyMono ? 'rgba(255,255,255,0.18)' : COLORS.rail,
              boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.12), 0 1px 5px rgba(0,0,0,0.18)',
            }}
          />
        ))}
      </div>
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 28,
          height: 8,
          borderRadius: 999,
          opacity: 0.95,
          clipPath: `inset(0 ${clipRight} 0 0 round 999px)`,
          boxShadow: assemblyMono ? '0 0 8px rgba(255,255,255,0.24)' : '0 0 13px rgba(66,133,244,0.24), 0 0 11px rgba(251,188,5,0.17)',
          overflow: 'hidden',
          willChange: 'clip-path',
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: assemblyMono ? 'linear-gradient(90deg, rgba(245,245,247,0.56), #FFFFFF)' : googleGradient,
            backgroundSize: '138% 100%',
            backgroundPosition: assemblyMono ? '0 0' : `${colorShift}px 0`,
            filter: assemblyMono ? 'none' : 'saturate(1.2) contrast(1.04)',
          }}
        />
        {!assemblyMono && localPartial > 0.01 && filledSegments < timeline.length ? (
          <div
            style={{
              position: 'absolute',
              left: shimmer,
              top: -7,
              width: 24,
              height: 22,
              transform: 'rotate(18deg)',
              background: 'linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,0.54), rgba(255,255,255,0))',
              filter: 'blur(1px)',
              opacity: 0.42,
            }}
          />
        ) : null}
      </div>
    </div>
  );
};

const PrimaryCaption: React.FC<{cue: CaptionCue}> = ({cue}) => {
  const zhLayout = fitSingleLine(cue.zh, ZH_CAPTION_FONT_SIZES);
  const en = cue.en || '';
  const enLayout = fitSingleLine(en, EN_CAPTION_FONT_SIZES);

  return (
    <div
      style={{
        position: 'absolute',
        left: LAYOUT.captionLeft,
        top: LAYOUT.captionTop,
        width: LAYOUT.captionWidth,
        height: LAYOUT.captionHeight,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        opacity: 1,
        color: COLORS.ink,
        textAlign: 'center',
      }}
    >
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 'fit-content',
          maxWidth: LAYOUT.captionWidth,
          minHeight: 74,
          padding: '8px 18px 10px',
          borderRadius: 8,
          background: 'rgba(4,6,8,0.84)',
          border: 'none',
          boxShadow: '0 3px 10px rgba(0,0,0,0.22)',
          fontFamily: '"PingFang SC", "Hiragino Sans GB", Arial, sans-serif',
          fontSize: zhLayout.fontSize,
          lineHeight: 1.08,
          fontWeight: 300,
          letterSpacing: 0.2,
          textShadow: '0 1px 1px rgba(0,0,0,0.30)',
          whiteSpace: 'nowrap',
        }}
      >
        {cue.zh}
      </div>
      {en ? (
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 'fit-content',
            marginTop: 6,
            maxWidth: LAYOUT.captionWidth,
            minHeight: 38,
            padding: '4px 13px 6px',
            borderRadius: 7,
            background: 'rgba(4,6,8,0.84)',
            border: 'none',
            boxShadow: '0 3px 9px rgba(0,0,0,0.20)',
            fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
            fontSize: enLayout.fontSize,
            lineHeight: 1.08,
            fontWeight: 300,
            color: 'rgba(248,250,253,0.96)',
            letterSpacing: 0.1,
            textShadow: '0 1px 1px rgba(0,0,0,0.28)',
            whiteSpace: 'nowrap',
          }}
        >
          {en}
        </div>
      ) : null}
    </div>
  );
};
