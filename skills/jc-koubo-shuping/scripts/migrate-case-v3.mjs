#!/usr/bin/env node

import {copyFileSync, existsSync} from 'node:fs';
import path from 'node:path';
import {loadManifest, parseArgs, writeJson} from './lib.mjs';

const usage = `Usage:
  node scripts/migrate-case-v3.mjs /abs/case/case_manifest.json

Creates an adjacent v2 backup, preserves legacy nodes as non-renderable drafts,
and blocks the case until a new v3 semantic motion map is authored and compiled.`;

const args = parseArgs(process.argv.slice(2));
if (args.help || args.h || args._.length === 0) {
  console.log(usage);
  process.exit(args._.length === 0 ? 2 : 0);
}
const {manifestPath, manifest} = loadManifest(args._[0]);
if (Number(manifest.schemaVersion) === 3) throw new Error('case is already schemaVersion 3');
const backup = manifestPath.replace(/\.json$/u, '.schema-v2-backup.json');
if (existsSync(backup)) throw new Error(`migration backup already exists: ${backup}`);
copyFileSync(manifestPath, backup);
manifest.schemaVersion = 3;
manifest.packageVersion = '0.4.1-candidate';
manifest.draftNodes = Array.isArray(manifest.nodes) ? manifest.nodes : [];
manifest.nodes = [];
manifest.workflow = {
  ...(manifest.workflow || {}),
  planningMode: 'legacy_v2_migrated_draft',
  renderBlockedReason: 'semantic_motion_map_not_compiled',
  legacyMotionMap: manifest.workflow?.motionMap || null,
  motionMap: null,
  semanticPlan: null,
};
writeJson(manifestPath, manifest);
console.log(JSON.stringify({result: 'migrated_and_blocked', manifest: manifestPath, backup, next: 'author v3 source motion map and run compile-motion-map.mjs'}, null, 2));
