#!/usr/bin/env node

import {spawnSync} from 'node:child_process';
import {existsSync, mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {loadManifest, parseArgs, scriptDir, writeJson} from './lib.mjs';

const args = parseArgs(process.argv.slice(2));
if (!args._[0]) throw new Error('Usage: node scripts/verify-adversarial.mjs /abs/case/case_manifest.json');
const {caseDir, manifest} = loadManifest(args._[0]);
const validator = path.join(scriptDir, 'validate-final.mjs');
const renderer = path.join(scriptDir, 'render-overlay.mjs');
const tempRoot = path.join(os.tmpdir(), `jc-koubo-adversarial-${Date.now()}`);
mkdirSync(tempRoot, {recursive: true});
const results = [];

function expectBlocked(name, command, commandArgs, expected, options = {}) {
  const result = spawnSync(command, commandArgs, {encoding: 'utf8', ...options});
  const output = `${result.stdout || ''}\n${result.stderr || ''}`;
  if (result.status === 0 || !output.includes(expected)) throw new Error(`${name} was not blocked as expected (${expected})\n${output}`);
  results.push({name, blockedBy: expected});
}

function adversarialManifest(name, mutate) {
  const copy = structuredClone(manifest);
  mutate(copy);
  const file = path.join(caseDir, `adversarial-${name}.json`);
  writeJson(file, copy);
  return file;
}

const victim = path.join(tempRoot, 'victim');
mkdirSync(victim, {recursive: true});
const sentinel = path.join(victim, 'sentinel.txt');
writeFileSync(sentinel, 'must survive\n');
const unsafeRender = adversarialManifest('unsafe-render-path', (copy) => {
  copy.workflow.stage = 'pilot_accepted';
  copy.workflow.history = copy.workflow.history.slice(0, 7);
});
expectBlocked('case path escape', 'node', [renderer, unsafeRender, '--out', victim], 'must be a child of');
if (!existsSync(sentinel) || readFileSync(sentinel, 'utf8') !== 'must survive\n') throw new Error('unsafe render path deleted the sentinel');

expectBlocked(
  'runtime path escape',
  'node',
  [path.join(scriptDir, 'install-runtime.mjs')],
  'must be a child of',
  {env: {...process.env, JC_KOUBO_SHUPING_RUNTIME_DIR: victim}},
);
if (!existsSync(sentinel)) throw new Error('unsafe runtime path deleted the sentinel');

expectBlocked(
  'late full rerender',
  'node',
  [renderer, args._[0]],
  'full render requires exact workflow.stage=pilot_accepted',
);

const intake = adversarialManifest('intake-release', (copy) => {
  copy.workflow = {stage: 'intake', history: [copy.workflow.history[0]], planningMode: 'draft_auto_equal_duration'};
});
expectBlocked('workflow bypass', 'node', [validator, intake, '--require-acceptance'], 'requires exact workflow.stage=technical_pass');

const poorQuality = adversarialManifest('poor-quality', (copy) => {
  copy.qualityProfile.videoEncoding.crf = 51;
  copy.qualityProfile.videoEncoding.preset = 'ultrafast';
  copy.qualityProfile.upscale.filter = 'neighbor';
});
expectBlocked('quality profile spoof', 'node', [validator, poorQuality], 'quality profile differs from canonical contract');

const silent = adversarialManifest('silent-final', (copy) => {
  copy.finalVideo = copy.composite.videoOnlyIntermediate;
});
expectBlocked('silent final', 'node', [validator, silent], 'final must contain exactly one audio stream');

const fakeQa = path.join(caseDir, 'qa', 'fake-contact.jpg');
writeFileSync(fakeQa, 'not an image\n');
const placeholderQa = adversarialManifest('placeholder-qa', (copy) => {
  copy.qa.finalContactSheet = [path.relative(caseDir, fakeQa)];
});
expectBlocked('placeholder QA', 'node', [validator, placeholderQa], 'is not a decodable image');

const fakeAcceptance = path.join(caseDir, 'qa', 'acceptance-wrong-artifact.json');
const acceptance = JSON.parse(readFileSync(path.join(caseDir, manifest.acceptance.record), 'utf8'));
acceptance.artifact = manifest.composite.videoOnlyIntermediate;
writeJson(fakeAcceptance, acceptance);
const wrongArtifact = adversarialManifest('wrong-acceptance-artifact', (copy) => {
  copy.acceptance.record = path.relative(caseDir, fakeAcceptance);
});
expectBlocked('wrong acceptance artifact', 'node', [validator, wrongArtifact, '--require-acceptance'], 'artifact must equal manifest.finalVideo');

console.log(JSON.stringify({result: 'pass', total: results.length, results, sentinelSurvived: true}, null, 2));
