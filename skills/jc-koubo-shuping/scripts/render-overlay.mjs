#!/usr/bin/env node

import {createRequire} from 'node:module';
import {existsSync, rmSync} from 'node:fs';
import path from 'node:path';
import {
  assertManagedChild,
  commandText,
  ensureDir,
  loadManifest,
  parseArgs,
  runtimeCacheRoot,
  runtimeTemplateDir,
  resolveManifestPath,
  skillDir,
  writeJson,
} from './lib.mjs';
import {assertCanonicalQuality} from './quality-core.mjs';
import {validateWorkflow} from './workflow-core.mjs';

const usage = `Usage:
  node scripts/render-overlay.mjs /abs/case/case_manifest.json [--frames 0-120] [--concurrency 3]

Renders transparent Remotion PNG overlay frames. It does not composite final video.`;

const args = parseArgs(process.argv.slice(2));
if (args.help || args.h || args._.length === 0) {
  console.log(usage);
  process.exit(args._.length === 0 ? 2 : 0);
}

const parseFrameRange = (value) => {
  if (!value) return null;
  const [from, to] = String(value).split('-').map(Number);
  if (!Number.isFinite(from) || !Number.isFinite(to) || to < from) {
    throw new Error(`invalid --frames: ${value}`);
  }
  return [from, to];
};

const {manifestPath, caseDir, manifest} = loadManifest(args._[0]);
if (Number(manifest.schemaVersion) !== 3) throw new Error(`canonical render requires schemaVersion 3; run migrate-case-v3.mjs, got ${manifest.schemaVersion}`);
assertManagedChild(runtimeTemplateDir, runtimeCacheRoot, 'runtime directory');
const nodeModules = path.join(runtimeTemplateDir, 'node_modules');
if (!existsSync(nodeModules)) {
  throw new Error(`Remotion runtime is not installed. Run: node ${path.join(skillDir, 'scripts/install-runtime.mjs')}`);
}

const projectRequire = createRequire(path.join(runtimeTemplateDir, 'package.json'));
const {bundle} = projectRequire('@remotion/bundler');
const {renderFrames, selectComposition} = projectRequire('@remotion/renderer');

const entryPoint = path.join(runtimeTemplateDir, 'src/index.tsx');
const frameRange = parseFrameRange(args.frames);
const purpose = String(args.purpose || (frameRange ? '' : 'full'));
if (!['static-preview', 'pilot', 'full'].includes(purpose)) throw new Error('partial renders require --purpose static-preview or --purpose pilot');
if (purpose !== 'full' && !frameRange) throw new Error(`${purpose} render requires --frames from-to`);
if (purpose === 'full' && frameRange) throw new Error('full render must not use --frames');
const requiredStage = purpose === 'static-preview' ? 'motion_map_ready' : purpose === 'pilot' ? 'static_preview_accepted' : 'pilot_accepted';
if (manifest.workflow?.planningMode !== 'semantic_manual' || !manifest.workflow?.motionMap || !Array.isArray(manifest.nodes) || manifest.nodes.length === 0) {
  throw new Error('semantic render gate failed: author motion map and run compile-motion-map.mjs before any canonical render');
}
if (manifest.workflow?.stage !== requiredStage) throw new Error(`${purpose} render requires exact workflow.stage=${requiredStage}, got ${manifest.workflow?.stage}`);
const workflowCheck = validateWorkflow({caseDir, manifest, requiredStage});
if (workflowCheck.failures.length) throw new Error(`workflow gate failed for ${purpose}: ${workflowCheck.failures.join('; ')}`);
const defaultOutput = purpose === 'full' ? 'remotion_overlay_frames' : `preview_overlay_frames/${purpose}`;
const outputDir = resolveManifestPath(caseDir, args.out || defaultOutput);
const bundleDir = path.join(caseDir, purpose === 'full' ? 'remotion_bundle' : `remotion_bundle_${purpose}`);
assertManagedChild(outputDir, caseDir, 'overlay output directory');
assertManagedChild(bundleDir, caseDir, 'Remotion bundle directory');
const compositionId = 'JCKouboOverlay';
const quality = assertCanonicalQuality(manifest.qualityProfile, {width: manifest.video?.width, height: manifest.video?.height});
const renderScale = Number(quality.overlay.renderScale);
if (!Number.isFinite(renderScale) || renderScale <= 0) {
  throw new Error(`invalid render scale: ${renderScale}`);
}
if (args.scale && Math.abs(Number(args.scale) - renderScale) > 0.000001) throw new Error(`--scale cannot override canonical render scale ${renderScale}`);
const sourceWidth = Number(manifest.video?.width || 720);
const sourceHeight = Number(manifest.video?.height || 1280);
const overlayWidth = Number(quality.overlay?.width || Math.round(sourceWidth * renderScale));
const overlayHeight = Number(quality.overlay?.height || Math.round(sourceHeight * renderScale));

