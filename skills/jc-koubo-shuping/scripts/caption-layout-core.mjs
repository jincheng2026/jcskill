export const CAPTION_LAYOUT = {
  width720: 636,
  zhFontSizes720: [54, 48, 42, 38],
  enFontSizes720: [25, 23, 21, 19],
  maxLines: 1,
  englishRequired: true,
  separateLanguagePlates: true,
};

function unit(character) {
  if (/\s/u.test(character)) return 0.3;
  if (/[\u0000-\u00ff]/u.test(character)) return 0.58;
  if (/[，。！？；：、,.!?;:（）()《》「」『』【】]/u.test(character)) return 0.56;
  return 1;
}

export function textUnits(text) {
  return Array.from(String(text || '')).reduce((total, character) => total + unit(character), 0);
}

function fitSingleLine(text, fontSizes) {
  const normalized = String(text || '').trim();
  for (const fontSize of fontSizes) {
    const maxUnits = CAPTION_LAYOUT.width720 / fontSize / 1.08;
    if (normalized && textUnits(normalized) <= maxUnits) {
      return {text: normalized, fontSize, lines: [normalized], overflow: false, maxUnits};
    }
  }
  const fontSize = fontSizes.at(-1);
  return {
    text: normalized,
    fontSize,
    lines: normalized ? [normalized] : [],
    overflow: true,
    maxUnits: CAPTION_LAYOUT.width720 / fontSize / 1.08,
  };
}

export function fitCaptionText(text) {
  return fitSingleLine(text, CAPTION_LAYOUT.zhFontSizes720);
}

export function fitEnglishText(text) {
  return fitSingleLine(text, CAPTION_LAYOUT.enFontSizes720);
}

export function analyzeCaptionTrack(captions = []) {
  const items = captions.map((cue) => {
    const zh = fitCaptionText(cue.zh);
    const en = fitEnglishText(cue.en);
    const missingEnglish = !String(cue.en || '').trim();
    const severity = zh.overflow || en.overflow || missingEnglish ? 'P1' : 'pass';
    return {
      id: cue.id,
      text: cue.zh,
      enText: cue.en || '',
      severity,
      missingEnglish,
      fontSize: zh.fontSize,
      lines: zh.lines,
      overflow: zh.overflow,
      maxUnits: zh.maxUnits,
      enFontSize: en.fontSize,
      enLines: en.lines,
      enOverflow: en.overflow,
      enMaxUnits: en.maxUnits,
    };
  });
  const failures = items.filter((item) => item.severity === 'P1');
  return {
    result: failures.length ? 'fail' : 'pass',
    policy: CAPTION_LAYOUT,
    summary: {cues: items.length, p1: failures.length, bilingual: items.filter((item) => !item.missingEnglish).length},
    failures,
    items,
  };
}
