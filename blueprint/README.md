# Blueprint — a starter kit for building software with Claude Code

This kit is the starting point for every app you build. It packages the
fundamentals a formal engineering education teaches — requirements before
code, deliberate architecture, incremental delivery, real QA — as documents
and copy-paste prompts you can execute with Claude Code, without reading or
writing code yourself. It generalizes the practices that already work in this
repo (the client-workspaces design doc, the QA ledger, the run-the-actual-app
rule) into a portable system.

The flow, in one line:

**DESIGN_DOC** (what to build) → **LIFECYCLE** (how to build it) →
**QA_CHECKLIST + QA_LEDGER** (how to trust it) → **CLAUDE.md** (how Claude
remembers all of it)

## The files

| File | What it is | New project? |
|---|---|---|
| [LIFECYCLE.md](LIFECYCLE.md) | The 7-phase development lifecycle — principle, Claude Code moves, and exit criteria per phase. The spine of the system | Keep open as reference |
| [DESIGN_DOC_TEMPLATE.md](DESIGN_DOC_TEMPLATE.md) | The blueprint design document: 10 sections with inline guidance, tiered LIGHT/FULL | **Copy** as `DESIGN_DOC.md` |
| [QA_CHECKLIST.md](QA_CHECKLIST.md) | The pre-release checklist you can run without reading code | **Copy** unchanged |
| [QA_LEDGER_TEMPLATE.md](QA_LEDGER_TEMPLATE.md) | The recurring-defect-class ledger — the project's memory of what kinds of bugs it breeds | **Copy** as `QA_LEDGER.md` |
| [CLAUDE_MD_TEMPLATE.md](CLAUDE_MD_TEMPLATE.md) | Per-project instructions Claude reads automatically — what makes the whole system run unprompted | **Copy** as `CLAUDE.md`, fill blanks |
| [examples/storylet-game-design-doc.md](examples/storylet-game-design-doc.md) | The template fully filled in, for a real project (the storylet game) | Read once |

## First time here: read in this order

1. This README (10 minutes).
2. [LIFECYCLE.md](LIFECYCLE.md) start to finish (30 minutes) — everything
   else hangs off it.
3. Skim [DESIGN_DOC_TEMPLATE.md](DESIGN_DOC_TEMPLATE.md), then read the
   [storylet example](examples/storylet-game-design-doc.md) *next to it* —
   blank versus filled is the fastest way to learn the template.
4. Skim the two QA files so you know what's waiting at Phase 4.

## Starting a new project: the 15-minute ritual

1. Create the new project's repository.
2. Copy in the four "copy" files from the table above, renaming as noted.
3. Open Claude Code in the new repo. You can do steps 2–3 in one paste:

   ```
   Copy from <path to this kit>: DESIGN_DOC_TEMPLATE.md as DESIGN_DOC.md,
   QA_CHECKLIST.md as QA_CHECKLIST.md, QA_LEDGER_TEMPLATE.md as
   QA_LEDGER.md, and CLAUDE_MD_TEMPLATE.md as CLAUDE.md. Then help me fill
   in CLAUDE.md's blanks.
   ```

4. Begin [LIFECYCLE.md](LIFECYCLE.md) Phase 0.

## Which tier?

| Tier | When |
|---|---|
| **LIGHT** | A weekend automation or script: no users but you, no data you'd grieve. Fill design doc sections 1, 2, 3, 4, 9, 10 |
| **FULL** | Users other than you, saved data that matters, or more than ~3 build phases. Fill everything |

When unsure, start LIGHT and upgrade sections as the project proves it
deserves them.

## How the documents reference each other

- LIFECYCLE Phase 1 produces the design doc; Phase 3 consumes its Section 10
  phases and updates its status header; Phase 4 runs the QA checklist.
- DESIGN_DOC Section 3's scenarios become Section 9's acceptance walkthrough,
  which QA_CHECKLIST Part A executes.
- QA_CHECKLIST Part D runs the QA_LEDGER recurrence check.
- QA_LEDGER's promotion rule feeds permanent rules into CLAUDE.md — which is
  what makes Claude apply all of the above without being asked.

All links are relative, so the kit survives being copied wholesale into any
new project or repo.
