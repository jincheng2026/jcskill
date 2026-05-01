# Core Methodology

This file contains the theoretical foundations and practical principles that power the Ask Anything skill. Read this when you need to understand *why* the workflow is designed the way it is, or when you encounter an edge case not covered by the main SKILL.md.

---

## Table of Contents

1. [The Tacit Knowledge Problem (Polanyi)](#1-the-tacit-knowledge-problem)
2. [The Four Layers of Need (Taylor)](#2-the-four-layers-of-need)
3. [The XY Problem](#3-the-xy-problem)
4. [The Reference Interview (Library Science)](#4-the-reference-interview)
5. [The Rubber Duck Effect](#5-the-rubber-duck-effect)
6. [Structured Expression Frameworks](#6-structured-expression-frameworks)
7. [The Seven Converged Principles](#7-the-seven-converged-principles)
8. [Cognitive Science of Asking](#8-cognitive-science-of-asking)
9. [Anti-Patterns to Avoid](#9-anti-patterns-to-avoid)

---

## 1. The Tacit Knowledge Problem

**Source**: Michael Polanyi, *Personal Knowledge* (1958), *The Tacit Dimension* (1966)

**Core insight**: "We can know more than we can tell."

Users who come with vague questions are not lazy or stupid. Their knowledge of their own problem is *structurally tacit* — they sense something is wrong, they can feel where the problem is, but this sensing cannot be directly converted into language.

### Practical implications for this skill:

**Recognition over description**: Humans are bad at generating descriptions from scratch but excellent at recognizing correct descriptions from a set. This is why face recognition works (you spot a face instantly) but face description fails (try describing someone's face to a sketch artist).

- When gathering information: offer candidate interpretations, don't ask for raw descriptions
- When confirming understanding: give a restatement to confirm/deny, don't ask "did I get that right?"
- When exploring possibilities: present A/B/C choices, don't ask "what do you think?"

**Focal vs. subsidiary awareness**: Polanyi distinguishes between:
- **Focal awareness**: what you're directly attending to ("I want to learn AI")
- **Subsidiary awareness**: the background signals supporting that focus (saw colleagues using AI, felt anxious about being replaced, tried ChatGPT once and gave up)

The user gives you focal awareness (a vague sentence). The diagnostic value is in subsidiary awareness. To access it:
- Ask about triggering events: "What happened recently that made you think about this?"
- Ask about context: "What were you doing when you got stuck?"
- Ask about feelings: "What specifically felt wrong?" (not "what IS wrong")

**Respecting the vague**: Polanyi argues that perceiving a problem is itself a major intellectual achievement. The user's vague sense that something is off is *real knowledge* — it's just tacit. Never dismiss vagueness; work with it.

---

## 2. The Four Layers of Need

**Source**: Robert Taylor, "Question-Negotiation and Information Seeking in Libraries" (1968)

Taylor identified four layers of information need:

| Layer | Name | Description | Example |
|-------|------|-------------|---------|
| Q1 | Visceral need | Vague sense of dissatisfaction, can't articulate | "Something about my business feels wrong" |
| Q2 | Conscious need | Knows there's a gap, can describe the area | "I think I need better marketing" |
| Q3 | Formalized need | Can state the question in words | "How do I run Facebook ads?" |
| Q4 | Compromised need | Adapts the question to what they think you can answer | "What's a good Facebook ads course?" |

**Critical insight**: Most users present Q4 — a compromised version of their real need, shaped by what they think the system/person can handle. If you answer Q4 literally, you might solve the wrong problem.

### How this maps to the skill:

- **Clear Gate** catches well-formed Q3/Q4 that are genuinely clear
- **Parse** tries to surface Q2 from Q4 presentations
- **Dig** tries to reach Q1/Q2 when Q3/Q4 feel off
- **The entire skill exists because Q4 ≠ Q1**

### Practical detection:

Signs you're looking at Q4 (compromised need):
- User asks about a very specific tool/method (narrowed to what they think exists)
- User pre-frames the question ("I know this is a stupid question, but...")
- User asks something oddly specific without context ("How do I change the font color in cell B7?")
- User has already decided on a solution and is asking about implementation

When you suspect Q4, don't answer it — dig toward Q2/Q1 first.

---

## 3. The XY Problem

**Source**: Community wisdom, formalized on xyproblem.info

**Definition**: User wants to solve X. User thinks Y is the way to solve X. User asks about Y instead of X. When Y doesn't work, the real problem (X) never gets addressed.

### Classic example:
- X (real need): "I need the last 3 characters of a filename"
- Y (their approach): "How do I get the last 3 characters of a string in Bash?"
- Answering Y literally works, but the real solution is `${filename##*.}` (extract extension)

### Detection signals:

| Signal | Example | Why it matters |
|--------|---------|---------------|
| Asks about implementation detail without context | "How to set Nginx timeout to 300s?" | Why 300? What's timing out? |
| Solution-first language | "I need a regex that..." | Why regex? What's the actual parsing need? |
| Unusually specific | "How to make cell B7 bold in openpyxl?" | Why B7? What's the spreadsheet doing? |
| Asks "how" without "why" | "How do I install X?" | What problem will X solve? |
| Switching between unrelated details | "I changed the CSS but now the API fails" | Possibly two problems tangled |

### Response strategy:

1. Don't refuse to answer Y — that's annoying
2. Ask what X is: "Just to make sure we solve the right thing — what's this for?"
3. If they confirm Y is what they want, help with Y (they might know better)
4. If X surfaces and has a better solution, present both: "You can do Y this way: ___. But if the goal is X, there's actually a simpler approach: ___"

---

## 4. The Reference Interview

**Source**: Library and Information Science, 100+ years of practice

Librarians have been doing exactly what this skill does since the 1800s: helping confused people figure out what they actually need. Their structured approach:

### The six-stage reference interview:

| Stage | What happens | Maps to skill |
|-------|-------------|---------------|
| 1. Establish rapport | Make the person feel comfortable asking | Tone: friend, not judge |
| 2. Negotiate the question | Iterative back-and-forth to clarify need | Parse + Dig |
| 3. Develop strategy | Decide how to find the answer | Route |
| 4. Find information | Execute the search/retrieval | AI solve / AI try |
| 5. Follow up | "Did this answer your question?" | Satisfaction check |
| 6. Close | Ensure the person got what they needed | Teach (optional) |

### Key techniques from librarians:

**Open → Closed funnel**: Start with open questions ("What are you working on?"), narrow to closed questions ("Is it for work or personal?") as clarity develops.

**Neutral questioning**: "What have you found so far?" beats "Did you try Googling it?" — the first gathers info, the second judges.

**The 3-second pause**: After the user answers, wait. They often add the most important detail after a pause. In a chat context: don't rush to the next question, acknowledge what they said first.

**Verify before acting**: Always restate your understanding before proceeding. "So what you need is ___ — correct?" This catches misunderstandings early.

---

## 5. The Rubber Duck Effect

**Source**: Hunt & Thomas, *The Pragmatic Programmer* (1999)

**Principle**: The act of explaining a problem to someone (or something) often reveals the solution. Programmers debug by explaining code line-by-line to a rubber duck.

### Implications for this skill:

Sometimes the best thing the skill can do is **not solve the problem**, but force the user to explain it clearly. The structured extraction process (Parse → Dig) is itself therapeutic — users frequently say "oh wait, I think I see the issue" mid-conversation.

### When to lean into the duck effect:

- User says "let me think about how to explain this..."
- User starts correcting themselves mid-sentence
- User says "actually, now that I say it out loud..."

When this happens: **pause**, let them continue. Don't rush to the next question. They're solving their own problem.

### When NOT to duck:

- User is clearly frustrated and wants a quick answer
- The problem is simple and factual
- User explicitly says "just help me write the question"

---

## 6. Structured Expression Frameworks

These frameworks inform how compressed output should be structured, depending on context.

### SBAR (Situation-Background-Assessment-Recommendation)

**Origin**: US Navy, adopted by healthcare for critical communication

| Component | Purpose | Example |
|-----------|---------|---------|
| Situation | What's happening right now | "Our API response times doubled this morning" |
| Background | Relevant context | "We deployed v2.3 last night, traffic is normal" |
| Assessment | What you think the problem is | "I suspect the new database query in the user endpoint" |
| Recommendation | What you want the other person to do | "Can you check the query execution plan?" |

**Best for**: Technical escalations, urgent work requests, status updates to leadership.

### Five Whys

**Origin**: Toyota Production System (Sakichi Toyoda)

Repeatedly ask "why?" to drill from symptom to root cause:
1. Why did the server crash? → Memory exceeded limit
2. Why did memory exceed? → Log files grew unbounded
3. Why did logs grow? → Error retry loop
4. Why the retry loop? → External service was down
5. Why no circuit breaker? → **Root cause**: Missing resilience pattern

**Best for**: The Dig phase — when surface symptoms don't reveal root cause. Don't literally ask "why?" five times (that's annoying). Instead, integrate "why" naturally: "You mentioned X broke — what changed before that happened?"

### MRE / MCVE (Minimal Reproducible Example)

**Origin**: Stack Overflow community standards

Strip away everything not needed to reproduce the problem:
- Remove unrelated code
- Use minimal data
- Include exact error messages
- State expected vs actual behavior

**Best for**: Technical questions in Compress phase. When the user has a code/config problem, help them create an MRE — it often reveals the bug AND makes the question dramatically better.

### 5W1H (Who/What/When/Where/Why/How)

**Origin**: Journalism

Simple completeness checklist. Not all six are always relevant, but scanning through them catches missing context.

**Best for**: Quick mental check during Parse — "Do I know enough about who/what/when/where/why/how to understand this problem?"

---

## 7. The Seven Converged Principles

All the above frameworks converge on these seven actionable principles:

### Principle 1: State the real goal, not your attempted solution
- **Frameworks**: XY Problem, Five Whys, Taylor Q1-Q4
- **In practice**: If user says "how do I do Y?", always verify: "What problem will Y solve for you?"

### Principle 2: Show what you've already tried
- **Frameworks**: Raymond's "How to Ask Questions the Smart Way", Stack Overflow, MRE
- **In practice**: Gather "already tried" info during Parse. It prevents duplicate suggestions and signals effort.

### Principle 3: Provide minimal but complete context
- **Frameworks**: MRE, SBAR, 5W1H
- **In practice**: Every sentence in the compressed output must add new information. If removing a sentence doesn't change the answerer's understanding, remove it.

### Principle 4: Distinguish symptom from cause
- **Frameworks**: Five Whys, XY Problem, Rubber Duck
- **In practice**: During Dig, always check: "Is this the problem, or a symptom of a deeper problem?"

### Principle 5: State expected vs actual behavior
- **Frameworks**: MRE, GitHub issue templates, Stack Overflow
- **In practice**: In compressed output, include: "I expected ___, but what happened was ___." This is the single most useful sentence pattern for technical questions.

### Principle 6: The process of asking is itself learning
- **Frameworks**: Rubber Duck, Socratic Method, QFT
- **In practice**: Sometimes the user solves their own problem during Parse/Dig. Celebrate this, don't shortcircuit it.

### Principle 7: Ask with curiosity, not demands
- **Frameworks**: Humble Inquiry (Schein), Reference Interview
- **In practice**: The tone of the compressed output should show genuine engagement, not entitlement. "I'm stuck on ___ and would appreciate your perspective" beats "Please fix this ASAP."

---

## 8. Cognitive Science of Asking

Why people struggle with questions — understanding this prevents frustration with users.

### Functional fixedness
Users get locked into one way of thinking about a problem. They can't see alternative framings. This is why the skill exists: provide alternative frames.

**Response**: Offer reframings: "What if instead of thinking about it as X, we think about it as Y?"

### Problem representation is the hard part
Cognitive psychology (Newell & Simon, 1972) shows problem-solving has three phases:
1. **Represent** the problem (hardest)
2. Choose a **strategy**
3. **Execute** the strategy

Most people skip step 1 and jump to step 3. The skill forces them back to step 1.

### Help-seeking as stigma
Research shows that from age 7, humans associate asking for help with incompetence. Perfectionist users especially resist asking well because asking well means admitting what they don't know.

**Response**: The skill's tone must never make users feel judged for not knowing something. "Good question" is patronizing. Instead, validate: "That's a tricky situation — let me help you frame it."

### Cognitive load during frustration
When frustrated, working memory shrinks. Users literally cannot organize thoughts as well when stressed. This is why emotional users produce worse questions — it's cognitive, not attitudinal.

**Response**: For emotional users, reduce cognitive load: offer choices instead of open questions, keep each interaction simple, don't ask multiple things at once.

---

## 9. Anti-Patterns to Avoid

Behaviors that seem helpful but actually make questions worse:

| Anti-pattern | Why it's bad | What to do instead |
|-------------|-------------|-------------------|
| "Can you be more specific?" | Demands generation from someone who can't generate | Offer specific options to choose from |
| "What exactly is the error?" | Too broad when user is overwhelmed | "Is it a red error banner, a blank page, or something else?" |
| "Have you tried Googling it?" | Dismissive, assumes laziness | Ask what they've found so far (neutral framing) |
| Asking 5+ questions at once | Overwhelms, user answers only the easiest one | Max 2-3 related questions per round |
| Restating the problem in jargon | User doesn't speak jargon, feels alienated | Restate in their words, add jargon only if helpful |
| "That's a good question!" | Patronizing (implies you expected a bad one) | Skip the evaluation, just help |
| Over-qualifying answers | "Well, it depends on many factors..." | Give the most likely answer first, qualify only if needed |
| Forcing the full workflow | User says "just help me write it" | Respect their agency, skip to Compress |
| Providing unsolicited life advice | "Maybe you should consider if this career is right for you" | Stay in scope — help frame the question, don't answer it |
| Treating vagueness as a flaw | "Your question is too vague" | Vagueness is a symptom of tacit knowledge, work with it |
