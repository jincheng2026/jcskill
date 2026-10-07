#!/usr/bin/env node

import {execFileSync} from 'node:child_process';
import {closeSync, existsSync, openSync, readFileSync, readSync, readdirSync, statSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import {
  assertManagedChild,
  audioStream,
  commandText,
  ffprobeJson,
  frameCount,
  loadManifest,
  parseArgs,
  parseFraction,
  remotionTemplateDir,
  resolveManifestPath,
  runtimeTemplateDir,
  scriptDir,
  toRelative,
  videoStream,
  writeJson,
} from './lib.mjs';
import {assertCanonicalQuality, qualityProfileDifferences} from './quality-core.mjs';
import {appendWorkflowStage, validateWorkflow} from './workflow-core.mjs';

const usage = `Usage:
  node scripts/validate-final.mjs /abs/case/case_manifest.json
  node scripts/validate-final.mjs /abs/case/case_manifest.json --record-technical
  node scripts/validate-final.mjs /abs/case/case_manifest.json --require-acceptance

The default mode is read-only. --record-technical records a successful technical
gate and advances full_rendered -> technical_pass. Release mode validates a
declared external user decision; it does not cryptographically authenticate its author.`;

const args = parseArgs(process.argv.slice(2));
if (args.help || args.h || args._.length === 0) {
  console.log(usage);
  process.exit(args._.length === 0 ? 2 : 0);
}
const requireAcceptance = Boolean(args['require-acceptance']);
const recordTechnical = Boolean(args['record-technical']);
if (requireAcceptance && recordTechnical) throw new Error('--require-acceptance and --record-technical are mutually exclusive');

const pass = [];
const warnings = [];
const failures = [];
const addPass = (message) => pass.push(message);
const addWarn = (message) => warnings.push(message);
const addFail = (message) => failures.push(message);
const nearlyEqual = (a, b, tolerance) => Number.isFinite(a) && Number.isFinite(b) && Math.abs(a - b) <= tolerance;
const sha256 = (file) => commandText('shasum', ['-a', '256', file]).match(/\b[a-f0-9]{64}\b/iu)?.[0]?.toLowerCase();

function requireFile(file, label) {
  if (!file || !existsSync(file) || !statSync(file).isFile() || statSync(file).size === 0) {
    addFail(`${label} missing or empty: ${file}`);
    return null;
  }
  return file;
}

function readJsonFile(file, label) {
  try {
    return JSON.parse(readFileSync(file, 'utf8'));
  } catch (error) {
    addFail(`${label} invalid JSON: ${file}: ${error.message}`);
    return null;
  }
}

function requireImage(file, label) {
  if (!requireFile(file, label)) return false;
  try {
    const stream = videoStream(ffprobeJson(file));
    if (!stream || Number(stream.width) < 32 || Number(stream.height) < 32) {
      addFail(`${label} is not a decodable image: ${file}`);
      return false;
    }
    return true;
  } catch (error) {
    addFail(`${label} image decode failed: ${file}: ${error.message}`);
    return false;
  }
}

function listOverlayFrames(dir) {
  if (!existsSync(dir) || !statSync(dir).isDirectory()) return [];
  return readdirSync(dir)
    .filter((name) => /^element-\d+\.png$/u.test(name))
    .map((name) => ({name, number: Number(name.match(/^element-(\d+)\.png$/u)[1]), file: path.join(dir, name)}))
    .sort((a, b) => a.number - b.number);
}

function pngHeader(file) {
  const buffer = Buffer.alloc(26);
  const descriptor = openSync(file, 'r');
  try {
    if (readSync(descriptor, buffer, 0, buffer.length, 0) !== buffer.length) return null;
  } finally {
    closeSync(descriptor);
  }
  const signature = buffer.subarray(0, 8).toString('hex');
  if (signature !== '89504e470d0a1a0a' || buffer.subarray(12, 16).toString('ascii') !== 'IHDR') return null;
  return {width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20), colorType: buffer[25]};
}

