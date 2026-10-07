#!/usr/bin/env node

import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import {existsSync, readFileSync} from 'node:fs';
import path from 'node:path';
import {analyzeCaptionTrack} from './caption-layout-core.mjs';
import {
  assertFile,
  assertManagedChild,
  ensureDir,
  loadManifest,
  parseArgs,
  resolveManifestPath,
  runtimeCacheRoot,
  runtimeTemplateDir,
  skillDir,
  writeJson,
} from './lib.mjs';
import {appendWorkflowStage, validateWorkflow} from './workflow-core.mjs';

const usage = `Usage:
  node scripts/render-static-preview.mjs /abs/case/case_manifest.json [--points 3.8,11.8,16.5,23,33.5,45.5] [--width 1080]

Renders 4-6 sparse Remotion stills, composites them on source frames, creates contact sheets,
records a minimal preview manifest, and stops for human review.`;

const args = parseArgs(process.argv.slice(2));
if (args.help || args.h || args._.length === 0) {
  console.log(usage);
  process.exit(args._.length === 0 ? 2 : 0);
}

const sha256 = (file) => createHash('sha256').update(readFileSync(file)).digest('hex');
const command = (bin, argv) => execFileSync(bin, argv, {encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe']});
const unique = (values) => [...new Set(values.map((value) => Number(Number(value).toFixed(3))))];

function defaultPoints(manifest) {
  const nodes = manifest.nodes || [];
  if (nodes.length < 4) throw new Error('fast preview requires at least 4 semantic beats or explicit --points');
  const indexes = nodes.length <= 6 ? nodes.map((_, index) => index) : [0, 1, 2, Math.floor(nodes.length / 2), nodes.length - 2, nodes.length - 1];
  return unique(indexes.map((index) => {
    const node = nodes[index];
    return Math.min(Number(node.end) - 0.1, Number(node.start) + Math.min(1, (Number(node.end) - Number(node.start)) / 2));
  }));
}

function requestedPoints(manifest) {
  const values = args.points ? String(args.points).split(',').map(Number) : defaultPoints(manifest);
  const points = unique(values);
  if (points.length < 4 || points.length > 6 || points.some((value) => !Number.isFinite(value) || value < 0 || value >= Number(manifest.video?.duration))) {
    throw new Error(`preview points must contain 4-6 unique in-range seconds, got ${JSON.stringify(points)}`);
  }
  return points;
}

function contactSheet(files, output, tileWidth, tileHeight, columns = 3, cropTop = false) {
  const inputs = files.flatMap((file) => ['-i', file]);
  const filters = files.map((_, index) => cropTop
    ? `[${index}:v]crop=iw:ih*0.34:0:0,scale=${tileWidth}:${Math.round(tileHeight * 0.34)}[p${index}]`
    : `[${index}:v]scale=${tileWidth}:${tileHeight}[p${index}]`).join(';');
  const actualHeight = cropTop ? Math.round(tileHeight * 0.34) : tileHeight;
  const layout = files.map((_, index) => `${(index % columns) * tileWidth}_${Math.floor(index / columns) * actualHeight}`).join('|');
  command('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', ...inputs, '-filter_complex', `${filters};${files.map((_, index) => `[p${index}]`).join('')}xstack=inputs=${files.length}:layout=${layout}:fill=0x202020[out]`, '-map', '[out]', '-frames:v', '1', '-q:v', '2', output]);
}

const {manifestPath, caseDir, manifest} = loadManifest(args._[0]);
if (Number(manifest.schemaVersion) !== 3) throw new Error('fast preview requires schemaVersion 3');
if (!['motion_map_ready', 'static_preview_pending'].includes(manifest.workflow?.stage)) {
  throw new Error(`fast preview requires motion_map_ready or static_preview_pending, got ${manifest.workflow?.stage}`);
}
const workflowCheck = validateWorkflow({caseDir, manifest, requiredStage: 'motion_map_ready'});
if (workflowCheck.failures.length) throw new Error(`workflow gate failed: ${workflowCheck.failures.join('; ')}`);
const captionReport = analyzeCaptionTrack(manifest.captionTrack || []);
ensureDir(path.join(caseDir, 'reports'));
writeJson(path.join(caseDir, 'reports', 'caption-preflight.json'), {...captionReport, generatedAt: new Date().toISOString()});
if (captionReport.result !== 'pass') throw new Error(`caption P1 preflight failed: ${captionReport.failures.map((item) => item.id).join(', ')}`);

const execution = manifest.workflow.execution || {};
const cycle = Number(execution.cycle || 1);
const maxAttempts = Number(execution.maxRenderAttempts || 2);
const attempt = Number(execution.renderAttempts || 0) + 1;
if (attempt > maxAttempts) throw new Error(`AUTO_FIX_LIMIT_REACHED: ${attempt - 1}/${maxAttempts} previews already rendered; WAIT_USER`);

assertManagedChild(runtimeTemplateDir, runtimeCacheRoot, 'runtime directory');
const nodeModules = path.join(runtimeTemplateDir, 'node_modules');
if (!existsSync(nodeModules)) throw new Error(`Remotion runtime missing; run node ${path.join(skillDir, 'scripts/install-runtime.mjs')}`);
const templateFiles = [
  'src/index.tsx',
  'src/Root.tsx',
  'src/TalkingHeadOverlay.tsx',
  'src/MgHero.tsx',
  'src/AssemblyMonoHero.tsx',
  'src/theme.ts',
  'src/types.ts',
  'src/mg-layout.json',
  'package-lock.json',
].map((file) => path.join(runtimeTemplateDir, file));
templateFiles.forEach((file) => assertFile(file, 'runtime template file'));
const templateHash = createHash('sha256');
templateFiles.forEach((file) => templateHash.update(readFileSync(file)));
const cacheKey = templateHash.digest('hex').slice(0, 20);
const bundleDir = path.join(runtimeCacheRoot, 'remotion-bundles', cacheKey);
assertManagedChild(bundleDir, runtimeCacheRoot, 'preview bundle cache');
ensureDir(bundleDir);

const projectRequire = createRequire(path.join(runtimeTemplateDir, 'package.json'));
const {bundle} = projectRequire('@remotion/bundler');
const {openBrowser, renderStill, selectComposition} = projectRequire('@remotion/renderer');
let bundleReused = existsSync(path.join(bundleDir, 'index.html'));
let serveUrl = bundleDir;
if (!bundleReused) {
  serveUrl = await bundle({
    entryPoint: path.join(runtimeTemplateDir, 'src/index.tsx'),
    outDir: bundleDir,
    rootDir: runtimeTemplateDir,
    publicDir: path.join(runtimeTemplateDir, 'public'),
    enableCaching: true,
    symlinkPublicDir: true,
  });
}

const sourceVideo = resolveManifestPath(caseDir, manifest.sourceVideo);
assertFile(sourceVideo, 'source video');
const points = requestedPoints(manifest);
const previewWidth = Number(args.width || 1080);
if (!Number.isFinite(previewWidth) || previewWidth < 360 || previewWidth > 1080) throw new Error('--width must be between 360 and 1080');
const previewHeight = Math.round(previewWidth * Number(manifest.video.height) / Number(manifest.video.width));
const scale = previewWidth / Number(manifest.video.width);
const cycleLabel = `cycle-${String(cycle).padStart(2, '0')}`;
const attemptLabel = `attempt-${String(attempt).padStart(2, '0')}`;
const attemptDir = path.join(caseDir, 'preview', cycleLabel, attemptLabel);
const overlayDir = path.join(attemptDir, 'overlay');
const sourceDir = path.join(attemptDir, 'source');
const compositeDir = path.join(attemptDir, 'composite');
const qaDir = path.join(caseDir, 'qa');
[overlayDir, sourceDir, compositeDir, qaDir].forEach(ensureDir);

const inputProps = {manifest};
const browser = await openBrowser('chrome', {chromeMode: 'headless-shell', logLevel: 'warn'});
let composition;
try {
  composition = await selectComposition({serveUrl, id: 'JCKouboOverlay', inputProps, puppeteerInstance: browser, timeoutInMilliseconds: 120000, logLevel: 'warn'});
  for (const [index, seconds] of points.entries()) {
    const frame = Math.min(Number(manifest.video.frameCount) - 1, Math.round(seconds * Number(manifest.video.fps)));
    await renderStill({
      serveUrl,
      composition,
      inputProps,
      puppeteerInstance: browser,
      frame,
      output: path.join(overlayDir, `${String(index + 1).padStart(2, '0')}-f${frame}.png`),
      imageFormat: 'png',
      overwrite: true,
      scale,
      timeoutInMilliseconds: 120000,
      logLevel: 'warn',
    });
  }
} finally {
  await browser.close({silent: true});
}

const composites = [];
const pointRecords = [];
for (const [index, seconds] of points.entries()) {
  const id = String(index + 1).padStart(2, '0');
  const frame = Math.min(Number(manifest.video.frameCount) - 1, Math.round(seconds * Number(manifest.video.fps)));
  const overlay = path.join(overlayDir, `${id}-f${frame}.png`);
  const source = path.join(sourceDir, `${id}-${seconds.toFixed(3)}s.png`);
  const composite = path.join(compositeDir, `${id}-${seconds.toFixed(3)}s.jpg`);
  command('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-ss', String(seconds), '-i', sourceVideo, '-vf', `scale=${previewWidth}:${previewHeight}:flags=spline`, '-frames:v', '1', source]);
  command('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-i', source, '-i', overlay, '-filter_complex', '[0:v][1:v]overlay=0:0:format=auto', '-frames:v', '1', '-q:v', '2', composite]);
  composites.push(composite);
  pointRecords.push({seconds, frame, composite: path.relative(caseDir, composite), sha256: sha256(composite)});
}

