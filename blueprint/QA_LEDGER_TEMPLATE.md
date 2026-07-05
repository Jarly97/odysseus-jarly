# QA Ledger

> **What this is.** Bugs come in *classes*, and classes recur. A missed edge
> case is a bug; "this project keeps missing edge cases around empty input" is
> a defect class — and classes are predictable. This file is the project's
> memory of what kinds of mistakes it breeds, so every future review checks
> for them. Tests catch known bugs; the ledger catches known *kinds* of bugs.
> Claude reads it before every review and appends to it after.
>
> Copy this file into each new project as `QA_LEDGER.md` and delete this
> header block down to the ruled line. The entry below is the template.

**Operating instructions**

- *After* every code review or QA run, tell Claude:
  `Add a QA_LEDGER.md entry for this review, following the template. Name
  defect CLASSES, not individual bugs.`
- *Before* every review, tell Claude:
  `Read QA_LEDGER.md first and check for recurrences of every class ever
  recorded.`
  (Your `CLAUDE.md` should make both of these automatic.)
- **The promotion rule — how the ledger drains instead of only growing:** a
  class that recurs twice graduates to a permanent rule in `CLAUDE.md`
  ("always X when Y"), so it is prevented at write time instead of caught at
  review time. Note the promotion in the entry and stop tracking it here.

---

## YYYY-MM-DD — <scope of review> (branch <name> vs main)

**New defect classes:**
- **<Short class name>:** <one-sentence mechanism — how this kind of bug
  happens here> → <consequence if unchecked>.

**Recurred from prior runs:** <class names, or "n/a">

**Systemic signal:** <what process step or checklist keeps getting missed —
the pattern behind the pattern>

**Coverage gap closed:** <what this run fixed or newly tests> **Opened:**
<what is now known to be untested or unverified>
