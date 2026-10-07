import {readFileSync} from 'node:fs';

const MOTION_MAP_SCHEMA = 'jc-koubo-shuping.motion-map.v3';
const mgLayout = JSON.parse(readFileSync(new URL('../assets/remotion-template/src/mg-layout.json', import.meta.url), 'utf8'));
const argumentTypes = new Set(['hook', 'claim', 'mechanism', 'evidence', 'contrast', 'action', 'cta']);
const boundaryTypes = new Set(['opening', 'claim_change', 'mechanism', 'evidence', 'contrast', 'action', 'cta']);
const semanticFields = ['semantic_function', 'viewer_need', 'trigger_rule', 'hero_visual', 'caption_policy', 'sound_cue', 'layout_risk'];
const mgCopyFields = ['label', 'eyebrow', 'title', 'sub', 'chips', 'accent'];
const mgVariants = new Set(Object.keys(mgLayout.variants));
const payloadRequired = new Set(['contrast_statement', 'numbered_list', 'prompt_fact', 'dual_relation', 'bookmark_relation', 'agent_flow', 'numeric_conclusion']);
const genericCopy = new Set([
  '关注核心问题', '找到正确方向', '马上采取行动', '提高你的效率', '真实素材', '马上动手',
  '抓住重点', '关键一步', '开始行动', '重要提醒', '核心逻辑', '底层逻辑',
]);
const placeholders = new Set(['x', 'xx', 'xxx', 'todo', 'tbd', 'placeholder', '待补充', '待定', '占位']);

export function cleanText(value) {
  return String(value || '').normalize('NFKC').replace(/[\p{Cf}\uFE00-\uFE0F\u{E0100}-\u{E01EF}]/gu, '').replace(/\s+/gu, ' ').trim();
}

function fingerprint(value) {
  return cleanText(value).replace(/[\s\p{P}\p{S}]+/gu, '').toLowerCase();
}

function visibleLength(value) {
  return cleanText(value).replace(/\s/gu, '').length;
}

function meaningful(value) {
  const text = cleanText(value);
  return /[\p{L}\p{N}]/u.test(text) && !placeholders.has(fingerprint(text));
}

function normalizePanel(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return value;
  return {
    ...(value.label !== undefined ? {label: cleanText(value.label)} : {}),
    title: cleanText(value.title),
    ...(value.sub !== undefined ? {sub: cleanText(value.sub)} : {}),
  };
}

function normalizePayload(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return value;
  return {
    ...(Array.isArray(value.items) ? {items: value.items.map((item) => ({
      label: cleanText(item?.label),
      ...(item?.note !== undefined ? {note: cleanText(item.note)} : {}),
    }))} : {}),
    ...(value.quote !== undefined ? {quote: cleanText(value.quote)} : {}),
    ...(value.left !== undefined ? {left: normalizePanel(value.left)} : {}),
    ...(value.right !== undefined ? {right: normalizePanel(value.right)} : {}),
    ...(value.operator !== undefined ? {operator: cleanText(value.operator)} : {}),
    ...(value.footer !== undefined ? {footer: cleanText(value.footer)} : {}),
    ...(value.value !== undefined ? {value: cleanText(value.value)} : {}),
    ...(value.unit !== undefined ? {unit: cleanText(value.unit)} : {}),
    ...(Array.isArray(value.flow) ? {flow: value.flow.map(cleanText)} : {}),
    ...(value.tag !== undefined ? {tag: cleanText(value.tag)} : {}),
  };
}

