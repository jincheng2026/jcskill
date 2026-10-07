import React from 'react';
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import type {MgItem, MgPanel, MgVariant, NodeBeat} from './types';

const C = {
  bright: '#FFFFFF',
  white: '#F5F5F7',
  silver: '#C7C7CC',
  mid: '#8E8E93',
  dim: '#636366',
  line: 'rgba(255,255,255,0.17)',
  lineStrong: 'rgba(255,255,255,0.36)',
};
const zh = '"Noto Sans SC", "PingFang SC", sans-serif';
const en = '"Inter", "Helvetica Neue", sans-serif';
const number = '"Archivo Black", "Arial Black", sans-serif';
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

function reveal(frame: number, delay: number, duration = 10) {
  return interpolate(frame, [delay, delay + duration], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
}

function enter(p: number, x = 0, y = 10): React.CSSProperties {
  return {opacity: p, transform: `translate(${(1 - p) * x}px, ${(1 - p) * y}px)`};
}

function clean(value = '') {
  return value.replaceAll(',', '，').replaceAll(':', '：');
}

function titleSize(text = '', max = 53) {
  const length = Array.from(text.replace(/\s/gu, '')).length;
  if (length >= 18) return Math.min(max, 32);
  if (length >= 15) return Math.min(max, 36);
  if (length >= 12) return Math.min(max, 41);
  if (length >= 9) return Math.min(max, 47);
  return max;
}

function panel(value: MgPanel | undefined, fallback: string, label: string): Required<MgPanel> {
  return {label: value?.label || label, title: value?.title || fallback, sub: value?.sub || ''};
}

const Shell: React.FC<{children: React.ReactNode; top?: number}> = ({children, top = 166}) => (
  <div
    style={{
      position: 'absolute',
      left: 42,
      right: 42,
      top,
      color: C.white,
      fontFamily: zh,
      textShadow: '0 3px 14px rgba(0,0,0,0.82)',
    }}
  >
    {children}
  </div>
);

const Kicker: React.FC<{children: React.ReactNode}> = ({children}) => (
  <div style={{fontFamily: en, fontSize: 13, lineHeight: 1, fontWeight: 700, letterSpacing: '0.14em', color: C.silver}}>
    {children}
  </div>
);

const Rule: React.FC<{width?: number}> = ({width = 76}) => <div style={{width, height: 1.5, background: C.white, opacity: 0.9}} />;

const Statement: React.FC<{beat: NodeBeat; local: number}> = ({beat, local}) => (
  <Shell>
    <div style={enter(reveal(local, 0))}><Kicker>{beat.eyebrow}</Kicker></div>
    <div style={{marginTop: 18, fontSize: titleSize(beat.title), lineHeight: 1.05, fontWeight: 790, letterSpacing: '-0.042em', color: C.bright, ...enter(reveal(local, 8))}}>
      {clean(beat.title)}
    </div>
    <div style={{marginTop: 19, width: `${reveal(local, 22) * 100}%`, height: 1.5, background: C.white, opacity: 0.8}} />
    <div style={{marginTop: 20, fontSize: 25, lineHeight: 1.25, fontWeight: 580, color: C.silver, ...enter(reveal(local, 31))}}>{clean(beat.sub)}</div>
    <div style={{marginTop: 25, display: 'flex', gap: 22, alignItems: 'center', ...enter(reveal(local, 48))}}>
      {beat.chips.slice(0, 3).map((chip, index) => (
        <React.Fragment key={`${beat.id}-${chip}`}>
          {index > 0 ? <div style={{width: 4, height: 4, borderRadius: '50%', background: C.silver}} /> : null}
          <div style={{fontSize: 17, fontWeight: 650, color: index === 0 ? C.bright : C.silver}}>{chip}</div>
        </React.Fragment>
      ))}
    </div>
  </Shell>
);

const Chapter: React.FC<{beat: NodeBeat; local: number}> = ({beat, local}) => {
  const parts = clean(beat.title).split('，');
  return (
    <Shell>
      <div style={enter(reveal(local, 0))}><Kicker>{beat.eyebrow}</Kicker></div>
      <div style={{marginTop: 18, fontSize: 55, lineHeight: 1.03, fontWeight: 760, letterSpacing: '-0.045em', ...enter(reveal(local, 7))}}>{parts[0]}</div>
      <div style={{marginTop: 8, fontSize: 61, lineHeight: 1, fontWeight: 900, letterSpacing: '-0.052em', color: C.bright, ...enter(reveal(local, 20))}}>
        {parts.slice(1).join('，') || clean(beat.sub)}
      </div>
      <div style={{marginTop: 24, display: 'flex', alignItems: 'center', gap: 14, ...enter(reveal(local, 35))}}><Rule /><div style={{fontSize: 18, fontWeight: 560, color: C.silver}}>{clean(beat.sub)}</div></div>
    </Shell>
  );
};

const Numeric: React.FC<{beat: NodeBeat; local: number}> = ({beat, local}) => {
  const raw = beat.payload?.value || '1';
  const parsed = Number(raw);
  const animated = Number.isFinite(parsed) ? Math.round(interpolate(local, [8, 34], [0, parsed], clamp)) : raw;
  return (
    <Shell>
      <div style={enter(reveal(local, 0))}><Kicker>{beat.eyebrow}</Kicker></div>
      <div style={{marginTop: 20, display: 'grid', gridTemplateColumns: '245px 1fr', gap: 26, alignItems: 'center'}}>
        <div style={enter(reveal(local, 7))}>
          <div style={{fontFamily: number, fontSize: 119, lineHeight: 0.8, letterSpacing: '-0.075em', color: C.bright}}>{animated}</div>
          <div style={{marginTop: 25, fontSize: 22, fontWeight: 690, color: C.silver}}>{beat.payload?.unit || beat.label}</div>
        </div>
        <div style={enter(reveal(local, 26))}><Rule width={64} /><div style={{marginTop: 20, fontSize: titleSize(beat.title, 39), lineHeight: 1.08, fontWeight: 780}}>{clean(beat.title)}</div><div style={{marginTop: 17, fontSize: 19, lineHeight: 1.35, color: C.silver}}>{clean(beat.sub)}</div></div>
      </div>
    </Shell>
  );
};

const Relation: React.FC<{beat: NodeBeat; local: number; bookmark?: boolean}> = ({beat, local, bookmark = false}) => {
  const left = panel(beat.payload?.left, beat.title, bookmark ? '索引' : '左侧');
  const right = panel(beat.payload?.right, beat.sub, bookmark ? '完整信息' : '右侧');
  return (
    <Shell>
      <div style={enter(reveal(local, 0))}><Kicker>{beat.eyebrow}</Kicker></div>
      <div style={{marginTop: 17, fontSize: titleSize(beat.title, 40), fontWeight: 760, letterSpacing: '-0.035em', ...enter(reveal(local, 7))}}>{clean(beat.title)}</div>
      <div style={{marginTop: 29, display: 'grid', gridTemplateColumns: '1fr 78px 1fr', alignItems: 'center', minHeight: 150}}>
        {[left, right].map((item, index) => (
          <React.Fragment key={`${beat.id}-${index}`}>
            <div style={{textAlign: index ? 'right' : 'left', ...enter(reveal(local, 17 + index * 52), index ? 14 : -14, 0)}}>
              <div style={{fontSize: 16, color: C.silver}}>{item.label}</div>
              <div style={{marginTop: 14, fontSize: 36, lineHeight: 1, fontWeight: 790, color: C.bright}}>{clean(item.title)}</div>
              <div style={{marginTop: 14, fontSize: 19, color: C.silver}}>{clean(item.sub)}</div>
            </div>
            {index === 0 ? <div style={{position: 'relative', height: 128, opacity: reveal(local, 43)}}><div style={{position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, background: C.lineStrong}} /><div style={{position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%,-50%)', fontSize: 28}}>{beat.payload?.operator || '→'}</div></div> : null}
          </React.Fragment>
        ))}
      </div>
      <div style={{height: 1, width: `${reveal(local, 91) * 100}%`, background: C.lineStrong}} />
      {bookmark ? <div style={{marginTop: 15, fontSize: 18, color: C.silver, ...enter(reveal(local, 98))}}>{clean(beat.payload?.footer || beat.sub)}</div> : null}
    </Shell>
  );
};

const Contrast: React.FC<{beat: NodeBeat; local: number}> = ({beat, local}) => {
  const left = panel(beat.payload?.left, beat.title, 'BEFORE');
  const right = panel(beat.payload?.right, beat.sub, 'AFTER');
  return (
    <Shell>
      <div style={enter(reveal(local, 0))}><Kicker>{beat.eyebrow}</Kicker></div>
      <div style={{marginTop: 17, fontSize: titleSize(beat.title, 40), fontWeight: 760, ...enter(reveal(local, 7))}}>{clean(beat.title)}</div>
      <div style={{marginTop: 25, paddingTop: 22, borderTop: `1px solid ${C.lineStrong}`, display: 'grid', gridTemplateColumns: '1fr 1px 1fr', gap: 27}}>
        <div style={enter(reveal(local, 20), -10, 0)}><div style={{fontFamily: en, fontSize: 13, color: C.mid}}>{left.label}</div><div style={{marginTop: 12, fontSize: 29, fontWeight: 690, color: C.silver}}>{clean(left.title)}</div><div style={{marginTop: 10, fontSize: 18, color: C.mid}}>{clean(left.sub)}</div></div>
        <div style={{height: 116, background: C.lineStrong, opacity: reveal(local, 40)}} />
        <div style={{textAlign: 'right', ...enter(reveal(local, 58), 10, 0)}}><div style={{fontFamily: en, fontSize: 13, color: C.silver}}>{right.label}</div><div style={{marginTop: 12, fontSize: 29, fontWeight: 790, color: C.bright}}>{clean(right.title)}</div><div style={{marginTop: 10, fontSize: 18, color: C.silver}}>{clean(right.sub)}</div></div>
      </div>
      <div style={{marginTop: 20, fontSize: 20, fontWeight: 650, ...enter(reveal(local, 82))}}>{clean(beat.payload?.footer || beat.sub)}</div>
    </Shell>
  );
};

const List: React.FC<{beat: NodeBeat; local: number}> = ({beat, local}) => {
  const items: MgItem[] = beat.payload?.items || beat.chips.map((label) => ({label}));
  const rowHeight = items.length >= 4 ? 48 : 58;
  return (
    <Shell top={164}>
      <div style={{display: 'flex', justifyContent: 'space-between'}}>
        <div style={enter(reveal(local, 0))}><Kicker>{beat.eyebrow}</Kicker><div style={{marginTop: 14, fontSize: titleSize(beat.title, 39), fontWeight: 760}}>{clean(beat.title)}</div></div>
        <div style={{fontFamily: number, fontSize: 72, lineHeight: 0.9, color: 'transparent', WebkitTextStroke: `1.4px ${C.silver}`, opacity: reveal(local, 8)}}>{String(items.length).padStart(2, '0')}</div>
      </div>
      <div style={{marginTop: 23, borderTop: `1px solid ${C.lineStrong}`}}>
        {items.map((item, index) => {
          const p = reveal(local, 10 + index * 18);
          return <div key={`${beat.id}-${index}`} style={{height: rowHeight, display: 'grid', gridTemplateColumns: '54px 1fr 150px', alignItems: 'center', borderBottom: `1px solid ${C.line}`, ...enter(p, 15, 0)}}><div style={{fontFamily: en, fontSize: 14, fontWeight: 700, color: C.silver}}>{String(index + 1).padStart(2, '0')}</div><div style={{fontSize: 22, fontWeight: index === items.length - 1 ? 740 : 610}}>{clean(item.label)}</div><div style={{fontSize: 15, textAlign: 'right', color: C.silver}}>{clean(item.note)}</div></div>;
        })}
      </div>
    </Shell>
  );
};

const Flow: React.FC<{beat: NodeBeat; local: number}> = ({beat, local}) => {
  const flow = beat.payload?.flow || beat.chips;
  return (
    <Shell>
      <div style={enter(reveal(local, 0))}><Kicker>{beat.eyebrow}</Kicker></div>
      <div style={{marginTop: 17, fontSize: titleSize(beat.title, 39), fontWeight: 760, ...enter(reveal(local, 7))}}>{clean(beat.title)}</div>
      <div style={{marginTop: 35, display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
        {flow.map((item, index) => <React.Fragment key={`${beat.id}-${index}`}><div style={{minWidth: 90, textAlign: 'center', ...enter(reveal(local, 18 + index * 20))}}><div style={{fontFamily: en, fontSize: 12, color: C.mid}}>{String(index + 1).padStart(2, '0')}</div><div style={{marginTop: 12, fontSize: flow.length >= 4 ? 17 : 21, fontWeight: index === flow.length - 1 ? 750 : 620, color: index === flow.length - 1 ? C.bright : C.silver}}>{clean(item)}</div></div>{index < flow.length - 1 ? <div style={{fontSize: 25, color: C.silver, opacity: reveal(local, 30 + index * 20)}}>→</div> : null}</React.Fragment>)}
      </div>
      <div style={{marginTop: 33, width: `${reveal(local, 72) * 100}%`, height: 1.5, background: C.lineStrong}} />
      <div style={{marginTop: 17, fontSize: 19, color: C.silver, ...enter(reveal(local, 85))}}>{clean(beat.sub)}</div>
    </Shell>
  );
};

const Prompt: React.FC<{beat: NodeBeat; local: number}> = ({beat, local}) => (
  <Shell>
    <div style={enter(reveal(local, 0))}><Kicker>{beat.eyebrow}</Kicker></div>
    <div style={{marginTop: 17, fontSize: 31, fontWeight: 620, color: C.silver, ...enter(reveal(local, 8))}}>{clean(beat.title)}</div>
    <div style={{marginTop: 18, fontSize: 61, lineHeight: 1, fontWeight: 900, letterSpacing: '-0.05em', ...enter(reveal(local, 20))}}>{clean(beat.payload?.quote || beat.title)}</div>
    <div style={{marginTop: 22, width: `${reveal(local, 36) * 100}%`, height: 1.5, background: C.white}} />
    <div style={{marginTop: 25, display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: C.silver}}>
      <div style={enter(reveal(local, 51), -10, 0)}>{clean(beat.payload?.left?.title || '旧方式')}</div>
      <div style={{fontSize: 31, opacity: reveal(local, 68)}}>→</div>
      <div style={{fontSize: 24, fontWeight: 750, color: C.bright, ...enter(reveal(local, 82), 10, 0)}}>{clean(beat.payload?.right?.title || '新方式')}</div>
    </div>
  </Shell>
);

export const AssemblyMonoHero: React.FC<{beat: NodeBeat}> = ({beat}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = Math.max(0, frame - Math.round(beat.start * fps));
  const variant: MgVariant = beat.variant || 'semantic_card';
  if (variant === 'chapter_title') return <Chapter beat={beat} local={local} />;
  if (variant === 'numeric_conclusion') return <Numeric beat={beat} local={local} />;
  if (variant === 'dual_relation') return <Relation beat={beat} local={local} />;
  if (variant === 'bookmark_relation') return <Relation beat={beat} local={local} bookmark />;
  if (variant === 'contrast_statement') return <Contrast beat={beat} local={local} />;
  if (variant === 'numbered_list') return <List beat={beat} local={local} />;
  if (variant === 'agent_flow') return <Flow beat={beat} local={local} />;
  if (variant === 'prompt_fact') return <Prompt beat={beat} local={local} />;
  return <Statement beat={beat} local={local} />;
};

export const AssemblyMonoContrastLayer: React.FC = () => (
  <>
    <div style={{position: 'absolute', left: 12, right: 12, top: 65, height: 112, background: 'radial-gradient(ellipse at 50% 48%, rgba(0,0,0,0.28) 0%, rgba(0,0,0,0.14) 54%, rgba(0,0,0,0) 82%)', filter: 'blur(12px)'}} />
    <div style={{position: 'absolute', left: 6, right: 6, top: 128, height: 390, background: 'radial-gradient(ellipse at 48% 34%, rgba(0,0,0,0.31) 0%, rgba(0,0,0,0.17) 50%, rgba(0,0,0,0) 82%)', filter: 'blur(18px)'}} />
  </>
);