rmSync(outputDir, {recursive: true, force: true});
rmSync(bundleDir, {recursive: true, force: true});
ensureDir(outputDir);
ensureDir(bundleDir);

if (purpose === 'full') {
  const component = path.join(runtimeTemplateDir, 'src/TalkingHeadOverlay.tsx');
  const styleRenderer = path.join(runtimeTemplateDir, 'src', manifest.visualStyleId === 'assembly-mono' ? 'AssemblyMonoHero.tsx' : 'MgHero.tsx');
  manifest.visualRenderer = 'Remotion';
  manifest.remotion = {
    component,
    visualStyleId: manifest.visualStyleId,
    baselineId: manifest.workflow.baselineId,
    styleRenderer,
    entry: entryPoint,
    compositionId,
    rendererScript: path.join(skillDir, 'scripts/render-overlay.mjs'),
    rendererSha256: commandText('shasum', ['-a', '256', path.join(skillDir, 'scripts/render-overlay.mjs')]).split(/\s+/u)[0],
    componentSha256: commandText('shasum', ['-a', '256', component]).split(/\s+/u)[0],
    styleRendererSha256: commandText('shasum', ['-a', '256', styleRenderer]).split(/\s+/u)[0],
    rootSha256: commandText('shasum', ['-a', '256', path.join(runtimeTemplateDir, 'src/Root.tsx')]).split(/\s+/u)[0],
    themeSha256: commandText('shasum', ['-a', '256', path.join(runtimeTemplateDir, 'src/theme.ts')]).split(/\s+/u)[0],
    packageLockSha256: commandText('shasum', ['-a', '256', path.join(runtimeTemplateDir, 'package-lock.json')]).split(/\s+/u)[0],
  };
  manifest.overlayFrames = {
    dir: path.relative(caseDir, outputDir),
    pattern: 'element-*.png',
    startNumber: 0,
    expectedCount: Number(manifest.video?.frameCount),
    width: overlayWidth,
    height: overlayHeight,
    renderScale,
  };
  writeJson(manifestPath, manifest);
}

const inputProps = {manifest};
const serveUrl = await bundle({
  entryPoint,
  outDir: bundleDir,
  rootDir: runtimeTemplateDir,
  publicDir: path.join(runtimeTemplateDir, 'public'),
  enableCaching: true,
  symlinkPublicDir: true,
});

const composition = await selectComposition({
  serveUrl,
  id: compositionId,
  inputProps,
  timeoutInMilliseconds: 120000,
});

await renderFrames({
  serveUrl,
  composition,
  outputDir,
  inputProps,
  imageFormat: 'png',
  imageSequencePattern: 'element-[frame].png',
  frameRange,
  scale: renderScale,
  concurrency: Number(args.concurrency || 3),
  muted: true,
  timeoutInMilliseconds: 120000,
  logLevel: 'info',
});

console.log(`[jc-koubo-shuping] overlay frames -> ${outputDir} (${overlayWidth}x${overlayHeight}, scale=${renderScale})`);
