#!/usr/bin/env node

import {loadManifest, parseArgs, writeJson} from './lib.mjs';

const phases = new Set(['subtitle_review', 'semantic_analysis', 'static_preview', 'pilot', 'full_render', 'qa']);
const usage = `Usage:
  node scripts/record-workflow-timing.mjs /abs/case/case_manifest.json --phase semantic_analysis --start
  node scripts/record-workflow-timing.mjs /abs/case/case_manifest.json --phase semantic_analysis --stop`;
const args = parseArgs(process.argv.slice(2));
if (args.help || args.h || args._.length === 0 || !args.phase || (!args.start && !args.stop) || (args.start && args.stop)) {
  console.log(usage);
  process.exit(args.help || args.h ? 0 : 2);
}
const phase = String(args.phase);
if (!phases.has(phase)) throw new Error(`invalid phase: ${phase}`);
const {manifestPath, manifest} = loadManifest(args._[0]);
manifest.workflow ||= {};
manifest.workflow.timings ||= {};
const current = manifest.workflow.timings[phase] || {};
if (args.start) {
  if (current.startedAt && !current.completedAt) throw new Error(`${phase} timer already running`);
  manifest.workflow.timings[phase] = {startedAt: new Date().toISOString(), completedAt: null, durationSeconds: null};
} else {
  if (!current.startedAt || current.completedAt) throw new Error(`${phase} timer is not running`);
  const completedAt = new Date().toISOString();
  manifest.workflow.timings[phase] = {...current, completedAt, durationSeconds: Number(((Date.parse(completedAt) - Date.parse(current.startedAt)) / 1000).toFixed(3))};
}
writeJson(manifestPath, manifest);
console.log(JSON.stringify({phase, ...manifest.workflow.timings[phase]}, null, 2));
