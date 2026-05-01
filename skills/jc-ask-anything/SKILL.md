---
name: jc-ask-anything
description: >
  Turn messy, unclear questions into precise, answerable requests. Use when
  user says "help me ask", "I don't know how to ask this", "help me phrase
  this question", "ask-anything", or when user has a vague problem they need
  help articulating. Also triggers when user wants to formulate a question
  for a group chat, email, GitHub issue, expert consultation, or AI prompt.
  Covers: question clarification, problem diagnosis, XY problem detection,
  question compression, and smart routing (AI solve vs ask a human).
---

# Ask Anything

Turn unclear questions into precise, answerable requests through structured diagnosis and compression.

**Core insight (Polanyi)**: People know more than they can say. Users sense where the problem is, but that sensing is tacit — it can't directly become clear language. This skill bridges that gap.

**First design principle — Recognition > Description**: Never ask users to describe from scratch. Always offer candidate interpretations for them to recognize and correct.

- Bad: "Can you elaborate?"
- Good: "I'm guessing it's one of these: A / B / C — which is closest?"

## Workflow

```
Input → Clear Gate → Parse → Dig (skippable) → Route → Compress
```

### Startup Modes

**Cold start**: User invokes skill with a question (one sentence or a wall of text).

**Hot start**: User has been chatting, problem unresolved, then invokes skill.
- Auto-extract from conversation: what user is doing / where stuck / what was tried / what AI said / why it didn't work
- Only ask about missing pieces — never re-ask what's already in context
- If goal + blocker are both clear from context → skip Dig, go straight to Route

## Clear Gate

Evaluate before doing anything. Pass = zero-overhead release.

