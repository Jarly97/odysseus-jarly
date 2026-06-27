# QA Ledger
Recurring defect classes and review history for this project.

## 2026-06-26 — CM Client-workspace buildout (branch claude/bold-fermat-2ea2c4 vs main)
**New defect classes:**
- **Agent-tool blast radius:** new `manage_clients` tool exposes destructive, cascading, irreversible ops (`delete_client` cascades all stakeholders/ITM/TRI/rituals/transcripts) to the agent, which routinely processes untrusted content (transcripts, email, web fetches) → prompt-injection data-loss path with no confirmation guard.
- **Security-policy drift on new tools:** a new sensitive data tool was added to dispatch but NOT to `NON_ADMIN_BLOCKED_TOOLS`, unlike every comparable peer (`manage_memory/calendar/documents/tasks`). New tools default to *more* exposed than their peers.
- **Intent vs. implementation gap on data residency:** `synthesize_resolved` sends confidential transcripts to the global default LLM endpoint and ignores the per-client `model_policy` ("local-sensitive"), silently contradicting the stated confidentiality model.
- **Confidentiality conditioned on auth:** owner-scoping no-ops when `require_user` returns "" (AUTH_ENABLED=false / LOCALHOST_BYPASS) — acceptable app-wide, but the new subsystem is confidential-by-promise.
- **Cross-platform encoding:** unencoded `Path.read_text()` / `open()` in tests aborted Windows collection (cp1252). Fixed this run.

**Recurred from prior runs:** n/a (first ledger entry).
**Systemic signal:** when adding a tool to the agent surface, two checklists are easy to miss — (1) the `NON_ADMIN_BLOCKED_TOOLS` policy, (2) whether destructive actions belong on an agent-reachable surface at all.
**Coverage gap closed:** Windows test collection now clean (1880 collected). **Opened:** no tests for non-admin/public gating of `manage_clients`, nor for cascade behavior of transcript deletion.