function validatePanel(value, prefix, failures) {
  const limits = mgLayout.limits;
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    failures.push(`${prefix} must be an object`);
    return;
  }
  if (!meaningful(value.title)) failures.push(`${prefix}.title must contain meaningful text`);
  if (visibleLength(value.title) > limits.panelTitleMax) failures.push(`${prefix}.title exceeds ${limits.panelTitleMax} visible characters`);
  if (value.label !== undefined && (!meaningful(value.label) || visibleLength(value.label) > limits.panelLabelMax)) failures.push(`${prefix}.label is invalid or exceeds ${limits.panelLabelMax} visible characters`);
  if (value.sub !== undefined && (!meaningful(value.sub) || visibleLength(value.sub) > limits.panelSubMax)) failures.push(`${prefix}.sub is invalid or exceeds ${limits.panelSubMax} visible characters`);
}

function validateVariantPayload(copy, prefix, failures) {
  const variant = cleanText(copy.variant || 'semantic_card');
  const limits = mgLayout.limits;
  if (!mgVariants.has(variant)) {
    failures.push(`${prefix}.mg_copy.variant invalid: ${variant}`);
    return;
  }
  const payload = copy.payload;
  if (payloadRequired.has(variant) && (!payload || typeof payload !== 'object' || Array.isArray(payload))) {
    failures.push(`${prefix}.mg_copy.payload required for ${variant}`);
    return;
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return;
  if (variant === 'contrast_statement' || variant === 'dual_relation' || variant === 'bookmark_relation' || variant === 'prompt_fact') {
    validatePanel(payload.left, `${prefix}.mg_copy.payload.left`, failures);
    validatePanel(payload.right, `${prefix}.mg_copy.payload.right`, failures);
  }
  if (variant === 'numbered_list') {
    const items = Array.isArray(payload.items) ? payload.items : [];
    if (items.length < limits.itemCountMin || items.length > limits.itemCountMax) failures.push(`${prefix}.mg_copy.payload.items must contain ${limits.itemCountMin}-${limits.itemCountMax} items`);
    for (const [index, item] of items.entries()) {
      if (!meaningful(item?.label) || visibleLength(item?.label) > limits.itemLabelMax) failures.push(`${prefix}.mg_copy.payload.items[${index}].label is invalid or exceeds ${limits.itemLabelMax} visible characters`);
      if (item?.note !== undefined && (!meaningful(item.note) || visibleLength(item.note) > limits.itemNoteMax)) failures.push(`${prefix}.mg_copy.payload.items[${index}].note is invalid or exceeds ${limits.itemNoteMax} visible characters`);
    }
  }
  if (variant === 'prompt_fact' && (!meaningful(payload.quote) || visibleLength(payload.quote) > limits.quoteMax)) failures.push(`${prefix}.mg_copy.payload.quote is invalid or exceeds ${limits.quoteMax} visible characters`);
  if (variant === 'bookmark_relation' && (!meaningful(payload.footer) || visibleLength(payload.footer) > limits.footerMax)) failures.push(`${prefix}.mg_copy.payload.footer is invalid or exceeds ${limits.footerMax} visible characters`);
  if (variant === 'agent_flow') {
    const flow = Array.isArray(payload.flow) ? payload.flow : [];
    if (flow.length < limits.flowCountMin || flow.length > limits.flowCountMax) failures.push(`${prefix}.mg_copy.payload.flow must contain ${limits.flowCountMin}-${limits.flowCountMax} items`);
    for (const [index, item] of flow.entries()) if (!meaningful(item) || visibleLength(item) > limits.flowItemMax) failures.push(`${prefix}.mg_copy.payload.flow[${index}] is invalid or exceeds ${limits.flowItemMax} visible characters`);
  }
  if (variant === 'numeric_conclusion') {
    if (!meaningful(payload.value) || visibleLength(payload.value) > limits.valueMax) failures.push(`${prefix}.mg_copy.payload.value is invalid or exceeds ${limits.valueMax} visible characters`);
    if (!meaningful(payload.unit) || visibleLength(payload.unit) > limits.unitMax) failures.push(`${prefix}.mg_copy.payload.unit is invalid or exceeds ${limits.unitMax} visible characters`);
  }
  if (payload.operator !== undefined && !new Set(['+', '→', 'vs']).has(payload.operator)) failures.push(`${prefix}.mg_copy.payload.operator must be +, →, or vs`);
}

function asciiTokens(value) {
  return cleanText(value).match(/[A-Za-z][A-Za-z0-9+#.-]*/gu)?.map((token) => token.toLowerCase()) || [];
}

function bigrams(value) {
  const text = fingerprint(value);
  if (text.length < 2) return new Set(text ? [text] : []);
  return new Set(Array.from({length: text.length - 1}, (_, index) => text.slice(index, index + 2)));
}

function similarity(left, right) {
  const a = bigrams(left);
  const b = bigrams(right);
  if (!a.size || !b.size) return 0;
  const intersection = [...a].filter((item) => b.has(item)).length;
  return intersection / (a.size + b.size - intersection);
}

function formatTime(seconds) {
  const value = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(value / 60);
  const secs = value - minutes * 60;
  return `${String(minutes).padStart(2, '0')}:${secs.toFixed(3).padStart(6, '0')}`;
}

function warning(id, code, message, beatId = null) {
  return {id, code, beatId, message};
}

function validateArgumentMap(argumentMap, failures) {
  if (!argumentMap || typeof argumentMap !== 'object') {
    failures.push('motion map argument_map missing');
    return new Map();
  }
  for (const field of ['core_claim', 'audience_problem', 'ending_action']) {
    if (!meaningful(argumentMap[field])) failures.push(`motion map argument_map.${field} must contain meaningful text`);
  }
  const progression = Array.isArray(argumentMap.progression) ? argumentMap.progression : [];
  if (!progression.length) failures.push('motion map argument_map.progression must be non-empty');
  const result = new Map();
  for (const [index, item] of progression.entries()) {
    const prefix = `motion map argument_map.progression[${index}]`;
    const id = cleanText(item?.id);
    if (!id) failures.push(`${prefix}.id missing`);
    else if (result.has(id)) failures.push(`${prefix}.id duplicated: ${id}`);
    if (!argumentTypes.has(item?.type)) failures.push(`${prefix}.type invalid`);
    if (!meaningful(item?.claim)) failures.push(`${prefix}.claim must contain meaningful text`);
    if (id) result.set(id, item);
  }
  return result;
}

function expectedBeatEvidence(manifest, beats, failures) {
  const captions = Array.isArray(manifest.captionTrack) ? manifest.captionTrack : [];
  const byId = new Map(captions.map((cue, index) => [String(cue.id), {cue, index}]));
  let cursor = 0;
  const evidence = [];
  for (const [beatIndex, beat] of beats.entries()) {
    const prefix = `motion map beats[${beatIndex}]`;
    const cueIds = Array.isArray(beat?.cue_ids) ? beat.cue_ids.map(String) : [];
    if (!cueIds.length) failures.push(`${prefix}.cue_ids must be non-empty`);
    const cues = [];
    for (const cueId of cueIds) {
      const found = byId.get(cueId);
      if (!found) {
        failures.push(`${prefix}.cue_ids references unknown cue ${cueId}`);
        continue;
      }
      if (found.index !== cursor) failures.push(`${prefix}.cue_ids must form an ordered exact partition; expected ${captions[cursor]?.id || 'end'}, got ${cueId}`);
      cursor = Math.max(cursor, found.index + 1);
      cues.push(found.cue);
    }
    evidence.push(cues);
  }
  if (cursor !== captions.length) failures.push(`motion map cue coverage incomplete: covered ${cursor}/${captions.length}`);
  return evidence;
}

export function compileNodesFromMotionMap(motionMap) {
  return (motionMap?.beats || []).map((beat) => {
    const node = {
      id: cleanText(beat.id),
      start: Number(beat.start),
      end: Number(beat.end),
      ...Object.fromEntries(mgCopyFields.map((field) => [field, beat.mg_copy?.[field]])),
    };
    if (beat.mg_copy?.variant) node.variant = cleanText(beat.mg_copy.variant);
    if (beat.mg_copy?.payload) node.payload = normalizePayload(beat.mg_copy.payload);
    return node;
  });
}

export function buildCompiledMotionMap({manifest, source}) {
  const failures = [];
  if (Number(manifest.schemaVersion) !== 3) failures.push(`schemaVersion must equal 3, got ${manifest.schemaVersion}`);
  if (!source || typeof source !== 'object' || Array.isArray(source)) failures.push('source motion map must be an object');
  const beats = Array.isArray(source?.beats) ? source.beats : [];
  if (!beats.length) failures.push('source motion map beats must be non-empty');
  validateArgumentMap(source?.argument_map, failures);
  const evidence = expectedBeatEvidence(manifest, beats, failures);
  if (failures.length) return {compiled: null, failures};
  const videoDuration = Number(manifest.video?.duration || manifest.captionTrack?.at(-1)?.end || 0);
  const compiledBeats = beats.map((beat, index) => {
    const cues = evidence[index];
    const start = index === 0 ? 0 : Number(cues[0]?.start);
    const nextCueId = beats[index + 1]?.cue_ids?.[0];
    const nextCue = manifest.captionTrack.find((cue) => String(cue.id) === String(nextCueId));
    const end = index === beats.length - 1 ? videoDuration : Number(nextCue?.start);
    const normalizedCopy = beat.mg_copy && typeof beat.mg_copy === 'object' ? {
      ...beat.mg_copy,
      label: cleanText(beat.mg_copy.label),
      eyebrow: cleanText(beat.mg_copy.eyebrow),
      title: cleanText(beat.mg_copy.title),
      sub: cleanText(beat.mg_copy.sub),
      chips: Array.isArray(beat.mg_copy.chips) ? beat.mg_copy.chips.map(cleanText) : beat.mg_copy.chips,
      accent: cleanText(beat.mg_copy.accent),
      ...(beat.mg_copy.variant !== undefined ? {variant: cleanText(beat.mg_copy.variant)} : {}),
      ...(beat.mg_copy.payload !== undefined ? {payload: normalizePayload(beat.mg_copy.payload)} : {}),
    } : beat.mg_copy;
    return {
      ...beat,
      id: cleanText(beat.id),
      argument_id: cleanText(beat.argument_id),
      boundary: beat.boundary ? {type: cleanText(beat.boundary.type), change: cleanText(beat.boundary.change)} : beat.boundary,
      ...Object.fromEntries(semanticFields.map((field) => [field, Array.isArray(beat[field]) ? beat[field] : cleanText(beat[field])])),
      mg_copy: normalizedCopy,
      start: Number(start.toFixed(3)),
      end: Number(end.toFixed(3)),
      timecode: `${formatTime(start)}-${formatTime(end)}`,
      spoken_line: cues.map((cue) => cleanText(cue.zh)).filter(Boolean).join(' '),
    };
  });
  const riskOverrides = Array.isArray(source.risk_overrides) ? source.risk_overrides.map((item) => ({id: cleanText(item?.id), reason: cleanText(item?.reason)})) : [];
  return {compiled: {...source, schemaVersion: MOTION_MAP_SCHEMA, risk_overrides: riskOverrides, beats: compiledBeats}, failures: []};
}

export function validateCompiledSemanticPlan({manifest, motionMap}) {
  const failures = [];
  const warnings = [];
  if (Number(manifest.schemaVersion) !== 3) failures.push(`schemaVersion must equal 3, got ${manifest.schemaVersion}`);
  if (motionMap?.schemaVersion !== MOTION_MAP_SCHEMA) failures.push(`motion map schemaVersion must equal ${MOTION_MAP_SCHEMA}`);
  const argumentsById = validateArgumentMap(motionMap?.argument_map, failures);
  const beats = Array.isArray(motionMap?.beats) ? motionMap.beats : [];
  if (!beats.length) failures.push('motion map beats must be non-empty');
  const evidence = expectedBeatEvidence(manifest, beats, failures);
  const ids = new Set();
  const titleKeys = new Map();
  const chipKeys = new Map();
  const durations = [];
  const usedArguments = new Set();

  for (const [index, beat] of beats.entries()) {
    const prefix = `motion map beats[${index}]`;
    const id = cleanText(beat?.id);
    if (!id) failures.push(`${prefix}.id missing`);
    else if (ids.has(id)) failures.push(`${prefix}.id duplicated: ${id}`);
    ids.add(id);
    const cues = evidence[index] || [];
    if (cues.length) {
      const expectedStart = index === 0 ? 0 : Number(cues[0].start);
      const nextCueId = beats[index + 1]?.cue_ids?.[0];
      const nextCue = manifest.captionTrack?.find((cue) => String(cue.id) === String(nextCueId));
      const expectedEnd = index === beats.length - 1 ? Number(manifest.video?.duration) : Number(nextCue?.start);
      const expectedSpoken = cues.map((cue) => cleanText(cue.zh)).filter(Boolean).join(' ');
      if (Math.abs(Number(beat.start) - expectedStart) > 0.001 || Math.abs(Number(beat.end) - expectedEnd) > 0.001) failures.push(`${prefix} timing must be compiler-derived from cue_ids`);
      if (cleanText(beat.spoken_line) !== expectedSpoken) failures.push(`${prefix}.spoken_line must be compiler-derived from cue_ids`);
    }
    const duration = Number(beat.end) - Number(beat.start);
    if (!Number.isFinite(duration) || duration <= 0) failures.push(`${prefix} duration invalid`);
    else {
      durations.push(duration);
      if (duration < 3 || duration > 10) warnings.push(warning(`duration_outlier:${id}`, 'duration_outlier', `${prefix} duration ${duration.toFixed(3)}s is outside the preferred 3-10s range`, id));
    }
    const argumentId = cleanText(beat.argument_id);
    if (!argumentsById.has(argumentId)) failures.push(`${prefix}.argument_id must reference argument_map.progression`);
    else usedArguments.add(argumentId);
    if (!boundaryTypes.has(beat?.boundary?.type)) failures.push(`${prefix}.boundary.type invalid`);
    if (!meaningful(beat?.boundary?.change)) failures.push(`${prefix}.boundary.change must explain the semantic change`);
    for (const field of semanticFields) if (!meaningful(beat?.[field])) failures.push(`${prefix}.${field} must contain meaningful text`);
    if (Array.isArray(beat.hero_visual) && beat.hero_visual.length > 1) failures.push(`${prefix} has more than one hero`);

    const copy = beat?.mg_copy;
    if (!copy || typeof copy !== 'object') {
      failures.push(`${prefix}.mg_copy missing`);
      continue;
    }
    for (const field of mgCopyFields) {
      if (field === 'chips') {
        if (!Array.isArray(copy.chips) || copy.chips.length < 1 || copy.chips.length > 3) failures.push(`${prefix}.mg_copy.chips must contain 1-3 items`);
        for (const [chipIndex, chip] of (copy.chips || []).entries()) {
          if (!meaningful(chip)) failures.push(`${prefix}.mg_copy.chips[${chipIndex}] must contain meaningful text`);
          if (visibleLength(chip) > 10) failures.push(`${prefix}.mg_copy.chips[${chipIndex}] exceeds 10 visible characters`);
        }
      } else if (!meaningful(copy[field])) failures.push(`${prefix}.mg_copy.${field} must contain meaningful text`);
    }
    if (visibleLength(copy.label) > 8) failures.push(`${prefix}.mg_copy.label exceeds 8 visible characters`);
    if (visibleLength(copy.eyebrow) > 24) failures.push(`${prefix}.mg_copy.eyebrow exceeds 24 visible characters`);
    if (visibleLength(copy.title) > 20) failures.push(`${prefix}.mg_copy.title exceeds 20 visible characters`);
    if (visibleLength(copy.sub) > 28) failures.push(`${prefix}.mg_copy.sub exceeds 28 visible characters`);
    if (fingerprint(copy.title) && fingerprint(copy.title) === fingerprint(copy.sub)) failures.push(`${prefix} title and sub must not repeat`);
    validateVariantPayload(copy, prefix, failures);

    const titleKey = fingerprint(copy.title);
    if (titleKeys.has(titleKey)) warnings.push(warning(`repeated_title:${id}`, 'repeated_title', `${prefix}.mg_copy.title repeats beat ${titleKeys.get(titleKey)}`, id));
    else if (titleKey) titleKeys.set(titleKey, id);
    const chipsKey = Array.isArray(copy.chips) ? copy.chips.map(fingerprint).sort().join('|') : '';
    if (chipKeys.has(chipsKey)) warnings.push(warning(`repeated_chips:${id}`, 'repeated_chips', `${prefix}.mg_copy.chips repeats beat ${chipKeys.get(chipsKey)}`, id));
    else if (chipsKey) chipKeys.set(chipsKey, id);
    if (genericCopy.has(cleanText(copy.title)) || genericCopy.has(cleanText(copy.sub))) warnings.push(warning(`generic_copy:${id}`, 'generic_copy', `${prefix} contains generic reusable copy`, id));
    for (let earlier = 0; earlier < index; earlier += 1) {
      const score = similarity(`${copy.title}${copy.sub}`, `${beats[earlier]?.mg_copy?.title || ''}${beats[earlier]?.mg_copy?.sub || ''}`);
      if (score >= 0.82) warnings.push(warning(`near_duplicate_copy:${id}`, 'near_duplicate_copy', `${prefix} is ${score.toFixed(2)} similar to beat ${beats[earlier]?.id}`, id));
    }
    const evidenceTokens = new Set(asciiTokens(beat.spoken_line));
    const copyTokens = asciiTokens([copy.title, copy.sub, ...(copy.chips || []), JSON.stringify(copy.payload || {})].join(' '));
    for (const token of copyTokens) {
      if (evidenceTokens.has(token)) continue;
      const longer = [...evidenceTokens].find((candidate) => candidate.length > token.length && candidate.startsWith(token));
      if (longer) failures.push(`${prefix}.mg_copy contains clipped ASCII token ${token}; evidence contains ${longer}`);
    }
  }
  for (const argumentId of argumentsById.keys()) if (!usedArguments.has(argumentId)) warnings.push(warning(`unused_argument:${argumentId}`, 'unused_argument', `argument ${argumentId} is not mapped to any beat`));
  if (durations.length >= 3) {
    const mean = durations.reduce((sum, value) => sum + value, 0) / durations.length;
    const variance = durations.reduce((sum, value) => sum + (value - mean) ** 2, 0) / durations.length;
    if (Math.sqrt(variance) / mean < 0.05) warnings.push(warning('near_equal_duration:global', 'near_equal_duration', 'beat durations are suspiciously uniform; confirm semantic boundaries'));
  }
  const overrides = new Map((motionMap?.risk_overrides || []).map((item) => [cleanText(item?.id), cleanText(item?.reason)]));
  for (const id of overrides.keys()) if (!warnings.some((item) => item.id === id)) failures.push(`risk override references unknown warning: ${id}`);
  const unresolved = warnings.filter((item) => !meaningful(overrides.get(item.id)) || visibleLength(overrides.get(item.id)) < 6);
  const expectedNodes = compileNodesFromMotionMap(motionMap);
  if (JSON.stringify(manifest.nodes || []) !== JSON.stringify(expectedNodes)) failures.push('manifest.nodes must exactly match compiler-derived motion-map nodes');
  return {failures, warnings, unresolved, expectedNodes};
}

export const semanticMotionMapSchema = MOTION_MAP_SCHEMA;
