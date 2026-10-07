#!/usr/bin/env node

import {spawnSync} from 'node:child_process';
import {existsSync, mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import {commandText, parseArgs, readJson, run, scriptDir, tmpCaseDir, writeJson} from './lib.mjs';

const usage = `Usage:
  node scripts/verify-install.mjs [--out /tmp/case] [--style assembly-mono|google-semantic]

Creates a real 9:16 SDR fixture and exercises every enforced gate, Remotion
render, preserve-source composite, technical record, and declared acceptance.`;

const args = parseArgs(process.argv.slice(2));
if (args.help || args.h) {
  console.log(usage);
  process.exit(0);
}

const styleId = String(args.style || 'google-semantic');
const outRoot = args.out ? path.resolve(String(args.out)) : tmpCaseDir(`jc-koubo-shuping-${styleId}-smoke`);
const fixtureDir = path.join(outRoot, 'fixture');
const caseDir = path.join(outRoot, 'case');
mkdirSync(fixtureDir, {recursive: true});

run('node', [path.join(scriptDir, 'validate-error-bank.mjs')]);
run('node', [path.join(scriptDir, 'verify-workflow.mjs')]);

const sourceVideo = path.join(fixtureDir, 'source.mp4');
const sourceSrt = path.join(fixtureDir, 'source.srt');
writeFileSync(sourceSrt, `1
00:00:00,000 --> 00:00:02,200
先看环境 || check the environment first

2
00:00:02,200 --> 00:00:04,300
明星八卦不是重点 || celebrity gossip is not the point

3
00:00:04,200 --> 00:00:06,000
直接开干 || start doing it now
`);

if (!existsSync(sourceVideo)) {
  run('ffmpeg', [
    '-y', '-f', 'lavfi', '-i', 'testsrc2=size=720x1280:rate=30:duration=6',
    '-f', 'lavfi', '-i', 'sine=frequency=660:duration=6:sample_rate=44100',
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
    '-x264-params', 'colorprim=bt709:transfer=bt709:colormatrix=bt709',
    '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv',
    '-c:a', 'aac', '-t', '6', sourceVideo,
  ]);
}

run('node', [path.join(scriptDir, 'install-runtime.mjs')]);
run('node', [path.join(scriptDir, 'create-case.mjs'), '--video', sourceVideo, '--srt', sourceSrt, '--out', caseDir, '--case-id', 'smoke-fixture', '--style', styleId, '--force']);

const manifestPath = path.join(caseDir, 'case_manifest.json');
const manifest = readJson(manifestPath);
const reportsDir = path.join(caseDir, 'reports');
const planningDir = path.join(caseDir, 'planning');
const staticDir = path.join(caseDir, 'static');
const pilotDir = path.join(caseDir, 'pilot');
mkdirSync(planningDir, {recursive: true});
mkdirSync(staticDir, {recursive: true});
mkdirSync(pilotDir, {recursive: true});
const rel = (file) => path.relative(caseDir, file);
const sha256 = (file) => commandText('shasum', ['-a', '256', file]).split(/\s+/u)[0];
const makeImage = (file, color) => run('ffmpeg', ['-loglevel', 'error', '-y', '-f', 'lavfi', '-i', `color=c=${color}:s=360x640:d=0.1`, '-frames:v', '1', '-update', '1', file]);

const revisedSrt = path.join(caseDir, 'source', 'revised.srt');
writeFileSync(revisedSrt, readFileSync(sourceSrt));
const subtitleDiff = path.join(reportsDir, 'subtitle-diff.json');
writeJson(subtitleDiff, {changes: [{cue: 'c002', from: '明星八挂', to: '明星八卦', reason: '错别字'}]});
const motionMap = path.join(planningDir, 'motion-map.json');
writeJson(motionMap, {
  argument_map: {
    core_claim: '先判断当前环境，再决定如何让 AI 执行',
    audience_problem: '把等待误当成准备，迟迟没有行动',
    ending_action: '完成环境判断后立即下达任务',
    progression: [{id: 'a01', type: 'action', claim: '判断环境之后立即行动'}],
  },
  risk_overrides: [],
  beats: [{
  id: 'n01',
  cue_ids: ['c001', 'c002', 'c003'],
  argument_id: 'a01',
  boundary: {type: 'opening', change: '从环境判断进入立即行动的完整结论'},
  semantic_function: 'conclusion',
  viewer_need: 'understand and act',
  trigger_rule: 'opening conclusion',
  hero_visual: 'upper semantic card',
  caption_policy: 'single follow caption',
  sound_cue: 'one semantic hit',
  layout_risk: 'upper card and face safe zone',
  mg_copy: {
    label: '结论', eyebrow: 'FIRST CHECK', title: '先看环境再行动', sub: '别把等待当准备',
    chips: ['环境', '判断', '行动'], accent: 'blue',
  },
  }],
});
manifest.workflow.subtitleReview = {revisedSrt: rel(revisedSrt), diff: rel(subtitleDiff)};
manifest.workflow.motionMap = rel(motionMap);
writeJson(manifestPath, manifest);
run('node', [path.join(scriptDir, 'compile-motion-map.mjs'), manifestPath]);
Object.assign(manifest, readJson(manifestPath));

const staticFiles = ['red', 'green', 'blue', 'yellow'].map((color, index) => {
  const file = path.join(staticDir, `preview-${index + 1}.png`);
  makeImage(file, color);
  return rel(file);
});
const staticContact = path.join(caseDir, 'qa', 'static-contact.jpg');
makeImage(staticContact, 'white');
const pilotVideo = path.join(pilotDir, 'pilot.mp4');
run('ffmpeg', ['-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=360x640:rate=15:duration=10', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', pilotVideo]);
const pilotContacts = {};
for (const [key, color] of [['overview', 'red'], ['animationRisk', 'green'], ['captionRisk', 'blue'], ['safeZone', 'yellow']]) {
  const file = path.join(caseDir, 'qa', `pilot-${key}.jpg`);
  makeImage(file, color);
  pilotContacts[key] = rel(file);
}
const decision = (artifact, messageId, statement) => ({
  decision: 'accepted', reviewerType: 'human', userStatement: statement,
  evidence: {
    source: 'external_user_message', threadId: 'smoke-host-thread', messageId,
    recordedAt: '2026-07-16T00:01:00.000Z', artifact: rel(artifact), sha256: sha256(artifact),
  },
});
manifest.workflow.staticPreview = {files: staticFiles, contactSheet: rel(staticContact), ...decision(staticContact, 'static-approved', '静态预览可以')};
manifest.workflow.pilot = {video: rel(pilotVideo), contacts: pilotContacts, baselineId: manifest.workflow.baselineId, ...decision(pilotVideo, 'pilot-approved', '样片可以，继续全片')};
manifest.workflow.fullBuild = {baselineId: manifest.workflow.baselineId};
manifest.workflow.stage = 'pilot_accepted';
manifest.workflow.history = ['intake', 'subtitle_reviewed', 'motion_map_ready', 'static_preview_pending', 'static_preview_accepted', 'pilot_pending', 'pilot_accepted']
  .map((stage, index) => ({stage, at: `2026-07-16T00:00:${String(index).padStart(2, '0')}.000Z`}));
const bank = readJson(path.join(path.dirname(scriptDir), 'evals', 'error-cases.json'));
manifest.errorBank.applied = bank.cases.filter((item) => item.status === 'active').map((item) => item.id);
const regressionReport = path.join(reportsDir, 'error-regression.json');
run('node', [path.join(scriptDir, 'validate-error-bank.mjs'), '--out', regressionReport]);
manifest.errorBank.regressionReport = rel(regressionReport);
writeJson(manifestPath, manifest);

run('node', [path.join(scriptDir, 'validate-workflow.mjs'), manifestPath, '--require-stage', 'pilot_accepted']);
run('node', [path.join(scriptDir, 'render-overlay.mjs'), manifestPath, '--concurrency', '2']);
run('node', [path.join(scriptDir, 'composite-preserve-source.mjs'), manifestPath]);
run('node', [path.join(scriptDir, 'validate-final.mjs'), manifestPath, '--record-technical']);

const releaseBefore = spawnSync('node', [path.join(scriptDir, 'validate-final.mjs'), manifestPath, '--require-acceptance'], {encoding: 'utf8'});
if (releaseBefore.status === 0) throw new Error('release gate unexpectedly passed without qa/acceptance.json');
const technicalManifest = readJson(manifestPath);
const finalVideo = path.join(caseDir, technicalManifest.finalVideo);
const finalSha = sha256(finalVideo);
const acceptance = {
  schemaVersion: 1,
  caseId: technicalManifest.caseId,
  decision: 'accepted',
  reviewer: {type: 'human'},
  artifact: technicalManifest.finalVideo,
  evidence: {
    source: 'external_user_message',
    threadId: 'smoke-host-thread',
    messageId: 'final-approved',
    recordedAt: '2026-07-16T00:02:00.000Z',
    user_statement: '这个成片可以发布',
    sha256: finalSha,
    technical_report: technicalManifest.qa.technicalValidation,
  },
};
const acceptancePath = path.join(caseDir, 'qa', 'acceptance.json');
writeJson(acceptancePath, acceptance);
technicalManifest.acceptance = {record: rel(acceptancePath)};
writeJson(manifestPath, technicalManifest);
run('node', [path.join(scriptDir, 'validate-final.mjs'), manifestPath, '--require-acceptance']);
run('node', [path.join(scriptDir, 'verify-adversarial.mjs'), manifestPath]);

console.log(`[jc-koubo-shuping] smoke case passed: ${caseDir}`);
