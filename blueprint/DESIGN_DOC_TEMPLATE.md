# Design Document — <project name>

> **How to use this template.** Copy this file into your new project's repo as
> `DESIGN_DOC.md`, then fill it in with Claude in plan mode, section by section
> (see [LIFECYCLE.md](LIFECYCLE.md), Phase 1). Every section starts with a
> blockquote like this one explaining what it's for — delete the blockquotes as
> you fill in, or keep them as reminders. Nobody grades this document; its only
> job is to make you and Claude agree on what you're building before you build it.
>
> **Pick a tier before you start:**
>
> | Tier | Use it for | Fill in |
> |---|---|---|
> | **LIGHT** | A weekend automation, a script, a small tool with no users but you and no precious saved data | Sections marked LIGHT only (1, 2, 3, 4, 9, 10) |
> | **FULL** | Anything with users other than you, saved data you'd be upset to lose, or more than about 3 build phases | Everything |
>
> When unsure, start LIGHT — you can upgrade a section from one sentence to the
> full treatment any time.
>
> **This is a living document.** It is not a contract you write once; it is the
> map you keep correcting as the territory becomes clear. Claude updates the
> status line below at the end of every build phase, and moves deferred work to
> Section 10's Follow-on list. A design doc that disagrees with the code is
> worse than no design doc.

**Tier:** LIGHT / FULL
**Status:** Not started · *(Claude updates this each phase, e.g. "Phases 00–02 done; Phase 03 in progress")*
**Last updated:** YYYY-MM-DD

---

## 1. What & Why — *(LIGHT)*

> One paragraph: what is this, what problem does it solve, and for whom? Write
> it so a stranger would understand it. If you can't state the problem in two
> sentences, you are not ready to build — the most expensive bugs in software
> are built-the-wrong-thing bugs, and this paragraph is where you catch them.
> *(Engineering fundamental: problem framing — the problem statement every
> design course starts with.)*

<what this is and why it should exist>

## 2. Goals & Non-Goals — *(LIGHT)*

> Goals: 3–7 bullets that must be true when this is done. Non-goals: 3–7 things
> you are explicitly NOT doing. The non-goals list is the most valuable list in
> this document — it is your pre-written answer for every time you or Claude is
> tempted to add "just one more thing". Scope creep doesn't announce itself; it
> asks politely, one feature at a time.
> *(Fundamental: scope definition.)*

**Goals**
- <goal>

**Non-goals**
- <thing we are deliberately not doing, and won't feel bad about>

## 3. Users & Scenarios — *(LIGHT)*

> Who uses this, and what does a typical session look like, step by step? Write
> 2–4 short narrated walkthroughs: "I open the app, I see X, I click Y, Z
> happens." Include yourself-as-operator if you'll run or maintain it. These
> scenarios become your acceptance tests in Section 9 — every scenario written
> here must be checkable there.
> *(Fundamental: use cases / user stories — requirements elicitation.)*

**Scenario A — <name>**
<narrated walkthrough>

**Scenario B — <name>**
<narrated walkthrough>

## 4. Requirements — *(LIGHT)*

