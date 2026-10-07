export const VISUAL_STYLES = Object.freeze({
  'assembly-mono': Object.freeze({
    id: 'assembly-mono',
    label: '黑白 Assembly',
    baselineId: '0726-approved-assembly-mono-v1',
    aliases: ['assembly', 'assembly mono', 'mono', 'monochrome', 'black white', 'black-and-white', '黑白', '黑白版', '黑白 assembly', '苹果黑白'],
  }),
  'google-semantic': Object.freeze({
    id: 'google-semantic',
    label: 'Google 语义配色',
    baselineId: '0721-approved-baseline-v4-multi-mg',
    aliases: ['google', 'google semantic', 'google color', '谷歌', '谷歌配色', '彩色', '语义配色', 'google 语义配色'],
  }),
});

export const STYLE_SELECTION_QUESTION = '这条用「黑白 Assembly」还是「Google 语义配色」？';

function key(value) {
  return String(value || '').trim().toLowerCase().replace(/[_-]+/gu, ' ').replace(/\s+/gu, ' ');
}

export function normalizeVisualStyle(value) {
  const normalized = key(value);
  if (!normalized) return null;
  for (const style of Object.values(VISUAL_STYLES)) {
    if (key(style.id) === normalized || style.aliases.some((alias) => key(alias) === normalized)) return style.id;
  }
  return null;
}

export function requireVisualStyle(value) {
  const styleId = normalizeVisualStyle(value);
  if (!styleId) {
    const suffix = value ? `；无法识别：${value}` : '';
    throw new Error(`VISUAL_STYLE_REQUIRED: ${STYLE_SELECTION_QUESTION}${suffix}`);
  }
  return styleId;
}

export function styleDefinition(value) {
  return VISUAL_STYLES[requireVisualStyle(value)];
}

export function baselineForStyle(value) {
  return styleDefinition(value).baselineId;
}