Pass criteria (all three must be true):
1. Goal is clear (what user wants to achieve)
2. Blocker is specific (where exactly they're stuck)
3. Context is sufficient (enough info for the answerer to understand and respond)

If pass → say "Your question is already clear — go ahead and ask it as-is." Stop here unless user wants help anyway.

If fail → proceed to Parse.

## Parse (Understand)

Extract structured info from raw input. Four dimensions:

| Dimension | Required? | How to ask |
|-----------|-----------|------------|
| **Goal** (what they want) | Always | Offer candidate goals: "Are you trying to do A, B, or C?" |
| **Symptom** (where stuck) | Always | Probe the subsidiary layer: "What happened that made you think of this?" |
| **Tried** (what they did) | If hinted | If user implies effort ("spent hours", "can't figure out"), must ask what specifically they tried |
| **Environment** (constraints) | Depends | Ask only when problem type requires it (tech: version/OS; work: role/org) |

**Polanyi principles for all questions:**
- Offer candidate interpretations, don't demand descriptions
- Probe the subsidiary layer (ask about triggering events and context, not "what do you mean by X?")
- Acknowledge that the user's vague sense of a problem is real and valid

Output: One-sentence restatement → "So your situation is: ____ — is that right?"

**Special cases:**
- 500+ chars of text → compress to core first, confirm understanding
- "I don't even know what to ask" → start from scene: "What are you working on? Where does it feel off?"
- Emotional ("I'm losing it", "so frustrated") → validate once ("sounds like a real headache"), then steer to specifics

## Dig (Deepen) — Skippable

**Purpose**: Catch XY problems. Find the real question behind the stated question.

**Enter Dig only when signals detected:**
- User asks about a specific solution, not the problem itself
- Logical jumps in description (conclusion without premises)
- User is uncertain ("I think maybe...?")
- Question is too broad to answer

**Skip Dig when**: Parse confirmed correct understanding AND question is singular and specific.

**Rules:**
1. Every follow-up must include AI's guess: "I think what you really need is ____?"
2. Batch related questions: ask 2-3 per round to reduce back-and-forth
3. Max 3 rounds. User says "yes" or "that's it" → stop. After 3 rounds → proceed with best current understanding, flag uncertain parts
4. Tone: friend helping think through, not interrogator

**Compound problems**: If one "question" is actually multiple tangled problems → split them: "You actually have two questions here: A is ____, B is ____. Want to tackle them one at a time?" Each sub-question enters Route independently.

## Route (Triage)

Determine optimal resolution path.

| Path | Condition | Action |
|------|-----------|--------|
| **AI solves** | Factual, searchable, or deducible | Search and answer directly |
| **AI tries first** | AI can give 60-80% answer | Search, attempt answer, ask if satisfactory |
| **Must ask a human** | Involves others' decisions, permissions, subjective judgment, internal info, or human connection | Proceed to Compress |

**AI-tries-first loop:**
1. Search and attempt an answer based on the clarified question
2. No useful results → tell user honestly, pivot to ask-human path. Never fabricate
3. Got results → ask: "Does this solve it?"
4. Yes → done (conditionally trigger Teach)
5. No → "This one really needs a human. Let me help you phrase it." → Compress, using info gathered during the AI attempt to improve the question

## Compress (Express + Anticipate)

Transform the clarified question into a send-ready text the answerer can understand in one read.

**Internal completeness checklist** (not the output format):
- [ ] Question: one sentence, what's being asked
- [ ] Background: minimal context needed to understand
- [ ] Blocker: specific step where stuck, what happens
- [ ] Tried: methods attempted and results (if any)
- [ ] Expected help: what form of help is needed (direction / specific action / judgment)

**Output format adapts to context:**

| Context | Format |
|---------|--------|
| Group chat | Compact, fits one screen, bold key info |
| Email / formal message | Open with why you're reaching out, slightly formal tone |
| GitHub Issue | Environment + Reproduction steps + Expected vs Actual |
| Asking a senior / expert | Show homework done, narrow to what only they can answer |
| Asking AI | Rewrite then ask: "Want me to ask this for you right now?" → if yes, answer in-place |
| Unspecified | General format: concise paragraphs, complete info |

**Compression principles:**
- Information density first — every sentence adds new info
- Length follows content — 50 chars if enough, 500 if needed
- Strip noise — remove pleasantries ("hey experts", "sorry to bother")
- Strip redundancy — say each thing once
- Keep critical details — error messages, version numbers, key screenshots

**Self-check**: After compressing, verify: "Does this version preserve the user's core intent? Did compression lose anything important?"

**Sensitive info**: Auto-redact passwords, tokens, keys in output. Alert user to review.

**Anticipate follow-ups** (optional, complex questions only):
- Predict 1-3 likely follow-up questions from the answerer
- Provide suggested responses: "They might ask ____, you can say: ____"
- Suggest preparing supplementary materials (screenshots, logs, files) if helpful

## Teach (Reflect) — Conditional

Triggers only when original question was significantly transformed:
- Went through Dig (question was redefined) → trigger
- Went through ask-human path with major rewrite → trigger
- AI solved directly and question was already clear → skip
- Clear Gate passed → skip

Format (max 5 lines):
```
---
Reflecting on your question:

Original: "{verbatim user input}"
Gap: {one sentence — what was missing or misdirected}
Improved: "{compressed/restructured version}"
Next time, try: {one-sentence formula specific to this case}
---
```

Principles: brief, specific, show contrast (before vs after), no lecturing.

## Edge Cases

| Case | Response |
|------|----------|
| One sentence "how do I X" | Parse with candidate guesses, don't rush to answer |
| 500+ char wall of text | Compress to core, confirm understanding |
| Emotional user | Validate once ("that sounds rough"), then steer to specifics |
| "I don't know what to ask" | Start from scene: "What are you working on lately?" |
| Complete beginner | Lower the bar, use analogies, supply vocabulary |
| Multiple tangled questions | Split, prioritize or let user choose order |
| Wrong assumption in question | Point out during Dig: "You're assuming X, but actually ____" |
| Venting, not asking | "Do you want to solve this, or vent first? Both are fine" |
| Asking authority/superior | Adapt tone in Compress, add "why this needs you" framing |
| Sensitive info in context | Auto-redact in output, remind user to check |
| User goes silent after follow-up | Output best version with current info, note "feel free to add more details later" |

## Interaction Principles

1. Tone: friend helping you think, not teacher grading you
2. Every follow-up includes AI's guess (recognition > description)
3. Batch related questions to minimize rounds
4. Use "you" not formal address — conversational, not stiff
5. When solving directly, don't lecture — teach only in Teach section
6. Never re-ask what user already said (especially in hot start)
7. User says "good enough" or "just do it" → immediately output best result with current info, don't force the full workflow

## What This Skill Does NOT Do

- Make decisions for the user
- Provide therapy or emotional counseling
- Fabricate information or fake search results
- Over-engineer simple questions — if it's clear, let it through

## Reference Materials

This skill includes detailed reference files. Load them as needed — not all at once.

| File | When to read | Content |
|------|-------------|---------|
| [references/examples.md](references/examples.md) | Before first use, or when unsure how to handle a case | 8 complete worked examples: XY problem, vague→specific, ask-human, Clear Gate pass, hot start, AI-try→fallback, compound problem, emotional user |
| [references/methodology.md](references/methodology.md) | When you need to understand *why* the workflow works this way, or hit an edge case not covered above | Polanyi's tacit knowledge, Taylor's 4 layers, XY problem theory, reference interview technique, rubber duck effect, SBAR/Five Whys/MRE frameworks, 7 converged principles, cognitive science of asking, anti-patterns |
| [references/compression-templates.md](references/compression-templates.md) | During the Compress phase — pick the template matching the user's target context | Output templates for 8 contexts: group chat, email, GitHub Issue, expert, AI prompt, general, Slack, forum post. Each with filled real-world examples + quality checklist |
| [references/dig-patterns.md](references/dig-patterns.md) | During Parse/Dig — when you need to probe deeper or something feels off | XY detection patterns, question banks for 5 situation types (tech, career, learning, interpersonal, business), 6 common misdirection patterns, compound problem decomposition, depth calibration guide |
| [references/edge-cases.md](references/edge-cases.md) | When you encounter a tricky user interaction | Full dialogue examples for all 12 edge cases: one-sentence input, wall of text, emotional, doesn't know what to ask, beginner, tangled questions, wrong assumption, venting, authority, sensitive info, silence, already clear |
