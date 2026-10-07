import {readFileSync, readdirSync} from 'node:fs';
import path from 'node:path';
import {canonicalQualityProfile} from './quality-core.mjs';
import {parseSrtText, remotionTemplateDir, scriptDir} from './lib.mjs';
import {validateWorkflow} from './workflow-core.mjs';
import {buildCompiledMotionMap, validateCompiledSemanticPlan} from './semantic-core.mjs';
import {analyzeCaptionTrack} from './caption-layout-core.mjs';
import {baselineForStyle, normalizeVisualStyle, STYLE_SELECTION_QUESTION} from './style-core.mjs';

function source(name) {
  return readFileSync(path.join(scriptDir, name), 'utf8');
}

function templateSource(name) {
  return readFileSync(path.join(remotionTemplateDir, 'src', name), 'utf8');
}

function baseWorkflowManifest() {
  return {
    schemaVersion: 3,
    visualStyleId: 'google-semantic',
    workflow: {
      stage: 'intake',
      history: [{stage: 'intake', at: '2026-07-16T00:00:00.000Z'}],
      planningMode: 'draft_auto_equal_duration',
      baselineId: '0721-approved-baseline-v4-multi-mg',
    },
    captionTrack: [],
    nodes: [],
    errorBank: {applied: []},
  };
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function testWorkflowRejected(mutator, expectedFragment) {
  const manifest = baseWorkflowManifest();
  mutator(manifest);
  const result = validateWorkflow({caseDir: '/tmp/does-not-exist-jc-koubo', manifest});
  assert(result.failures.some((item) => item.includes(expectedFragment)), `expected workflow failure containing: ${expectedFragment}; got ${result.failures.join('; ')}`);
}

const tests = {
  'KBE-001': () => {
    const cues = parseSrtText('1\n00:00:00,000 --> 00:00:01,000\n明星八卦\n');
    assert(cues.length === 1 && cues[0].zh === '明星八卦', 'revised SRT text was not preserved');
  },
  'KBE-002': () => {
    const theme = templateSource('theme.ts');
    const value = (name) => Number(theme.match(new RegExp(`${name}\\s*:\\s*([0-9.]+)`, 'u'))?.[1]);
    assert(value('cardTop') + value('cardHeight') <= 360, 'semantic card intrudes into 720-design face-safe zone');
  },
  'KBE-003': () => {
    testWorkflowRejected((manifest) => {
      manifest.workflow.stage = 'pilot_accepted';
      manifest.workflow.history = ['intake', 'subtitle_reviewed', 'motion_map_ready', 'static_preview_pending', 'static_preview_accepted', 'pilot_pending', 'pilot_accepted'].map((stage, index) => ({stage, at: `2026-07-16T00:00:0${index}.000Z`}));
      manifest.workflow.baselineId = '0721-approved-baseline-v4-multi-mg';
      manifest.workflow.pilot = {baselineId: 'drifted'};
    }, 'pilot baseline');
  },
  'KBE-004': () => {
    testWorkflowRejected((manifest) => {
      manifest.workflow.stage = 'full_rendered';
      manifest.workflow.history = [{stage: 'full_rendered', at: '2026-07-16T00:00:00.000Z'}];
    }, 'workflow.history');
  },
  'KBE-005': () => {
    testWorkflowRejected((manifest) => {
      manifest.workflow.stage = 'motion_map_ready';
      manifest.workflow.history = ['intake', 'subtitle_reviewed', 'motion_map_ready'].map((stage, index) => ({stage, at: `2026-07-16T00:00:0${index}.000Z`}));
    }, 'planningMode must be semantic_manual');
    const manifest = {
      schemaVersion: 3,
      video: {duration: 6},
      captionTrack: [{id: 'c001', start: 0, end: 6, displayEnd: 6, zh: 'A 方案优于 AI 自动执行'}],
      nodes: [],
    };
    const sourceMap = {
      argument_map: {
        core_claim: '先选择方案再交给 AI 执行', audience_problem: '容易把方案判断和自动执行混在一起', ending_action: '选择 A 方案后再启动 AI',
        progression: [{id: 'a01', type: 'claim', claim: 'A 方案优于直接自动执行'}],
      },
      risk_overrides: [],
      beats: [{
        id: 'n01', cue_ids: ['c001'], argument_id: 'a01', boundary: {type: 'opening', change: '开场建立方案选择标准'},
        semantic_function: '提出结论', viewer_need: '区分方案与执行', trigger_rule: '出现方案对比', hero_visual: '顶部结论卡',
        caption_policy: '字幕跟读', sound_cue: '单次提示音', layout_risk: '避开人物面部',
        mg_copy: {label: '判断', eyebrow: 'CORE CLAIM', title: '选择 A', sub: '再让 AI 自动执行', chips: ['方案', 'AI'], accent: 'blue'},
      }],
    };
    const built = buildCompiledMotionMap({manifest, source: sourceMap});
    assert(built.failures.length === 0, `valid golden source failed: ${built.failures.join('; ')}`);
    const expectedNodes = [{id: 'n01', start: 0, end: 6, label: '判断', eyebrow: 'CORE CLAIM', title: '选择 A', sub: '再让 AI 自动执行', chips: ['方案', 'AI'], accent: 'blue'}];
    const valid = validateCompiledSemanticPlan({manifest: {...manifest, nodes: expectedNodes}, motionMap: built.compiled});
    assert(valid.failures.length === 0 && valid.unresolved.length === 0, `valid golden plan rejected: ${[...valid.failures, ...valid.unresolved.map((item) => item.id)].join('; ')}`);

    const clippedSource = structuredClone(sourceMap);
    clippedSource.beats[0].mg_copy.title = '用 A 提效';
    const clippedManifest = {...manifest, captionTrack: [{id: 'c001', start: 0, end: 6, displayEnd: 6, zh: '用 AI 提效'}]};
    const clippedBuilt = buildCompiledMotionMap({manifest: clippedManifest, source: clippedSource});
    const clippedNodes = [{...expectedNodes[0], title: '用 A 提效'}];
    const clipped = validateCompiledSemanticPlan({manifest: {...clippedManifest, nodes: clippedNodes}, motionMap: clippedBuilt.compiled});
    assert(clipped.failures.some((item) => item.includes('clipped ASCII token')), 'mid-sentence AI -> A truncation was not rejected');

    const punctuationSource = structuredClone(sourceMap);
    punctuationSource.beats[0].mg_copy = {label: '！', eyebrow: '！', title: '！！！', sub: '？？？', chips: ['！！！'], accent: '！'};
    const punctuationBuilt = buildCompiledMotionMap({manifest, source: punctuationSource});
    const punctuationNodes = [{id: 'n01', start: 0, end: 6, ...punctuationSource.beats[0].mg_copy}];
    const punctuation = validateCompiledSemanticPlan({manifest: {...manifest, nodes: punctuationNodes}, motionMap: punctuationBuilt.compiled});
    assert(punctuation.failures.some((item) => item.includes('meaningful text')), 'punctuation-only MG was not rejected');

    const placeholderSource = structuredClone(sourceMap);
    placeholderSource.beats[0].semantic_function = 'x';
    const placeholderBuilt = buildCompiledMotionMap({manifest, source: placeholderSource});
    const placeholder = validateCompiledSemanticPlan({manifest: {...manifest, nodes: expectedNodes}, motionMap: placeholderBuilt.compiled});
    assert(placeholder.failures.some((item) => item.includes('semantic_function')), 'placeholder semantic analysis was not rejected');

    const drifted = structuredClone(expectedNodes);
    drifted[0].title = '绕过 motion map';
    const drift = validateCompiledSemanticPlan({manifest: {...manifest, nodes: drifted}, motionMap: built.compiled});
    assert(drift.failures.some((item) => item.includes('exactly match')), 'motion-map/node drift was not rejected');

    const downgraded = buildCompiledMotionMap({manifest: {...manifest, schemaVersion: 2}, source: sourceMap});
    assert(downgraded.failures.some((item) => item.includes('schemaVersion must equal 3')), 'schema downgrade was not rejected');

    const uniformManifest = {
      schemaVersion: 3, video: {duration: 12}, nodes: [],
      captionTrack: [
        {id: 'c001', start: 0, end: 4, displayEnd: 4, zh: '先观察真实环境'},
        {id: 'c002', start: 4, end: 8, displayEnd: 8, zh: '再建立判断标准'},
        {id: 'c003', start: 8, end: 12, displayEnd: 12, zh: '最后开始具体行动'},
      ],
    };
    const uniformSource = {
      argument_map: {
        core_claim: '观察判断之后再行动', audience_problem: '缺少完整决策顺序', ending_action: '完成判断后立即行动',
        progression: [
          {id: 'a01', type: 'evidence', claim: '先观察环境'},
          {id: 'a02', type: 'mechanism', claim: '再建立标准'},
          {id: 'a03', type: 'action', claim: '最后执行行动'},
        ],
      },
      risk_overrides: [],
      beats: ['c001', 'c002', 'c003'].map((cueId, index) => ({
        id: `n0${index + 1}`, cue_ids: [cueId], argument_id: `a0${index + 1}`,
        boundary: {type: index === 0 ? 'opening' : index === 1 ? 'mechanism' : 'action', change: ['建立观察起点', '从观察进入判断', '从判断进入行动'][index]},
        semantic_function: ['提供环境证据', '解释判断机制', '给出执行动作'][index], viewer_need: ['看清环境', '理解标准', '开始执行'][index],
        trigger_rule: ['出现环境信息', '出现判断标准', '出现行动指令'][index], hero_visual: '顶部语义卡', caption_policy: '字幕跟读', sound_cue: '单次提示音', layout_risk: '避开人物面部',
        mg_copy: {
          label: ['观察', '判断', '行动'][index], eyebrow: ['OBSERVE', 'DECIDE', 'ACT'][index],
          title: ['先看清环境', '再建立标准', '最后开始行动'][index], sub: ['别急着下指令', '知道什么才重要', '把判断变成结果'][index],
          chips: [["环境"], ["标准"], ["执行"]][index], accent: ['blue', 'yellow', 'green'][index],
        },
      })),
    };
    uniformSource.beats[1].mg_copy.title = `${uniformSource.beats[0].mg_copy.title}\u200B`;
    const uniformBuilt = buildCompiledMotionMap({manifest: uniformManifest, source: uniformSource});
    const uniformNodes = [
      {id: 'n01', start: 0, end: 4, label: '观察', eyebrow: 'OBSERVE', title: '先看清环境', sub: '别急着下指令', chips: ['环境'], accent: 'blue'},
      {id: 'n02', start: 4, end: 8, label: '判断', eyebrow: 'DECIDE', title: '先看清环境', sub: '知道什么才重要', chips: ['标准'], accent: 'yellow'},
      {id: 'n03', start: 8, end: 12, label: '行动', eyebrow: 'ACT', title: '最后开始行动', sub: '把判断变成结果', chips: ['执行'], accent: 'green'},
    ];
    const uniform = validateCompiledSemanticPlan({manifest: {...uniformManifest, nodes: uniformNodes}, motionMap: uniformBuilt.compiled});
    assert(uniform.unresolved.some((item) => item.code === 'near_equal_duration'), 'uniform-duration risk was not surfaced');
    assert(uniform.unresolved.some((item) => item.code === 'repeated_title'), 'zero-width repeated title was not surfaced');
  },
  'KBE-006': () => {
    const theme = templateSource('theme.ts');
    const progressTop = Number(theme.match(/progressTop:\s*([0-9.]+)/u)?.[1]);
    const cardTop = Number(theme.match(/cardTop:\s*([0-9.]+)/u)?.[1]);
    assert(progressTop >= 90 && progressTop <= 110 && cardTop >= 140 && cardTop <= 210, 'publish-safe top geometry drifted');
  },
  'KBE-007': () => {
    const component = `${templateSource('TalkingHeadOverlay.tsx')}\n${templateSource('MgHero.tsx')}`;
    assert(component.includes('fitTitleSize(beat.title)'), 'title fitting function is not applied');
    assert(!/fitTitleSize\(beat\.title\)[\s\S]{0,350}textOverflow:\s*'ellipsis'/u.test(component), 'title fitting still hides overflow with ellipsis');
  },
  'KBE-008': () => {
    const cues = parseSrtText('1\n00:00:00,000 --> 00:00:02,000\n前句\n\n2\n00:00:01,800 --> 00:00:03,000\n后句\n');
    assert(cues[0].displayEnd === 1.8 && cues[1].displayEnd === 3, 'overlapping captions were not clamped');
  },
  'KBE-009': () => {
    const forbidden = /OffthreadVideo|Html5Video|<Video\b|<video\b|<Img\b|<img\b|drawImage|<canvas\b|backgroundImage|url\s*\(/u;
    for (const name of readdirSync(path.join(remotionTemplateDir, 'src'))) {
      if (/\.(?:ts|tsx)$/u.test(name)) assert(!forbidden.test(templateSource(name)), `source media renderer found in ${name}`);
    }
  },
  'KBE-010': () => {
    const quality = canonicalQualityProfile({sourceWidth: 720, sourceHeight: 1280});
    assert(quality.output.width === 1080 && quality.output.height === 1920, 'sub-1080 source does not produce 1080 master');
    assert(quality.overlay.width === 1080 && quality.upscale.filter === 'spline36', 'native overlay or spline36 contract missing');
  },
  'KBE-011': () => {
    const quality = canonicalQualityProfile({sourceWidth: 720, sourceHeight: 1280});
    assert(quality.videoEncoding.codec === 'libx264' && quality.videoEncoding.crf === 8 && quality.videoEncoding.preset === 'slow', 'canonical encoder contract drifted');
  },
  'KBE-012': () => {
    const composite = source('composite-preserve-source.mjs');
    assert(composite.includes("videoArgs.includes('-shortest')"), 'composite lacks an explicit -shortest rejection');
    assert(composite.includes('shortest=0'), 'overlay filter does not pin shortest=0');
  },
  'KBE-013': () => {
    const composite = source('composite-preserve-source.mjs');
    assert(composite.includes('video-only.mp4') && composite.includes("'1:a:0'") && composite.includes("'-c', 'copy'"), 'two-stage source-audio remux contract missing');
  },
  'KBE-014': () => {
    const semantic = source('semantic-core.mjs');
    assert(semantic.includes('has more than one hero'), 'one-readable-hero assertion missing');
  },
  'KBE-015': () => {
    const component = templateSource('TalkingHeadOverlay.tsx');
    const absoluteFill = component.match(/<AbsoluteFill[\s\S]*?>/u)?.[0] || '';
    assert(!/background(?:Color)?\s*:/u.test(absoluteFill), 'global dark-room overlay found on AbsoluteFill');
  },
  'KBE-016': () => {
    const validator = source('validate-final.mjs');
    assert(validator.includes('artifact must equal manifest.finalVideo'), 'acceptance artifact is not pinned to final video');
    assert(validator.includes('external_user_message') && validator.includes('threadId') && validator.includes('messageId'), 'external acceptance provenance fields missing');
    assert(validator.includes('remotion.rendererScript is not the canonical Skill renderer'), 'current renderer provenance is not enforced');
    assert(validator.includes('remotion.component is not the managed runtime component'), 'current Remotion component provenance is not enforced');
    assert(validator.includes('rendererSha256') && validator.includes('componentSha256') && validator.includes('styleRendererSha256'), 'current Remotion source hashes are not enforced');
    assert(validator.includes('remotion.styleRenderer does not match manifest.visualStyleId'), 'style-specific Remotion provenance is not enforced');
  },
  'KBE-017': () => {
    for (const name of readdirSync(scriptDir)) {
      if (name.endsWith('.mjs') && name !== 'regression-suite.mjs') assert(!source(name).includes('drawtext='), `uncontrolled inline drawtext filter found in ${name}`);
    }
  },
  'KBE-018': () => {
    const valid = analyzeCaptionTrack([
      {id: 'short', zh: '先找轮子', en: 'Research first'},
      {id: 'mixed', zh: '先用 Vibe Coding', en: 'Start with Vibe Coding'},
    ]);
    assert(valid.result === 'pass', `valid single-line bilingual captions failed: ${JSON.stringify(valid.failures)}`);
    assert(valid.policy.maxLines === 1 && valid.items.every((item) => item.lines.length === 1 && item.enLines.length === 1), 'caption layout is not strictly one line per language');
    const invalid = analyzeCaptionTrack([{id: 'long', zh: '这是一条没有经过语义拆分而且明显超过单行安全宽度的中文字幕', en: 'This sentence was not semantically split before rendering'}]);
    assert(invalid.result === 'fail' && invalid.failures[0]?.severity === 'P1', 'unsplit long caption did not fail before render');
  },
  'KBE-019': () => {
    const preview = source('render-static-preview.mjs');
    assert(preview.includes('maxRenderAttempts || 2') && preview.includes('AUTO_FIX_LIMIT_REACHED') && preview.includes("status: attempt >= maxAttempts ? 'wait_user'"), 'fast-preview render budget is not enforced');
  },
  'KBE-020': () => {
    const preview = source('render-static-preview.mjs');
    assert(preview.includes("'remotion-bundles', cacheKey") && preview.includes('bundleReused') && preview.includes('enableCaching: true'), 'template fingerprint bundle cache is missing');
  },
  'KBE-021': () => {
    const contract = readFileSync(path.join(path.dirname(scriptDir), 'references', 'fast-preview.md'), 'utf8');
    assert(contract.includes('一个写入 Agent') && contract.includes('不做双模型 ASR'), 'fast preview does not enforce one writer and conditional ASR');
  },
  'KBE-022': () => {
    const samples = [
      {zh: 'Vibe Coding 提示词', en: 'A Vibe Coding prompt'},
      {zh: '去 GitHub 找项目', en: 'Search GitHub for projects'},
    ];
    const report = analyzeCaptionTrack(samples.map((item, index) => ({id: `ascii-${index}`, ...item})));
    assert(report.result === 'pass', `ASCII token caption layout failed: ${JSON.stringify(report.failures)}`);
    for (const item of report.items) {
      assert(item.lines.length === 1 && item.enLines.length === 1, `ASCII token caption was not single-line: ${item.text}`);
    }
  },
  'KBE-023': () => {
    const component = templateSource('TalkingHeadOverlay.tsx');
    const core = source('caption-layout-core.mjs');
    assert(core.includes('englishRequired: true') && core.includes('separateLanguagePlates: true'), 'bilingual single-line preflight contract missing');
    assert(component.includes("background: 'rgba(4,6,8,0.84)'") && component.match(/background: 'rgba\(4,6,8,0\.84\)'/gu)?.length >= 2, 'separate translucent black caption plates missing');
    assert(component.includes('{en}') && !component.includes('en.toLowerCase()'), 'natural English translation rendering missing');
    assert(!component.includes('HighlightedText') && !component.includes('WebkitTextStroke'), 'legacy highlighted or thick-stroke caption style remains');
  },
  'KBE-024': () => {
    const component = templateSource('TalkingHeadOverlay.tsx');
    assert(component.includes('"PingFang SC", "Hiragino Sans GB", Arial, sans-serif'), 'light Chinese caption font stack missing');
    assert(component.includes('"Helvetica Neue", Helvetica, Arial, sans-serif'), 'light English caption font stack missing');
    assert(component.match(/fontWeight: 300/gu)?.length >= 2, 'light caption weights missing');
    assert(component.match(/border: 'none'/gu)?.length >= 2, 'borderless caption plates missing');
  },
  'KBE-025': () => {
    const component = `${templateSource('TalkingHeadOverlay.tsx')}\n${templateSource('MgHero.tsx')}`;
    assert(component.includes('const opacity = 1;'), 'semantic card must be visible from beat +0f');
    assert(component.includes('frame >= cueFrom(node.start, fps) && frame < cueFrom(node.end, fps)'), 'node switching must share integer-frame boundaries with captions');
    assert(component.includes('frame >= cueFrom(chapter.start, fps) && frame < cueFrom(chapter.end, fps)'), 'macro chapter label must switch on chapter +0f');
    assert(component.includes('const isActive = index === resolvedIndex && resolvedIndex < timeline.length;'), 'macro chapter active label must switch on chapter +0f');
    assert(!component.includes('const isActive = index === filledSegments && localPartial > 0.01'), 'legacy delayed progress activation remains');
  },
  'KBE-026': () => {
    const renderer = source('render-overlay.mjs');
    assert(renderer.includes('rmSync(outputDir, {recursive: true, force: true});'), 'overlay output reset missing');
    assert(renderer.includes('rmSync(bundleDir, {recursive: true, force: true});'), 'Remotion bundle reset missing');
    assert(renderer.indexOf('rmSync(bundleDir') < renderer.indexOf('ensureDir(bundleDir)'), 'bundle must be reset before recreation');
  },
  'KBE-027': () => {
    const layout = JSON.parse(templateSource('mg-layout.json'));
    const component = templateSource('MgHero.tsx');
    for (const [variant, box] of Object.entries(layout.variants)) {
      assert(box.top + box.height <= layout.safeZones.heroBottomMax, `${variant} exceeds the upper hero safe zone`);
      assert(box.paddingBottom >= 16, `${variant} lacks a minimum bottom-padding budget`);
    }
    assert(layout.variants.prompt_fact.height === 220 && layout.variants.prompt_fact.paddingBottom >= 25, 'prompt card spacing fix drifted');
    assert(layout.variants.dual_relation.height === 216 && layout.inner.relationPanelHeight === 116, 'dual relation panel budget drifted');
    assert(layout.variants.bookmark_relation.height === 252 && layout.inner.bookmarkFooterHeight === 34 && layout.inner.bookmarkFooterGap === 14, 'bookmark footer budget drifted');
    assert(layout.variants.numeric_conclusion.height >= 234, 'numeric conclusion result row budget drifted');
    assert(component.includes("boxSizing: 'border-box'") && component.includes('MG_LAYOUT.inner.relationPanelHeight') && component.includes('MG_LAYOUT.inner.bookmarkFooterHeight'), 'renderer does not consume the fixed card budgets');
  },
  'KBE-028': () => {
    const manifest = {
      schemaVersion: 3,
      video: {duration: 6},
      captionTrack: [{id: 'c001', start: 0, end: 6, displayEnd: 6, zh: '交接文档只写五件事'}],
      nodes: [],
    };
    const sourceMap = {
      argument_map: {
        core_claim: '交接文档只保留必要信息',
        audience_problem: '把所有聊天记录当成交接',
        ending_action: '按清单写交接文档',
        progression: [{id: 'a01', type: 'action', claim: '用清单整理交接内容'}],
      },
      risk_overrides: [],
      beats: [{
        id: 'n01',
        cue_ids: ['c001'],
        argument_id: 'a01',
        boundary: {type: 'opening', change: '开场给出交接清单'},
        semantic_function: '列出必要信息',
        viewer_need: '快速看懂清单',
        trigger_rule: '出现并列事项',
        hero_visual: '编号列表',
        caption_policy: '字幕跟读',
        sound_cue: '仅标题出现时提示',
        layout_risk: '列表不得越过卡片底边',
        mg_copy: {
          label: '清单',
          eyebrow: 'HANDOFF / LIST',
          title: '交接只写 3 件事',
          sub: '每项都有明确作用',
          chips: ['当前状态', '阻塞点', '下一步'],
          accent: 'yellow',
          variant: 'numbered_list',
          payload: {items: [
            {label: '目前在做什么', note: '当前任务'},
            {label: '卡在哪里', note: '阻塞点'},
            {label: '下一步做什么', note: '下一步'}
          ]}
        }
      }]
    };
    const built = buildCompiledMotionMap({manifest, source: sourceMap});
    const nodes = built.compiled ? [{
      id: 'n01', start: 0, end: 6,
      label: '清单', eyebrow: 'HANDOFF / LIST', title: '交接只写 3 件事', sub: '每项都有明确作用',
      chips: ['当前状态', '阻塞点', '下一步'], accent: 'yellow', variant: 'numbered_list',
      payload: {items: [
        {label: '目前在做什么', note: '当前任务'},
        {label: '卡在哪里', note: '阻塞点'},
        {label: '下一步做什么', note: '下一步'}
      ]}
    }] : [];
    const valid = validateCompiledSemanticPlan({manifest: {...manifest, nodes}, motionMap: built.compiled});
    assert(built.failures.length === 0 && valid.failures.length === 0 && valid.unresolved.length === 0, `valid numbered-list variant rejected: ${[...built.failures, ...valid.failures].join('; ')}`);
    const invalidSource = structuredClone(sourceMap);
    invalidSource.beats[0].mg_copy.variant = 'random_card';
    const invalidBuilt = buildCompiledMotionMap({manifest, source: invalidSource});
    const invalidNodes = invalidBuilt.compiled ? [{...nodes[0], variant: 'random_card'}] : [];
    const invalid = validateCompiledSemanticPlan({manifest: {...manifest, nodes: invalidNodes}, motionMap: invalidBuilt.compiled});
    assert(invalid.failures.some((item) => item.includes('variant invalid')), 'unknown MG variant was not rejected');
  },
  'KBE-029': () => {
    const component = templateSource('TalkingHeadOverlay.tsx');
    assert(component.includes("id: 'whole-video'") && component.includes("label: ''"), 'unlabeled whole-video progress fallback missing');
    assert(component.includes('manifest?.progressChapters'), 'macro progress chapters are not routed from manifest');
    assert(!component.includes('{node.label}'), 'semantic beat labels are still dumped into progress chrome');
    assert(component.includes('timeline.map((chapter, index)') && component.includes('{chapter.label}'), 'full macro chapter label row missing');
    assert(!component.includes('{activeChapter.label}') && !component.includes("padStart(2, '0')"), 'incorrect current-only chapter treatment remains');
    testWorkflowRejected((manifest) => {
      manifest.workflow.stage = 'motion_map_ready';
      manifest.workflow.history = ['intake', 'subtitle_reviewed', 'motion_map_ready'].map((stage, index) => ({stage, at: `2026-07-16T00:00:0${index}.000Z`}));
      manifest.workflow.planningMode = 'semantic_manual';
      manifest.video = {duration: 10};
      manifest.progressChapters = Array.from({length: 6}, (_, index) => ({id: `c${index}`, start: index, end: index + 1, label: `章${index}`}));
    }, 'progressChapters must contain 3-5 macro chapters');
  },
  'KBE-030': () => {
    assert(normalizeVisualStyle('黑白版') === 'assembly-mono', 'black-white alias did not resolve to assembly-mono');
    assert(normalizeVisualStyle('谷歌配色') === 'google-semantic', 'Google alias did not resolve to google-semantic');
    assert(baselineForStyle('assembly-mono') === '0726-approved-assembly-mono-v1', 'assembly-mono baseline mapping drifted');
    assert(baselineForStyle('google-semantic') === '0721-approved-baseline-v4-multi-mg', 'google-semantic baseline mapping drifted');
    assert(STYLE_SELECTION_QUESTION.includes('黑白 Assembly') && STYLE_SELECTION_QUESTION.includes('Google 语义配色'), 'single style selection question drifted');
    testWorkflowRejected((manifest) => {
      delete manifest.visualStyleId;
    }, 'visualStyleId must be canonical');
    testWorkflowRejected((manifest) => {
      manifest.visualStyleId = 'assembly-mono';
    }, 'workflow.baselineId must match visualStyleId');
  },
  'KBE-031': () => {
    const component = templateSource('TalkingHeadOverlay.tsx');
    const mono = templateSource('AssemblyMonoHero.tsx');
    assert(component.includes("visualStyleId === 'assembly-mono'") && component.includes('<AssemblyMonoHero beat={activeNode} />'), 'runtime template does not route assembly-mono');
    assert(component.includes('<MgHero beat={activeNode} />'), 'runtime template lost Google semantic renderer');
    assert(mono.includes("bright: '#FFFFFF'") && mono.includes("silver: '#C7C7CC'"), 'assembly monochrome palette drifted');
    assert(mono.includes('AssemblyMonoContrastLayer') && mono.includes('radial-gradient'), 'assembly local feathered contrast layer missing');
    assert(!mono.includes('#4285F4') && !mono.includes('#EA4335') && !mono.includes('#FBBC05') && !mono.includes('#34A853'), 'Google semantic accents leaked into assembly-mono');
  },
};

export function runErrorRegressions(activeCases) {
  const passed = [];
  const failed = [];
  for (const item of activeCases) {
    const testId = item.testId;
    const test = tests[testId];
    if (!test) {
      failed.push({id: item.id, testId, error: 'no executable test registered'});
      continue;
    }
    try {
      test();
      passed.push(item.id);
    } catch (error) {
      failed.push({id: item.id, testId, error: error.message});
    }
  }
  return {passed, failed};
}
