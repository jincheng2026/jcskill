#!/usr/bin/env node

import {loadManifest, parseArgs} from './lib.mjs';
import {validateWorkflow} from './workflow-core.mjs';

const usage = `Usage:
  node scripts/validate-workflow.mjs /abs/case/case_manifest.json [--require-stage pilot_accepted]

Read-only workflow gate. It validates ordered stage history, real artifacts,
semantic planning, external decision evidence, and executable error regressions.`;

const args = parseArgs(process.argv.slice(2));
if (args.help || args.h || args._.length === 0) {
  console.log(usage);
  process.exit(args._.length === 0 ? 2 : 0);
}

const {manifestPath, caseDir, manifest} = loadManifest(args._[0]);
const result = validateWorkflow({caseDir, manifest, requiredStage: args['require-stage'] || null});
const payload = {...result, manifest: manifestPath};
console.log(JSON.stringify(payload, null, 2));
process.exit(result.failures.length === 0 ? 0 : 1);
