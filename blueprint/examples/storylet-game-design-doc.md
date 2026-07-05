# Design Document — Tidewrack *(worked example)*

> **What this file is.** A completely filled-in FULL-tier example of
> [DESIGN_DOC_TEMPLATE.md](../DESIGN_DOC_TEMPLATE.md), so you can see the
> blank template and a finished document side by side. It describes a real
> project — your storylet game — but every design decision marked
> **[ASSUMED]** is a guess made to complete the example. Correct them freely;
> replacing assumptions with your actual intent is exactly what Lifecycle
> Phase 1 is for. Copy this file into the game's repo as its starting
> `DESIGN_DOC.md` if the guesses are close, or just read it here as a model.

**Tier:** FULL
**Status:** Not started — design under review
**Last updated:** 2026-07-05

---

## 1. What & Why

*Tidewrack* **[ASSUMED name]** is a single-player, browser-based,
quality-based narrative game: the player accumulates *qualities* (numbers and
flags like `Nerve 3` or `Has the Rusted Key`) that determine which pieces of
story — *storylets* — are available to play next, in the tradition of Fallen
London and StoryNexus **[ASSUMED genre model]**. The problem it solves is the
author's, not just the player's: you want to write large amounts of branching
narrative without programming, so all story content must live in plain data
files you can edit directly — the game engine is a machine that plays your
files, and code changes are never required to add story.

## 2. Goals & Non-Goals

**Goals**
- Playable in any modern browser, no install, no account.
- All narrative content lives in human-editable data files — adding a
  storylet never requires touching code.
