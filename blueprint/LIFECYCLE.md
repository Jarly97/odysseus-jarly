# The Development Lifecycle

How to take a project from idea to released, maintained software — the way
engineering schools teach it, executed the way you actually work: you direct,
Claude Code builds. Each phase below gives you the classical principle (so you
know *why*), the exact Claude Code moves (so you know *what to type*), and the
exit criteria (so you know *when you're done*).

Read this once, start to finish. After that, the cheat sheet is usually all
you need.

## Cheat sheet

| Phase | You say to Claude | You get out | Done when |
|---|---|---|---|
| 0. Idea → Brief | "Interview me about this idea" (plan mode) | A one-paragraph brief | You can state problem, user, and 3 MUSTs out loud |
| 1. Design | "Fill in DESIGN_DOC.md with me, section by section" | A filled design doc | Adversarial review done; you understand every sentence |
| 2. Setup | "Set up the project: git, uv, tests, run command" | A repo skeleton that runs | App starts, tests green, CLAUDE.md filled in |
| 3. Phased Build | "Plan Phase NN only" → build → "run it and show me" → `/code-review` | Working software, one phase at a time | Each phase: seen working, reviewed, docs updated, committed |
| 4. QA Hardening | Run [QA_CHECKLIST.md](QA_CHECKLIST.md) top to bottom | A checked, honest quality picture | All green, or every red consciously accepted in writing |
| 5. Release | "Tag v0.1, write release notes, prove a fresh install works" | A named, restorable version | Tag exists; fresh install works; you can get back to it |
| 6. Maintain | Bugs: "write a failing test first". Features: new phase in the design doc | Software that stays alive | Never — that's the point |

---

## Phase 0 — Idea → Brief *(about 30 minutes)*

**The principle.** Separate the problem from the solution. Ideas arrive as
solutions ("an app that does X") but hide the actual problem, and the cheapest
moment to discover you're solving the wrong problem is before anything exists.
Engineers call this the cost-of-change curve: a wrong assumption costs a
sentence to fix today, a rewrite to fix in three weeks.

**The Claude Code moves.**

1. Before opening Claude, write 5–10 sentences yourself, unaided: what
   problem, whose problem, and what "working" would look like. If this is
   hard, that's the finding — sit with it.
2. Then, in a new Claude Code session:

   ```
   Enter plan mode. Here's my idea: <paste your sentences>.
   Interview me — ask the questions a software architect would ask before
   designing this. One or two at a time. Don't design anything yet.
   ```

3. Answer honestly, including "I don't know". End by asking Claude to write
   the brief back to you in one paragraph, and correct it until it's yours.

**Done when** you can state, out loud and without notes: the problem, the
user, and three MUST-requirements.

## Phase 1 — Design *(the design doc)*

**The principle.** Requirements and architecture before code — the one lesson
of waterfall that survived. But corrected by everything learned since: the
design doc is a living map you keep updating, not a frozen contract. Its job
is to make disagreements between you and Claude visible while they're still
cheap words instead of expensive code.

**The Claude Code moves.**

1. Copy [DESIGN_DOC_TEMPLATE.md](DESIGN_DOC_TEMPLATE.md) into the new
   project's repo as `DESIGN_DOC.md` and pick a tier (LIGHT or FULL — the rule
   is in the template's header).
2. Fill it in together:

   ```
   Enter plan mode. Read DESIGN_DOC.md. Fill it in with me section by
   section for tier <LIGHT/FULL>, using our brief: <paste Phase 0 brief>.
   Ask me before assuming anything; where you must assume, mark it [ASSUMED].
   ```

3. **The adversarial design review.** In a *fresh* session (fresh matters —
   the session that wrote the doc is invested in it):

   ```
   Read DESIGN_DOC.md as a skeptical senior engineer reviewing a stranger's
   design. List the 5 biggest holes, unstated assumptions, and decisions that
   will be expensive to change later. Don't fix anything; just list them.
   ```

   Fix the doc, not the reviewer's feelings. Repeat once if round one found
   real holes.
4. Check Section 10: is Phase 01 small enough to build in one sitting? If
   not, split it.

**Done when** every tier-applicable section is filled; the adversarial review
ran and its findings are addressed or consciously rejected; and you personally
understand every sentence in the doc. House rule: if you can't explain a
section, make Claude re-explain it until you can — it is *your* blueprint, and
"Claude understands it" is not the same as "I understand it".

## Phase 2 — Project Setup *(one session)*

**The principle.** Version control, environment management, and automation are
the safety rails that make iteration cheap. Git means no change is ever
irreversible; a deterministic environment means "it worked yesterday" stops
being a mystery; a test runner wired up on day one means tests get written
alongside code instead of never.

**The Claude Code moves.**

1. In the new project:

   ```
   Set up this project per DESIGN_DOC.md Section 6:
   - init a git repository with a sensible .gitignore
   - for Python: set up the project with uv (uv init; dependencies via
     uv add so they're recorded in pyproject.toml and locked in uv.lock)
   - for a web/JS project: npm with a package.json, the same idea
   - a single documented command that runs the app
   - a test runner with one trivial passing test
   Then run the app once and show me it starts.
   ```

   **Why uv, specifically (Python projects):** uv (from Astral) replaces the
   pip + venv juggling act with one tool and one command shape — `uv run
   <anything>` always executes inside the right, locked environment. That
   determinism is worth more to you than to a professional: it deletes the
   entire "wrong environment / missing package / works on my machine" class of
   debugging sessions, and Claude never has to guess which Python is active.
   Existing pip-based projects (Odysseus itself, for instance) don't need
   retrofitting; this rule is for *new* projects.
2. Copy in the kit files: [CLAUDE_MD_TEMPLATE.md](CLAUDE_MD_TEMPLATE.md) as
   `CLAUDE.md` (fill in its blanks — this is what makes Claude follow this
   whole system unprompted), [QA_CHECKLIST.md](QA_CHECKLIST.md) as is, and
   [QA_LEDGER_TEMPLATE.md](QA_LEDGER_TEMPLATE.md) as `QA_LEDGER.md`.
3. Optional but recommended for FULL-tier projects — continuous integration,
   so tests run automatically on every push:

   ```
   Set up a GitHub Actions workflow that runs the test suite on every push.
   Model it on odysseus-jarly/.github/workflows/tests.yml.
   ```

**Done when** `git log` shows an initial conventional commit; the app skeleton
starts; the test suite runs green; `CLAUDE.md` is filled in.

## Phase 3 — Phased Build *(the loop you'll live in)*

**The principle.** Small batches, always-working software, review before
merge. Code review is the quality practice with the strongest evidence base in
all of software engineering, and incremental delivery is why: small diffs get
real reviews, big diffs get rubber stamps. You can't review code yourself —
so you review *behavior* (step 3) and delegate the code review to a fresh
Claude (step 4).

**The Claude Code moves — the per-phase ritual.**

1. **Plan.**

   ```
   Enter plan mode. Read DESIGN_DOC.md. Plan Phase NN only — nothing from
   later phases. Flag anything in the design that you now believe is wrong
   or underspecified.
   ```

   Read the plan. Approve it only when you understand what will exist
   afterward.
2. **Build.** One branch per phase (`claude/<slug>`), Conventional Commits
   with the phase marker — `feat(engine): quality gating (Phase 01)` —
   several small commits, not one blob. (Your `CLAUDE.md` makes this
   automatic.)
3. **See it work.** Non-negotiable:

   ```
   Run the app and walk me through what Phase NN added, step by step.
   ```

   For anything visual, get a screenshot. Type-checks and unit tests are not
   enough; the standard is *you watched it work*.
4. **Review.** Run `/code-review`. Have Claude fix confirmed findings before
   anything merges.
5. **Update the paper.**

   ```
   Update DESIGN_DOC.md: mark Phase NN done in the status header; move
   anything we deferred to Follow-on. If the review found a recurring kind
   of mistake, add a QA_LEDGER.md entry per its template.
   ```

6. **Merge to main. Next phase.**

**When a phase blows up** (wildly bigger than planned, or the plan turns out
wrong): stop, split it into NN-a and NN-b in the design doc, finish the small
half. Never grind through a phase that has stopped matching its plan — that's
how always-working software becomes weeks-of-broken software.

**The scope rule.** When Claude offers to "also improve" something outside the
phase, the answer is Follow-on. Section 2's non-goals list and Section 10's
Follow-on list exist precisely so that saying "not now" costs one line.

**Done when, per phase:** plan approved → built → seen working with your own
eyes → code-reviewed → design doc and ledger updated → merged.

## Phase 4 — QA Hardening *(before any release, or before anyone else uses it)*

**The principle.** Verification asks "did we build it right?" (does it meet
the spec); validation asks "did we build the right thing?" (does it actually
serve the user). You, the non-coder, can fully *own* validation — you're the
user — and you can *direct* verification by making Claude prove coverage
rather than assert it.

**The Claude Code moves.** Run [QA_CHECKLIST.md](QA_CHECKLIST.md) top to
bottom. It covers: the behavioral pass (you, hands on keyboard, trying to
break it), the adversarial Claude-vs-Claude review, the three-question
coverage interview, the ledger recurrence check, and release hygiene. Every
item is either something you do or an exact prompt to paste.

**Done when** every checklist item is green, or every red one is consciously
accepted *in writing* (the checklist's footer explains this rule), and a
`QA_LEDGER.md` entry exists for the QA run.

## Phase 5 — Release

**The principle.** A release is a *named, restorable state* — not "whatever
main is today". Naming it (a version tag) lets you talk about it; being able
to restore it means the next round of changes can't destroy the last good
version.

**The Claude Code moves.**

1. ```
   Tag this as v0.1 and write RELEASE_NOTES.md describing what a user gets,
   in plain language.
   ```
2. The fresh-install test:

   ```
   Prove the README setup instructions work from scratch: fresh clone, clean
   environment, follow the README exactly, show me the app running.
   ```
3. If the app holds real data, back it up now and write down (in the README)
   how restore works.

**Done when** the tag exists; a fresh install works by following the README
alone; you know how to get back to this exact version.

## Phase 6 — Maintain & Evolve

**The principle.** Maintenance is 60–80 percent of software's real lifetime
cost, and it is not a lesser activity — it is the same lifecycle, run smaller.
Everything flows through the same pipeline: design doc, phases, review,
ledger.

**The Claude Code moves.**

- **Bugs:** reproduce before fixing, always:

  ```
  Before fixing this, write a failing automated test that reproduces it.
  Then fix it and show the test passing.
  ```

  Then ask: is this a new defect class or a recurrence? Ledger it either way.
- **New features:** add a new numbered phase to `DESIGN_DOC.md` Section 10,
  then re-enter Phase 3. No feature skips the design doc — that's how living
  documents die.
- **Periodically** (every handful of phases):

  ```
  Read the whole repo and DESIGN_DOC.md. Where has the code drifted from the
  doc? List the differences; don't change anything yet.
  ```

  Then update whichever one is wrong — sometimes it's the doc.

**Done when:** never. That's the point. Software you stop maintaining is
software you've decided to let die, which is also a legitimate choice — just
make it on purpose, and tag a final release first.
