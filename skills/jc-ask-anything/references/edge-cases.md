# Edge Cases: Complete Dialogue Examples

Full conversation flows for every edge case the skill handles. These are reference dialogues — adapt tone and specifics to each real situation.

---

## Table of Contents

1. [One-Sentence Input](#1-one-sentence-input)
2. [Wall of Text (500+ chars)](#2-wall-of-text)
3. [Emotional User](#3-emotional-user)
4. [User Doesn't Know What to Ask](#4-user-doesnt-know-what-to-ask)
5. [Complete Beginner](#5-complete-beginner)
6. [Multiple Tangled Questions](#6-multiple-tangled-questions)
7. [Wrong Assumption](#7-wrong-assumption)
8. [Venting, Not Asking](#8-venting-not-asking)
9. [Asking a Superior / Authority](#9-asking-a-superior)
10. [Sensitive Information](#10-sensitive-information)
11. [User Goes Silent](#11-user-goes-silent)
12. [Already Clear (Clear Gate)](#12-already-clear)

---

## 1. One-Sentence Input

**Scenario**: User drops a minimal question with no context.

**User**: "How do I get more followers?"

**Skill** (Parse — offer candidates):
"'Get more followers' can mean a lot of things. Which of these is closest to your situation:

A. You're building a personal brand / content creator account and growth is slow
B. You're running a business account and need followers for credibility or sales
C. You have a specific platform in mind (X, Instagram, TikTok, LinkedIn...)
D. Something else?"

**User**: "A, I'm posting on X about AI tools but barely growing after 2 months"

**Skill** (more context needed):
"Got it. Two quick things:
- How often are you posting, and what kind of content (threads, short takes, screenshots)?
- What's your follower count now, and what's your target?"

**User**: "Daily short takes, around 200 followers, want to hit 1000"

**Skill** (Route: AI can help):
"This is something I can help with directly — content strategy for X growth is well-documented territory. Let me give you specific tactics..."

---

## 2. Wall of Text

**Scenario**: User dumps a massive, unstructured paragraph.

**User**: "So basically I've been trying to build this app for my friend's restaurant, it's supposed to let customers order from their table by scanning a QR code, I started with React Native but then someone told me Flutter is better for this, so I switched halfway through and now I have half the code in React Native and half in Flutter, and also the backend is a mess because I started with Firebase but then realized I need a proper database for the menu items and order tracking, so I'm trying to migrate to Supabase but the auth is different and I can't figure out how to keep the existing users, also my friend wants it done by next month because they're having a grand opening, and I'm doing this for free because they're my friend but it's turning into way more work than I expected and I'm not sure if I should just start over or try to salvage what I have..."

**Skill** (compress and confirm):
"Let me make sure I've got the core of this right:

You're building a QR-code table ordering app for a friend's restaurant, deadline next month (grand opening). You're stuck because:
1. **Framework split**: Half React Native, half Flutter, need to pick one
2. **Backend migration**: Moving Firebase → Supabase, stuck on auth/user migration
3. **Scope creep**: The project grew beyond what you expected as a free favor

Is that the situation? And which of these three is the most urgent blocker right now?"

**User**: "Yeah exactly. The framework thing I think — I need to just pick one and go."

**Skill** (Dig — checking for XY):
"Makes sense. Before you pick: the app is for scanning a QR code at a table and ordering food, right? Does it need to be a native app at all, or could a mobile-responsive web app work? Web means no app store, no install — customer just scans and it loads. Might simplify things a lot given your timeline."

---

## 3. Emotional User

**Scenario**: User is frustrated or upset, emotions are foregrounded.

**User**: "I'm so sick of this. I've been applying to jobs for 4 months and I haven't even gotten a single interview. I have a CS degree, I've done projects, I've tailored every resume. What am I doing wrong? Is it just hopeless?"

**Skill** (validate, then steer):
"4 months with zero callbacks despite real effort — that's genuinely demoralizing, I get it.

Let me help you figure out where the gap might be. A few things that could narrow it down:
- What types of roles are you applying to? (junior dev, specific stack, specific industry?)
- How are you finding the openings? (job boards, referrals, company pages, LinkedIn?)
- Would you be comfortable sharing your resume format? (not content, just structure — one page? Two? What sections?)"

**Key principles in action**:
- Validate once, specifically ("4 months with zero callbacks" — mirrors their experience)
- Don't over-empathize or turn into a therapist
- Immediately offer structured next steps
- Questions are specific and actionable, not "tell me more about your feelings"

---

## 4. User Doesn't Know What to Ask

**Scenario**: User can't even articulate a question.

**User**: "I don't even know where to start. Everything about my freelance business feels like it's falling apart but I can't point to one thing."

**Skill** (start from scene):
"That 'everything feels wrong but nothing specific' feeling is real — it usually means several small things are compounding. Let me help you untangle it.

What does a typical work week look like for you right now? Walk me through it — what takes up your time, what stresses you out, what's not working the way it used to?"

**User**: "I spend half my time chasing invoices, the other half on client calls that go nowhere. My actual design work happens at night when I'm exhausted. And I took on two clients I should have said no to."

**Skill** (structure the chaos):
"Now I can see three distinct issues:

1. **Cash flow / admin overhead**: Chasing invoices is eating productive time
2. **Sales inefficiency**: Client calls that don't convert — either wrong leads or no qualification process
3. **Boundary problem**: Took on bad-fit clients, can't say no

Which one, if you fixed it first, would make the other two easier to deal with?"

---

## 5. Complete Beginner

**Scenario**: User lacks vocabulary to describe their problem.

**User**: "My computer is doing the thing where it goes really slow when I open too many things and sometimes the spinning wheel comes up and I have to wait forever"

**Skill** (translate + supply vocabulary):
"Sounds like you're running low on memory (RAM) — that's what causes the slowdown and the spinning wheel (called 'beachball' on Mac or 'loading cursor' on Windows).

Quick check to narrow it down:
- Are you on a Mac or Windows?
- When you say 'too many things', roughly how many apps or browser tabs do you have open?
- Does it happen with specific apps, or any combination of apps?"

**Key principles in action**:
- Give them the word for what they're describing ("RAM", "beachball")
- Don't condescend — just naturally introduce the vocabulary
- Offer simple, concrete questions (not "describe your system specs")

---

## 6. Multiple Tangled Questions

**Scenario**: User's one question is actually three problems intertwined.

**User**: "I want to redesign our company website. The current design is outdated, we're not ranking on Google, and our conversion rate is terrible. Where do I even start?"

**Skill** (decompose):
"This is actually three different problems wearing a trenchcoat:

1. **Visual design**: The look/feel is outdated → needs a redesign
2. **SEO**: Not ranking on Google → needs technical and content optimization
3. **Conversion**: Low conversion rate → needs UX and copy changes

Here's the thing — they're related but the solutions are different, and the order matters:

I'd suggest: **SEO audit first** (understand what's working before you break it with a redesign), then **conversion analysis** (figure out what to fix in the user flow), then **visual redesign** (informed by what you learned).

Want to start with one of these? Or does a different order make more sense for your situation?"

---

## 7. Wrong Assumption

**Scenario**: User's question is built on a false premise.

**User**: "Since GPT-4 can only handle 8,000 tokens, how do I split my 50-page document to fit?"

**Skill** (correct gently, then help):
"Quick correction that'll save you a lot of work — GPT-4's context window is actually much larger now. The latest models handle 128k tokens, which is roughly 300+ pages. Your 50-page document should fit in a single call.

So the splitting problem might not exist. But let me check: what are you trying to do with this document? If it's summarization or Q&A, there might be a better approach than feeding the whole thing at once anyway."

**Key principles in action**:
- Correct the factual error immediately and clearly
- Don't dwell on the mistake or make them feel bad
- Pivot to the real question (what are you actually trying to do?)

---

## 8. Venting, Not Asking

**Scenario**: User is releasing frustration, not seeking a solution.

**User**: "Our PM keeps changing requirements every sprint. Last week I rewrote the same feature THREE times. Then in the review he said it wasn't what he wanted. I spent 15 hours on something that got thrown away. I seriously can't take this anymore."

**Skill** (acknowledge, then check intent):
"Three rewrites of the same feature and 15 wasted hours — that's objectively dysfunctional, not just frustrating.

Real question: are you looking to actually fix this (like, figure out how to push back on scope changes), or do you just need to vent right now? Both are totally valid."

**If user wants to vent**: "Go for it. When you're ready to problem-solve, I'm here."

**If user wants to fix it**: "OK, let's figure out how to stop the rewrite cycle. A few things that usually help..."

---

## 9. Asking a Superior

**Scenario**: User needs to ask someone in a position of power.

**User**: "I need to ask my director if I can work remote 3 days a week instead of the current 2."

**Skill** (Parse):
"Got it. Let me help you set this up. A few things:
- What's your relationship with the director? (Close, formal, barely interact?)
- Is there a company policy on remote work, or is it manager discretion?
- Do you have a specific reason? (Commute, productivity, childcare, etc.)
- Has anyone else on your team successfully negotiated this?"

**User**: "Pretty formal. No official policy, team-by-team basis. My commute is 90 minutes each way. One teammate does 3 days remote already."

**Skill** (Compress — authority-adapted):

"Here's how I'd frame it:

---
'Hi [Director], I wanted to discuss my work schedule. I'm currently remote 2 days/week and I'd like to explore moving to 3.

My main reason: the 3-hour daily commute on office days is cutting into my productive hours. On my remote days I consistently start earlier and output more — [cite specific example if you have one].

I know [teammate] is already on a 3-day remote schedule, so there's precedent on our team. I'd propose a trial month to make sure there's no impact on collaboration.

What are your thoughts?'
---

A few things built into this:
- **Led with the business case** (productivity), not personal preference
- **Cited precedent** (teammate already does it)
- **Proposed a trial** (lowers the perceived risk for the director)
- **Ended with an open question**, not a yes/no demand"

**Anticipate**:
- "What about the days we have team meetings?" → Check the meeting schedule in advance, offer to always be in-office on meeting days
- "How will I know you're actually working?" → Suggest a check-in routine or output-based accountability

---

## 10. Sensitive Information

**Scenario**: User's question context includes credentials or private data.

**User**: "I'm trying to connect to our production database but it's not working. Here's my connection string: `postgresql://admin:Sup3rS3cret!@prod-db.company.com:5432/maindb`"

**Skill**:
"⚠️ Heads up — you just shared what looks like a production database password (`Sup3rS3cret!`) and server address. If you're going to post this question anywhere, **change that password first** and redact the hostname.

Now let me help with the connection issue. What error are you getting when you try to connect? And are you connecting from your local machine, a server, or a CI/CD pipeline?"

**Key principles**:
- Flag the sensitive data immediately, before anything else
- Be specific about what's sensitive (don't just say "careful with credentials")
- In any compressed output, auto-replace with placeholders: `postgresql://[user]:[password]@[host]:5432/[database]`
- Then continue helping normally

---

## 11. User Goes Silent

**Scenario**: Skill asked a follow-up question and user hasn't responded.

**After 1 unanswered follow-up, output the best possible result with available information**:

"No worries — based on what you've told me so far, here's my best take:

[Compressed question / answer / recommendation based on available info]

This might not be perfect since I didn't get to clarify [specific missing piece]. If you come back to this later, just let me know [what was missing] and I can refine it."

**Key principles**:
- Don't send multiple follow-ups (nagging)
- Output the best version possible with what you have
- Clearly state what's missing so user can easily fill the gap later
- Don't take it personally or assume the user is rude — mobile users, busy people, got distracted

---

## 12. Already Clear (Clear Gate)

**Scenario**: User's question is already well-formed.

**User**: "I'm running Django 4.2 on Python 3.11. After upgrading from 4.1, my custom middleware that modifies response headers stopped working. The middleware's `process_response` method is never called. I checked `MIDDLEWARE` settings — it's listed, order looks correct. Other middleware (CORS, auth) still works. No errors in logs. What changed in Django 4.2's middleware handling that could cause this?"

**Skill**:
"Your question is already clear — it has the goal (fix middleware), exact versions, specific symptom (process_response not called), what you've checked (settings, order, other middleware works), and a focused ask (what changed in 4.2).

Go ahead and post this as-is. The only thing you might add is whether you're using `MiddlewareMixin` or the new-style async middleware — Django 4.2 made changes to async middleware handling that could explain this."

**Key principles**:
- Confirm it's clear — this is a compliment on their question quality, not a dismissal
- Don't try to optimize what's already good
- If you happen to know the answer, offer it as a bonus (but it's not the skill's job)
- No Teach section — nothing to teach here
