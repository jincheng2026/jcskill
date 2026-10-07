#!/usr/bin/env node

import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import {loadManifest, parseArgs, resolveManifestPath, writeJson} from './lib.mjs';
import {requireVisualStyle} from './style-core.mjs';

const args = parseArgs(process.argv.slice(2));
if (args.help || args.h || args._.length === 0 || !args.target) {
  console.log('Usage: node scripts/repair-case.mjs /abs/case/case_manifest.json --target caption|copy|layout|motion|source [--apply]');
  process.exit(args.help || args.h ? 0 : 2);
}

const routes = {
  caption: {invalidate: ['captionPreflight', 'overlay', 'composite', 'captionQA'], rerun: ['preflight-captions', 'render-static-preview']},
  copy: {invalidate: ['compiledMotionMap', 'overlay', 'composite', 'visualQA'], rerun: ['compile-motion-map', 'preflight-captions', 'render-static-preview']},
  layout: {invalidate: ['overlay', 'composite', 'layoutQA'], rerun: ['render-static-preview']},
  motion: {invalidate: ['compiledMotionMap', 'overlay', 'composite', 'animationQA'], rerun: ['compile-motion-map', 'render-static-preview']},
  source: {invalidate: ['sourceProbe', 'subtitleAlignment', 'motionMap', 'overlay', 'composite', 'allQA'], rerun: ['create-case'], requiresNewCase: true},
};
const target = String(args.target);
if (!routes[target]) throw new Error(`unknown repair target: ${target}`);
const {manifestPath, caseDir, manifest} = loadManifest(args._[0]);
const visualStyleId = requireVisualStyle(manifest.visualStyleId);
const hash = (value) => {
  if (!value) return null;
  const file = resolveManifestPath(caseDir, value);
  try { return createHash('sha256').update(readFileSync(file)).digest('hex'); } catch { return null; }
};
const plan = {
  schemaVersion: 'jc-koubo-shuping.repair-plan.v1',
  generatedAt: new Date().toISOString(),
  caseId: manifest.caseId,
  visualStyleId,
  target,
  ...routes[target],
  preserve: ['sourceVideo', 'approvedBaseline', 'unaffectedPlanning', 'previousAttempts'],
  fingerprintsBefore: {
    source: hash(manifest.sourceVideo),
    subtitle: hash(manifest.subtitle),
    motionMap: hash(manifest.workflow?.motionMap),
    baselineId: manifest.workflow?.baselineId,
    visualStyleId,
  },
  policy: 'Write repaired artifacts to a new attempt directory; never delete or overwrite prior approved evidence.',
};
if (args.apply) {
  const previousExecution = manifest.workflow.execution || {};
  manifest.workflow.execution = {
    ...previousExecution,
    mode: 'repair',
    cycle: Number(previousExecution.cycle || 1) + 1,
    renderAttempts: 0,
    autoFixes: 0,
    status: routes[target].requiresNewCase ? 'new_case_required' : 'repair_planned',
    repairTarget: target,
    invalidated: routes[target].invalidate,
  };
  plan.newCycle = manifest.workflow.execution.cycle;
  plan.budgetReset = {renderAttempts: 0, autoFixes: 0};
  writeJson(path.join(caseDir, 'reports', 'repair-plan.json'), plan);
  writeJson(manifestPath, manifest);
}
console.log(JSON.stringify({...plan, applied: Boolean(args.apply)}, null, 2));
