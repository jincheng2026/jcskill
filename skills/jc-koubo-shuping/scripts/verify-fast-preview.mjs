#!/usr/bin/env node

import {spawnSync} from 'node:child_process';
import {existsSync, mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import {commandText, parseArgs, readJson, run, scriptDir, tmpCaseDir, writeJson} from './lib.mjs';

const args = parseArgs(process.argv.slice(2));
if (args.help || args.h) {
  console.log('Usage: node scripts/verify-fast-preview.mjs [--out /tmp/test-root]');
  process.exit(0);
}

const root = args.out ? path.resolve(String(args.out)) : tmpCaseDir('jc-koubo-fast-preview');
const fixture = path.join(root, 'fixture');
const caseDir = path.join(root, 'case');
mkdirSync(fixture, {recursive: true});
const video = path.join(fixture, 'source.mp4');
const srt = path.join(fixture, 'source.srt');
writeFileSync(srt, `1
00:00:00,000 --> 00:00:03,000
先锁定这次使用的真实素材

2
00:00:03,000 --> 00:00:07,000
再用四张检样判断整体方向

3
00:00:07,000 --> 00:00:12,000
字幕必须保持单行

4
00:00:12,000 --> 00:00:16,000
确认之后才进入正式成片
`);
if (!existsSync(video)) {
  run('ffmpeg', ['-y', '-f', 'lavfi', '-i', 'testsrc2=size=720x1280:rate=30:duration=16', '-f', 'lavfi', '-i', 'sine=frequency=550:duration=16:sample_rate=44100', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-x264-params', 'colorprim=bt709:transfer=bt709:colormatrix=bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv', '-c:a', 'aac', '-t', '16', video]);
}
run('node', [path.join(scriptDir, 'create-case.mjs'), '--video', video, '--srt', srt, '--out', caseDir, '--case-id', 'fast-preview-smoke', '--style', 'assembly-mono', '--force']);
const manifestPath = path.join(caseDir, 'case_manifest.json');
const manifest = readJson(manifestPath);
const fixtureTranslations = ['Lock the real source first', 'Use four stills to judge direction', 'Keep every caption on one line', 'Approve before full production'];
manifest.captionTrack = manifest.captionTrack.map((cue, index) => ({...cue, en: fixtureTranslations[index]}));
const revised = path.join(caseDir, 'source', 'revised.srt');
writeFileSync(revised, readFileSync(srt));
const diff = path.join(caseDir, 'reports', 'subtitle-diff.json');
writeJson(diff, {changes: []});
const motionMap = path.join(caseDir, 'planning', 'motion-map.json');
mkdirSync(path.dirname(motionMap), {recursive: true});
const cueIds = ['c001', 'c002', 'c003', 'c004'];
const titles = ['锁定真实素材', '先看四张检样', '字幕保持单行', '确认再做成片'];
writeJson(motionMap, {
  argument_map: {
    core_claim: '先快速检样，再正式制作',
    audience_problem: '昂贵步骤发生太早，用户很晚才看到画面',
    ending_action: '确认检样之后进入正式成片',
    progression: cueIds.map((_, index) => ({id: `a0${index + 1}`, type: ['evidence', 'mechanism', 'contrast', 'action'][index], claim: titles[index]})),
  },
  risk_overrides: [],
  beats: cueIds.map((cueId, index) => ({
    id: `n0${index + 1}`,
    cue_ids: [cueId],
    argument_id: `a0${index + 1}`,
    boundary: {type: ['opening', 'mechanism', 'contrast', 'action'][index], change: ['建立素材前提', '进入检样方法', '指出字幕风险', '给出下一步'][index]},
    semantic_function: ['建立前提', '解释机制', '提示风险', '推动行动'][index],
    viewer_need: ['确认素材', '看到方向', '避免返工', '继续生产'][index],
    trigger_rule: ['出现真实素材', '出现检样', '出现字幕风险', '出现确认动作'][index],
    hero_visual: 'upper semantic card',
    caption_policy: 'single follow caption',
    sound_cue: 'one semantic hit',
    layout_risk: 'upper card and face safe zone',
    mg_copy: {label: ['素材', '检样', '字幕', '行动'][index], eyebrow: ['SOURCE', 'PREVIEW', 'CAPTION', 'NEXT'][index], title: titles[index], sub: ['先别剪错', '尽快给反馈', '中英都单行', '再投入成本'][index], chips: [["Take"], ["4 帧"], ["单行"], ["确认"]][index], accent: ['blue', 'yellow', 'red', 'green'][index]},
  })),
});
manifest.workflow.subtitleReview = {revisedSrt: path.relative(caseDir, revised), diff: path.relative(caseDir, diff)};
writeJson(manifestPath, manifest);
run('node', [path.join(scriptDir, 'compile-motion-map.mjs'), manifestPath, '--motion-map', path.relative(caseDir, motionMap)]);
const compiled = readJson(manifestPath);
compiled.workflow.stage = 'motion_map_ready';
compiled.workflow.history = ['intake', 'subtitle_reviewed', 'motion_map_ready'].map((stage, index) => ({stage, at: `2026-07-21T00:00:0${index}.000Z`}));
writeJson(manifestPath, compiled);

const started = Date.now();
run('node', [path.join(scriptDir, 'run-fast-preview.mjs'), manifestPath, '--width', '540']);
const first = readJson(path.join(caseDir, 'preview', 'cycle-01', 'attempt-01', 'preview-manifest.json'));
run('node', [path.join(scriptDir, 'run-fast-preview.mjs'), manifestPath, '--width', '540']);
const second = readJson(path.join(caseDir, 'preview', 'cycle-01', 'attempt-02', 'preview-manifest.json'));
const third = spawnSync('node', [path.join(scriptDir, 'run-fast-preview.mjs'), manifestPath, '--width', '540'], {encoding: 'utf8'});
if (!existsSync(path.join(caseDir, first.qa.contactSheet)) || !existsSync(path.join(caseDir, second.qa.contactSheet))) throw new Error('preview contact sheet missing');
if (!second.cache.reused) throw new Error('second preview did not reuse the bundle cache');
if (third.status === 0 || !`${third.stdout}\n${third.stderr}`.includes('AUTO_FIX_LIMIT_REACHED')) throw new Error('third preview did not stop at the render budget');
run('node', [path.join(scriptDir, 'repair-case.mjs'), manifestPath, '--target', 'caption', '--apply']);
const repairState = readJson(manifestPath).workflow.execution;
if (repairState.cycle !== 2 || repairState.renderAttempts !== 0) throw new Error('repair did not open a fresh cycle budget');
run('node', [path.join(scriptDir, 'run-fast-preview.mjs'), manifestPath, '--width', '540']);
const repaired = readJson(path.join(caseDir, 'preview', 'cycle-02', 'attempt-01', 'preview-manifest.json'));
if (repaired.cycle !== 2 || !existsSync(path.join(caseDir, repaired.qa.contactSheet))) throw new Error('repair cycle preview missing');
const result = {
  result: 'pass',
  caseDir,
  elapsedSeconds: Number(((Date.now() - started) / 1000).toFixed(2)),
  firstBundleReused: first.cache.reused,
  secondBundleReused: second.cache.reused,
  thirdAttemptBlocked: true,
  repairCycle: repaired.cycle,
  repairBundleReused: repaired.cache.reused,
  contactSheet: path.join(caseDir, repaired.qa.contactSheet),
  contactSha256: commandText('shasum', ['-a', '256', path.join(caseDir, repaired.qa.contactSheet)]).split(/\s+/u)[0],
};
console.log(JSON.stringify(result, null, 2));
