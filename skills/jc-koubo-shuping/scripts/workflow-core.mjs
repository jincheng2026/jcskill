import {existsSync, readFileSync, statSync} from 'node:fs';
import path from 'node:path';
import {commandText, ffprobeJson, parseSrtText, resolveManifestPath, skillDir, videoStream} from './lib.mjs';
import {validateCompiledSemanticPlan} from './semantic-core.mjs';
import {baselineForStyle, normalizeVisualStyle} from './style-core.mjs';

export const WORKFLOW_STAGES = [
  'intake',
  'subtitle_reviewed',
  'motion_map_ready',
  'static_preview_pending',
  'static_preview_accepted',
  'pilot_pending',
  'pilot_accepted',
  'full_rendered',
  'technical_pass',
  'final_release_accepted',
];

function readJson(file, label, failures) {
  try {
    return JSON.parse(readFileSync(file, 'utf8'));
  } catch (error) {
    failures.push(`${label} invalid JSON: ${file}: ${error.message}`);
    return null;
  }
}

function requireFile(caseDir, value, label, failures, pass) {
  const file = resolveManifestPath(caseDir, value);
  if (!value || !existsSync(file) || !statSync(file).isFile() || statSync(file).size === 0) {
    failures.push(`${label} missing or empty: ${file || value}`);
    return null;
  }
  pass.push(`${label} ok`);
  return file;
}

function requireImage(caseDir, value, label, failures, pass) {
  const file = requireFile(caseDir, value, label, failures, pass);
  if (!file) return null;
  try {
    const stream = videoStream(ffprobeJson(file));
    if (!stream || Number(stream.width) < 32 || Number(stream.height) < 32) {
      failures.push(`${label} is not a decodable image: ${file}`);
      return null;
    }
  } catch (error) {
    failures.push(`${label} image decode failed: ${file}: ${error.message}`);
    return null;
  }
  return file;
}

function requireVideo(caseDir, value, label, failures, pass, durationRange = null) {
  const file = requireFile(caseDir, value, label, failures, pass);
  if (!file) return null;
  try {
    const probe = ffprobeJson(file);
    const stream = videoStream(probe);
    const duration = Number(probe.format?.duration || stream?.duration || 0);
    if (!stream || !Number.isFinite(duration) || duration <= 0) failures.push(`${label} is not a decodable video: ${file}`);
    if (durationRange && (duration < durationRange[0] - 0.05 || duration > durationRange[1] + 0.05)) {
      failures.push(`${label} duration must be ${durationRange[0]}-${durationRange[1]}s, got ${duration.toFixed(3)}s`);
    }
  } catch (error) {
    failures.push(`${label} video decode failed: ${file}: ${error.message}`);
  }
  return file;
}

function sha256(file) {
  return commandText('shasum', ['-a', '256', file]).match(/\b[a-f0-9]{64}\b/iu)?.[0]?.toLowerCase();
}

function validateExternalDecision(caseDir, gate, label, expectedArtifact, failures, pass) {
  if (!['accepted', 'accepted_with_risks'].includes(gate?.decision)) failures.push(`${label}.decision must be accepted`);
  if (gate?.reviewerType !== 'human') failures.push(`${label}.reviewerType must be human`);
  if (!gate?.userStatement?.trim()) failures.push(`${label}.userStatement missing`);
  const evidence = gate?.evidence || {};
  if (evidence.source !== 'external_user_message') failures.push(`${label}.evidence.source must be external_user_message`);
  for (const key of ['threadId', 'messageId', 'recordedAt']) {
    if (!evidence[key]) failures.push(`${label}.evidence.${key} missing`);
  }
  if (evidence.recordedAt && !Number.isFinite(Date.parse(evidence.recordedAt))) failures.push(`${label}.evidence.recordedAt invalid`);
  const artifact = resolveManifestPath(caseDir, evidence.artifact);
  const expected = resolveManifestPath(caseDir, expectedArtifact);
  if (!evidence.artifact || !artifact || path.resolve(artifact) !== path.resolve(expected || '')) {
    failures.push(`${label}.evidence.artifact must equal the reviewed artifact`);
  } else if (!existsSync(artifact) || !statSync(artifact).isFile()) {
    failures.push(`${label}.evidence.artifact missing: ${artifact}`);
  } else {
    const actualSha = sha256(artifact);
    if (!evidence.sha256 || evidence.sha256.toLowerCase() !== actualSha) failures.push(`${label}.evidence.sha256 mismatch`);
    else pass.push(`${label} artifact SHA ok`);
  }
}