function validateTransparentSample(file, label) {
  try {
    const alpha = execFileSync('ffmpeg', ['-v', 'error', '-i', file, '-vf', 'alphaextract', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], {
      encoding: 'buffer',
      maxBuffer: 64 * 1024 * 1024,
    });
    let minimum = 255;
    for (const value of alpha) minimum = Math.min(minimum, value);
    if (minimum !== 0) addFail(`${label} has no transparent pixel; overlay may cover the source`);
  } catch (error) {
    addFail(`${label} alpha decode failed: ${error.message}`);
  }
}

function validateOverlay(caseDir, manifest, expectedWidth, expectedHeight) {
  const overlayDir = resolveManifestPath(caseDir, manifest.overlayFrames?.dir);
  if (!overlayDir || !existsSync(overlayDir) || !statSync(overlayDir).isDirectory()) {
    addFail(`overlayFrames.dir missing: ${overlayDir}`);
    return;
  }
  const frames = listOverlayFrames(overlayDir);
  const expected = Number(manifest.overlayFrames?.expectedCount);
  if (!Number.isInteger(expected) || frames.length !== expected) addFail(`overlay frame count mismatch: expected=${expected}, actual=${frames.length}`);
  for (let index = 0; index < frames.length; index += 1) {
    const frame = frames[index];
    if (frame.number !== index) addFail(`overlay frames are not contiguous at ${frame.name}`);
    const header = pngHeader(frame.file);
    if (!header) addFail(`overlay frame is not PNG: ${frame.name}`);
    else {
      if (header.width !== expectedWidth || header.height !== expectedHeight) {
        addFail(`overlay frame size mismatch: ${frame.name}, expected=${expectedWidth}x${expectedHeight}, actual=${header.width}x${header.height}`);
      }
      if (![4, 6].includes(header.colorType)) addFail(`overlay frame lacks alpha channel: ${frame.name}`);
    }
  }
  const sampleIndexes = [...new Set([0, Math.floor(frames.length / 4), Math.floor(frames.length / 2), Math.floor((frames.length * 3) / 4), frames.length - 1])]
    .filter((index) => frames[index]);
  for (const index of sampleIndexes) validateTransparentSample(frames[index].file, `overlay frame ${frames[index].name}`);
  if (frames.length === expected && failures.length === 0) addPass(`all overlay PNG headers ok: ${frames.length}`);
}

