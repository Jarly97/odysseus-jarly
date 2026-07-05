# QA Checklist

Run this top to bottom before any release, and before anyone but you uses the
app (Lifecycle Phase 4). Every item is either something you do with your own
hands or an exact prompt to paste into Claude Code. You do not need to read
code to run this checklist — that is its entire design.

Copy this file unchanged into each new project.

## A. Behavioral pass — you, hands on keyboard

The one thing no tool can do for you: be the user.

- [ ] Run every scenario in `DESIGN_DOC.md` Section 3, exactly as written
      there. Each one passes or fails — no "mostly works".
- [ ] Run your acceptance walkthrough from `DESIGN_DOC.md` Section 9.
- [ ] Now try to break it like a hostile user: empty inputs, absurdly long
      inputs, wrong formats, clicking buttons twice, refreshing mid-action,
      doing steps out of order, going back.
- [ ] Kill the app mid-operation (close the tab, stop the process) and
      restart it. Is your data intact?

## B. Adversarial review — Claude vs. Claude

The session that wrote the code believes in it. Get a hostile stranger.
In a **fresh** session:

```
You did not write this code and owe its author nothing. Review this repo as
a hostile senior engineer paid per bug found: what breaks first under real
use, what can lose or corrupt user data, and what happens when input is
malicious or malformed? Rank by severity. Don't fix anything yet.
```

- [ ] Adversarial review run; findings triaged (fix now / Follow-on / reject
      with a reason).
- [ ] If the app touches the network, secrets, other people's content, or has
      an AI agent reading untrusted input: run `/security-review` as well.

## C. The coverage interview — three questions, verbatim

Make Claude prove test coverage instead of asserting it.

- [ ] ```
      For each MUST in DESIGN_DOC.md Section 4, point me to the specific test
      that covers it — or say "untested". No partial credit.
      ```
- [ ] ```
      What is the worst bug the current test suite could NOT catch?
      ```
      (Whatever the answer is, decide: add a test, or accept the risk in
      writing below.)
- [ ] ```
      If I gave this app to a stranger today, what is the first thing they'd
      hit that we'd be embarrassed by?
      ```

## D. Ledger recurrence check

Your project's bug history is a prediction of its bug future — use it.

- [ ] ```
      Read QA_LEDGER.md. Check the current code for a recurrence of every
      defect class ever recorded, and report class by class.
      ```
- [ ] After this whole QA run: add a new `QA_LEDGER.md` entry (its template
      shows the format).

## E. Release hygiene

- [ ] Fresh-install test: `Prove the README setup instructions work from
      scratch: fresh clone, clean environment, follow the README exactly,
      show me the app running.`
- [ ] README still describes the app that actually exists.
- [ ] ```
      Search this repo, including git history, for API keys, passwords,
      tokens, or personal data that should not be committed.
      ```
- [ ] Screenshots (README, release notes) show the current version, not an
      old one.

---

**The footer rule.** A red item does not block release — an *unexamined* red
item does. For anything you ship red, write one line here (or in the release
notes) saying what you're accepting and why. Quality isn't the absence of
known problems; it's the absence of surprises.

**Accepted risks for this release:**
- <red item> — <why it's acceptable for now>
