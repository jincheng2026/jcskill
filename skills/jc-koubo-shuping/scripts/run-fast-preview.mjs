#!/usr/bin/env node

import {spawnSync} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
if (!args.length || args.includes('--help') || args.includes('-h')) {
  console.log('Usage: node scripts/run-fast-preview.mjs /abs/case/case_manifest.json [--points sec,sec,sec,sec] [--width 1080]');
  process.exit(args.length ? 0 : 2);
}

for (const script of ['install-runtime.mjs', 'preflight-captions.mjs', 'render-static-preview.mjs']) {
  const scriptArgs = script === 'install-runtime.mjs' ? [] : args;
  const result = spawnSync(process.execPath, [path.join(scriptDir, script), ...scriptArgs], {stdio: 'inherit'});
  if (result.status !== 0) process.exit(result.status || 1);
}
