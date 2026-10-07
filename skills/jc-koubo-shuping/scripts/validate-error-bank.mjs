#!/usr/bin/env node

import {existsSync, readFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {parseArgs, writeJson} from './lib.mjs';
import {runErrorRegressions} from './regression-suite.mjs';

const args = parseArgs(process.argv.slice(2));

const skillDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const bankPath = path.join(skillDir, 'evals', 'error-cases.json');
const failures = [];
const allowedCategories = new Set(['subtitle', 'workflow', 'layout', 'style', 'render', 'quality', 'audio', 'release']);
const allowedStatuses = new Set(['active', 'retired']);

if (!existsSync(bankPath)) failures.push(`missing error bank: ${bankPath}`);
let bank = null;
try {
  bank = JSON.parse(readFileSync(bankPath, 'utf8'));
} catch (error) {
  failures.push(`invalid error bank JSON: ${error.message}`);
}

if (bank) {
  if (bank.schemaVersion !== 'jc-koubo-shuping.error-bank.v1') failures.push(`unsupported schemaVersion: ${bank.schemaVersion}`);
  if (!Array.isArray(bank.cases) || bank.cases.length === 0) failures.push('cases must be a non-empty array');
  const ids = new Set();
  for (const [index, item] of (bank.cases || []).entries()) {
    const label = `cases[${index}]`;
    for (const key of ['id', 'category', 'symptom', 'rootCause', 'prevention', 'detection', 'evidence', 'regression', 'testId', 'status']) {
      if (!(key in item)) failures.push(`${label} missing ${key}`);
    }
    if (!/^KBE-\d{3}$/u.test(item.id || '')) failures.push(`${label} invalid id: ${item.id}`);
    if (ids.has(item.id)) failures.push(`${label} duplicate id: ${item.id}`);
    ids.add(item.id);
    if (!allowedCategories.has(item.category)) failures.push(`${label} invalid category: ${item.category}`);
    if (!allowedStatuses.has(item.status)) failures.push(`${label} invalid status: ${item.status}`);
    if (!Array.isArray(item.evidence) || item.evidence.length === 0) failures.push(`${label} evidence must be non-empty`);
    if (!item.regression?.type || !item.regression?.assertion) failures.push(`${label} regression requires type and assertion`);
    for (const key of ['symptom', 'rootCause', 'prevention', 'detection']) {
      if (typeof item[key] !== 'string' || item[key].trim().length < 8) failures.push(`${label} ${key} is too weak`);
    }
  }
}

const activeCases = bank?.cases?.filter((item) => item.status === 'active') || [];
const regression = failures.length === 0 ? runErrorRegressions(activeCases) : {passed: [], failed: []};
for (const item of regression.failed) failures.push(`${item.id}/${item.testId}: ${item.error}`);

const payload = {
  result: failures.length === 0 ? 'pass' : 'fail',
  path: bankPath,
  total: bank?.cases?.length || 0,
  active: bank?.cases?.filter((item) => item.status === 'active').length || 0,
  passed: regression.passed,
  regressionFailures: regression.failed,
  failures,
};

if (args.out) writeJson(path.resolve(String(args.out)), payload);

console.log(JSON.stringify(payload, null, 2));
process.exit(failures.length === 0 ? 0 : 1);
