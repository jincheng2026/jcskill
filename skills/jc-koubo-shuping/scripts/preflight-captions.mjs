#!/usr/bin/env node

import path from 'node:path';
import {analyzeCaptionTrack} from './caption-layout-core.mjs';
import {loadManifest, parseArgs, writeJson} from './lib.mjs';

const args = parseArgs(process.argv.slice(2));
if (args.help || args.h || args._.length === 0) {
  console.log('Usage: node scripts/preflight-captions.mjs /abs/case/case_manifest.json [--out reports/caption-preflight.json]');
  process.exit(args._.length === 0 ? 2 : 0);
}

const {caseDir, manifest} = loadManifest(args._[0]);
const report = analyzeCaptionTrack(manifest.captionTrack || []);
const output = path.resolve(caseDir, String(args.out || 'reports/caption-preflight.json'));
writeJson(output, {...report, generatedAt: new Date().toISOString()});
console.log(JSON.stringify({result: report.result, output, summary: report.summary}, null, 2));
if (report.result !== 'pass') process.exit(1);