function validateMedia(sourceVideo, finalVideo, manifest) {
  const sourceProbe = ffprobeJson(sourceVideo);
  const finalProbe = ffprobeJson(finalVideo);
  const sourceV = videoStream(sourceProbe);
  const finalV = videoStream(finalProbe);
  if (!sourceV || !finalV) {
    addFail('source or final has no video stream');
    return {};
  }
  let quality = null;
  try {
    quality = assertCanonicalQuality(manifest.qualityProfile, {width: sourceV.width, height: sourceV.height});
    addPass(`canonical quality profile ok: ${quality.name}`);
  } catch (error) {
    addFail(error.message);
    return {sourceProbe, finalProbe, sourceV, finalV};
  }
  const expectedWidth = Number(quality.output.width);
  const expectedHeight = Number(quality.output.height);
  if (Number(finalV.width) !== expectedWidth || Number(finalV.height) !== expectedHeight) addFail(`final size mismatch: expected=${expectedWidth}x${expectedHeight}, actual=${finalV.width}x${finalV.height}`);
  if (finalV.codec_name !== 'h264') addFail(`final codec must be h264, got ${finalV.codec_name}`);
  if (String(finalV.profile || '').toLowerCase() !== 'high') addFail(`final H.264 profile must be High, got ${finalV.profile}`);
  if (finalV.pix_fmt !== 'yuv420p') addFail(`final pixel format must be yuv420p, got ${finalV.pix_fmt}`);
  for (const [field, expected] of [['color_space', 'bt709'], ['color_transfer', 'bt709'], ['color_primaries', 'bt709']]) {
    if (sourceV[field] !== expected) addFail(`source ${field} must be ${expected}, got ${sourceV[field]}`);
    if (finalV[field] !== expected) addFail(`final ${field} must be ${expected}, got ${finalV[field]}`);
  }
  if (!['tv', 'mpeg'].includes(sourceV.color_range)) addFail(`source color_range must be limited, got ${sourceV.color_range}`);
  if (!['tv', 'mpeg'].includes(finalV.color_range)) addFail(`final color_range must be limited, got ${finalV.color_range}`);
  const sourceFrames = frameCount(sourceV);
  const finalFrames = frameCount(finalV);
  if (!sourceFrames || sourceFrames !== finalFrames || finalFrames !== Number(manifest.video?.frameCount)) {
    addFail(`frame count mismatch: source=${sourceFrames}, final=${finalFrames}, manifest=${manifest.video?.frameCount}`);
  } else addPass(`frame count ok: ${finalFrames}`);
  const sourceFps = parseFraction(sourceV.avg_frame_rate || sourceV.r_frame_rate);
  const finalFps = parseFraction(finalV.avg_frame_rate || finalV.r_frame_rate);
  if (!nearlyEqual(sourceFps, finalFps, 0.001)) addFail(`fps mismatch: source=${sourceFps}, final=${finalFps}`);
  const sourceDuration = Number(sourceProbe.format?.duration || sourceV.duration);
  const finalDuration = Number(finalProbe.format?.duration || finalV.duration);
  if (!nearlyEqual(sourceDuration, finalDuration, 0.05)) addFail(`duration mismatch: source=${sourceDuration}, final=${finalDuration}`);
  const sourceAudio = (sourceProbe.streams || []).filter((stream) => stream.codec_type === 'audio');
  const finalAudio = (finalProbe.streams || []).filter((stream) => stream.codec_type === 'audio');
  if (sourceAudio.length !== 1) addFail(`source must contain exactly one audio stream, got ${sourceAudio.length}`);
  if (finalAudio.length !== 1) addFail(`final must contain exactly one audio stream, got ${finalAudio.length}`);
  if (audioStream(sourceProbe) && audioStream(finalProbe)) {
    const sourceHash = commandText('ffmpeg', ['-v', 'error', '-i', sourceVideo, '-map', '0:a:0', '-c:a', 'copy', '-f', 'hash', '-hash', 'SHA256', '-']);
    const finalHash = commandText('ffmpeg', ['-v', 'error', '-i', finalVideo, '-map', '0:a:0', '-c:a', 'copy', '-f', 'hash', '-hash', 'SHA256', '-']);
    if (sourceHash !== finalHash) addFail(`audio packet hash mismatch: source=${sourceHash}, final=${finalHash}`);
    else addPass('audio packet hash ok');
  }
  return {sourceProbe, finalProbe, sourceV, finalV, quality, expectedWidth, expectedHeight};
}

function flagValue(argv, flag) {
  const index = argv.indexOf(flag);
  return index === -1 ? null : argv[index + 1];
}

function containsSequence(argv, sequence) {
  return argv.some((_, index) => sequence.every((part, offset) => argv[index + offset] === part));
}

