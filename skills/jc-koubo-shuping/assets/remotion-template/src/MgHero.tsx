import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {ACCENT, COLORS, FONT, MG_LAYOUT} from './theme';
import type {MgItem, MgPanel, MgVariant, NodeBeat} from './types';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const mono = FONT.en;

function reveal(frame: number, delay: number, duration = 12) {
  return interpolate(frame, [delay, delay + duration], [0, 1], clamp);
}

function fitTitleSize(text: string) {
  const len = text.replace(/\s/gu, '').length;
  if (len > 20) return 24;
  if (len > 16) return 28;
  if (len > 14) return 32;
  if (len > 11) return 35;
  if (len > 8) return 40;
  if (len > 6) return 46;
  return 54;
}

function layoutFor(variant: MgVariant) {
  return MG_LAYOUT.variants[variant];
}

const Eyebrow: React.FC<{accent: string; children: React.ReactNode}> = ({accent, children}) => (
  <div style={{fontFamily: mono, fontSize: 15, lineHeight: 1, fontWeight: 900, letterSpacing: 1.15, color: accent}}>
    {children}
  </div>
);

const AccentRail: React.FC<{accent: string}> = ({accent}) => (
  <>
    <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: 10, background: accent}} />
    <div style={{position: 'absolute', left: 10, right: 0, top: 0, height: 4, background: `linear-gradient(90deg, ${accent}, rgba(255,255,255,0.22) 44%, rgba(255,255,255,0))`}} />
  </>
);

const glass: React.CSSProperties = {
  boxSizing: 'border-box',
  borderRadius: 22,
  background: 'linear-gradient(135deg, rgba(8,11,17,0.84), rgba(20,25,36,0.78) 54%, rgba(11,14,20,0.70))',
  border: '1px solid rgba(248,250,253,0.20)',
  backdropFilter: 'blur(14px)',
  boxShadow: '0 24px 56px rgba(0,0,0,0.32)',
  overflow: 'hidden',
};

