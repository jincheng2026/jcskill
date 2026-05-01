# Worked Examples

8 complete examples showing the full skill flow from input to output, covering diverse scenarios.

---

## Table of Contents

1. [XY Problem (Technical)](#example-1-xy-problem-technical)
2. [Too Vague → Narrowed](#example-2-too-vague--narrowed)
3. [Must Ask a Human (Workplace)](#example-3-must-ask-a-human-workplace)
4. [Clear Gate Pass](#example-4-clear-gate-pass)
5. [Hot Start (Context Inheritance)](#example-5-hot-start-context-inheritance)
6. [AI Tries First → Falls Back to Human](#example-6-ai-tries-first--falls-back-to-human)
7. [Compound Problem Decomposition](#example-7-compound-problem-decomposition)
8. [Emotional User → Structured Resolution](#example-8-emotional-user--structured-resolution)

---

## Example 1: XY Problem (Technical)

**User input**: "How do I configure Nginx reverse proxy to forward WebSocket?"

**Clear Gate**: Fail — asks about a specific solution, possible XY problem. → Parse

**Parse**:
- Goal: unclear (claims Nginx config, but why?)
- Symptom: not stated
- Tried: not stated

**Dig** (signal: user asks about specific solution, not problem):

> **Skill**: "I can help with Nginx WebSocket config. Just to make sure I give you the most useful answer — what's this for? I'm guessing one of these:
> A. You're deploying a real-time app (chat, collab) to production
> B. Your local dev server's hot reload isn't connecting
> C. Something else?"
>
> **User**: "B — my Vite dev server hot reload won't connect through my local proxy"

**Route**: AI solves — this is a dev environment config issue, not a production Nginx question.

**Output**: Provides Vite devServer proxy configuration. Explains that Nginx is overkill for local dev — Vite has built-in proxy support:
```javascript
// vite.config.js
export default {
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        ws: true  // this enables WebSocket proxying
      }
    }
  }
}
```

**Teach**:
```
---
Reflecting on your question:

Original: "How do I configure Nginx reverse proxy to forward WebSocket?"
Gap: Asked about a solution (Nginx) instead of the problem (local dev hot reload broken). Nginx is for production; Vite handles this natively for dev.
Improved: "Vite dev server hot reload WebSocket not connecting through local proxy — how to configure?"
Next time, try: Say what's broken + what tool/context you're in, not the fix you're attempting.
---
```

---

## Example 2: Too Vague → Narrowed

**User input**: "How do I learn AI?"

**Clear Gate**: Fail — no goal, no blocker, no context. → Parse

**Parse** (offering candidates):

> **Skill**: "That's a huge space — let me narrow it down. Which is closest to your situation:
> A. Need AI for work right now — boss wants you to start using it
> B. Considering a career pivot into AI/ML engineering
> C. Running a business and want to use AI to save time or make money
> D. Just curious about the landscape?"
>
> **User**: "A — I'm in marketing, boss wants everyone using AI tools by next quarter"
>
> **Skill**: "Got it. Two more things:
> - What's your main daily work? (Writing copy, data analysis, campaign management, social media, other?)
> - Have you tried any AI tools? Even once — ChatGPT, Midjourney, anything?"
>
> **User**: "Mostly writing — ad copy and email campaigns. Tried ChatGPT a few times but everything it writes sounds robotic and generic"

**Dig**: Skip — problem is now specific: marketer needs AI for copywriting, tried ChatGPT, dissatisfied with output quality.

**Route**: AI solves — prompt engineering for natural copy is well-documented.

**Output**: Provides 3 specific techniques for getting human-sounding copy from AI (persona seeding, example-based few-shot, iterative refinement), with before/after examples using ad copy.

**Teach**: Skip — AI solved directly, question was clear after Parse.

---

## Example 3: Must Ask a Human (Workplace)

**User input**: "I want to ask my boss if I can transfer to the product team"

**Clear Gate**: Fail — goal is clear, but no context. → Parse

**Parse**:

> **Skill**: "Internal transfers can be delicate. Let me help you set it up:
> - What team are you on now, and how long?
> - Why product? (Frustrated with current role / genuinely interested / career growth / other?)
> - How's your relationship with your boss? Ever discussed career direction?"
>
> **User**: "Dev team, 2 years. Always interested in product — I've done user research on my own time. Good relationship, but never brought this up."

**Dig**: Skip — clear, specific, sufficient context.

**Route**: Must ask human — requires another person's decision and action.

**Compress** (context: face-to-face or message to direct manager):

```
"Hey [boss], I wanted to talk about something career-related.

I've been on the dev team for two years and the work's been going well. Alongside that, I've been consistently drawn to the product side — I've been doing user research on my own and studying product thinking.

I wanted to ask: is there a path to transfer to the product team? I'd love to grow in that direction, and I'd really value your perspective on whether that makes sense and what steps would be involved."
```

**Anticipate**:
1. "What about your current projects?" → Have a handoff plan ready. Know your sprint commitments and who could pick up your work
2. "What do you know about product?" → Prepare your self-directed user research as concrete evidence
3. "Why not stay in dev?" → Be honest about pull (interest in product), not push (dissatisfaction with dev)

**Teach**:
```
---
Original: "I want to ask my boss if I can transfer to the product team"
Gap: Missing the 'why you' evidence — tenure, demonstrated interest, self-directed learning — that makes the ask credible
Improved: Shows track record + genuine interest + homework done + asks for guidance (not just permission)
Next time, try: [Your ask] + [evidence you're serious] + [open question inviting their input]
---
```

---

## Example 4: Clear Gate Pass

**User input**: "MacOS Ventura upgrade broke Homebrew — getting 'Error: Cannot install in Homebrew on ARM processor in Intel default prefix'. Reinstalled Homebrew to /opt/homebrew, added `eval $(/opt/homebrew/bin/brew shellenv)` to .zshrc, PATH still not picking it up. Other CLI tools work fine."

**Clear Gate**: Pass
- Goal: clear (fix Homebrew path after OS upgrade)
- Blocker: specific (PATH change not taking effect despite correct .zshrc config)
- Context: complete (OS version, exact error, what was tried, what works vs doesn't)

**Output**:
"Your question is already well-formed — goal, blocker, and context are all there. Go ahead and post it as-is.

Since you're here: did you open a new terminal window after editing .zshrc? Or run `source ~/.zshrc`? The change requires a new shell session. Also check if your default shell is actually zsh (`echo $SHELL`) — sometimes upgrades reset it to bash."

**Teach**: Skip — Clear Gate passed.

---

## Example 5: Hot Start (Context Inheritance)

**Prior conversation context**: User has been debugging a React app for 20 messages. The app renders blank after deploying to Vercel. AI suggested checking environment variables, build logs, and console errors. User tried all three — env vars are set, build succeeds, console shows `TypeError: Cannot read properties of undefined (reading 'map')` on the data fetching component.

**User invokes skill**: "Help me ask about this in the Next.js Discord"

**Hot start extraction** (from context):
- Goal: Fix blank page after Vercel deploy
- Symptom: TypeError on `.map()` — data fetching returns undefined in production
- Tried: Checked env vars (set correctly), build logs (clean), found console error
- Environment: Next.js on Vercel, data fetching component
- Why AI didn't solve it: Likely a runtime environment difference between local and Vercel

**Skill** (enough context, skip Dig, go to Compress):

"I've got enough from our conversation to write this up. Here's a question for the Next.js Discord:

```
Blank page after Vercel deploy — data fetching returns undefined in production only

My Next.js app works locally but shows a blank page on Vercel. Console error:
`TypeError: Cannot read properties of undefined (reading 'map')`

This is in my data fetching component — the API response is `undefined` in production but works fine locally.

What I've checked:
- Environment variables: set in Vercel dashboard, matching local .env
- Build logs: clean, no errors
- Same code, same branch — only difference is the runtime environment

Suspecting it's a server-side vs client-side data fetching issue in production. Has anyone seen this pattern?
```

They'll probably ask:
1. 'Are you using `getServerSideProps` or `useEffect` for data fetching?' → Check your component and be ready to share the relevant code
2. 'What API are you calling? Is it accessible from Vercel's servers?' → Test the API URL from an external source to rule out network issues"

**Teach**: Skip — question was clear from context, just needed formatting for Discord.

---

## Example 6: AI Tries First → Falls Back to Human

**User input**: "What's the best way to structure equity for a 3-person startup where one founder is full-time, one is part-time, and one is just contributing IP?"

**Clear Gate**: Fail — goal is clear but context-dependent (no one-size answer). → Parse

**Parse**:

> **Skill**: "Equity splits depend heavily on context. Quick questions:
> - What stage? (Pre-revenue idea, prototype, or already generating income?)
> - What's the IP? (Patent, codebase, domain expertise, client relationships?)
> - How long has the part-time person committed to staying part-time?"
>
> **User**: "Pre-revenue, have a working prototype. IP is a proprietary algorithm one founder developed at a previous job (they own it, confirmed). Part-time person plans to go full-time in 6 months."

**Route**: AI tries first — there are general frameworks for this, but the IP and transition timeline make it nuanced.

**AI attempt**: Provides a general framework (dynamic equity split / Slicing Pie model, vesting schedules, IP assignment considerations). Explains the 3 common approaches with pros/cons.

> **Skill**: "Here's a general framework based on your situation: [detailed breakdown]. Does this give you enough to work with?"
>
> **User**: "This is helpful for the general structure, but I'm worried about the IP valuation part — how do you value an algorithm that hasn't generated revenue yet?"

**Falls back to human**:

> **Skill**: "That's a fair concern — IP valuation pre-revenue is genuinely subjective and has legal implications. This is one where you should talk to a startup lawyer. Let me help you frame that conversation:
>
> ```
> I need help structuring equity for a 3-person startup:
> - Founder A: Full-time, building the product
> - Founder B: Part-time now, going full-time in ~6 months
> - Founder C: Contributing a proprietary algorithm they own from previous work
>
> We're pre-revenue with a working prototype. The core question: how do we value Founder C's IP contribution relative to A and B's time contributions, given the algorithm hasn't generated revenue yet?
>
> We've looked at dynamic equity models (Slicing Pie) and standard vesting, but the IP component doesn't fit neatly into either. Looking for guidance on:
> 1. How to value pre-revenue IP for equity purposes
> 2. How to structure the IP assignment agreement
> 3. What protections each founder should have
> ```
>
> I'd recommend a startup-focused attorney, not a general business lawyer — this is specialized enough that it matters."

**Teach**:
```
---
Original: "What's the best way to structure equity for a 3-person startup..."
Gap: The question was reasonable, but "best way" implied a single answer exists — equity splits are negotiation + legal, not optimization
Improved: Separated the general framework (AI can help) from the specific IP valuation (needs a lawyer), and framed each appropriately
Next time, try: For questions with both general and specialized parts, expect them to be split — AI handles the framework, experts handle the edge cases
---
```

---

## Example 7: Compound Problem Decomposition

**User input**: "I need to launch our SaaS by end of month but we don't have documentation, the onboarding flow is broken, and I'm not sure our pricing is right"

**Clear Gate**: Fail — multiple problems tangled. → Parse

**Parse** (compress and decompose):

> **Skill**: "I'm hearing three separate problems with a shared deadline:
>
> 1. **Documentation gap**: No docs for launch
> 2. **Broken onboarding**: The first-run experience has issues
> 3. **Pricing uncertainty**: Not confident in the pricing model
>
> These are related but need different solutions. Quick check: is the end-of-month deadline hard (investor demo? public launch?) or soft (self-imposed)?
>
> And which one, if not fixed, would actually block the launch?"

**User**: "Hard deadline — we promised beta users. Onboarding is the real blocker. Pricing we could adjust later. Docs we could do minimal."

**Skill** (prioritized decomposition):

"OK, so the real priority order is:

1. **Onboarding (blocker)** — what specifically is broken?
2. **Minimal docs (launch requirement)** — what's the minimum viable documentation?
3. **Pricing (can iterate)** — park this for post-launch

Let's focus on #1. What's the onboarding flow supposed to do, and where does it break?"

Each sub-problem then gets its own Route treatment: onboarding bug → AI solves; minimal docs → AI helps draft; pricing → parked for later conversation.

---

## Example 8: Emotional User → Structured Resolution

**User input**: "I just got rejected from my dream company after 5 rounds of interviews. 5 ROUNDS. Two months of prep. I even got positive feedback from every interviewer. Then a generic rejection email. I don't understand what happened and I don't know if I should even keep trying."

**Clear Gate**: Fail — emotional, needs unpacking. → Parse

**Parse** (validate, then structure):

> **Skill**: "5 rounds and positive signals, then a form rejection — that's genuinely disorienting. The gap between the feedback you got and the outcome doesn't make sense, and that's the worst kind of rejection.
>
> I want to help, but first — what would be most useful right now:
> A. Figure out what might have actually happened (understand the rejection)
> B. Decide whether and how to follow up with the company
> C. Reset your strategy for other applications
> D. You just needed to say this out loud and that's fine too"

**User**: "B — I want to follow up but I don't want to seem desperate"

**Skill** (Route: must ask human — this is communication with a specific person):

**Compress** (context: email to recruiter/hiring manager):

```
Subject: Following up on [Role] — feedback request

Hi [Recruiter/Hiring Manager],

Thank you for the opportunity to interview for [Role]. I enjoyed the conversations with the team, especially [specific topic/person if memorable].

I was surprised by the outcome given the positive feedback during the process. I completely respect the decision — but if there's any specific feedback on where I fell short, I'd genuinely appreciate it. It would help me improve for future opportunities.

I remain very interested in [Company] and would welcome the chance to be considered for future roles that might be a better fit.

Best,
[Name]
```

> **Skill**: "This email does three things:
> - Shows maturity (no resentment, respects the decision)
> - Asks for actionable feedback (gives them permission to be specific)
> - Keeps the door open (many people get hired on second attempts)
>
> They might ask: 'What role would you be interested in?' → Have a clear answer ready based on what you learned during the interview process."

**Teach**:
```
---
Original: "I don't understand what happened and I don't know if I should keep trying"
Gap: Two questions tangled — "what happened" (need to ask the company) and "should I keep trying" (personal decision, not for this email)
Improved: Separated the actionable ask (feedback request to company) from the internal decision (which you can make after getting feedback)
Next time, try: When rejection stings, separate "understand this specific outcome" from "rethink my whole strategy" — handle them sequentially, not simultaneously
---
```