- Save and resume: closing the browser never loses progress.
- At least 30 storylets of real content at v0.1 **[ASSUMED target]**.
- The engine tells the author about broken content (a storylet no player
  could ever reach, an effect on a quality that doesn't exist).

**Non-goals**
- Multiplayer, accounts, or any server component.
- Graphics beyond text, CSS styling, and optional still images.
- Mobile app packaging (mobile *browser* should work, but is not tuned for).
- Monetization of any kind.
- A visual story editor (the data files are the editor for now — see
  Follow-on).

## 3. Users & Scenarios

**Scenario A — The player**
I open the game's URL. I see my current location ("The Shingle Market"), a
sidebar listing my qualities, and a hand of storylet cards I currently
qualify for. I pick one, read its prose, and choose one of its options. The
option is a challenge against my `Nerve` quality — I see my odds before
committing. I succeed; the success text plays, `Nerve` goes up by 1, and a new
storylet appears in my hand that wasn't there before. I close the tab.
Tomorrow I open the same URL and continue exactly where I left off.

**Scenario B — The author (you)**
I open `content/storylets/shingle-market.yaml` in a text editor, change a line
of prose, and add a new option with a `Shadowy` challenge. I reload the game
in the browser and play the changed storylet immediately. No build step I have
to think about, no programmer in the loop. If I typo a quality name, the game
tells me loudly instead of failing silently.

**Scenario C — The author, auditing**
Before a content release I run the validator. It lists: two storylets no
player can reach (their requirements can never be met), one option whose
effect targets a misspelled quality, and one location with no storylets. I fix
the files and re-run until clean.

## 4. Requirements

**MUST**
- Storylets are defined entirely in data files: requirements (quality
  ranges/flags that gate availability), prose, location, and options.
- Options support challenges: a test against a quality with success and
  failure branches, each with its own text and effects.
- Effects change qualities: add/subtract a number, set a flag, remove a flag.
- Game state persists across browser restarts without any user action.
- The player can export their save to a file and import it later
  (protection against browser storage being cleared).
- A content validator reports unreachable storylets, references to undefined
  qualities, and empty locations.
- A debug view shows all current qualities and lets the author set any
  quality's value while testing.

**SHOULD**
- Deck/draw mechanics: some storylets appear randomly from a location's deck
  rather than always being listed **[ASSUMED — core to the Fallen London
  feel]**.
- One optional still image per storylet.
- Challenge odds displayed to the player before they commit to an option.

**LATER**
- Sound and music.
- Import from Twine.
- Packaging for itch.io distribution.
- A web-based storylet editor for authoring without raw file editing.

## 5. Data Model

| Entity | Purpose | Key fields | Relates to |
|---|---|---|---|
| Quality | A named fact about the player: counter, flag, or tag | id, name, type (counter/flag/tag), description, hidden? | Referenced by Requirements, Challenges, Effects |
| Storylet | One playable unit of story | id, title, prose, location, requirements (quality conditions), frequency (always / deck) | Belongs to a Location; contains Options |
| Option | A choice inside a storylet | label, challenge (quality + difficulty, optional), success text/effects, failure text/effects | Belongs to a Storylet; carries Effects |
| Effect | One change to the player's state | target quality, operation (add/set/clear), amount | Targets a Quality |
| Location | A place that groups storylets | id, name, description, deck rules | Contains Storylets |
| SaveState | Everything about one player's progress | current location, all quality values, played-storylet history | Snapshots Qualities; references Location |

This is the standard quality-based-narrative (QBN) model **[ASSUMED as the
intended structure]** — qualities are the single source of truth, and
everything else either reads them (requirements, challenges) or writes them
(effects).

## 6. System Shape & Stack

**Parts**
- **Content files** (`content/`) — YAML files: one per location, storylets
  inline. The author's entire workspace.
- **Engine** (`src/engine/`) — pure logic, no screen: evaluates requirements,
  resolves challenges, applies effects, manages saves. This is where almost
  all automated tests point.
- **UI** (`src/ui/`) — renders location, quality sidebar, storylet hand,
  option buttons, result panel. Talks only to the engine.
- **Validator** (`src/validate/`) — reads all content, reports authoring
  errors (Scenario C). Runs from the command line and in CI.
- **Debug panel** — hidden UI surface for the author: quality table, set-any-
  quality, and "why is/isn't this storylet available" explainer.

**Stack decisions** *(all **[ASSUMED]** — a proposal to accept or overturn)*

| Choice | Why (one line) |
|---|---|
| Static web app: HTML/CSS/vanilla JS, no server | Nothing to operate, pay for, or secure; the whole game is files (Non-goal: no server) |
| Story content in YAML files | The most comfortably human-editable structured format — the author is the primary "interface user" (Section 1) |
| Saves in browser localStorage + export/import to file | Zero infrastructure; the export file covers the storage-cleared risk (Section 8) |
| npm for tooling (validator, tests) | Standard for JS; the "uv equivalent" for this stack — one command shape, locked dependencies |
| Deploy on GitHub Pages | Free static hosting straight from the repo; a release is just a push |
| Why not Twine? | Twine embeds logic inside passages; QBN needs a quality engine playing authorable data files — different architecture (Section 1's core requirement) |

## 7. Interfaces

**Screens / commands**
- **Play screen** — location header and description; quality sidebar (name +
  value, hidden qualities omitted); the hand of eligible storylet cards
  (title + teaser); selected storylet view (prose, options with odds shown);
  result panel (success/failure text, quality changes called out).
- **Save menu** — export save to file, import save from file, restart
  (with confirmation).
- **Debug panel** (hidden behind a keystroke) — all qualities editable;
  eligibility explainer ("Storylet X unavailable: requires Nerve ≥ 4, you
  have 2").
- **Validator command** — `npm run validate`: prints authoring errors with
  file and line.

**Machine surfaces (file formats)**
- **The storylet YAML schema** — this *is* the authoring interface, so it is
  the contract to get right. One annotated example is the spec:

  ```yaml
  id: rumor-of-the-wreck
  title: A Rumor of the Wreck
  location: shingle-market
  frequency: always          # or: deck
  requires:
    Nerve: {min: 2}
    Has the Rusted Key: true
  prose: >
    The fishwife leans close. "They say the Tidewrack didn't sink,"
    she whispers. "They say it was *taken*."
  options:
    - label: Press her for details
      challenge: {quality: Persuasive, difficulty: 3}
      success:
        text: She tells you where the lifeboat washed ashore.
        effects: [{quality: Wreck Rumors, add: 1}]
      failure:
        text: She clams up and waves you off.
        effects: [{quality: Nerve, add: -1}]
    - label: Leave it alone
      success:
        text: Some stories are better unheard.
        effects: []
  ```
- **Save file** — JSON export of SaveState; versioned so old saves survive
  engine updates.

## 8. Risks & Open Questions

**Risks**
- Content outgrows the engine (30 storylets fine, 300 unmanageable) —
  medium — the validator and the unreachable-storylet report exist from
  Phase 04 precisely so scale problems surface as reports, not as mysteries.
- localStorage silently cleared by the browser → total progress loss — high
  impact — mitigation is the MUST save export/import; the UI nudges the
  player to export after long sessions.
- Combinatorial quality explosion makes stories untestable (nobody can check
  every path) — medium — keep qualities few and coarse; the validator's
  reachability analysis is the backstop.
- Author burnout: writing YAML by hand stops being fun at scale — medium —
  accepted for v0.1; the web-based editor sits in Follow-on as the answer if
  it materializes.

**Open questions**
- Deck/draw rules: pure random, or weighted with pity timers? — owner: you,
  after playing with real content in Phase 05.
- Does failure on a challenge always cost something, or are some retries
  free? — owner: you (it's a game-feel question, not a technical one).
- One long game or multiple short "stories"? — owner: you; affects SaveState
  shape, so decide before Phase 03.

## 9. How We'll Know It Works

**Automated tests must cover**
- Requirements gating → a storylet appears exactly when its conditions are
  met, and never otherwise.
- Challenge resolution → success/failure branch selection and odds math are
  correct at boundary values.
- Effects → every operation (add/set/clear) applies correctly, including
  compound option effects.
- Save round-trip → save, reload, export, import: state identical after each.
- Validator → seeded broken content (unreachable storylet, undefined
  quality, empty location) is caught; clean content passes.
- Content validation runs in CI on every push, so broken story files can't
  land on main.

**My acceptance walkthrough (by hand, in the running app)**
1. Play Scenario A start to finish — pass if a challenge shows odds, changes
   a quality on success, and unlocks a new storylet.
2. Close the tab mid-game, reopen — pass if I'm exactly where I left off.
3. Edit a storylet's prose in the YAML, reload — pass if the change is live
   with no other steps.
4. Misspell a quality name in a storylet, run the validator — pass if it
   names the file and the misspelling.
5. Export my save, restart the game fresh, import — pass if progress is
   fully restored.

## 10. Build Phases & Follow-On

| Phase | Delivers (visible when done) |
|---|---|
| 00 | Skeleton page loads; quality store works; debug panel shows and edits qualities |
| 01 | Storylet engine gates on requirements; 3 hand-written storylets playable |
| 02 | Options with challenges, success/failure branches, and effects |
| 03 | Persistent saves + export/import of the save file |
| 04 | Content validator (CLI + CI) and the eligibility explainer in the debug panel |
| 05 | Real content pass: 30 storylets across 3 locations; deck/draw if SHOULD holds |
| 06 | Visual polish and v0.1 release on GitHub Pages |

**Follow-on (not yet built)**
- Deck/draw refinements (weighting, pity timers) beyond the Phase 05 basics.
- Per-storylet images.
- Web-based storylet editor.
- Twine import; itch.io packaging; sound.
