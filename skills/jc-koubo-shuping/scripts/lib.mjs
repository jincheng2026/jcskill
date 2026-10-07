#!/usr/bin/env node

import {execFileSync, spawnSync} from 'node:child_process';
import {copyFileSync, existsSync, lstatSync, mkdirSync, readFileSync, realpathSync, statSync, writeFileSync} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

export const scriptDir = path.dirname(fileURLToPath(import.meta.url));
export const skillDir = path.dirname(scriptDir);
export const remotionTemplateDir = path.join(skillDir, 'assets', 'remotion-template');
export const runtimeCacheRoot = path.join(os.homedir(), '.cache', 'jc-koubo-shuping');
export const runtimeTemplateDir =
  process.env.JC_KOUBO_SHUPING_RUNTIME_DIR ||
  process.env.JC_KOUBO_PACKAGER_RUNTIME_DIR ||
  path.join(runtimeCacheRoot, 'remotion-template');

export function parseArgs(argv) {
  const args = {};
  const positional = [];
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (item.startsWith('--')) {
      const key = item.slice(2);
      const next = argv[index + 1];
      if (!next || next.startsWith('--')) {
        args[key] = true;
      } else {
        args[key] = next;
        index += 1;
      }
    } else {
      positional.push(item);
    }
  }
  args._ = positional;
  return args;
}

export function ensureDir(dir) {
  mkdirSync(dir, {recursive: true});
}

export function assertFile(file, label = 'file') {
  if (!file || !existsSync(file) || !statSync(file).isFile()) {
    throw new Error(`${label} does not exist or is not a file: ${file}`);
  }
}

export function readJson(file) {
  return JSON.parse(readFileSync(file, 'utf8'));
}

export function writeJson(file, value) {
  writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`);
}

export function resolveFrom(baseDir, value) {
  if (!value) return value;
  return path.isAbsolute(value) ? value : path.join(baseDir, value);
}

export function isPathInside(parent, child) {
  const relative = path.relative(path.resolve(parent), path.resolve(child));
  return relative !== '' && !relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative);
}

function nearestExistingParent(value) {
  let current = path.resolve(value);
  while (!existsSync(current)) {
    const parent = path.dirname(current);
    if (parent === current) return current;
    current = parent;
  }
  return current;
}

export function assertManagedChild(target, allowedRoot, label = 'managed path') {
  const resolvedTarget = path.resolve(target);
  const resolvedRoot = path.resolve(allowedRoot);
  if (!isPathInside(resolvedRoot, resolvedTarget)) {
    throw new Error(`${label} must be a child of ${resolvedRoot}: ${resolvedTarget}`);
  }
  const realRoot = realpathSync(resolvedRoot);
  const existingParent = nearestExistingParent(resolvedTarget);
  const realParent = realpathSync(existingParent);
  if (realParent !== realRoot && !isPathInside(realRoot, realParent)) {
    throw new Error(`${label} escapes allowed root through symlink: ${resolvedTarget} -> ${realParent}`);
  }
  if (existsSync(resolvedTarget) && lstatSync(resolvedTarget).isSymbolicLink()) {
    const realTarget = realpathSync(resolvedTarget);
    if (!isPathInside(realRoot, realTarget)) {
      throw new Error(`${label} symlink target escapes allowed root: ${resolvedTarget} -> ${realTarget}`);
    }
  }
  return resolvedTarget;
}

export function toRelative(baseDir, value) {
  const relative = path.relative(baseDir, value);
  return relative.startsWith('..') ? value : relative;
}

export function manifestPathFromArg(value) {
  if (!value) throw new Error('missing manifest or case directory');
  const resolved = path.resolve(value);
  if (existsSync(resolved) && statSync(resolved).isDirectory()) {
    return path.join(resolved, 'case_manifest.json');
  }
  return resolved;
}

export function loadManifest(value) {
  const manifestPath = manifestPathFromArg(value);
  assertFile(manifestPath, 'case_manifest.json');
  return {
    manifestPath,
    caseDir: path.dirname(manifestPath),
    manifest: readJson(manifestPath),
  };
}

export function resolveManifestPath(caseDir, value) {
  return resolveFrom(caseDir, value);
}

export function commandText(command, args, options = {}) {
  return execFileSync(command, args, {encoding: 'utf8', ...options}).trim();
}

export function run(command, args, options = {}) {
  const result = spawnSync(command, args, {stdio: 'inherit', ...options});
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} failed with exit code ${result.status}`);
  }
}

export function ffprobeJson(file) {
  const output = commandText('ffprobe', [
    '-v',
    'error',
    '-count_frames',
    '-show_entries',
    'stream=index,codec_type,codec_name,profile,width,height,pix_fmt,r_frame_rate,avg_frame_rate,duration,bit_rate,nb_frames,nb_read_frames,color_space,color_transfer,color_primaries,color_range,sample_rate,channels',
    '-show_entries',
    'format=duration,size,bit_rate',
    '-of',
    'json',
    file,
  ]);
  return JSON.parse(output);
}

export function videoStream(probe) {
  return probe?.streams?.find((stream) => stream.codec_type === 'video');
}

export function audioStream(probe) {
  return probe?.streams?.find((stream) => stream.codec_type === 'audio');
}

export function frameCount(stream) {
  const raw = stream?.nb_read_frames ?? stream?.nb_frames;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

export function parseFraction(value) {
  if (typeof value !== 'string') return null;
  const [num, den] = value.split('/').map(Number);
  if (!Number.isFinite(num) || !Number.isFinite(den) || den === 0) return null;
  return num / den;
}

export function secondsFromSrtTime(value) {
  const match = value.match(/^(\d{2}):(\d{2}):(\d{2}),(\d{3})$/u);
  if (!match) throw new Error(`invalid srt time: ${value}`);
  const [, hh, mm, ss, ms] = match.map(Number);
  return hh * 3600 + mm * 60 + ss + ms / 1000;
}

export function parseSrtText(text) {
  const blocks = text.replace(/\r/g, '').trim().split(/\n\s*\n/u).filter(Boolean);
  const cues = blocks.map((block, index) => {
    const lines = block.split('\n').map((line) => line.trim()).filter(Boolean);
    const timeLineIndex = lines.findIndex((line) => line.includes('-->'));
    if (timeLineIndex === -1) throw new Error(`srt block ${index + 1} has no time line`);
    const [startRaw, endRaw] = lines[timeLineIndex].split('-->').map((part) => part.trim().split(/\s+/u)[0]);
    const content = lines.slice(timeLineIndex + 1).join(' ').replace(/\s+/gu, ' ').trim();
    const [zhRaw, enRaw = ''] = content.split(/\s*\|\|\s*/u);
    return {
      id: `c${String(index + 1).padStart(3, '0')}`,
      start: secondsFromSrtTime(startRaw),
      end: secondsFromSrtTime(endRaw),
      zh: zhRaw.trim(),
      en: enRaw.trim(),
    };
  });
  return cues.map((cue, index) => {
    const nextStart = cues[index + 1]?.start;
    const displayEnd = Number.isFinite(nextStart) ? Math.min(cue.end, nextStart) : cue.end;
    return {...cue, displayEnd: Math.max(cue.start, displayEnd)};
  });
}

export function copyIntoDir(source, targetDir) {
  ensureDir(targetDir);
  const target = path.join(targetDir, path.basename(source));
  copyFileSync(source, target);
  return target;
}

export function tmpCaseDir(prefix = 'jc-koubo-shuping-smoke') {
  return path.join(os.tmpdir(), `${prefix}-${Date.now()}`);
}
