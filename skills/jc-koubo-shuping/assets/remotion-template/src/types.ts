export type AccentName = 'blue' | 'red' | 'yellow' | 'green';
export type VisualStyleId = 'assembly-mono' | 'google-semantic';

export type MgVariant =
  | 'semantic_card'
  | 'chapter_title'
  | 'contrast_statement'
  | 'numbered_list'
  | 'prompt_fact'
  | 'dual_relation'
  | 'bookmark_relation'
  | 'agent_flow'
  | 'numeric_conclusion';

export type MgItem = {
  label: string;
  note?: string;
};

export type MgPanel = {
  label?: string;
  title: string;
  sub?: string;
};

export type MgPayload = {
  items?: MgItem[];
  quote?: string;
  left?: MgPanel;
  right?: MgPanel;
  operator?: '+' | '→' | 'vs';
  footer?: string;
  value?: string;
  unit?: string;
  flow?: string[];
  tag?: string;
};

export type CaptionCue = {
  id: string;
  sourceCueId?: string;
  start: number;
  end: number;
  startFrame?: number;
  endFrame?: number;
  displayEnd?: number;
  zh: string;
  highlights?: string[];
  en?: string;
};

export type NodeBeat = {
  id: string;
  start: number;
  end: number;
  label: string;
  eyebrow: string;
  title: string;
  sub: string;
  chips: string[];
  accent: AccentName;
  variant?: MgVariant;
  payload?: MgPayload;
};

export type ProgressChapter = {
  id: string;
  start: number;
  end: number;
  label: string;
};

export type CaseManifest = {
  caseId: string;
  visualStyleId?: VisualStyleId;
  title?: string;
  video?: {
    width?: number;
    height?: number;
    fps?: number;
    duration?: number;
    frameCount?: number;
  };
  qualityProfile?: {
    output?: {width?: number; height?: number};
  };
  nodes?: NodeBeat[];
  progressChapters?: ProgressChapter[];
  captionTrack?: CaptionCue[];
};

export type OverlayProps = {
  manifest?: CaseManifest;
};