function validateHistory(workflow, stageIndex, failures, pass) {
  const history = workflow.history;
  if (!Array.isArray(history)) {
    failures.push('workflow.history must be an append-only array');
    return;
  }
  const expected = WORKFLOW_STAGES.slice(0, stageIndex + 1);
  const actual = history.map((item) => item?.stage);
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    failures.push(`workflow.history must contain every stage in order: expected=${expected.join('>')}, actual=${actual.join('>')}`);
    return;
  }
  let previous = 0;
  for (const [index, item] of history.entries()) {
    const timestamp = Date.parse(item?.at || '');
    if (!Number.isFinite(timestamp) || timestamp < previous) failures.push(`workflow.history[${index}].at invalid or out of order`);
    previous = timestamp;
  }
  if (workflow.stage !== actual[actual.length - 1]) failures.push('workflow.stage must equal the last history entry');
  else pass.push('workflow history ok');
}

function validateMotionMap(file, manifest, failures, warnings, pass) {
  const data = readJson(file, 'workflow.motionMap', failures);
  if (!data) return null;
  const result = validateCompiledSemanticPlan({manifest, motionMap: data});
  failures.push(...result.failures, ...result.unresolved.map((item) => `unresolved semantic risk ${item.id}: ${item.message}`));
  warnings.push(...result.warnings.map((item) => `${item.id}: ${item.message}`));
  if (!result.failures.length && !result.unresolved.length) pass.push(`motion map schema and risk overrides ok: ${data.beats.length} beats`);
  return data.beats;
}

function activeErrorIds() {
  const bank = JSON.parse(readFileSync(path.join(skillDir, 'evals', 'error-cases.json'), 'utf8'));
  return bank.cases.filter((item) => item.status === 'active').map((item) => item.id).sort();
}

function validateProgressChapters(manifest, failures, pass) {
  const chapters = manifest.progressChapters;
  if (chapters === undefined) {
    pass.push('progress defaults to unlabeled whole-video rail');
    return;
  }
  if (!Array.isArray(chapters) || chapters.length < 3 || chapters.length > 5) {
    failures.push(`progressChapters must contain 3-5 macro chapters, got ${Array.isArray(chapters) ? chapters.length : 'non-array'}`);
    return;
  }
  const duration = Number(manifest.video?.duration);
  const labels = [];
  for (const [index, chapter] of chapters.entries()) {
    const start = Number(chapter?.start);
    const end = Number(chapter?.end);
    const label = String(chapter?.label || '').trim();
    labels.push(label);
    if (!chapter?.id) failures.push(`progressChapters[${index}].id missing`);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) failures.push(`progressChapters[${index}] has invalid timing`);
    if (!label || label.replace(/\s/gu, '').length > 6) failures.push(`progressChapters[${index}].label must contain 1-6 visible characters`);
    if (index === 0 && Math.abs(start) > 0.001) failures.push('progressChapters must start at 0');
    if (index > 0 && Math.abs(start - Number(chapters[index - 1].end)) > 0.001) failures.push(`progressChapters[${index}] must be contiguous`);
  }
  if (new Set(labels).size !== labels.length) failures.push('progressChapters labels must be unique');
  if (Number.isFinite(duration) && Math.abs(Number(chapters[chapters.length - 1].end) - duration) > 0.001) failures.push('progressChapters must end at video.duration');
  if (!failures.some((item) => item.startsWith('progressChapters'))) pass.push(`progress chapters ok: ${chapters.length} macro chapters`);
}

