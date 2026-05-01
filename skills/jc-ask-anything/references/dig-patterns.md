# Dig Patterns: Deep Exploration Toolkit

Signal detection, question banks, and common misdirection patterns for the Dig (Deep Exploration) phase. Read this when you need to go deeper than surface-level parsing, or when something about the user's question feels off but you can't pinpoint why.

---

## Table of Contents

1. [XY Problem Detection Patterns](#1-xy-problem-detection-patterns)
2. [Question Bank by Situation Type](#2-question-bank-by-situation-type)
3. [Common Misdirection Patterns](#3-common-misdirection-patterns)
4. [Compound Problem Decomposition](#4-compound-problem-decomposition)
5. [Depth Calibration Guide](#5-depth-calibration-guide)

---

## 1. XY Problem Detection Patterns

### High-confidence XY signals

These almost always indicate the user is asking about their attempted solution (Y), not their actual problem (X):

| Signal | Example | What to probe |
|--------|---------|---------------|
| **Tool-specific how-to without context** | "How do I use sed to replace text in multiple files?" | What's the actual editing task? Maybe their IDE can do it. |
| **Asking about step 5 of a 10-step plan** | "How do I parse the JSON response from this API?" | Why are they calling this API? What data do they actually need? |
| **Bizarrely specific** | "How to make a div exactly 347px wide?" | Why 347? What layout problem is this solving? |
| **"I need X so I can Y"** | "I need to convert this PDF to Word so I can edit a table" | Maybe they can edit the PDF directly, or the table exists elsewhere |
| **Solution shopping** | "Is tool A or tool B better for X?" | What is X? They may not need either tool |
| **Implementation detail as the question** | "What's the regex for matching emails?" | What's the actual validation requirement? Regex is rarely the right email validator |

### Medium-confidence signals (probe gently)

| Signal | Example | What to probe |
|--------|---------|---------------|
| **Presupposes a constraint** | "Since we can't use React, how do I...?" | Is that constraint real? Who said no React? |
| **Asks for workaround** | "How to bypass the rate limit?" | Why are you hitting the limit? Maybe the approach is wrong |
| **References a specific technology unprompted** | "I'm building this in Kubernetes..." | Does this need Kubernetes? What's the actual infrastructure need? |

### Probing XY without being annoying

The goal is not to interrogate — it's to ensure you solve the right problem. Always frame as trying to help better:

**Pattern 1 — The casual redirect**:
"Quick check before I dive in — what's this for? I want to make sure I give you the most useful answer."

**Pattern 2 — The "just to be thorough"**:
"I can help with that. Just to be thorough — is [X] the actual goal, or is there a bigger picture I should know about?"

**Pattern 3 — The offer of alternatives**:
"There are a few ways to approach this depending on the actual goal. Are you trying to: A) ___, B) ___, or C) something else?"

**Pattern 4 — Answer Y, then probe X**:
"Here's how to do [Y]: ___. By the way, if your underlying goal is [X], there might be a simpler approach — want me to explore that?"

---

## 2. Question Bank by Situation Type

Pre-built questions for common categories of problems. Always adapt to context — never ask these robotically.

### Technical / Code Problems

**Gathering context**:
- "What were you doing right before this broke? Did anything change recently?" (triggers subsidiary awareness)
- "Is this happening every time, or only sometimes? If sometimes, what's different when it works?"
- "What does the error message say? Can you paste the exact text?"
- "What OS / version / tool version are you using?"

**Finding the real problem**:
- "What would success look like here? If this worked perfectly, what would happen next?"
- "I'm guessing you're trying to [X] — is that right, or is there more to it?"
- "When did this last work? What changed between then and now?"

**Checking assumptions**:
- "You mentioned [specific technology] — is that a hard requirement, or are you open to alternatives?"
- "Is this for production, or a local/dev environment? The approach might differ."

### Career / Work Decisions

**Understanding motivation**:
- "What triggered this thought? Was there a specific moment, or has it been building?"
- "When you imagine this going well, what does that look like in 6 months?"
- "What's the cost of NOT doing this? What happens if you stay where you are?"

**Checking framing**:
- "You said you want to [do X]. Is that because of [push factor] or [pull factor]?" (push = running from something, pull = running toward something — different advice)
- "Who else is affected by this decision? Have you talked to them?"
- "What's your biggest worry about this?"

### Learning / Skill Acquisition

**Narrowing scope**:
- "Are you learning this for a specific project, for career growth, or out of curiosity?"
- "What's your current level? Have you done anything similar before?"
- "Do you learn better by reading, watching, or doing?"

**Finding the real block**:
- "What part feels overwhelming? Is it 'too much to learn' or 'don't know where to start'?"
- "Have you tried learning this before? What happened?"
- "Is there a deadline or goal driving this, or is it open-ended?"

### Interpersonal / Communication

**Understanding the relationship**:
- "How well do you know this person? What's your relationship like?"
- "Have you brought up anything like this before? How did they react?"
- "What's the power dynamic here? Are they above you, below you, or peer?"

**Understanding the goal**:
- "What's the best realistic outcome of this conversation?"
- "Are you looking for permission, buy-in, or just informing them?"
- "What would make this conversation feel successful to you?"

### Product / Business Decisions

**Understanding constraints**:
- "Who are the stakeholders on this decision?"
- "What's the timeline? Is there a hard deadline?"
- "What resources (budget, team, tools) are available?"

**Checking assumptions**:
- "Have you validated this with users/customers? What did they say?"
- "What's the minimum version of this that would be useful?"
- "What happens if this doesn't work? What's your fallback?"

---

## 3. Common Misdirection Patterns

Patterns where the stated question consistently leads away from the real need.

### Pattern: "How do I learn X?" (when the real question is "Should I learn X?")

**Signal**: User asks about learning paths/resources for a specific skill, but context reveals uncertainty about whether to pursue it at all.

**Example**: "What's the best way to learn machine learning?" (user is a marketing manager exploring career options)

**Redirect**: "Before we dive into resources — what would you do with ML once you know it? That'll determine whether ML is the right thing to learn, and which parts to focus on."

### Pattern: "Which tool is best?" (when the real question is "How do I solve this problem?")

**Signal**: Comparative tool questions without stated criteria or use case.

**Example**: "Should I use Notion or Obsidian?"

**Redirect**: "Depends on what you need. Quick check: are you working solo or with a team? Do you need web access or offline is fine? What kind of content — notes, project management, wiki?"

### Pattern: "How do I convince X?" (when the real question is "Am I right about this?")

**Signal**: User assumes their position is correct and wants persuasion tactics.

**Example**: "How do I convince my team to switch to TypeScript?"

**Redirect**: "What's driving the switch? If it's type safety, there might be lighter options. If it's DX, that's a stronger case. What's their main objection?"

### Pattern: "Is this normal?" (when the real question is "What should I do?")

**Signal**: User describes a situation and asks if it's normal/common, but actually wants guidance.

**Example**: "Is it normal for an internship to not give you any real work?"

**Redirect**: "That happens, unfortunately. More importantly — is this something you want to change? If so, I can help you figure out how to ask for more meaningful work."

### Pattern: "Can you review this?" (when the real question is "I feel insecure about this")

**Signal**: User shares completed work for "review" but actually wants reassurance or validation.

**Example**: "Can you look at my resume? I feel like something's off."

**Redirect**: "I'll take a look. Before I do — what specifically feels off to you? Is it the content, the format, or something about how it positions you?"

### Pattern: "What's the difference between A and B?" (when the real question is "Which should I pick?")

**Signal**: Comparison question that's actually a decision in disguise.

**Example**: "What's the difference between React and Vue?"

**Redirect**: "I can compare them, but it'll be more useful if I know your context. Are you picking one for a project? What kind of project, and what's your team's experience?"

---

## 4. Compound Problem Decomposition

When a user's "one question" is actually multiple tangled problems.

### Detection signals

- User's description shifts topics mid-paragraph
- Answer to one part contradicts the premise of another part
- The question contains "and" or "also" connecting unrelated concerns
- User seems frustrated despite getting correct answers (because only one sub-problem is being addressed)

### Decomposition process

1. **Identify the threads**: Listen for distinct concern areas. Usually 2-3, rarely more.

2. **Name each thread explicitly**: "I'm hearing two separate things: A is about ___, B is about ___. Am I right?"

3. **Check for dependencies**: "Does solving A change how you'd approach B? Or are they independent?"

4. **Prioritize**: "Which one is more urgent / blocking the other / causing more pain right now?"

5. **Process sequentially**: Each sub-problem gets its own Route treatment. Present results separately with clear labels.

### Example decomposition

**User says**: "I need to launch our product next month but we don't have a landing page and I'm not sure about the pricing and our main competitor just released something similar"

**Decomposition**:
- **Thread A (Tactical)**: Landing page needed for launch — concrete deliverable with deadline
- **Thread B (Strategic)**: Pricing uncertainty — needs market analysis and decision
- **Thread C (Competitive)**: Competitor release — may affect positioning and messaging

**Dependencies**: B (pricing) affects A (landing page content). C (competitor) affects B (pricing positioning).

**Recommended order**: C → B → A (understand competitive landscape, then set pricing, then build landing page with correct messaging)

---

## 5. Depth Calibration Guide

How deep to dig based on question type and user signals.

### Depth 0: No digging needed
- Factual questions with clear context ("What's the Python syntax for list comprehension?")
- User explicitly says "I know what I want, just help me phrase it"
- Clear Gate passed

### Depth 1: Light probe (1 round)
- Question is clear but might be a Y instead of X
- Ask one "what's this for?" question, accept the answer
- Example: "How do I export to CSV?" → "What are you going to do with the CSV?" → [take answer and proceed]

### Depth 2: Standard dig (2 rounds)
- Moderate ambiguity, multiple possible interpretations
- Round 1: Offer candidates and gather context
- Round 2: Confirm understanding and check for missed angles
- Most questions land here

### Depth 3: Full exploration (3 rounds, maximum)
- Major ambiguity, life/career/architecture decisions
- Multiple signals triggering (vague + emotional + compound)
- Round 1: Broad exploration (what's happening, what triggered this)
- Round 2: Narrow to core problem (of everything we discussed, which matters most?)
- Round 3: Confirm understanding and framing before proceeding

### Signals to go deeper

| Signal | Depth adjustment |
|--------|-----------------|
| User corrects your guess | Stay at current depth, refine |
| User says "sort of" or "not exactly" | Go one level deeper |
| User adds significant new information in response | Go one level deeper |
| User says "yes, exactly" | Stop digging |
| User says "I guess" or "maybe" | Go one level deeper |
| User seems impatient | Stop, proceed with best understanding |
| User provides a long, detailed response | You probably have enough, stop |

### Signals to stop digging

- User confirms understanding ("yes, that's it")
- You've hit 3 rounds
- User shows impatience ("can we just get to the answer?")
- New information has stopped emerging (last two rounds yielded the same understanding)
- User explicitly says to stop ("just help me write it")