> Precisely what must the system do, and how well? Label each line MUST (v1
> fails without it), SHOULD (valuable, cuttable under pressure), or LATER
> (explicitly deferred — these seed Section 10's Follow-on list). Include
> quality requirements in plain words: "must not lose a saved game", "must run
> offline", "a full run must finish in under 5 minutes". Vague requirements
> produce vague software — "MUST validate content" is testable, "should be
> robust" is not.
> *(Fundamental: functional and non-functional requirements specification.)*

**MUST**
- <requirement>

**SHOULD**
- <requirement>

**LATER**
- <requirement>

## 5. Data Model — *(FULL; LIGHT projects: one sentence on what gets stored where)*

> Name every *thing* that exists in your system, what facts you keep about
> each, and how they relate. One row per entity. You do not need to know
> databases — Claude will pick the storage technology; what only YOU can do is
> name the nouns of your app and what matters about them. This table is the
> single most reused artifact in the whole document: screens display these
> entities, the API moves them, tests verify them.
> *(Fundamental: data modeling / entity–relationship design.)*

| Entity | Purpose | Key fields | Relates to |
|---|---|---|---|
| <Name> | <what it represents> | <the facts we keep> | <other entities and how> |

## 6. System Shape & Stack — *(FULL; LIGHT: one paragraph)*

> The 3–6 big parts of the system, how they talk to each other, and what
> technology each is built with — with the reason recorded. Ask Claude to
> propose a stack and justify it against Section 4's requirements, then write
> down both the choice AND the one-line reason (a mini decision record — future
> you will ask "why on earth did we pick this?", and this table answers).
> Prefer boring, popular technology: it is what Claude is best at and what the
> internet has answers for.
> *(Fundamental: software architecture + architecture decision records.)*

**Parts**
- <part> — <what it does, what it talks to>

**Stack decisions**

| Choice | Why (one line) |
|---|---|
| <technology> | <reason, tied to a requirement> |

## 7. Interfaces — *(FULL; LIGHT: skip, or one rough sketch)*

> Everything the user sees or touches (screens, pages, commands), and every
> surface machines touch (API routes, file formats, integrations). One line
> each. Be exhaustive rather than detailed: if a screen or endpoint is not
> listed here, Claude will invent it during the build — and you'll discover its
> design at review time instead of choosing it now.
> *(Fundamental: interface design / API contracts.)*

**Screens / commands**
- <screen> — <what's on it, what each control does>

**Machine surfaces (API routes, file formats, integrations)**
- <route or format> — <one line>

## 8. Risks & Open Questions — *(FULL; LIGHT: 2–3 bullets)*

> What could sink this project or hurt its users, and what don't you know yet?
> For each risk: what happens, how bad it is, and what you'll do about it.
> Two questions are mandatory: the data-loss question ("what happens if X is
> deleted, corrupted, or lost mid-operation?") and — if the app takes input
> from the outside world (email, web content, other people's text, anything an
> AI agent reads) — the abuse question ("what happens when the input is
> malicious?"). Every open question gets an owner: you, or "ask Claude to
> research".
> *(Fundamental: risk analysis / threat modeling.)*

**Risks**
- <risk> — <impact> — <mitigation>

**Open questions**
- <question> — <owner>

## 9. How We'll Know It Works — *(LIGHT)*

> Two lists. First: what Claude's automated tests must cover — at minimum one
> line per Section 4 MUST (if a MUST has no test, it is a hope, not a
> requirement). Second: your personal acceptance walkthrough — the Section 3
> scenarios rewritten as pass/fail steps you will perform yourself, by hand, in
> the running app. House rule, inherited from hard experience: **passing tests
> are not enough; you must see the actual app work with your own eyes.**
> Details of how to run this at release time live in
> [QA_CHECKLIST.md](QA_CHECKLIST.md).
> *(Fundamental: testing strategy — verification and validation, with
> traceability from requirements to tests.)*

**Automated tests must cover**
- <MUST from Section 4> → <what the test proves>

**My acceptance walkthrough (by hand, in the running app)**
1. <step> — pass if <observable result>

## 10. Build Phases & Follow-On — *(LIGHT)*

> The build order, as numbered phases (00, 01, 02…). The rule that keeps
> morale and momentum: **every phase ends in something you can run and see
> working** — never two "invisible plumbing" phases in a row. Claude tags every
> commit with its phase (`feat(saves): autosave slots (Phase 03)`), so the git
> history reads as progress against this list. When something gets cut or
> deferred mid-build, it moves to Follow-on — guiltlessly. Follow-on is not a
> graveyard; it is Section 4's LATER bucket plus everything reality taught you
> to postpone.
> *(Fundamental: incremental / iterative delivery — milestone planning.)*

| Phase | Delivers (visible when done) |
|---|---|
| 00 | <smallest thing that runs> |
| 01 | <next visible increment> |

**Follow-on (not yet built)**
- <deferred item>