const tileWidth = 360;
const tileHeight = Math.round(tileWidth * previewHeight / previewWidth);
const contact = path.join(qaDir, `static-preview-${cycleLabel}-${attemptLabel}.jpg`);
const topContact = path.join(qaDir, `publish-safe-top-${cycleLabel}-${attemptLabel}.jpg`);
contactSheet(composites, contact, tileWidth, tileHeight);
contactSheet(composites, topContact, tileWidth, tileHeight, 3, true);

manifest.workflow.execution = {
  ...execution,
  mode: 'fast_preview',
  cycle,
  maxRenderAttempts: maxAttempts,
  maxAutoFixes: Number(execution.maxAutoFixes || 1),
  renderAttempts: attempt,
  autoFixes: Number(execution.autoFixes || 0),
  status: attempt >= maxAttempts ? 'wait_user' : 'pending_human_review',
};
manifest.workflow.staticPreview = {
  ...(manifest.workflow.staticPreview || {}),
  files: pointRecords.map((point) => point.composite),
  contactSheet: path.relative(caseDir, contact),
  decision: 'pending',
  reviewerType: null,
  userStatement: null,
  evidence: null,
};
if (manifest.workflow.stage === 'motion_map_ready') appendWorkflowStage(manifest.workflow, 'static_preview_pending');
const baselineLock = path.join(skillDir, 'assets', 'baselines', String(manifest.workflow.baselineId), 'baseline-lock.json');
assertFile(baselineLock, 'baseline lock');
const previewManifest = {
  schemaVersion: 'jc-koubo-shuping.fast-preview.v1',
  generatedAt: new Date().toISOString(),
  cycle,
  attempt,
  limits: {maxRenderAttempts: maxAttempts, maxAutoFixes: Number(manifest.workflow.execution.maxAutoFixes)},
  input: {video: path.relative(caseDir, sourceVideo), videoSha256: sha256(sourceVideo), subtitle: manifest.subtitle, subtitleSha256: sha256(resolveManifestPath(caseDir, manifest.subtitle))},
  visualStyleId: manifest.visualStyleId,
  baseline: {id: manifest.workflow.baselineId, lock: path.relative(skillDir, baselineLock), lockSha256: sha256(baselineLock)},
  fingerprints: {templateHash: cacheKey, motionMapSha256: sha256(resolveManifestPath(caseDir, manifest.workflow.motionMap))},
  cache: {bundleDir, reused: bundleReused},
  render: {compositionId: 'JCKouboOverlay', width: previewWidth, height: previewHeight, points: pointRecords},
  qa: {captionPreflight: 'reports/caption-preflight.json', contactSheet: path.relative(caseDir, contact), publishSafeTopContactSheet: path.relative(caseDir, topContact)},
  warnings: workflowCheck.warnings,
  next: 'WAIT_USER',
};
writeJson(path.join(attemptDir, 'preview-manifest.json'), previewManifest);
writeJson(manifestPath, manifest);
const finalCheck = validateWorkflow({caseDir, manifest, requiredStage: 'static_preview_pending'});
writeJson(path.join(qaDir, `workflow-validation-preview-${cycleLabel}-${attemptLabel}.json`), finalCheck);
if (finalCheck.failures.length) throw new Error(`post-render workflow validation failed: ${finalCheck.failures.join('; ')}`);
console.log(JSON.stringify({result: 'pass_pending_human_review', cycle, attempt, contactSheet: contact, bundleReused, next: 'WAIT_USER'}, null, 2));
