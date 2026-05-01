# Compression Templates

Output templates for each target context. Use these as structural guides when generating compressed questions in the Compress phase. Adapt wording to the specific situation — these are skeletons, not fill-in-the-blank forms.

---

## Table of Contents

1. [Group Chat / Community](#1-group-chat--community)
2. [Email / Formal Message](#2-email--formal-message)
3. [GitHub Issue / Bug Report](#3-github-issue--bug-report)
4. [Asking a Senior / Expert / Mentor](#4-asking-a-senior--expert--mentor)
5. [Asking AI (Prompt Rewrite)](#5-asking-ai)
6. [General / Unspecified](#6-general--unspecified)
7. [Slack / Work Chat](#7-slack--work-chat)
8. [Forum Post (Stack Overflow, Reddit, etc.)](#8-forum-post)
9. [Compression Quality Checklist](#9-compression-quality-checklist)

---

## 1. Group Chat / Community

**Design principle**: One screen, scannable, zero scroll needed for the core question.

**Structure**:
```
[One-sentence question — what you need help with]

Background: [1-2 sentences of context — what you're doing and why]
Stuck at: [Specific step/error/symptom]
Tried: [What you've done so far] (if applicable)

Anyone dealt with this before?
```

**Filled example (tech group)**:
```
Has anyone gotten Playwright to work with sites behind Cloudflare Turnstile?

I'm building an automated test suite for our staging site. The tests run fine locally but fail in CI because Turnstile blocks the headless browser. I've tried setting the user-agent and adding stealth plugin — Turnstile still triggers.

Any workaround or config I'm missing?
```

**Filled example (learning community)**:
```
How do you structure a portfolio when you have no "real" work experience?

I'm a sophomore CS major applying for summer internships. I have 3 personal projects (a todo app, a weather app, a CLI tool) but they feel too basic. I've seen advice to contribute to open source, but I don't know where to start with repos that have 10k+ lines of code.

What did you put in your portfolio that actually got you interviews?
```

**Key rules**:
- Bold or separate the core question from context
- No greetings ("Hey everyone!", "Hi all!") — wastes the first line
- No self-deprecation ("Sorry if this is dumb", "Complete noob here") — wastes space and invites dismissal
- End with a specific ask, not "any thoughts?"

---

## 2. Email / Formal Message

**Design principle**: Recipient knows why they're receiving this within the first two sentences.

**Structure**:
```
Subject: [Specific, actionable subject line]

Hi [Name],

[Why I'm reaching out — 1 sentence connecting to them]

[The situation — 2-3 sentences of context]

[The specific ask — what you need from this person specifically]

[Deadline/urgency if applicable — 1 sentence]

Thanks,
[Your name]
```

**Filled example (cross-department request)**:
```
Subject: Need access to the analytics dashboard for Q2 campaign report

Hi Sarah,

I'm putting together the Q2 campaign report for the marketing review next Friday.

I need access to the Mixpanel dashboard that tracks conversion events. I currently only have the basic view — I need the "Campaign Attribution" board specifically. Chen mentioned you manage dashboard permissions.

Could you grant me read access by Wednesday so I have time to pull the data before the review?

Thanks,
Jing
```

**Filled example (asking someone you don't know well)**:
```
Subject: Question about your Python-to-Rust migration talk at PyCon

Hi Dr. Li,

I watched your PyCon 2024 talk on migrating Python data pipelines to Rust. I'm facing a similar situation — we have a Python ETL pipeline processing 50M records/day and hitting memory limits.

You mentioned you kept Python for orchestration and only moved the hot path to Rust via PyO3. My question: how did you decide which functions were "hot path" enough to justify the Rust rewrite? We have ~40 transform functions and I'm unsure where to draw the line.

I've profiled with cProfile and identified 8 functions that account for 80% of runtime. Would you approach it by migrating those 8 first, or is there a different heuristic you used?

Thanks for your time,
Wei
```

**Key rules**:
- Subject line must be specific (not "Quick question" or "Help needed")
- First sentence explains why *this person* is receiving this email
- Ask must be specific and actionable — what exactly do you need them to do?
- Include timeline if relevant

---

## 3. GitHub Issue / Bug Report

**Design principle**: Reproducible by a stranger who has never seen your setup.

**Structure**:
```
## Description
[One paragraph: what happened vs what should have happened]

## Environment
- OS: [name and version]
- [Tool/Library] version: [exact version]
- [Other relevant versions]

## Steps to Reproduce
1. [Exact step]
2. [Exact step]
3. [Exact step]

## Expected Behavior
[What should happen]

## Actual Behavior
[What actually happens — include exact error messages]

## Additional Context
[Screenshots, logs, config snippets — anything that helps]

## What I've Tried
[Methods attempted and their results]
```

**Filled example**:
```
## Description
`astro build` fails with "Cannot read properties of undefined (reading 'default')" when using content collections with MDX files that import React components.

## Environment
- OS: macOS 14.2
- Node: 20.10.0
- Astro: 4.1.2
- @astrojs/mdx: 2.0.3
- React: 18.2.0

## Steps to Reproduce
1. Create content collection with MDX files
2. Import a React component in an MDX file: `import Counter from '../../components/Counter.tsx'`
3. Use the component: `<Counter client:load />`
4. Run `astro build`

## Expected Behavior
Build succeeds, component renders with client-side hydration.

## Actual Behavior
Build fails at the MDX compilation step:

```
error   Cannot read properties of undefined (reading 'default')
  at processContentEntryFile (astro/dist/content/utils.js:234:18)
```

## What I've Tried
- Downgrading @astrojs/mdx to 1.x → same error
- Using .jsx instead of .tsx → same error
- Removing client:load directive → builds but component doesn't hydrate
- Clean install (deleted node_modules + lockfile) → same error
```

**Key rules**:
- Exact version numbers, not "latest"
- Exact error messages, not paraphrased
- Minimal reproduction — strip everything not related to the bug
- "Steps to Reproduce" must be followable by someone with zero context

---

## 4. Asking a Senior / Expert / Mentor

**Design principle**: Show your homework, narrow to what only they can answer.

**Structure**:
```
[Context: what you're working on and why — 1-2 sentences]

[What you've researched/tried on your own — show effort]

[The specific question that requires their experience/judgment]

[Why their specific perspective matters — optional but powerful]
```

**Filled example (career advice)**:
```
I've been a backend developer for 3 years and I'm considering moving into engineering management. I've been leading a 4-person project team informally for the past 6 months.

I've read "The Manager's Path" and talked to two EMs at my company. The general advice is to try a tech lead role first, which I'm doing. But I'm unsure about one thing:

When you made the switch, how did you handle the shift from "my value = my code output" to "my value = team output"? I find myself jumping in to write code when the team is stuck, and I'm not sure if that's helping or undermining them.

You've managed teams of different sizes — I'd really value your perspective on where the line is.
```

**Filled example (technical expertise)**:
```
We're designing the payment system for our marketplace app (~10k transactions/day expected at launch). I've been reading about event sourcing vs traditional CRUD for financial systems.

I've prototyped both approaches:
- CRUD with audit logs: simpler, but I'm worried about consistency during refunds/disputes
- Event sourcing: audit trail is built-in, but the read-side complexity worries me at our team size (3 devs)

Given our scale and team size, would you go with event sourcing from day one, or start CRUD and migrate later if needed? I know you built [Company X]'s payment infra — curious if event sourcing was worth the upfront complexity at early stage.
```

**Key rules**:
- Show you did your homework before asking
- Narrow the question to what *their unique experience* can answer
- Don't ask something Google can answer
- Respect their time — be specific, not "tell me everything about X"

---

## 5. Asking AI

**Design principle**: Structured for maximum AI comprehension. After compression, offer to answer in-place.

**Structure**:
```
[Role/context setting — who you are, what you're doing]

[Specific task or question]

[Constraints and requirements]

[Expected output format]

[Key context/data if needed]
```

**Filled example**:
```
I'm a product manager writing user stories for a food delivery app's reorder feature.

Write 5 user stories for the "reorder past meal" feature. Each story should follow the format: "As a [user type], I want to [action] so that [benefit]."

Constraints:
- Cover both happy path and edge cases (restaurant closed, item unavailable, price changed)
- User types: frequent orderer, first-time reorderer, dietary-restricted user
- Must include acceptance criteria for each story

Output as a numbered list with acceptance criteria as sub-bullets.
```

**Key rules**:
- After compressing, always ask: "Want me to ask this for you right now?"
- If user says yes, execute the compressed prompt directly and return the answer
- This creates a closed loop — user doesn't need to copy-paste anywhere

---

## 6. General / Unspecified

**Design principle**: When no specific context is given, use a clean, universal format.

**Structure**:
```
[Core question — one sentence]

Context: [Why you're asking, what you're doing — 2-3 sentences]

Specifically stuck on: [The exact point of confusion or blocker]

What I've tried: [Previous attempts, if any]

Looking for: [What form of help you need — direction, specific answer, judgment call, etc.]
```

**Filled example**:
```
How do I set up CI/CD for a monorepo with 3 services that deploy independently?

Context: We have a Node.js API, a React frontend, and a Python data pipeline in one repo. Currently deploying manually via SSH. Want to automate with GitHub Actions.

Specifically stuck on: How to trigger only the relevant pipeline when files in one service change, without rebuilding everything.

What I've tried: Used `paths` filter in workflow files, but it doesn't handle shared dependencies (e.g., changes to /shared/utils should trigger all three).

Looking for: A pattern or example repo that handles selective builds in a monorepo with shared code.
```

---

## 7. Slack / Work Chat

**Design principle**: Respects the reader's attention in a high-noise environment.

**Structure**:
```
[emoji tag] [One-line summary of what you need]

> [Brief context — 1-2 sentences, use quote block for visual separation]

Specific question: [The exact thing you need answered/done]
```

**Filled example**:
```
🔍 Need help debugging the staging checkout flow

> Checkout started failing after this morning's deploy. Payment API returns 200 but order doesn't get created. Only happens on staging, prod is fine.

Has anyone seen this before? I suspect it's the new webhook validation but haven't confirmed yet. cc @backend-team
```

**Key rules**:
- Thread your question — don't dump multi-paragraph questions in the main channel
- Use emoji tags for scanability (🔍 question, 🚨 urgent, 📋 FYI)
- Tag relevant people/groups
- Keep main message short, add details in thread

---

## 8. Forum Post

**Design principle**: Searchable and self-contained — a stranger 2 years later should be able to understand and benefit.

**Structure**:
```
Title: [Specific, searchable title — include key terms]

[Problem statement — 2-3 sentences]

[What I've tried — with code/config snippets if relevant]

[Environment details if technical]

[Specific question — what kind of answer are you looking for?]
```

**Filled example (Stack Overflow style)**:
```
Title: TypeScript generic type not narrowing inside conditional branch

I have a generic function that should narrow the type based on a discriminated union, but TypeScript still shows the union type inside the conditional branch:

    function handle<T extends { type: 'a'; value: string } | { type: 'b'; value: number }>(input: T) {
      if (input.type === 'a') {
        // TypeScript still shows input.value as string | number here
        console.log(input.value.toUpperCase()); // Error
      }
    }

I expected `input.value` to narrow to `string` inside the `type === 'a'` branch.

TypeScript version: 5.3.3, strict mode enabled.

I've tried:
- Using `as const` on the type literals → no change
- Overloaded signatures → works but verbose
- Type guard function → works but shouldn't be necessary?

Is this a known TypeScript limitation with generic conditional narrowing, or am I structuring the type wrong?
```

**Key rules**:
- Title must contain the core technical terms (for searchability)
- Include minimal code that reproduces the issue
- State what you expected vs what happened
- List what you've tried to show effort and prevent duplicate answers

---

## 9. Compression Quality Checklist

Run this checklist after generating any compressed output:

### Information completeness
- [ ] Can a stranger understand the problem without additional questions?
- [ ] Is the goal/desired outcome stated?
- [ ] Is the specific blocker/question clear?
- [ ] Are relevant constraints mentioned (timeline, tools, environment)?

### Information density
- [ ] Every sentence adds new information (no redundancy)
- [ ] No filler phrases ("I was wondering if maybe...", "I hope this isn't too much trouble...")
- [ ] No self-deprecation ("Sorry if this is obvious", "I'm just a beginner")
- [ ] Technical details are precise (exact versions, exact error messages)

### Tone and format
- [ ] Matches the target context (formal for email, compact for chat)
- [ ] Shows effort/homework where appropriate (expert, forum)
- [ ] Respectful but not groveling
- [ ] Ends with a clear, specific ask

### Safety
- [ ] No passwords, tokens, API keys, or secrets in the output
- [ ] No unnecessary personal information
- [ ] Internal URLs/paths redacted if going to external audience
