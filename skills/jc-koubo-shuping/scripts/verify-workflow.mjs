#!/usr/bin/env node

import {spawnSync} from 'node:child_process';
import {mkdirSync, writeFileSync} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {commandText, readJson, run, scriptDir, writeJson} from './lib.mjs';

const root = path.join(os.tmpdir(), `jc-koubo-shuping-workflow-${Date.now()}`);
const validator = path.join(scriptDir, 'validate-workflow.mjs');
mkdirSync(root, {recursive: true});

const relative = (value) => path.relative(root, value);
const sha256 = (file) => commandText('shasum', ['-a', '256', file]).split(/\s+/u)[0];
const image = (name, color, format = 'png') => {
  const file = path.join(root, 'media', `${name}.${format}`);
  mkdirSync(path.dirname(file), {recursive: true});
  run('ffmpeg', ['-loglevel', 'error', '-y', '-f', 'lavfi', '-i', `color=c=${color}:s=64x96:d=0.1`, '-frames:v', '1', '-update', '1', file]);
  return relative(file);
};

const revisedSrt = path.join(root, 'source', 'revised.srt');
mkdirSync(path.dirname(revisedSrt), {recursive: true});
writeFileSync(revisedSrt, '1\n00:00:00,000 --> 00:00:06,000\n明星八卦\n');
const diff = path.join(root, 'reports', 'subtitle-diff.json');
mkdirSync(path.dirname(diff), {recursive: true});
writeJson(diff, {changes: [{cue: 'c001', from: '明星八挂', to: '明星八卦'}]});
const motionMap = path.join(root, 'planning', 'motion-map.json');
mkdirSync(path.dirname(motionMap), {recursive: true});
writeJson(motionMap, {
  argument_map: {
    core_claim: '明星八卦不是理解内容价值的重点',
    audience_problem: '观众容易被表面话题带偏',
    ending_action: '先识别真正需要理解的结论',
    progression: [{id: 'a01', type: 'claim', claim: '先识别真正结论'}],
  },
  risk_overrides: [],
  beats: [{
  id: 'n01',
  cue_ids: ['c001'],
  argument_id: 'a01',
  boundary: {type: 'opening', change: '开场直接建立核心判断'},
  semantic_function: 'conclusion',
  viewer_need: 'know the point',
  trigger_rule: 'spoken conclusion',
  hero_visual: 'upper semantic card',
  caption_policy: 'single follow caption',
  sound_cue: 'single hit',
  layout_risk: 'face safe zone',
  mg_copy: {label: '判断', eyebrow: 'CORE CLAIM', title: '别被八卦带偏', sub: '先识别真正的内容价值', chips: ['八卦', '价值'], accent: 'blue'},
  }],
});
const staticFiles = [
  image('static-1', 'red'),
  image('static-2', 'green'),
  image('static-3', 'blue'),
  image('static-4', 'yellow'),
];
const staticContact = image('static-contact', 'white', 'jpg');
const pilot = path.join(root, 'media', 'pilot.mp4');
run('ffmpeg', ['-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=64x96:rate=10:duration=10', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', pilot]);
const pilotContacts = {
  overview: image('pilot-overview', 'red', 'jpg'),
  animationRisk: image('pilot-animation', 'green', 'jpg'),
  captionRisk: image('pilot-caption', 'blue', 'jpg'),
  safeZone: image('pilot-safe', 'yellow', 'jpg'),
};
const decision = (artifact, messageId, statement) => ({
  decision: 'accepted',
  reviewerType: 'human',
  userStatement: statement,
  evidence: {
    source: 'external_user_message',
    threadId: 'workflow-fixture-thread',
    messageId,
    recordedAt: '2026-07-16T00:00:30.000Z',
    artifact,
    sha256: sha256(path.join(root, artifact)),
  },
});
const historyStages = ['intake', 'subtitle_reviewed', 'motion_map_ready', 'static_preview_pending', 'static_preview_accepted', 'pilot_pending', 'pilot_accepted'];
let base = {
  schemaVersion: 3,
  packageVersion: '0.8.0-candidate',
  caseId: 'workflow-fixture',
  visualStyleId: 'google-semantic',
  video: {duration: 6},
  captionTrack: [{id: 'c001', start: 0, end: 6, displayEnd: 6, zh: '明星八卦', en: ''}],
  nodes: [],
  errorBank: {applied: []},
  workflow: {
    stage: 'pilot_accepted',
    history: historyStages.map((stage, index) => ({stage, at: `2026-07-16T00:00:${String(index).padStart(2, '0')}.000Z`})),
    planningMode: 'draft_auto_equal_duration',
    renderBlockedReason: 'semantic_motion_map_not_compiled',
    semanticPlan: null,
    baselineId: '0721-approved-baseline-v4-multi-mg',
    subtitleReview: {revisedSrt: relative(revisedSrt), diff: relative(diff)},
    motionMap: relative(motionMap),
    staticPreview: {
      files: staticFiles,
      contactSheet: staticContact,
      ...decision(staticContact, 'static-accepted', '静态预览可以'),
    },
    pilot: {
      video: relative(pilot),
      contacts: pilotContacts,
      baselineId: '0721-approved-baseline-v4-multi-mg',
      ...decision(relative(pilot), 'pilot-accepted', '样片可以，继续全片'),
    },
    fullBuild: {baselineId: '0721-approved-baseline-v4-multi-mg'},
  },
};

const compiledBasePath = path.join(root, 'compiled-base.json');
writeJson(compiledBasePath, base);
run('node', [path.join(scriptDir, 'compile-motion-map.mjs'), compiledBasePath]);
base = readJson(compiledBasePath);

const execute = (name, manifest, expectedStatus) => {
  const manifestPath = path.join(root, `${name}.json`);
  writeJson(manifestPath, manifest);
  const result = spawnSync('node', [validator, manifestPath], {encoding: 'utf8'});
  if (result.status !== expectedStatus) throw new Error(`${name} expected exit ${expectedStatus}, got ${result.status}\n${result.stdout}\n${result.stderr}`);
  return JSON.parse(result.stdout);
};

const accepted = execute('accepted', base, 0);
const forged = structuredClone(base);
forged.workflow.pilot.evidence.artifact = staticContact;
const blockedArtifact = execute('forged-artifact', forged, 1);
const placeholder = structuredClone(base);
placeholder.workflow.staticPreview.files = ['fake-1.png', 'fake-2.png', 'fake-3.png', 'fake-4.png'];
for (const file of placeholder.workflow.staticPreview.files) writeFileSync(path.join(root, file), 'not an image');
const blockedPlaceholder = execute('placeholder-images', placeholder, 1);
const downgraded = structuredClone(base);
downgraded.schemaVersion = 2;
const blockedDowngrade = execute('schema-downgrade', downgraded, 1);

console.log(JSON.stringify({result: 'pass', root, accepted: accepted.result, forgedArtifact: blockedArtifact.result, placeholderImages: blockedPlaceholder.result, schemaDowngrade: blockedDowngrade.result}, null, 2));