const Shell: React.FC<{beat: NodeBeat; variant: MgVariant; children: React.ReactNode}> = ({beat, variant, children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = Math.max(0, frame - Math.round(beat.start * fps));
  const enter = spring({frame: local, fps, config: {damping: 16, stiffness: 180, mass: 0.72}});
  const opacity = 1;
  const y = interpolate(enter, [0, 1], [18, 0], clamp);
  const scale = interpolate(enter, [0, 1], [0.975, 1], clamp);
  const layout = layoutFor(variant);
  return (
    <div
      style={{
        position: 'absolute',
        left: layout.left,
        top: layout.top,
        width: layout.width,
        height: layout.height,
        color: COLORS.ink,
        opacity,
        transform: `translate3d(0, ${y}px, 0) scale(${scale})`,
        ...glass,
      }}
    >
      {children}
    </div>
  );
};

function panel(value: MgPanel | undefined, fallbackTitle: string, fallbackSub: string): Required<MgPanel> {
  return {
    label: value?.label || fallbackSub,
    title: value?.title || fallbackTitle,
    sub: value?.sub || '',
  };
}

const SemanticCard: React.FC<{beat: NodeBeat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = Math.max(0, frame - Math.round(beat.start * fps));
  const accent = ACCENT[beat.accent] || COLORS.blue;
  return (
    <Shell beat={beat} variant="semantic_card">
      <AccentRail accent={accent} />
      <div style={{height: '100%', boxSizing: 'border-box', padding: '20px 20px 18px 29px', display: 'flex', alignItems: 'center', gap: 18}}>
        <div style={{minWidth: 0, flex: '1 1 auto'}}>
          <Eyebrow accent={accent}>{beat.eyebrow}</Eyebrow>
          <div style={{marginTop: 12, fontSize: fitTitleSize(beat.title), lineHeight: 1.02, fontWeight: 950, overflowWrap: 'anywhere'}}>{beat.title}</div>
          <div style={{marginTop: 11, fontSize: beat.sub.replace(/\s/gu, '').length > 18 ? 18 : 22, lineHeight: 1.14, fontWeight: 780, color: COLORS.cardMuted}}>{beat.sub}</div>
        </div>
        <div style={{width: 184, display: 'flex', flexDirection: 'column', gap: 9, flex: '0 0 auto'}}>
          {beat.chips.slice(0, 3).map((chip, index) => {
            const p = reveal(local, 13 + index * 10);
            return <div key={`${beat.id}-${chip}`} style={{height: 36, boxSizing: 'border-box', borderRadius: 11, display: 'flex', alignItems: 'center', padding: '0 12px', background: index === 0 ? `${accent}24` : 'rgba(248,250,253,0.09)', border: `1px solid ${index === 0 ? `${accent}66` : 'rgba(248,250,253,0.14)'}`, fontSize: 16, fontWeight: 850, whiteSpace: 'nowrap', opacity: p, transform: `translateX(${(1 - p) * 14}px)`}}>{chip}</div>;
          })}
        </div>
      </div>
    </Shell>
  );
};

const ChapterTitle: React.FC<{beat: NodeBeat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = Math.max(0, frame - Math.round(beat.start * fps));
  const accent = ACCENT[beat.accent] || COLORS.blue;
  return (
    <div style={{position: 'absolute', left: 34, top: 164, width: 652, height: 224, boxSizing: 'border-box', color: COLORS.ink, textShadow: '0 8px 28px rgba(0,0,0,0.55)', overflow: 'hidden'}}>
      <div style={{opacity: reveal(local, 0), transform: `translateY(${(1 - reveal(local, 0)) * 10}px)`}}><Eyebrow accent={accent}>{beat.eyebrow}</Eyebrow></div>
      <div style={{marginTop: 16, fontSize: fitTitleSize(beat.title), lineHeight: 1.02, fontWeight: 950, opacity: reveal(local, 7), transform: `translateY(${(1 - reveal(local, 7)) * 16}px)`}}>{beat.title}</div>
      <div style={{marginTop: 12, fontSize: 25, fontWeight: 850, color: accent, opacity: reveal(local, 18)}}>{beat.sub}</div>
      <div style={{marginTop: 17, width: 146 * reveal(local, 26), height: 5, borderRadius: 999, background: accent}} />
    </div>
  );
};

const ContrastStatement: React.FC<{beat: NodeBeat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = Math.max(0, frame - Math.round(beat.start * fps));
  const accent = ACCENT[beat.accent] || COLORS.red;
  const left = panel(beat.payload?.left, beat.title, '旧认识');
  const right = panel(beat.payload?.right, beat.sub, '真正重点');
  return (
    <div style={{position: 'absolute', left: 34, top: 164, width: 652, height: 226, boxSizing: 'border-box', color: COLORS.ink, textShadow: '0 8px 28px rgba(0,0,0,0.55)', overflow: 'hidden'}}>
      <Eyebrow accent={accent}>{beat.eyebrow}</Eyebrow>
      <div style={{marginTop: 16, fontSize: 52, lineHeight: 1, fontWeight: 950, opacity: reveal(local, 4), transform: `translateX(${(1 - reveal(local, 4)) * -18}px)`}}>{left.title}</div>
      <div style={{marginTop: 7, fontSize: 52, lineHeight: 1, fontWeight: 950, color: accent, opacity: reveal(local, 18), transform: `translateX(${(1 - reveal(local, 18)) * 18}px)`}}>{right.title}</div>
      <div style={{marginTop: 18, display: 'inline-flex', maxWidth: 620, boxSizing: 'border-box', padding: '7px 12px', borderRadius: 8, background: 'rgba(4,6,8,0.66)', fontSize: 18, fontWeight: 800, opacity: reveal(local, 34)}}>{beat.payload?.footer || beat.sub}</div>
    </div>
  );
};

const NumberedList: React.FC<{beat: NodeBeat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = Math.max(0, frame - Math.round(beat.start * fps));
  const accent = ACCENT[beat.accent] || COLORS.yellow;
  const items: MgItem[] = beat.payload?.items?.slice(0, 5) || beat.chips.map((label) => ({label}));
  return (
    <Shell beat={beat} variant="numbered_list">
      <AccentRail accent={accent} />
      <div style={{height: '100%', boxSizing: 'border-box', padding: '18px 22px 16px 28px'}}>
        <div style={{display: 'flex', alignItems: 'baseline', justifyContent: 'space-between'}}>
          <div><Eyebrow accent={accent}>{beat.eyebrow}</Eyebrow><div style={{marginTop: 7, fontSize: 31, lineHeight: 1, fontWeight: 950}}>{beat.title}</div></div>
          <div style={{fontFamily: mono, fontSize: 42, fontWeight: 950, color: accent}}>{String(items.length).padStart(2, '0')}</div>
        </div>
        <div style={{height: 1, marginTop: 11, background: 'rgba(248,250,253,0.16)'}} />
        {items.map((item, index) => {
          const p = reveal(local, 18 + index * 10, 9);
          return <div key={`${beat.id}-${index}`} style={{height: 28, boxSizing: 'border-box', display: 'grid', gridTemplateColumns: '36px 1fr 108px', alignItems: 'center', borderBottom: index === items.length - 1 ? 'none' : '1px solid rgba(248,250,253,0.10)', padding: '0 5px', opacity: p, transform: `translateX(${(1 - p) * 18}px)`}}><span style={{fontFamily: mono, fontSize: 14, fontWeight: 900, color: accent}}>{String(index + 1).padStart(2, '0')}</span><span style={{fontSize: 19, fontWeight: 850}}>{item.label}</span><span style={{fontSize: 13, textAlign: 'right', color: COLORS.cardMuted}}>{item.note || ''}</span></div>;
        })}
      </div>
    </Shell>
  );
};

const RelationPanels: React.FC<{beat: NodeBeat; accent: string; local: number; bookmark?: boolean}> = ({beat, accent, local, bookmark = false}) => {
  const left = panel(beat.payload?.left, beat.title, '左侧');
  const right = panel(beat.payload?.right, beat.sub, '右侧');
  return (
    <div style={{marginTop: 17, display: 'grid', gridTemplateColumns: '1fr 64px 1fr', gap: 12, alignItems: 'center'}}>
      {[left, right].map((item, index) => {
        const p = reveal(local, 16 + index * 42);
        return (
          <React.Fragment key={`${beat.id}-panel-${index}`}>
            <div style={{height: MG_LAYOUT.inner.relationPanelHeight, boxSizing: 'border-box', padding: `12px 15px ${MG_LAYOUT.inner.relationPanelPaddingBottom}px`, borderRadius: 14, background: index === (bookmark ? 0 : 1) ? `${accent}22` : 'rgba(248,250,253,0.08)', border: `1px solid ${index === (bookmark ? 0 : 1) ? `${accent}66` : 'rgba(248,250,253,0.16)'}`, opacity: p, transform: `translateX(${(1 - p) * (index ? 14 : -14)}px)`, overflow: 'hidden'}}>
              <div style={{fontSize: 14, lineHeight: 1.15, color: COLORS.cardMuted}}>{item.label}</div>
              <div style={{marginTop: 8, fontSize: 29, lineHeight: 1.05, fontWeight: 950, color: index === (bookmark ? 0 : 1) ? accent : COLORS.ink}}>{item.title}</div>
              {item.sub ? <div style={{marginTop: 7, fontSize: 17, lineHeight: 1.05, fontWeight: 820}}>{item.sub}</div> : null}
            </div>
            {index === 0 ? <div style={{fontFamily: mono, fontSize: 40, fontWeight: 950, textAlign: 'center', color: accent, opacity: reveal(local, 42)}}>{beat.payload?.operator || (bookmark ? '→' : '+')}</div> : null}
          </React.Fragment>
        );
      })}
    </div>
  );
};

const PromptFact: React.FC<{beat: NodeBeat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = Math.max(0, frame - Math.round(beat.start * fps));
  const accent = ACCENT[beat.accent] || COLORS.green;
  const left = panel(beat.payload?.left, '旧方式', '旧方式');
  const right = panel(beat.payload?.right, '新方式', '新方式');
  return (
    <Shell beat={beat} variant="prompt_fact">
      <AccentRail accent={accent} />
      <div style={{height: '100%', boxSizing: 'border-box', padding: '18px 22px 25px 28px'}}>
        <div style={{display: 'flex', justifyContent: 'space-between'}}><Eyebrow accent={accent}>{beat.eyebrow}</Eyebrow><div style={{padding: '5px 10px', borderRadius: 8, background: accent, color: '#10131A', fontSize: 13, fontWeight: 950}}>{beat.payload?.tag || beat.label}</div></div>
        <div style={{marginTop: 15, borderRadius: 10, background: '#F1F3F4', padding: '14px 16px', color: '#141820', opacity: reveal(local, 14)}}><div style={{fontFamily: mono, fontSize: 32, lineHeight: 1.05, fontWeight: 900}}>{beat.payload?.quote || beat.title}</div></div>
        <div style={{marginTop: MG_LAYOUT.inner.promptComparisonGap, display: 'grid', gridTemplateColumns: '1fr 54px 1fr', alignItems: 'center', gap: 12, opacity: reveal(local, 34)}}>
          <div><div style={{fontSize: 13, color: COLORS.cardMuted}}>{left.label}</div><div style={{marginTop: 5, fontSize: 21, fontWeight: 850}}>{left.title}</div></div>
          <div style={{fontSize: 28, textAlign: 'center', color: accent}}>{beat.payload?.operator || '→'}</div>
          <div><div style={{fontSize: 13, color: COLORS.cardMuted}}>{right.label}</div><div style={{marginTop: 5, fontSize: 21, fontWeight: 900, color: accent}}>{right.title}</div></div>
        </div>
      </div>
    </Shell>
  );
};

const DualRelation: React.FC<{beat: NodeBeat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = Math.max(0, frame - Math.round(beat.start * fps));
  const accent = ACCENT[beat.accent] || COLORS.blue;
  return <Shell beat={beat} variant="dual_relation"><AccentRail accent={accent} /><div style={{height: '100%', boxSizing: 'border-box', padding: '18px 22px 23px 28px'}}><div style={{display: 'flex', justifyContent: 'space-between'}}><Eyebrow accent={accent}>{beat.eyebrow}</Eyebrow><div style={{fontFamily: mono, fontSize: 14, fontWeight: 900, color: accent}}>{beat.payload?.tag || 'COMBINE'}</div></div><RelationPanels beat={beat} accent={accent} local={local} /></div></Shell>;
};

const BookmarkRelation: React.FC<{beat: NodeBeat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = Math.max(0, frame - Math.round(beat.start * fps));
  const accent = ACCENT[beat.accent] || COLORS.blue;
  return <Shell beat={beat} variant="bookmark_relation"><AccentRail accent={accent} /><div style={{height: '100%', boxSizing: 'border-box', padding: '18px 22px 24px 28px'}}><Eyebrow accent={accent}>{beat.eyebrow}</Eyebrow><RelationPanels beat={beat} accent={accent} local={local} bookmark /><div style={{marginTop: MG_LAYOUT.inner.bookmarkFooterGap, height: MG_LAYOUT.inner.bookmarkFooterHeight, boxSizing: 'border-box', borderRadius: 9, background: 'rgba(248,250,253,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 17, lineHeight: 1, fontWeight: 850, opacity: reveal(local, 72)}}>{beat.payload?.footer || beat.sub}</div></div></Shell>;
};

const AgentFlow: React.FC<{beat: NodeBeat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = Math.max(0, frame - Math.round(beat.start * fps));
  const accent = ACCENT[beat.accent] || COLORS.green;
  const flow = beat.payload?.flow?.slice(0, 4) || beat.chips.slice(0, 3);
  return (
    <Shell beat={beat} variant="agent_flow">
      <AccentRail accent={accent} />
      <div style={{height: '100%', boxSizing: 'border-box', padding: '18px 22px'}}>
        <div style={{display: 'flex', justifyContent: 'space-between'}}><Eyebrow accent={accent}>{beat.eyebrow}</Eyebrow><div style={{padding: '5px 10px', borderRadius: 8, background: `${accent}24`, border: `1px solid ${accent}66`, fontSize: 13, fontWeight: 950}}>{beat.payload?.tag || beat.label}</div></div>
        <div style={{marginTop: 16, fontSize: 30, fontWeight: 950}}>{beat.title}</div>
        <div style={{marginTop: 18, display: 'flex', alignItems: 'center', gap: 9}}>
          {flow.map((item, index) => <React.Fragment key={`${beat.id}-flow-${index}`}><div style={{height: 54, minWidth: 0, flex: '1 1 0', boxSizing: 'border-box', borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', background: index === 1 ? `${accent}24` : 'rgba(248,250,253,0.08)', border: `1px solid ${index === 1 ? `${accent}66` : 'rgba(248,250,253,0.16)'}`, fontSize: item.length > 10 ? 14 : 17, fontWeight: 900, color: index === 1 ? accent : COLORS.ink, opacity: reveal(local, 15 + index * 14)}}>{item}</div>{index < flow.length - 1 ? <div style={{fontSize: 22, color: accent, opacity: reveal(local, 24 + index * 14)}}>→</div> : null}</React.Fragment>)}
        </div>
      </div>
    </Shell>
  );
};

const NumericConclusion: React.FC<{beat: NodeBeat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = Math.max(0, frame - Math.round(beat.start * fps));
  const accent = ACCENT[beat.accent] || COLORS.yellow;
  const rawValue = beat.payload?.value || '1';
  const numeric = Number(rawValue);
  const animatedValue = Number.isFinite(numeric) ? String(Math.round(interpolate(local, [8, 34], [0, numeric], clamp))) : rawValue;
  return (
    <Shell beat={beat} variant="numeric_conclusion">
      <AccentRail accent={accent} />
      <div style={{height: '100%', boxSizing: 'border-box', padding: '19px 22px 20px 28px'}}>
        <div style={{display: 'flex', justifyContent: 'space-between'}}><Eyebrow accent={accent}>{beat.eyebrow}</Eyebrow><div style={{padding: '5px 10px', borderRadius: 8, background: `${accent}26`, border: `1px solid ${accent}66`, fontSize: 13, fontWeight: 950}}>{beat.payload?.tag || beat.label}</div></div>
        <div style={{marginTop: 15, display: 'flex', alignItems: 'baseline', gap: 16}}><div style={{fontFamily: mono, fontSize: 80, lineHeight: 0.86, fontWeight: 950, color: accent}}>{animatedValue}</div><div style={{fontSize: 31, lineHeight: 1.05, fontWeight: 950}}>{beat.payload?.unit || beat.title}<br /><span style={{fontSize: 25, color: accent, opacity: reveal(local, 28)}}>{beat.sub}</span></div></div>
        <div style={{marginTop: 16, display: 'grid', gridTemplateColumns: `repeat(${Math.max(1, Math.min(2, beat.chips.length))}, 1fr)`, gap: 12, opacity: reveal(local, 48)}}>{beat.chips.slice(0, 2).map((chip, index) => <div key={`${beat.id}-result-${index}`} style={{height: 34, boxSizing: 'border-box', borderRadius: 10, background: index ? `${accent}20` : 'rgba(248,250,253,0.08)', border: index ? `1px solid ${accent}55` : '1px solid transparent', display: 'flex', alignItems: 'center', padding: '0 12px', fontSize: 16, fontWeight: 850, color: index ? accent : COLORS.ink}}>{String(index + 1).padStart(2, '0')} · {chip}</div>)}</div>
      </div>
    </Shell>
  );
};

export const MgHero: React.FC<{beat: NodeBeat}> = ({beat}) => {
  const variant: MgVariant = beat.variant || 'semantic_card';
  if (variant === 'chapter_title') return <ChapterTitle beat={beat} />;
  if (variant === 'contrast_statement') return <ContrastStatement beat={beat} />;
  if (variant === 'numbered_list') return <NumberedList beat={beat} />;
  if (variant === 'prompt_fact') return <PromptFact beat={beat} />;
  if (variant === 'dual_relation') return <DualRelation beat={beat} />;
  if (variant === 'bookmark_relation') return <BookmarkRelation beat={beat} />;
  if (variant === 'agent_flow') return <AgentFlow beat={beat} />;
  if (variant === 'numeric_conclusion') return <NumericConclusion beat={beat} />;
  return <SemanticCard beat={beat} />;
};
