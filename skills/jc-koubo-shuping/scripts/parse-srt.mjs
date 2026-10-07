#!/usr/bin/env node

import {readFileSync} from 'node:fs';
import {parseArgs, parseSrtText} from './lib.mjs';

const usage = `Usage:
  node scripts/parse-srt.mjs /path/to/subtitle.srt

Text format:
  Chinese subtitle || optional English subtitle`;

const args = parseArgs(process.argv.slice(2));
if (args.help || args.h || args._.length === 0) {
  console.log(usage);
  process.exit(args._.length === 0 ? 2 : 0);
}

const cues = parseSrtText(readFileSync(args._[0], 'utf8'));
console.log(JSON.stringify(cues, null, 2));