function validateRenderEvidence(caseDir, manifest, media, sourceVideo, finalVideo) {
  const evidencePath = resolveManifestPath(caseDir, manifest.qa?.renderEvidence || manifest.composite?.renderEvidence);
  if (!requireFile(evidencePath, 'qa.renderEvidence')) return;
  const evidence = readJsonFile(evidencePath, 'qa.renderEvidence');
  if (!evidence) return;
  const actualSourceSha = sha256(sourceVideo);
  const actualFinalSha = sha256(finalVideo);
  if (evidence.sourceSha256 !== actualSourceSha) addFail('render evidence source SHA mismatch');
  if (evidence.finalSha256 !== actualFinalSha) addFail('render evidence final SHA mismatch');
  const compositor = path.join(scriptDir, 'composite-preserve-source.mjs');
  if (evidence.compositorScriptSha256 !== sha256(compositor)) addFail('render evidence compositor script SHA mismatch');
  const differences = qualityProfileDifferences(evidence.qualityProfile, media.quality || {});
  if (differences.length) addFail(`render evidence quality profile mismatch: ${differences.map((item) => item.field).join(', ')}`);
  const videoArgs = evidence.videoArgs;
  const remuxArgs = evidence.remuxArgs;
  if (!Array.isArray(videoArgs) || !Array.isArray(remuxArgs)) {
    addFail('render evidence must contain structured videoArgs and remuxArgs');
    return;
  }
  if (videoArgs.includes('-shortest') || videoArgs.join(' ').includes('shortest=1')) addFail('videoArgs contains forbidden shortest behavior');
  const encoding = media.quality?.videoEncoding || {};
  if (flagValue(videoArgs, '-c:v') !== encoding.codec) addFail(`videoArgs codec mismatch: ${flagValue(videoArgs, '-c:v')}`);
  if (flagValue(videoArgs, '-pix_fmt') !== 'yuv420p') addFail('videoArgs pixel format is not yuv420p');
  if (encoding.codec === 'libx264') {
    if (flagValue(videoArgs, '-crf') !== '8' || flagValue(videoArgs, '-preset') !== 'slow' || flagValue(videoArgs, '-profile:v') !== 'high') {
      addFail('videoArgs must use libx264 CRF 8 slow High');
    }
  } else if (flagValue(videoArgs, '-b:v') !== '45M' || flagValue(videoArgs, '-profile:v') !== 'high') {
    addFail('videoArgs must use h264_videotoolbox 45M High');
  }
  const filter = flagValue(videoArgs, '-filter_complex') || '';
  if (media.quality?.upscale?.enabled && (!filter.includes('filter=spline36') || !filter.includes(`w=${media.expectedWidth}:h=${media.expectedHeight}`))) {
    addFail('videoArgs do not prove canonical spline36 upscale');
  }
  if (!containsSequence(remuxArgs, ['-map', '0:v:0']) || !containsSequence(remuxArgs, ['-map', '1:a:0']) || !containsSequence(remuxArgs, ['-c', 'copy'])) {
    addFail('remuxArgs do not prove video plus original-audio stream copy');
  }
  if (JSON.stringify(manifest.composite?.videoArgs) !== JSON.stringify(videoArgs) || JSON.stringify(manifest.composite?.remuxArgs) !== JSON.stringify(remuxArgs)) {
    addFail('manifest composite argv differ from render evidence');
  } else addPass('structured render evidence ok');
}

function walkSourceFiles(root) {
  const files = [];
  for (const entry of readdirSync(root, {withFileTypes: true})) {
    const file = path.join(root, entry.name);
    if (entry.isDirectory()) files.push(...walkSourceFiles(file));
    else if (/\.(?:ts|tsx|js|jsx)$/u.test(entry.name)) files.push(file);
  }
  return files;
}

