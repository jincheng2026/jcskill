# Release Gates

## Case Gates

Full render is blocked unless:

- SRT review and diff exist;
- semantic motion map exists;
- 4–6 static previews are human-accepted;
- representative 10–15 second pilot is human-accepted;
- the pilot and full build use the same approved baseline;
- active error-bank cases have been applied.

## Technical Gate

Run:

```bash
node scripts/validate-workflow.mjs /abs/case/case_manifest.json
node scripts/validate-error-bank.mjs --out /abs/case/reports/error-regression.json
node scripts/validate-final.mjs /abs/case/case_manifest.json --record-technical
```

Technical success may report only `technical_pass_pending_acceptance`.

## Release Gate

After explicit user acceptance, run:

```bash
node scripts/validate-final.mjs /abs/case/case_manifest.json --require-acceptance
```

通过时脚本返回 `release_gate_pass_with_declared_external_acceptance`。只有真实对话中存在用户明确接受消息时，执行者才可对外报告「已验收」；脚本不宣称能从 JSON 鉴别人类身份。

## Skill Release Gate

Before distributing this Skill:

- `quick_validate.py` passes;
- meta-skill validation and resource-boundary checks pass;
- all JavaScript files pass `node --check`;
- error-bank validation passes;
- preserve-source smoke passes;
- adversarial smoke blocks path escape, late full rerender, workflow bypass, quality spoof, silent final, placeholder QA, and wrong acceptance artifact;
- workflow fixtures cover blocked and accepted stage transitions;
- Claude, Codex, and NewMax resolve to the same shared truth and matching SHA.

## Not Claimed

- Windows or Linux support.
- automatic semantic judgment quality;
- automatic subtitle translation quality;
- aesthetic acceptance without a human decision;
- pixel-identical hardware-accelerated encoding across machines.
