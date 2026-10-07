#!/usr/bin/env node

import {existsSync, readdirSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import {
  assertManagedChild,
  commandText,
  ensureDir,
  ffprobeJson,
  loadManifest,
  parseArgs,
  resolveManifestPath,
  run,
  scriptDir,
  toRelative,
  writeJson,
} from './lib.mjs';
import {assertCanonicalQuality} from './quality-core.mjs';
import {appendWorkflowStage, validateWorkflow} from './workflow-core.mjs';

const usage = `Usage:
  node scripts/composite-preserve-source.mjs /abs/case/case_manifest.json

Requires a pilot_accepted workflow, canonical quality profile, complete Remotion
overlay frames, and a passing executable error-regression report.`;

const args = parseArgs(process.argv.slice(2));
if (args.help || args.h || args._.length === 0) {
  console.log(usage);
  process.exit(args._.length === 0 ? 2 : 0);
}

const {manifestPath, caseDir, manifest} = loadManifest(args._[0]);
if (Number(manifest.schemaVersion) !== 3) throw new Error(`canonical composite requires schemaVersion 3; run migrate-case-v3.mjs, got ${manifest.schemaVersion}`);
if (manifest.workflow?.stage !== 'pilot_accepted') throw new Error(`full composite requires exact workflow.stage=pilot_accepted, got ${manifest.workflow?.stage}`);
const prospective = structuredClone(manifest);
appendWorkflowStage(prospective.workflow, 'full_rendered');
const prospectiveCheck = validateWorkflow({caseDir, manifest: prospective, requiredStage: 'full_rendered'});
if (prospectiveCheck.failures.length) throw new Error(`full-render workflow gate failed: ${prospectiveCheck.failures.join('; ')}`);

const sourceVideo = resolveManifestPath(caseDir, manifest.sourceVideo);
const overlayDir = resolveManifestPath(caseDir, manifest.overlayFrames?.dir || 'remotion_overlay_frames');
const outputVideo = resolveManifestPath(caseDir, manifest.finalVideo || 'output/final.mp4');
const videoOnly = outputVideo.replace(/\.mp4$/u, '.video-only.mp4');
const qaDir = resolveManifestPath(caseDir, manifest.qa?.dir || 'qa');
for (const [target, label] of [
  [sourceVideo, 'source video'],
  [overlayDir, 'overlay directory'],
  [outputVideo, 'final output'],
  [videoOnly, 'video-only output'],
  [qaDir, 'QA directory'],
]) assertManagedChild(target, caseDir, label);
if (!existsSync(sourceVideo)) throw new Error(`source video missing: ${sourceVideo}`);

const fps = Number(manifest.video?.fps);
const expectedFrames = Number(manifest.video?.frameCount);
if (!Number.isFinite(fps) || fps <= 0 || !Number.isInteger(expectedFrames) || expectedFrames <= 0) throw new Error('manifest video fps/frameCount invalid');
const quality = assertCanonicalQuality(manifest.qualityProfile, {width: manifest.video?.width, height: manifest.video?.height});
const encoding = quality.videoEncoding;
const sourceWidth = Number(manifest.video.width);
const sourceHeight = Number(manifest.video.height);
const outputWidth = Number(quality.output.width);
const outputHeight = Number(quality.output.height);
const shouldScale = outputWidth !== sourceWidth || outputHeight !== sourceHeight;

const frameNames = existsSync(overlayDir)
  ? readdirSync(overlayDir).filter((name) => /^element-\d+\.png$/u.test(name)).sort()
  : [];
if (frameNames.length !== expectedFrames) throw new Error(`overlay frame count mismatch before composite: expected=${expectedFrames}, actual=${frameNames.length}`);
const firstFrameMatch = frameNames[0]?.match(/^element-(\d+)\.png$/u);
const digitWidth = firstFrameMatch ? firstFrameMatch[1].length : 4;
const overlayPattern = path.join(overlayDir, `element-%0${digitWidth}d.png`);
const baseFilter = shouldScale
  ? `[0:v]zscale=w=${outputWidth}:h=${outputHeight}:filter=spline36,format=yuv420p[base];`
  : '[0:v]format=yuv420p[base];';
const filterComplex = `${baseFilter}[base][1:v]overlay=0:0:format=auto:shortest=0,format=yuv420p[v]`;
const encoderArgs = encoding.codec === 'h264_videotoolbox'
  ? ['-c:v', 'h264_videotoolbox', '-b:v', '45M', '-profile:v', 'high', '-realtime', '1']
  : ['-c:v', 'libx264', '-crf', '8', '-preset', 'slow', '-profile:v', 'high', '-x264-params', 'colorprim=bt709:transfer=bt709:colormatrix=bt709'];

ensureDir(path.dirname(outputVideo));
ensureDir(qaDir);
const videoArgs = [
  '-y', '-i', sourceVideo,
  '-framerate', String(fps), '-i', overlayPattern,
  '-filter_complex', filterComplex,
  '-map', '[v]',
  ...encoderArgs,
  '-pix_fmt', 'yuv420p',
  '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv',
  '-frames:v', String(expectedFrames), '-movflags', '+faststart', videoOnly,
];
if (videoArgs.includes('-shortest') || filterComplex.includes('shortest=1')) throw new Error('canonical composite must not use -shortest');
run('ffmpeg', videoArgs);

const remuxArgs = [
  '-y', '-i', videoOnly, '-i', sourceVideo,
  '-map', '0:v:0', '-map', '1:a:0', '-c', 'copy', '-movflags', '+faststart', outputVideo,
];
run('ffmpeg', remuxArgs);

const sourceProbePath = path.join(qaDir, 'ffprobe_source.json');
const finalProbePath = path.join(qaDir, 'ffprobe_final.json');
writeJson(sourceProbePath, ffprobeJson(sourceVideo));
writeJson(finalProbePath, ffprobeJson(outputVideo));

const frameAt = (seconds) => Math.max(0, Math.min(expectedFrames - 1, Math.round(Number(seconds) * fps)));
const uniqueFrames = (frames) => [...new Set(frames.filter((frame) => Number.isInteger(frame) && frame >= 0 && frame < expectedFrames))].sort((a, b) => a - b);
const contactPages = (input, baseName, requestedFrames) => {
  const frames = uniqueFrames(requestedFrames);
  const pageSize = 100;
  const outputs = [];
  for (let offset = 0; offset < frames.length; offset += pageSize) {
    const pageFrames = frames.slice(offset, offset + pageSize);
    const rows = Math.ceil(pageFrames.length / 5);
    const pageNumber = Math.floor(offset / pageSize) + 1;
    const suffix = frames.length > pageSize ? `-p${String(pageNumber).padStart(3, '0')}` : '';
    const output = path.join(qaDir, `${baseName}${suffix}.jpg`);
    const select = pageFrames.map((frame) => `eq(n\\,${frame})`).join('+');
    run('ffmpeg', ['-y', '-i', input, '-vf', `select='${select}',scale=360:-1,tile=5x${rows}`, '-frames:v', '1', '-q:v', '2', '-update', '1', output]);
    outputs.push(output);
  }
  return {frames, outputs};
};

const duration = Number(manifest.video.duration);
const overviewFrames = Array.from({length: 20}, (_, index) => frameAt((duration * index) / 19));
const nodeFrames = (manifest.nodes || []).flatMap((node) => [
  frameAt(node.start), frameAt(node.start + 0.2), frameAt(node.start + 1), frameAt((node.start + node.end) / 2), frameAt(Math.max(node.start, node.end - 0.2)),
]);
const animationFrames = (manifest.nodes || []).flatMap((node) => [0, 6, 12, 18, 30].map((offset) => Math.min(expectedFrames - 1, frameAt(node.start) + offset)));
const captionFrames = (manifest.captionTrack || []).flatMap((cue) => [
  Math.min(expectedFrames - 1, frameAt(cue.start) + 2), frameAt((cue.start + cue.displayEnd) / 2), Math.max(0, frameAt(cue.displayEnd) - 2),
]);
const cueCoverageFrames = (manifest.captionTrack || []).map((cue) => frameAt((cue.start + cue.displayEnd) / 2));
const overlapFrames = (manifest.captionTrack || []).flatMap((cue, index, cues) => cue.end > Number(cues[index + 1]?.start ?? cue.end) ? [frameAt(cues[index + 1].start)] : []);

const contacts = {
  sourceContactSheet: contactPages(sourceVideo, 'source-contact', overviewFrames),
  finalContactSheet: contactPages(outputVideo, 'final-contact', overviewFrames),
  overviewContactSheet: contactPages(outputVideo, 'overview-contact', overviewFrames),
  sceneBoundaryContactSheet: contactPages(outputVideo, 'scene-boundary-contact', nodeFrames),
  captionRiskContactSheet: contactPages(outputVideo, 'caption-risk-contact', captionFrames),
  cueCoverageContactSheet: contactPages(outputVideo, 'cue-coverage-contact', cueCoverageFrames),
  safeZoneContactSheet: contactPages(outputVideo, 'safe-zone-contact', [...overviewFrames, ...nodeFrames]),
  publishSafeTopContactSheet: contactPages(outputVideo, 'publish-safe-top-contact', [...overviewFrames, ...nodeFrames]),
  animationRiskContactSheet: contactPages(outputVideo, 'animation-risk-contact', animationFrames),
  overlapContactSheet: overlapFrames.length ? contactPages(outputVideo, 'overlap-contact', overlapFrames) : {frames: [], outputs: []},
};
const coveragePath = path.join(qaDir, 'contact-sheet-coverage.json');
writeJson(coveragePath, Object.fromEntries(Object.entries(contacts).map(([key, value]) => [key, {frames: value.frames, pages: value.outputs.map((file) => toRelative(caseDir, file))}])));

run('ffmpeg', ['-v', 'error', '-i', outputVideo, '-f', 'null', '-']);
const finalSha = commandText('shasum', ['-a', '256', outputVideo]).split(/\s+/u)[0];
const sourceSha = commandText('shasum', ['-a', '256', sourceVideo]).split(/\s+/u)[0];
const decodePath = path.join(qaDir, 'full-decode.json');
writeJson(decodePath, {result: 'pass', finalSha256: finalSha, checkedAt: new Date().toISOString()});
const shaPath = path.join(qaDir, 'sha256_final.txt');
writeFileSync(shaPath, `${finalSha}  ${path.basename(outputVideo)}\n`);
const evidencePath = path.join(qaDir, 'render-evidence.json');
writeJson(evidencePath, {
  schemaVersion: 1,
  createdAt: new Date().toISOString(),
  sourceSha256: sourceSha,
  finalSha256: finalSha,
  compositorScriptSha256: commandText('shasum', ['-a', '256', path.join(scriptDir, 'composite-preserve-source.mjs')]).split(/\s+/u)[0],
  qualityProfile: quality,
  videoArgs,
  remuxArgs,
  remotion: manifest.remotion,
});

appendWorkflowStage(manifest.workflow, 'full_rendered');
manifest.status = 'full_rendered';
manifest.compositor = 'ffmpeg';
manifest.composite = {
  usedShortest: false,
  audioPolicy: 'copy_original_packets',
  outputWidth,
  outputHeight,
  upscaleFilter: shouldScale ? 'spline36' : null,
  videoOnlyIntermediate: toRelative(caseDir, videoOnly),
  renderEvidence: toRelative(caseDir, evidencePath),
  videoArgs,
  remuxArgs,
};
manifest.finalVideo = toRelative(caseDir, outputVideo);
manifest.qa = {
  ...(manifest.qa || {}),
  dir: toRelative(caseDir, qaDir),
  sourceFfprobe: toRelative(caseDir, sourceProbePath),
  finalFfprobe: toRelative(caseDir, finalProbePath),
  coverageManifest: toRelative(caseDir, coveragePath),
  fullDecode: toRelative(caseDir, decodePath),
  renderEvidence: toRelative(caseDir, evidencePath),
  sha256: toRelative(caseDir, shaPath),
  ...Object.fromEntries(Object.entries(contacts).map(([key, value]) => [key, value.outputs.map((file) => toRelative(caseDir, file))])),
};
manifest.report = manifest.report || 'reports/final_report.md';
writeJson(manifestPath, manifest);

const reportPath = resolveManifestPath(caseDir, manifest.report);
assertManagedChild(reportPath, caseDir, 'final report');
ensureDir(path.dirname(reportPath));
writeFileSync(reportPath, `# ${manifest.caseId}\n\nStatus: full_rendered; technical validation and external acceptance are pending.\n\n- Quality profile: ${quality.name}\n- Fixed route: Remotion RGBA overlay -> ffmpeg video-only preserve-source composite -> source-audio remux\n- Output size: ${outputWidth}x${outputHeight}\n- Final video: ${manifest.finalVideo}\n- Render evidence: ${manifest.qa.renderEvidence}\n- Contact coverage: ${manifest.qa.coverageManifest}\n`);
console.log(`[jc-koubo-shuping] final -> ${outputVideo}`);
