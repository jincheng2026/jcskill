#!/usr/bin/env node

import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {performance} from 'node:perf_hooks';
import path from 'node:path';
import {assertFile, assertManagedChild, loadManifest, parseArgs, resolveManifestPath, skillDir, writeJson} from './lib.mjs';
import {buildCompiledMotionMap, compileNodesFromMotionMap, validateCompiledSemanticPlan} from './semantic-core.mjs';

const usage = `Usage:
  node scripts/compile-motion-map.mjs /abs/case/case_manifest.json [--motion-map planning/motion-map.json] [--out planning/motion-map.compiled.json]

Compiles cue evidence into deterministic timing and spoken_line, validates
argument mapping and MG copy, and records source/compiler dependency hashes.
Unresolved risk warnings are written to the manifest but keep rendering blocked.`;

const args = parseArgs(process.argv.slice(2));
if (args.help || args.h || args._.length === 0) {
  console.log(usage);
  process.exit(args._.length === 0 ? 2 : 0);
}

const started = performance.now();
const {manifestPath, caseDir, manifest} = loadManifest(args._[0]);
if (Number(manifest.schemaVersion) !== 3) throw new Error(`compile-motion-map.mjs requires schemaVersion exactly 3; run migrate-case-v3.mjs first, got ${manifest.schemaVersion}`);
const sourceValue = String(args['motion-map'] || manifest.workflow?.semanticPlan?.sourceMotionMap || manifest.workflow?.motionMap || '');
if (!sourceValue) throw new Error('source motion map path missing: pass --motion-map');
const sourceFile = resolveManifestPath(caseDir, sourceValue);
assertManagedChild(sourceFile, caseDir, 'source motion map');
assertFile(sourceFile, 'source motion map');
const outputValue = String(args.out || path.join(path.dirname(path.relative(caseDir, sourceFile)), 'motion-map.compiled.json'));
const outputFile = resolveManifestPath(caseDir, outputValue);
assertManagedChild(outputFile, caseDir, 'compiled motion map');
if (path.resolve(outputFile) === path.resolve(sourceFile)) throw new Error('compiled motion map must not overwrite the authored source motion map');

const sourceRaw = readFileSync(sourceFile, 'utf8');
const source = JSON.parse(sourceRaw);
const built = buildCompiledMotionMap({manifest, source});
if (built.failures.length) throw new Error(`semantic evidence compile failed: ${built.failures.join('; ')}`);
const candidate = structuredClone(manifest);
candidate.nodes = compileNodesFromMotionMap(built.compiled);
const check = validateCompiledSemanticPlan({manifest: candidate, motionMap: built.compiled});
if (check.failures.length) throw new Error(`semantic hard gate failed: ${check.failures.join('; ')}`);

writeJson(outputFile, built.compiled);
const compiledRaw = readFileSync(outputFile, 'utf8');
manifest.nodes = candidate.nodes;
manifest.workflow.motionMap = path.relative(caseDir, outputFile);
manifest.workflow.planningMode = 'semantic_manual';
manifest.workflow.renderBlockedReason = check.unresolved.length ? 'semantic_risks_unresolved' : null;
manifest.workflow.semanticPlan = {
  sourceMotionMap: path.relative(caseDir, sourceFile),
  sourceMotionMapSha256: createHash('sha256').update(sourceRaw).digest('hex'),
  compiledMotionMapSha256: createHash('sha256').update(compiledRaw).digest('hex'),
  compiler: 'scripts/compile-motion-map.mjs',
  compilerSha256: createHash('sha256').update(readFileSync(path.join(skillDir, 'scripts', 'compile-motion-map.mjs'))).digest('hex'),
  semanticCoreSha256: createHash('sha256').update(readFileSync(path.join(skillDir, 'scripts', 'semantic-core.mjs'))).digest('hex'),
  compiledAt: new Date().toISOString(),
  compileDurationMs: Number((performance.now() - started).toFixed(1)),
  warnings: check.warnings,
  unresolvedWarnings: check.unresolved,
};
writeJson(manifestPath, manifest);
console.log(JSON.stringify({
  result: check.unresolved.length ? 'blocked_by_semantic_risks' : 'pass',
  nodes: manifest.nodes.length,
  warnings: check.warnings,
  unresolved: check.unresolved,
  manifest: manifestPath,
}, null, 2));
if (check.unresolved.length) process.exit(1);
