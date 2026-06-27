"""Methodology synthesis (Buildout Phase 04 — the core value loop).

Turns a meeting transcript into a methodology-defined deliverable. Two parts:

  - build_synthesis_prompt(context, artifact_kind): deterministic. Assembles the
    synthesis context (from src.clients.build_synthesis_context) into a chat-message
    prompt grounded in the Kaldway Path 1 methodology — the ITM (esp. expected
    loss), the recommended comms frames, and the avoid-list.
  - synthesize(...): thin async wrapper that builds the context + prompt and calls
    the LLM. Endpoint is passed in by the caller (same convention as the memory
    extractor), so this module stays provider-agnostic and testable.

The set of deliverables is intentionally a registry (ARTIFACT_KINDS) — the real
artifacts are defined by the methodology; these are the common enablement outputs.
"""
from __future__ import annotations

from typing import Optional

from src import clients

# Common enablement deliverables. Each: title + instruction for the LLM.
ARTIFACT_KINDS: dict[str, dict] = {
    "session_summary": {
        "title": "Session summary + action items",
        "instruction": ("Produce a concise, structured recap of the meeting: what happened, key "
                        "decisions, and explicit action items with owners and due dates where stated. "
                        "Written for the governance/CX team."),
    },
    "comms_draft": {
        "title": "Stakeholder comms draft",
        "instruction": ("Draft a short comms piece to the stakeholder that advances their identity "
                        "transition. Select ONE of the recommended frames (cite its id), adapt it to the "
                        "stakeholder's own voice, and validate it against their expected-loss diagnosis. "
                        "Never use any avoid-frame language."),
    },
    "journey_update": {
        "title": "Transformation-journey update",
        "instruction": ("Summarize how this session moved the stakeholder along their transition "
                        "(stage change and the signals that justify it) and state the next step."),
    },
    "risk_log": {
        "title": "Risk / resistance + adoption signals",
        "instruction": ("Extract resistance/blocker signals and adoption signals from the transcript, "
                        "mapped to the stakeholder's expected loss. Flag anything governance should see."),
    },
    "itm_update": {
        "title": "Proposed ITM updates",
        "instruction": ("Propose updates to the five ITM dimensions based only on what the transcript "
                        "reveals. Be specific; mark uncertain items. Do not invent beyond the transcript."),
    },
    "tri_assessment": {
        "title": "Proposed TRI assessment",
        "instruction": ("Score the 10 TRI items from observed behaviour/language in the transcript (1-4 "
                        "to the anchors), noting insufficient-signal items, and give the resulting stage. "
                        "Score to the anchors, not to overall impression."),
    },
}

_SYSTEM = (
    "You are the CM operating partner for a Kaldway (KTG) change-management engagement, running the "
    "Path 1 - Identity Transition methodology. Reason from the ITM, especially the expected-loss "
    "diagnosis. When you write stakeholder-facing language, select from the recommended comms frames "
    "and adapt to the stakeholder's voice; never use the avoid-frames. Be specific and grounded in the "
    "transcript - do not invent facts. Output only the requested artifact."
)


def build_synthesis_prompt(context: dict, artifact_kind: str) -> list[dict]:
    """Assemble a chat-message prompt from a synthesis context. Deterministic."""
    if artifact_kind not in ARTIFACT_KINDS:
        raise ValueError(f"Unknown artifact kind: {artifact_kind!r}")
    spec = ARTIFACT_KINDS[artifact_kind]
    t = context.get("transcript") or {}
    client = context.get("client") or {}
    sk = context.get("stakeholder") or {}
    itm = context.get("itm") or {}
    frames = context.get("recommended_frames") or []
    avoid = (context.get("methodology") or {}).get("avoid_frames") or []

    lines = [f"# Artifact requested: {spec['title']}", spec["instruction"], ""]
    lines.append(f"## Client\n{client.get('name', '(unknown)')} — sector: {client.get('sector') or 'n/a'}")
    if sk:
        lines.append(
            "## Stakeholder\n"
            f"{sk.get('name', '')} — role: {sk.get('role') or 'n/a'} — "
            f"archetype: {sk.get('archetype') or 'unmapped'} — "
            f"stage: {sk.get('transition_stage') or 'unknown'}"
        )
    if itm:
        dims = [f"- {d.replace('_', ' ')}: {itm[d]}" for d in
                ("current_identity", "target_identity", "expected_loss", "target_gain", "bridging_rituals")
                if itm.get(d)]
        if dims:
            lines.append("## ITM\n" + "\n".join(dims))
    if frames:
        lines.append("## Recommended comms frames (select from these)\n" +
                     "\n".join(f"- {f['id']}: {f['title']}" for f in frames))
    if avoid:
        lines.append("## Avoid these framings\n" + ", ".join(avoid))
    lines.append("\n## Meeting transcript\n" + (t.get("content") or "(no transcript content)"))

    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": "\n".join(lines)}]


async def synthesize(user: str, transcript_id: str, artifact_kind: str,
                     endpoint_url: str, model: str, headers: Optional[dict] = None,
                     temperature: float = 0.3, max_tokens: int = 1500) -> Optional[dict]:
    """Build the context + prompt for a transcript and run the LLM to produce the
    requested artifact. Returns None if the transcript isn't owned/found. The LLM
    endpoint is supplied by the caller (resolve the user's chat endpoint upstream)."""
    if artifact_kind not in ARTIFACT_KINDS:
        raise ValueError(f"Unknown artifact kind: {artifact_kind!r}")
    context = clients.build_synthesis_context(user, transcript_id)
    if context is None:
        return None
    messages = build_synthesis_prompt(context, artifact_kind)
    from src.llm_core import llm_call_async
    content = await llm_call_async(endpoint_url, model, messages, headers=headers,
                                   temperature=temperature, max_tokens=max_tokens,
                                   prompt_type="cm_synthesis")
    return {
        "artifact_kind": artifact_kind,
        "title": ARTIFACT_KINDS[artifact_kind]["title"],
        "content": content,
        "transcript_id": transcript_id,
        "client_id": (context.get("client") or {}).get("id"),
        "stakeholder_id": (context.get("transcript") or {}).get("stakeholder_id"),
    }
