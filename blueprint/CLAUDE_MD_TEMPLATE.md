# CLAUDE.md — <project name>

> **What this is.** The per-project instructions Claude Code reads
> automatically at the start of every session. Everything the lifecycle guide
> says Claude should do *unprompted* lives here, so you never have to remember
> to ask. Copy into the project root as `CLAUDE.md`, fill in the `<blanks>`,
> delete this block.

## Project

<one line: what this app is.> The blueprint is `DESIGN_DOC.md` — read it
before planning any work. Keep it alive: when a phase completes, update its
status header; when scope is cut or deferred, move it to Section 10's
Follow-on list. If code and doc disagree, flag it rather than silently
following either.

## How to run and check

- Run the app: `<command — Python projects: uv run <entrypoint>>`
- Run the tests: `<command — Python projects: uv run pytest>`
- Set up the environment: `<command — Python projects: uv sync>`

Python projects here use uv (Astral) exclusively: dependencies via `uv add`
(never bare pip), everything executed via `uv run` so the locked environment
is always the one in use.

## Workflow rules

- Enter plan mode before any change touching more than one file; get the plan
  approved before building.
- Build each design-doc phase on its own branch, named `claude/<slug>`.
- Conventional Commits with the phase marker: `feat(scope): summary (Phase NN)`.
  Several small commits, not one blob.
- Stay inside the current phase. Improvements outside it go to the design
  doc's Follow-on list, not into the diff.
- Never report work as done without running the actual app and demonstrating
  the new behavior. Passing tests alone are not "done".
- Anything visual: show a screenshot of the running app.

## QA rules

- Write tests alongside features, not after. Every design-doc Section 4 MUST
  gets a test.
- Before any code review: read `QA_LEDGER.md` and check the diff for
  recurrences of every recorded defect class.
- After any code review or QA run: append a `QA_LEDGER.md` entry per its
  template (defect classes, not individual bugs).
- Bug fixes start with a failing test that reproduces the bug.

## Project-specific conventions

<!-- Empty at project start. This section grows by the promotion rule: any
QA_LEDGER.md defect class that recurs twice becomes a permanent rule here,
phrased as "always X when Y". -->

- <promoted rule>
