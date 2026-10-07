#!/usr/bin/env node

import {createHash} from 'node:crypto';
import {cpSync, existsSync, readFileSync, rmSync} from 'node:fs';
import path from 'node:path';
import {assertManagedChild, ensureDir, parseArgs, remotionTemplateDir, run, runtimeCacheRoot, runtimeTemplateDir} from './lib.mjs';

const usage = `Usage:
  node scripts/install-runtime.mjs

Copies the bundled Remotion template into a local runtime cache and installs dependencies there.`;

const args = parseArgs(process.argv.slice(2));
if (args.help || args.h) {
  console.log(usage);
  process.exit(0);
}

assertManagedChild(runtimeTemplateDir, runtimeCacheRoot, 'runtime directory');
const sourceLock = path.join(remotionTemplateDir, 'package-lock.json');
const runtimeLock = path.join(runtimeTemplateDir, 'package-lock.json');
const digest = (file) => createHash('sha256').update(readFileSync(file)).digest('hex');
const canRefresh = existsSync(path.join(runtimeTemplateDir, 'node_modules')) && existsSync(sourceLock) && existsSync(runtimeLock) && digest(sourceLock) === digest(runtimeLock);
if (!canRefresh) rmSync(runtimeTemplateDir, {recursive: true, force: true});
ensureDir(path.dirname(runtimeTemplateDir));
cpSync(remotionTemplateDir, runtimeTemplateDir, {
  recursive: true,
  filter: (source) => !source.includes(`${path.sep}node_modules${path.sep}`) && !source.endsWith(`${path.sep}node_modules`),
});

if (!canRefresh) {
  const lock = path.join(runtimeTemplateDir, 'package-lock.json');
  const command = existsSync(lock) ? ['ci'] : ['install'];
  run('npm', command, {cwd: runtimeTemplateDir});
}
console.log(`[jc-koubo-shuping] runtime ${canRefresh ? 'refreshed without npm install' : 'installed'}: ${runtimeTemplateDir}`);
