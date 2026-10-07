#!/usr/bin/env node

import {createHash} from 'node:crypto';
import {readFileSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import {
  assertFile,
  assertManagedChild,
  loadManifest,
  parseArgs,
  parseSrtText,
  resolveManifestPath,
  writeJson,
} from './lib.mjs';
import {analyzeCaptionTrack} from './caption-layout-core.mjs';

const usage = `Usage:
  node scripts/compile-caption-plan.mjs /abs/case/case_manifest.json --plan planning/caption-plan.json

Compiles a complete semantic split plan into a one-line bilingual caption track.
Each source cue is preserved word-for-word and divided only inside its original frame range.`;

const args = parseArgs(process.argv.slice(2));
if (args.help || args.h || args._.length === 0 || !args.plan) {
  console.log(usage);
  process.exit(args.help || args.h ? 0 : 2);
}

const {manifestPath, caseDir, manifest} = loadManifest(args._[0]);
const planPath = resolveManifestPath(caseDir, String(args.plan));
assertManagedChild(planPath, caseDir, 'caption plan');
assertFile(planPath, 'caption plan');
const planRaw = readFileSync(planPath, 'utf8');
const plan = JSON.parse(planRaw);
if (plan.schemaVersion !== 'jc-koubo-shuping.caption-plan.v1') throw new Error(`unsupported caption plan schema: ${plan.schemaVersion}`);

const revisedValue = manifest.workflow?.subtitleReview?.revisedSrt;
if (!revisedValue) throw new Error('subtitle review revisedSrt is required before caption planning');
const revisedPath = resolveManifestPath(caseDir, revisedValue);
assertFile(revisedPath, 'revised SRT');
const sourceCues = parseSrtText(readFileSync(revisedPath, 'utf8'));
const planItems = Array.isArray(plan.cues) ? plan.cues : [];
const bySource = new Map(planItems.map((item) => [item.sourceCueId, item]));
const sourceIds = sourceCues.map((cue) => cue.id);
const failures = [];
for (const id of sourceIds) if (!bySource.has(id)) failures.push(`caption plan missing ${id}`);
for (const id of bySource.keys()) if (!sourceIds.includes(id)) failures.push(`caption plan has unknown ${id}`);

const compact = (value) => String(value || '').normalize('NFKC').replace(/\s/gu, '');
const weight = (value) => Array.from(String(value || '')).reduce((sum, character) => {
  if (/\s/u.test(character)) return sum + 0.15;
  if (/[\u0000-\u007f]/u.test(character)) return sum + 0.52;
  return sum + 1;
}, 0);
const fps = Number(manifest.video?.fps);
if (!Number.isFinite(fps) || fps <= 0) failures.push('manifest video fps is invalid');

const captionTrack = [];
const sourceToCompiled = new Map();
for (const sourceCue of sourceCues) {
  const item = bySource.get(sourceCue.id);
  if (!item) continue;
  const parts = Array.isArray(item.parts) ? item.parts : [];
  if (!parts.length) {
    failures.push(`${sourceCue.id} parts must be non-empty`);
    continue;
  }
  if (compact(parts.map((part) => part.zh).join('')) !== compact(sourceCue.zh)) failures.push(`${sourceCue.id} Chinese text is not preserved`);
  for (const [index, part] of parts.entries()) {
    if (!String(part.zh || '').trim()) failures.push(`${sourceCue.id}.parts[${index}].zh is empty`);
    if (!String(part.en || '').trim()) failures.push(`${sourceCue.id}.parts[${index}].en is empty`);
  }
  const startFrame = Math.round(Number(sourceCue.start) * fps);
  const endFrame = Math.round(Number(sourceCue.displayEnd ?? sourceCue.end) * fps);
  const availableFrames = endFrame - startFrame;
  const minimumFrames = 8;
  if (availableFrames < parts.length * minimumFrames) failures.push(`${sourceCue.id} has insufficient frames for ${parts.length} parts`);
  let cursor = startFrame;
  let remainingWeight = parts.reduce((sum, part) => sum + weight(part.zh), 0);
  const compiledIds = [];
  parts.forEach((part, index) => {
    let partEndFrame;
    if (index === parts.length - 1) {
      partEndFrame = endFrame;
    } else {
      const minimumRemaining = (parts.length - index - 1) * minimumFrames;
      const proportionalEnd = Math.round(cursor + ((endFrame - cursor) * weight(part.zh)) / remainingWeight);
      partEndFrame = Math.max(cursor + minimumFrames, Math.min(proportionalEnd, endFrame - minimumRemaining));
    }
    const id = `sc${String(captionTrack.length + 1).padStart(3, '0')}`;
    compiledIds.push(id);
    captionTrack.push({
      id,
      sourceCueId: sourceCue.id,
      start: Number((cursor / fps).toFixed(3)),
      end: Number((partEndFrame / fps).toFixed(3)),
      startFrame: cursor,
      endFrame: partEndFrame,
      zh: String(part.zh).trim(),
      en: String(part.en).trim(),
      displayEnd: Number((partEndFrame / fps).toFixed(3)),
    });
    remainingWeight -= weight(part.zh);
    cursor = partEndFrame;
  });
  sourceToCompiled.set(sourceCue.id, compiledIds);
}

const preflight = analyzeCaptionTrack(captionTrack);
if (preflight.failures.length) failures.push(...preflight.failures.map((item) => `${item.id} single-line bilingual preflight failed`));
if (failures.length) throw new Error(`caption plan compile failed: ${failures.join('; ')}`);

const semanticSourceValue = manifest.workflow?.semanticPlan?.sourceMotionMap;
if (semanticSourceValue) {
  const semanticSource = resolveManifestPath(caseDir, semanticSourceValue);
  assertFile(semanticSource, 'source motion map');
  const map = JSON.parse(readFileSync(semanticSource, 'utf8'));
  for (const beat of map.beats || []) beat.cue_ids = beat.cue_ids.flatMap((id) => sourceToCompiled.get(id) || [id]);
  writeJson(semanticSource, map);
}

const srtName = `${path.basename(revisedPath, path.extname(revisedPath))}.single-line-bilingual.srt`;
const srtPath = path.join(path.dirname(revisedPath), srtName);
assertManagedChild(srtPath, caseDir, 'single-line bilingual SRT');
const srtTime = (seconds) => {
  const milliseconds = Math.round(seconds * 1000);
  const hours = Math.floor(milliseconds / 3600000);
  const minutes = Math.floor((milliseconds % 3600000) / 60000);
  const secs = Math.floor((milliseconds % 60000) / 1000);
  const ms = milliseconds % 1000;
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(ms).padStart(3, '0')}`;
};
const srt = captionTrack.map((cue, index) => `${index + 1}\n${srtTime(cue.start)} --> ${srtTime(cue.end)}\n${cue.zh}\n${cue.en}`).join('\n\n');
writeFileSync(srtPath, `${srt}\n`);

const reportPath = path.join(caseDir, 'reports', 'caption-plan-compile.json');
const report = {
  schemaVersion: 'jc-koubo-shuping.caption-plan-report.v1',
  caseId: manifest.caseId,
  result: 'pass',
  sourceCueCount: sourceCues.length,
  outputCueCount: captionTrack.length,
  sourceWordsPreserved: true,
  continuousWithinSourceCueFrames: true,
  bilingualCueCount: captionTrack.length,
  singleLinePreflight: preflight.summary,
  plan: path.relative(caseDir, planPath),
  planSha256: createHash('sha256').update(planRaw).digest('hex'),
  outputSrt: path.relative(caseDir, srtPath),
};
writeJson(reportPath, report);

manifest.captionTrack = captionTrack;
manifest.subtitle = path.relative(caseDir, srtPath);
manifest.nodes = [];
manifest.workflow.motionMap = null;
manifest.workflow.semanticPlan = null;
manifest.workflow.renderBlockedReason = 'semantic_motion_map_not_compiled_after_caption_plan';
manifest.workflow.subtitleReview = {
  ...manifest.workflow.subtitleReview,
  captionPlan: path.relative(caseDir, planPath),
  captionPlanReport: path.relative(caseDir, reportPath),
  singleLineBilingualSrt: path.relative(caseDir, srtPath),
};
writeJson(manifestPath, manifest);
console.log(JSON.stringify(report, null, 2));
