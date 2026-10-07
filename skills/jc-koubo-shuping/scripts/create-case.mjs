#!/usr/bin/env node

import {existsSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import {
  assertFile,
  audioStream,
  copyIntoDir,
  ensureDir,
  ffprobeJson,
  frameCount,
  parseArgs,
  parseFraction,
  parseSrtText,
  toRelative,
  videoStream,
  writeJson,
} from './lib.mjs';
import {readFileSync} from 'node:fs';
import {canonicalQualityProfile} from './quality-core.mjs';
import {baselineForStyle, requireVisualStyle} from './style-core.mjs';

const usage = `Usage:
  node scripts/create-case.mjs --video /abs/input.mp4 --srt /abs/input.srt --out /abs/case --style assembly-mono|google-semantic [--case-id id] [--title title]

Creates a portable case folder and draft case_manifest.json. Equal-duration
draftNodes are navigation hints only and cannot render. Author a semantic motion
map, then run compile-motion-map.mjs to create renderable nodes.`;

const args = parseArgs(process.argv.slice(2));
if (args.help || args.h) {
  console.log(usage);
  process.exit(0);
}

if (!args.video || !args.srt || !args.out) {
  console.error(usage);
  process.exit(2);
}

const visualStyleId = requireVisualStyle(args.style);
const baselineId = baselineForStyle(visualStyleId);
const sourceVideo = path.resolve(String(args.video));
const subtitle = path.resolve(String(args.srt));
const caseDir = path.resolve(String(args.out));
const caseId = String(args['case-id'] || path.basename(caseDir));

assertFile(sourceVideo, 'video');
assertFile(subtitle, 'srt');
if (existsSync(path.join(caseDir, 'case_manifest.json')) && !args.force) {
  throw new Error(`case already exists: ${caseDir}. Use --force to overwrite manifest.`);
}

const sourceDir = path.join(caseDir, 'source');
const qaDir = path.join(caseDir, 'qa');
const reportsDir = path.join(caseDir, 'reports');
const outputDir = path.join(caseDir, 'output');
const overlayDir = path.join(caseDir, 'remotion_overlay_frames');
for (const dir of [sourceDir, qaDir, reportsDir, outputDir, overlayDir]) ensureDir(dir);

const copiedVideo = copyIntoDir(sourceVideo, sourceDir);
const copiedSrt = copyIntoDir(subtitle, sourceDir);
const sourceProbe = ffprobeJson(copiedVideo);
const sourceProbePath = path.join(qaDir, 'ffprobe_source.json');
writeJson(sourceProbePath, sourceProbe);

const stream = videoStream(sourceProbe);
if (!stream) throw new Error('source video has no video stream');
const averageFps = parseFraction(stream.avg_frame_rate);
const nominalFps = parseFraction(stream.r_frame_rate);
const fps = averageFps || nominalFps;
const duration = Number(sourceProbe.format?.duration || stream.duration || 0);
const frames = frameCount(stream);
const captions = parseSrtText(readFileSync(copiedSrt, 'utf8'));
const sourceWidth = Number(stream.width);
const sourceHeight = Number(stream.height);
const isVertical = sourceHeight > sourceWidth;
const aspect = sourceHeight / sourceWidth;
const audioStreams = (sourceProbe.streams || []).filter((item) => item.codec_type === 'audio');
const hdrTransfers = new Set(['smpte2084', 'arib-std-b67']);
if (!isVertical || Math.abs(aspect - 16 / 9) > 0.04) throw new Error(`unsupported input: expected near-9:16 vertical talking head, got ${sourceWidth}x${sourceHeight}`);
if (!Number.isFinite(fps) || fps <= 0 || !frames || frames <= 0 || !Number.isFinite(duration) || duration <= 0) {
  throw new Error('unsupported input: stable fps, duration, and ffprobe frame count are required');
}
if (averageFps && nominalFps && Math.abs(averageFps - nominalFps) > 0.001) {
  throw new Error(`unsupported input: VFR detected avg=${averageFps}, nominal=${nominalFps}`);
}
if (audioStreams.length !== 1 || !audioStream(sourceProbe)) throw new Error(`unsupported input: exactly one audio stream is required, got ${audioStreams.length}`);
if (!stream.color_space || !stream.color_transfer || !stream.color_primaries || !stream.color_range) {
  throw new Error('unsupported input: color metadata is incomplete; normalize to tagged SDR BT.709 first');
}
if (hdrTransfers.has(stream.color_transfer) || stream.color_primaries === 'bt2020') {
  throw new Error(`unsupported input: HDR/BT.2020 is not accepted (${stream.color_primaries}/${stream.color_transfer})`);
}
if (stream.color_space !== 'bt709' || stream.color_transfer !== 'bt709' || stream.color_primaries !== 'bt709' || !['tv', 'mpeg'].includes(stream.color_range)) {
  throw new Error(`unsupported input: normalize source to SDR BT.709 limited range first, got ${stream.color_space}/${stream.color_transfer}/${stream.color_primaries}/${stream.color_range}`);
}
if (!captions.length) throw new Error('unsupported input: SRT contains no cues');
for (const cue of captions) {
  if (!cue.zh || cue.end <= cue.start || cue.start < 0 || cue.end > duration + 0.5) throw new Error(`invalid SRT cue ${cue.id}`);
}
const qualityProfile = canonicalQualityProfile({sourceWidth, sourceHeight});
const targetWidth = qualityProfile.output.width;
const targetHeight = qualityProfile.output.height;
const renderScale = qualityProfile.overlay.renderScale;

const labels = duration > 70 ? ['开场', '机制', '误区', '转折', '行动'] : ['开场', '问题', '行动'];
const draftNodes = labels.map((label, index) => {
  const start = (duration / labels.length) * index;
  const end = index === labels.length - 1 ? duration : (duration / labels.length) * (index + 1);
  const firstCue = captions.find((cue) => cue.start >= start && cue.start < end) || captions[0];
  return {
    id: `n${String(index + 1).padStart(2, '0')}`,
    start: Number(start.toFixed(3)),
    end: Number(end.toFixed(3)),
    label,
    eyebrow: index === 0 ? 'FIRST CHECK' : index === labels.length - 1 ? 'FINAL MOVE' : 'KEY POINT',
    title: firstCue?.zh?.slice(0, 12) || label,
    sub: firstCue?.zh || label,
    chips: [label, '真实素材', '马上动手'],
    accent: ['blue', 'yellow', 'red', 'green', 'blue'][index % 5],
  };
});

const manifest = {
  schemaVersion: 3,
  package: 'jc-koubo-shuping',
  packageVersion: '0.8.0-candidate',
  caseId,
  status: 'intake',
  visualStyleId,
  target: {mode: 'fast_preview', profile: 'vertical_talking_head_v0'},
  workflow: {
    stage: 'intake',
    history: [{stage: 'intake', at: new Date().toISOString()}],
    planningMode: 'draft_auto_equal_duration',
    renderBlockedReason: 'semantic_motion_map_not_compiled',
    semanticPlan: null,
    timings: {},
    baselineId,
    execution: {
      mode: 'fast_preview',
      cycle: 1,
      maxRenderAttempts: 2,
      maxAutoFixes: 1,
      renderAttempts: 0,
      autoFixes: 0,
      status: 'ready',
    },
    subtitleReview: {revisedSrt: null, diff: null},
    motionMap: null,
    staticPreview: {files: [], contactSheet: null, decision: 'pending', reviewerType: null, userStatement: null},
    pilot: {
      video: null,
      contacts: {overview: null, animationRisk: null, captionRisk: null, safeZone: null},
      decision: 'pending',
      reviewerType: null,
      userStatement: null,
      evidence: null,
      baselineId: null,
    },
    fullBuild: {baselineId: null},
    finalAcceptance: {decision: 'pending', reviewerType: null, userStatement: null},
  },
  sourcePreservation: {
    base: 'original',
    sourceInRemotion: false,
    fixedRoute: 'remotion_rgba_overlay_then_ffmpeg_video_only_then_source_audio_remux',
  },
  errorBank: {schemaVersion: 'jc-koubo-shuping.error-bank.v1', applied: [], regressionReport: null},
  qualityProfile,
  title: String(args.title || caseId),
  sourceVideo: toRelative(caseDir, copiedVideo),
  subtitle: toRelative(caseDir, copiedSrt),
  video: {
    width: sourceWidth,
    height: sourceHeight,
    fps,
    duration,
    frameCount: frames,
    colorSpace: stream.color_space || null,
    colorTransfer: stream.color_transfer || null,
    colorPrimaries: stream.color_primaries || null,
    colorRange: stream.color_range || null,
  },
  draftNodes,
  nodes: [],
  captionTrack: captions,
  visualRenderer: null,
  compositor: null,
  remotion: null,
  overlayFrames: {
    dir: 'remotion_overlay_frames',
    pattern: 'element-*.png',
    startNumber: 0,
    expectedCount: frames,
    width: targetWidth,
    height: targetHeight,
    renderScale,
  },
  composite: {usedShortest: false, audioPolicy: 'copy', command: ''},
  finalVideo: 'output/final.mp4',
  qa: {
    dir: 'qa',
    sourceFfprobe: toRelative(caseDir, sourceProbePath),
    finalFfprobe: 'qa/ffprobe_final.json',
    sourceContactSheet: 'qa/source_contact.jpg',
    finalContactSheet: 'qa/final_contact.jpg',
    captionRiskContactSheet: 'qa/caption_risk_contact.jpg',
    safeZoneContactSheet: 'qa/safe_zone_contact.jpg',
    animationRiskContactSheet: 'qa/animation_risk_contact.jpg',
    overviewContactSheet: 'qa/overview-contact.jpg',
    sceneBoundaryContactSheet: 'qa/scene-boundary-contact.jpg',
    cueCoverageContactSheet: 'qa/cue-coverage-contact.jpg',
    publishSafeTopContactSheet: 'qa/publish-safe-top-contact.jpg',
    overlapContactSheet: [],
    coverageManifest: 'qa/contact-sheet-coverage.json',
    fullDecode: 'qa/full-decode.json',
    renderEvidence: 'qa/render-evidence.json',
    technicalValidation: 'qa/technical-validation.json',
    sha256: 'qa/sha256_final.txt',
  },
  report: 'reports/final_report.md',
};

writeJson(path.join(caseDir, 'case_manifest.json'), manifest);
writeFileSync(
  path.join(reportsDir, 'final_report.md'),
  `# ${caseId}\n\nStatus: intake\n\nNext: review SRT, write subtitle diff and semantic motion map, then pass static preview and pilot gates before full render.\n`,
);

console.log(path.join(caseDir, 'case_manifest.json'));