function validateRemotion(manifest) {
  const remotion = manifest.remotion || {};
  const canonical = {
    renderer: path.join(scriptDir, 'render-overlay.mjs'),
    component: path.join(runtimeTemplateDir, 'src', 'TalkingHeadOverlay.tsx'),
    styleRenderer: path.join(runtimeTemplateDir, 'src', manifest.visualStyleId === 'assembly-mono' ? 'AssemblyMonoHero.tsx' : 'MgHero.tsx'),
  };
  if (path.resolve(remotion.rendererScript || '') !== path.resolve(canonical.renderer)) addFail('remotion.rendererScript is not the canonical Skill renderer');
  if (path.resolve(remotion.component || '') !== path.resolve(canonical.component)) addFail('remotion.component is not the managed runtime component');
  if (path.resolve(remotion.styleRenderer || '') !== path.resolve(canonical.styleRenderer)) addFail('remotion.styleRenderer does not match manifest.visualStyleId');
  if (remotion.visualStyleId !== manifest.visualStyleId) addFail('remotion.visualStyleId does not match manifest.visualStyleId');
  if (remotion.baselineId !== manifest.workflow?.baselineId) addFail('remotion.baselineId does not match workflow.baselineId');
  const files = {
    renderer: remotion.rendererScript,
    component: remotion.component,
    styleRenderer: remotion.styleRenderer,
    root: remotion.component ? path.join(path.dirname(remotion.component), 'Root.tsx') : null,
    theme: remotion.component ? path.join(path.dirname(remotion.component), 'theme.ts') : null,
    packageLock: remotion.component ? path.join(path.dirname(path.dirname(remotion.component)), 'package-lock.json') : null,
  };
  for (const [label, file] of Object.entries(files)) requireFile(file, `remotion.${label}`);
  const hashes = {
    rendererSha256: files.renderer && existsSync(files.renderer) ? sha256(files.renderer) : null,
    componentSha256: files.component && existsSync(files.component) ? sha256(files.component) : null,
    styleRendererSha256: files.styleRenderer && existsSync(files.styleRenderer) ? sha256(files.styleRenderer) : null,
    rootSha256: files.root && existsSync(files.root) ? sha256(files.root) : null,
    themeSha256: files.theme && existsSync(files.theme) ? sha256(files.theme) : null,
    packageLockSha256: files.packageLock && existsSync(files.packageLock) ? sha256(files.packageLock) : null,
  };
  for (const [key, actual] of Object.entries(hashes)) if (!remotion[key] || remotion[key] !== actual) addFail(`remotion.${key} mismatch`);
  for (const name of ['TalkingHeadOverlay.tsx', 'MgHero.tsx', 'AssemblyMonoHero.tsx', 'Root.tsx', 'theme.ts']) {
    const runtimeFile = path.join(runtimeTemplateDir, 'src', name);
    const bundledFile = path.join(remotionTemplateDir, 'src', name);
    if (!existsSync(runtimeFile) || !existsSync(bundledFile) || sha256(runtimeFile) !== sha256(bundledFile)) addFail(`runtime template drifted from bundled source: ${name}`);
  }
  const runtimeLock = path.join(runtimeTemplateDir, 'package-lock.json');
  const bundledLock = path.join(remotionTemplateDir, 'package-lock.json');
  if (!existsSync(runtimeLock) || !existsSync(bundledLock) || sha256(runtimeLock) !== sha256(bundledLock)) addFail('runtime package-lock drifted from bundled source');
  if (remotion.compositionId !== 'JCKouboOverlay') addFail(`unexpected Remotion composition: ${remotion.compositionId}`);
  if (files.component && existsSync(files.component)) {
    const sourceRoot = path.dirname(files.component);
    const forbidden = /OffthreadVideo|Html5Video|<Video\b|<video\b|<Img\b|<img\b|drawImage|<canvas\b|backgroundImage|url\s*\(/u;
    for (const file of walkSourceFiles(sourceRoot)) if (forbidden.test(readFileSync(file, 'utf8'))) addFail(`Remotion overlay source contains forbidden source-media renderer: ${file}`);
  }
  if (!failures.some((item) => item.startsWith('remotion.') || item.includes('Remotion overlay'))) addPass('Remotion provenance and overlay-only source graph ok');
}

function validateQa(caseDir, manifest, finalSha) {
  const qa = manifest.qa || {};
  for (const [key, label] of [['sourceFfprobe', 'qa.sourceFfprobe'], ['finalFfprobe', 'qa.finalFfprobe']]) {
    const file = resolveManifestPath(caseDir, qa[key]);
    if (requireFile(file, label)) readJsonFile(file, label);
  }
  const coveragePath = resolveManifestPath(caseDir, qa.coverageManifest);
  const coverage = requireFile(coveragePath, 'qa.coverageManifest') ? readJsonFile(coveragePath, 'qa.coverageManifest') : null;
  const requiredContacts = ['sourceContactSheet', 'finalContactSheet', 'overviewContactSheet', 'sceneBoundaryContactSheet', 'captionRiskContactSheet', 'cueCoverageContactSheet', 'safeZoneContactSheet', 'publishSafeTopContactSheet', 'animationRiskContactSheet'];
  for (const key of requiredContacts) {
    const pages = qa[key];
    if (!Array.isArray(pages) || pages.length === 0) {
      addFail(`qa.${key} must contain one or more pages`);
      continue;
    }
    const coveragePages = coverage?.[key]?.pages || [];
    if (JSON.stringify(pages) !== JSON.stringify(coveragePages)) addFail(`qa.${key} pages differ from coverage manifest`);
    if (!Array.isArray(coverage?.[key]?.frames) || coverage[key].frames.length === 0) addFail(`qa.${key} frame coverage is empty`);
    pages.forEach((value, index) => requireImage(resolveManifestPath(caseDir, value), `qa.${key}[${index}]`));
  }
  const hasOverlap = (manifest.captionTrack || []).some((cue, index, cues) => Number(cue.end) > Number(cues[index + 1]?.start ?? cue.end));
  if (hasOverlap) {
    const pages = qa.overlapContactSheet;
    if (!Array.isArray(pages) || pages.length === 0) addFail('qa.overlapContactSheet required for overlapping source cues');
    else pages.forEach((value, index) => requireImage(resolveManifestPath(caseDir, value), `qa.overlapContactSheet[${index}]`));
  }
  const decodePath = resolveManifestPath(caseDir, qa.fullDecode);
  const decode = requireFile(decodePath, 'qa.fullDecode') ? readJsonFile(decodePath, 'qa.fullDecode') : null;
  if (decode?.result !== 'pass' || decode?.finalSha256 !== finalSha) addFail('qa.fullDecode does not bind successful decode to final SHA');
  const shaPath = resolveManifestPath(caseDir, qa.sha256);
  const recorded = requireFile(shaPath, 'qa.sha256') ? readFileSync(shaPath, 'utf8').match(/\b[a-f0-9]{64}\b/iu)?.[0]?.toLowerCase() : null;
  if (recorded !== finalSha) addFail(`qa.sha256 mismatch: recorded=${recorded}, actual=${finalSha}`);
  else addPass('QA evidence decodes and binds to final SHA');
}

function validatePublishSafeTop(manifest) {
  const themePath = manifest.remotion?.component ? path.join(path.dirname(manifest.remotion.component), 'theme.ts') : null;
  if (!requireFile(themePath, 'publish-safe theme')) return;
  const theme = readFileSync(themePath, 'utf8');
  const value = (name) => Number(theme.match(new RegExp(`${name}\\s*:\\s*([0-9.]+)`, 'u'))?.[1]);
  const progressTop = value('progressTop');
  const cardTop = value('cardTop');
  if (progressTop < 90 || progressTop > 110) addFail(`progressTop outside 720-design publish-safe band: ${progressTop}`);
  if (cardTop < 140 || cardTop > 210) addFail(`cardTop outside 720-design publish-safe band: ${cardTop}`);
}

function validateAcceptance(caseDir, manifest, finalVideo, finalSha) {
  const acceptancePath = resolveManifestPath(caseDir, manifest.acceptance?.record || 'qa/acceptance.json');
  const acceptance = requireFile(acceptancePath, 'qa.acceptance') ? readJsonFile(acceptancePath, 'qa.acceptance') : null;
  if (!acceptance) return false;
  if ((acceptance.caseId || acceptance.case_id) !== manifest.caseId) addFail('qa.acceptance case mismatch');
  if (!['accepted', 'accepted_with_risks'].includes(acceptance.decision)) addFail(`qa.acceptance decision is not accepted: ${acceptance.decision}`);
  if (acceptance.reviewer?.type !== 'human') addFail('qa.acceptance reviewer.type must be human');
  const evidence = acceptance.evidence || {};
  if (evidence.source !== 'external_user_message') addFail('qa.acceptance evidence.source must be external_user_message');
  for (const key of ['threadId', 'messageId', 'recordedAt', 'user_statement']) if (!evidence[key]) addFail(`qa.acceptance evidence.${key} missing`);
  if (evidence.recordedAt && !Number.isFinite(Date.parse(evidence.recordedAt))) addFail('qa.acceptance evidence.recordedAt invalid');
  const artifact = resolveManifestPath(caseDir, acceptance.artifact);
  if (!artifact || path.resolve(artifact) !== path.resolve(finalVideo)) addFail('qa.acceptance artifact must equal manifest.finalVideo');
  else if (sha256(artifact) !== finalSha) addFail('qa.acceptance artifact SHA changed');
  if (!evidence.sha256 || evidence.sha256.toLowerCase() !== finalSha) addFail('qa.acceptance evidence.sha256 mismatch');
  const technical = resolveManifestPath(caseDir, evidence.technical_report);
  const expectedTechnical = resolveManifestPath(caseDir, manifest.qa?.technicalValidation);
  if (!technical || path.resolve(technical) !== path.resolve(expectedTechnical || '')) addFail('qa.acceptance technical_report must equal qa.technicalValidation');
  const technicalData = requireFile(technical, 'qa.acceptance technical report') ? readJsonFile(technical, 'qa.acceptance technical report') : null;
  if (technicalData?.result !== 'technical_pass_pending_acceptance' || technicalData?.finalSha256 !== finalSha) addFail('qa.acceptance technical report is not bound to final SHA');
  return true;
}

const {manifestPath, caseDir, manifest} = loadManifest(args._[0]);
if (Number(manifest.schemaVersion) !== 3) addFail(`canonical final gate requires schemaVersion 3; run migrate-case-v3.mjs, got ${manifest.schemaVersion}`);
const requiredStage = requireAcceptance ? 'technical_pass' : 'full_rendered';
if (requireAcceptance && manifest.workflow?.stage !== 'technical_pass') addFail(`release gate requires exact workflow.stage=technical_pass, got ${manifest.workflow?.stage}`);
if (!requireAcceptance && !['full_rendered', 'technical_pass'].includes(manifest.workflow?.stage)) addFail(`technical gate requires workflow.stage full_rendered or technical_pass, got ${manifest.workflow?.stage}`);
const workflow = validateWorkflow({caseDir, manifest, requiredStage});
for (const failure of workflow.failures) addFail(`workflow: ${failure}`);
if (!workflow.failures.length) addPass(`workflow gate ok: ${workflow.stage}`);

for (const key of ['schemaVersion', 'caseId', 'sourceVideo', 'subtitle', 'visualRenderer', 'compositor', 'remotion', 'overlayFrames', 'finalVideo', 'qa', 'report']) {
  if (!(key in manifest)) addFail(`manifest missing ${key}`);
}
if (manifest.visualRenderer !== 'Remotion') addFail(`visualRenderer must be Remotion, got ${manifest.visualRenderer}`);
if (manifest.compositor !== 'ffmpeg') addFail(`compositor must be ffmpeg, got ${manifest.compositor}`);
if (manifest.sourcePreservation?.sourceInRemotion !== false) addFail('sourcePreservation.sourceInRemotion must be false');
if (manifest.composite?.usedShortest !== false) addFail('composite.usedShortest must be false');
if (manifest.composite?.audioPolicy !== 'copy_original_packets') addFail(`composite.audioPolicy must be copy_original_packets, got ${manifest.composite?.audioPolicy}`);

const sourceVideo = resolveManifestPath(caseDir, manifest.sourceVideo);
const finalVideo = resolveManifestPath(caseDir, manifest.finalVideo);
for (const [file, label] of [[sourceVideo, 'sourceVideo'], [resolveManifestPath(caseDir, manifest.subtitle), 'subtitle'], [finalVideo, 'finalVideo'], [resolveManifestPath(caseDir, manifest.composite?.videoOnlyIntermediate), 'composite.videoOnlyIntermediate']]) {
  if (file) assertManagedChild(file, caseDir, label);
  requireFile(file, label);
}
const media = existsSync(sourceVideo) && existsSync(finalVideo) ? validateMedia(sourceVideo, finalVideo, manifest) : {};
if (media.sourceV) validateOverlay(caseDir, manifest, media.expectedWidth, media.expectedHeight);
validateRemotion(manifest);
if (media.quality) validateRenderEvidence(caseDir, manifest, media, sourceVideo, finalVideo);
const finalSha = existsSync(finalVideo) ? sha256(finalVideo) : null;
if (finalSha) validateQa(caseDir, manifest, finalSha);
validatePublishSafeTop(manifest);

const technicalFailureCount = failures.length;
let acceptancePresent = false;
if (requireAcceptance && technicalFailureCount === 0) acceptancePresent = validateAcceptance(caseDir, manifest, finalVideo, finalSha);
const result = failures.length
  ? requireAcceptance && technicalFailureCount === 0
    ? 'technical_pass_pending_external_acceptance'
    : 'fail'
  : requireAcceptance
    ? 'release_gate_pass_with_declared_external_acceptance'
    : 'technical_pass_pending_acceptance';
const payload = {
  result,
  manifest: manifestPath,
  finalSha256: finalSha,
  checkedAt: new Date().toISOString(),
  levels: {
    workflowPass: !failures.some((item) => item.startsWith('workflow:') || item.includes('workflow.stage')),
    hardMetadataPass: technicalFailureCount === 0,
    remotionProvenancePass: technicalFailureCount === 0 && pass.includes('Remotion provenance and overlay-only source graph ok'),
    sourcePreservationPass: technicalFailureCount === 0,
    audioPreservationPass: technicalFailureCount === 0 && pass.includes('audio packet hash ok'),
    visualQaEvidencePass: technicalFailureCount === 0 && pass.includes('QA evidence decodes and binds to final SHA'),
    acceptanceMetadataPass: requireAcceptance ? acceptancePresent && failures.length === 0 : false,
  },
  pass,
  warnings,
  failures,
};

if (recordTechnical && failures.length === 0) {
  const technicalPath = resolveManifestPath(caseDir, manifest.qa?.technicalValidation || 'qa/technical-validation.json');
  assertManagedChild(technicalPath, caseDir, 'technical validation report');
  writeJson(technicalPath, payload);
  manifest.qa.technicalValidation = toRelative(caseDir, technicalPath);
  if (manifest.workflow.stage === 'full_rendered') appendWorkflowStage(manifest.workflow, 'technical_pass');
  manifest.status = 'technical_pass';
  writeJson(manifestPath, manifest);
  const reportPath = resolveManifestPath(caseDir, manifest.report);
  assertManagedChild(reportPath, caseDir, 'final report');
  writeFileSync(reportPath, `# ${manifest.caseId}\n\nStatus: technical_pass; explicit external user acceptance is still required.\n\n- Final video: ${manifest.finalVideo}\n- Final SHA-256: ${finalSha}\n- Technical report: ${manifest.qa.technicalValidation}\n- Quality profile: ${manifest.qualityProfile.name}\n- Acceptance boundary: filesystem metadata is structurally checked but not cryptographically authenticated.\n`);
}

console.log(JSON.stringify(payload, null, 2));
process.exit(failures.length === 0 ? 0 : 1);
