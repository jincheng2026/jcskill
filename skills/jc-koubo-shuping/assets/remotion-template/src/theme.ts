import type {AccentName} from './types';
import mgLayout from './mg-layout.json';

export const CANVAS = {
  width: 720,
  height: 1280,
  fps: 30,
  durationInFrames: 120,
};

export const COLORS = {
  ink: '#F8FAFD',
  muted: 'rgba(248,250,253,0.74)',
  cardMuted: 'rgba(232,234,237,0.78)',
  rail: 'rgba(248,250,253,0.18)',
  blue: '#4285F4',
  red: '#EA4335',
  yellow: '#FBBC05',
  green: '#34A853',
};

export const ACCENT: Record<AccentName, string> = {
  blue: COLORS.blue,
  red: COLORS.red,
  yellow: COLORS.yellow,
  green: COLORS.green,
};

export const FONT = {
  zh: '"Noto Sans SC", "PingFang SC", "Hiragino Sans GB", Arial, sans-serif',
  en: '"JetBrains Mono", "SFMono-Regular", Menlo, Consolas, monospace',
};

export const LAYOUT = {
  progressTop: 104,
  cardTop: 160,
  cardLeft: 30,
  cardWidth: 660,
  cardHeight: 166,
  captionLeft: 42,
  captionTop: 890,
  captionWidth: 636,
  captionHeight: 264,
};

export const MG_LAYOUT = mgLayout;

export const googleGradient = `linear-gradient(90deg, ${COLORS.blue} 0%, ${COLORS.red} 13%, ${COLORS.yellow} 27%, ${COLORS.green} 41%, ${COLORS.blue} 56%, ${COLORS.red} 70%, ${COLORS.yellow} 84%, ${COLORS.green} 100%)`;