export function validateWorkflow({caseDir, manifest, requiredStage = null}) {
  const failures = [];
  const warnings = [];
  const pass = [];
  const workflow = manifest.workflow || {};
  const stage = workflow.stage || 'intake';
  const stageIndex = WORKFLOW_STAGES.indexOf(stage);
  const atLeast = (name) => stageIndex >= WORKFLOW_STAGES.indexOf(name);
  if (Number(manifest.schemaVersion) !== 3) failures.push(`schemaVersion must equal 3; migrate legacy case before canonical workflow, got ${manifest.schemaVersion}`);
  const visualStyleId = normalizeVisualStyle(manifest.visualStyleId);
  if (!visualStyleId || visualStyleId !== manifest.visualStyleId) {
    failures.push('visualStyleId must be canonical: assembly-mono or google-semantic');
  } else if (workflow.baselineId !== baselineForStyle(visualStyleId)) {
    failures.push(`workflow.baselineId must match visualStyleId=${visualStyleId}: expected ${baselineForStyle(visualStyleId)}, got ${workflow.baselineId}`);
  } else {
    pass.push(`visual style locked: ${visualStyleId}`);
  }
  if (stageIndex === -1) failures.push(`invalid workflow.stage: ${stage}`);
  if (requiredStage && stageIndex < WORKFLOW_STAGES.indexOf(requiredStage)) {
    failures.push(`workflow.stage must be at least ${requiredStage}, got ${stage}`);
  }
  if (stageIndex >= 0) validateHistory(workflow, stageIndex, failures, pass);

  if (atLeast('subtitle_reviewed')) {
    const revised = requireFile(caseDir, workflow.subtitleReview?.revisedSrt, 'workflow.subtitleReview.revisedSrt', failures, pass);
    if (revised) {
      try {
        const cues = parseSrtText(readFileSync(revised, 'utf8'));
        if (!cues.length || cues.some((cue) => !cue.zh || cue.end <= cue.start)) failures.push('revised SRT contains invalid cues');
      } catch (error) {
        failures.push(`revised SRT parse failed: ${error.message}`);
      }
    }
    const diff = requireFile(caseDir, workflow.subtitleReview?.diff, 'workflow.subtitleReview.diff', failures, pass);
    if (diff) {
      const data = readJson(diff, 'workflow.subtitleReview.diff', failures);
      if (!Array.isArray(data?.changes)) failures.push('workflow.subtitleReview.diff must contain changes[]');
    }
  }
  if (atLeast('motion_map_ready')) {
    validateProgressChapters(manifest, failures, pass);
    if (workflow.planningMode !== 'semantic_manual') failures.push('workflow.planningMode must be semantic_manual');
    const file = requireFile(caseDir, workflow.motionMap, 'workflow.motionMap', failures, pass);
    const beats = file ? validateMotionMap(file, manifest, failures, warnings, pass) : null;
    const canonicalCompiler = path.join(skillDir, 'scripts', 'compile-motion-map.mjs');
    const canonicalCore = path.join(skillDir, 'scripts', 'semantic-core.mjs');
    const sourceMap = requireFile(caseDir, workflow.semanticPlan?.sourceMotionMap, 'workflow.semanticPlan.sourceMotionMap', failures, pass);
    if (workflow.semanticPlan?.compiler !== 'scripts/compile-motion-map.mjs') failures.push('workflow.semanticPlan.compiler must be the canonical compiler');
    if (workflow.semanticPlan?.compilerSha256 !== sha256(canonicalCompiler)) failures.push('workflow.semanticPlan.compilerSha256 does not match the canonical compiler');
    if (workflow.semanticPlan?.semanticCoreSha256 !== sha256(canonicalCore)) failures.push('workflow.semanticPlan.semanticCoreSha256 does not match semantic-core.mjs');
    if (!workflow.semanticPlan?.sourceMotionMapSha256 || (sourceMap && workflow.semanticPlan.sourceMotionMapSha256 !== sha256(sourceMap))) failures.push('workflow.semanticPlan.sourceMotionMapSha256 mismatch');
    if (!workflow.semanticPlan?.compiledMotionMapSha256 || (file && workflow.semanticPlan.compiledMotionMapSha256 !== sha256(file))) failures.push('workflow.semanticPlan.compiledMotionMapSha256 mismatch');
    if (workflow.renderBlockedReason) failures.push('workflow.renderBlockedReason must be cleared before canonical render');
    if (!workflow.baselineId) failures.push('workflow.baselineId missing');
    if (!Array.isArray(manifest.nodes) || manifest.nodes.length === 0) failures.push('manifest.nodes must contain the approved semantic beats');
    for (const [index, node] of (manifest.nodes || []).entries()) {
      if (String(node.title || '').replace(/\s/gu, '').length > 20) failures.push(`manifest.nodes[${index}].title exceeds 20 visible characters`);
      if (String(node.sub || '').replace(/\s/gu, '').length > 28) failures.push(`manifest.nodes[${index}].sub exceeds 28 visible characters`);
      if (!Number.isFinite(Number(node.start)) || !Number.isFinite(Number(node.end)) || Number(node.end) <= Number(node.start)) failures.push(`manifest.nodes[${index}] has invalid timing`);
    }
    if (beats && beats.length !== (manifest.nodes || []).length) failures.push('manifest.nodes must match motion-map beat count');
    for (const [index, beat] of (beats || []).entries()) {
      const node = manifest.nodes?.[index];
      if (!node || Math.abs(Number(node.start) - Number(beat.start)) > 0.001 || Math.abs(Number(node.end) - Number(beat.end)) > 0.001) {
        failures.push(`manifest.nodes[${index}] timing must match motion-map beat`);
      }
    }
    const captions = manifest.captionTrack || [];
    for (const [index, cue] of captions.entries()) {
      const expectedEnd = Math.min(Number(cue.end), Number(captions[index + 1]?.start ?? cue.end));
      if (Math.abs(Number(cue.displayEnd) - expectedEnd) > 0.001) failures.push(`captionTrack[${index}].displayEnd does not clamp overlap`);
    }
  }
  if (atLeast('static_preview_pending')) {
    const files = workflow.staticPreview?.files || [];
    if (files.length < 4 || files.length > 6) failures.push(`workflow.staticPreview.files must contain 4-6 images, got ${files.length}`);
    if (new Set(files).size !== files.length) failures.push('workflow.staticPreview.files must be unique');
    const decoded = files.map((file, index) => requireImage(caseDir, file, `workflow.staticPreview.files[${index}]`, failures, pass)).filter(Boolean);
    if (decoded.length === files.length && new Set(decoded.map(sha256)).size !== decoded.length) failures.push('workflow.staticPreview.files must have unique content');
    requireImage(caseDir, workflow.staticPreview?.contactSheet, 'workflow.staticPreview.contactSheet', failures, pass);
  }
  if (atLeast('static_preview_accepted')) {
    validateExternalDecision(caseDir, workflow.staticPreview, 'workflow.staticPreview', workflow.staticPreview?.contactSheet, failures, pass);
  }
  if (atLeast('pilot_pending')) {
    requireVideo(caseDir, workflow.pilot?.video, 'workflow.pilot.video', failures, pass, [10, 15]);
    for (const key of ['overview', 'animationRisk', 'captionRisk', 'safeZone']) {
      requireImage(caseDir, workflow.pilot?.contacts?.[key], `workflow.pilot.contacts.${key}`, failures, pass);
    }
  }
  if (atLeast('pilot_accepted')) {
    validateExternalDecision(caseDir, workflow.pilot, 'workflow.pilot', workflow.pilot?.video, failures, pass);
    if (!workflow.pilot?.baselineId || workflow.pilot.baselineId !== workflow.baselineId) failures.push('pilot baseline must equal workflow.baselineId');
  }
  if (atLeast('full_rendered')) {
    if (!workflow.fullBuild?.baselineId || workflow.fullBuild.baselineId !== workflow.baselineId) failures.push('full build baseline must equal workflow.baselineId');
    const requiredIds = activeErrorIds();
    const applied = Array.isArray(manifest.errorBank?.applied) ? [...manifest.errorBank.applied].sort() : [];
    const unknown = applied.filter((id) => !requiredIds.includes(id));
    const missing = requiredIds.filter((id) => !applied.includes(id));
    if (unknown.length) failures.push(`errorBank.applied contains unknown IDs: ${unknown.join(', ')}`);
    if (missing.length) failures.push(`errorBank.applied missing active IDs: ${missing.join(', ')}`);
    const reportFile = requireFile(caseDir, manifest.errorBank?.regressionReport, 'errorBank.regressionReport', failures, pass);
    if (reportFile) {
      const report = readJson(reportFile, 'errorBank.regressionReport', failures);
      if (report?.result !== 'pass') failures.push('errorBank.regressionReport result must be pass');
      const passed = [...(report?.passed || [])].sort();
      if (JSON.stringify(passed) !== JSON.stringify(requiredIds)) failures.push('errorBank.regressionReport must pass every active ID');
    }
  }
  if (atLeast('technical_pass')) {
    const technical = requireFile(caseDir, manifest.qa?.technicalValidation, 'qa.technicalValidation', failures, pass);
    if (technical) {
      const report = readJson(technical, 'qa.technicalValidation', failures);
      if (report?.result !== 'technical_pass_pending_acceptance') failures.push('qa.technicalValidation does not prove technical pass');
    }
  }
  if (stage === 'final_release_accepted') {
    validateExternalDecision(caseDir, workflow.finalAcceptance, 'workflow.finalAcceptance', manifest.finalVideo, failures, pass);
  }
  return {result: failures.length === 0 ? 'pass' : 'fail', stage, pass, warnings, failures};
}

export function appendWorkflowStage(workflow, stage, at = new Date().toISOString()) {
  const currentIndex = WORKFLOW_STAGES.indexOf(workflow.stage);
  const nextIndex = WORKFLOW_STAGES.indexOf(stage);
  if (nextIndex !== currentIndex + 1) throw new Error(`illegal workflow transition: ${workflow.stage} -> ${stage}`);
  workflow.stage = stage;
  workflow.history = [...(workflow.history || []), {stage, at}];
}
