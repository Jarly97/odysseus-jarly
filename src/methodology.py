"""Kaldway "Path 1 — Identity Transition" methodology rules, as data (Phase 04 core).

Encodes the deterministic decisions the source docs specify so the synthesis
engine, the API, and the agent all reason from one place instead of re-deriving
them from prose:

  - TRI scoring -> stage + recommended action   (TRI v1.2 "Scoring and interpretation")
  - the comms frame-selection matrix            (Comms Library v1.2 "Quick selection matrix")
  - ITM dimensions / archetypes / stages

Full frame *text* lives in the cloned docs (data/personal_docs/CM-Strategy);
this module carries enough (id, stage, title, guidance) to select and reference
frames programmatically — the "selection over composition" volume lever.
"""
from __future__ import annotations

from typing import Optional

# --- ITM ------------------------------------------------------------------- #
ITM_DIMENSIONS = ("current_identity", "target_identity", "expected_loss",
                  "target_gain", "bridging_rituals")

# Canonical transition stages, ordered from least to most progressed.
STAGES = ("stuck", "moving", "landing", "landed")

# --- Archetypes (ITM archetype library) ------------------------------------ #
ARCHETYPES = ("Responsiveness Gatekeeper", "High-Capacity Executor", "Authority Expert")


# --- TRI scoring ----------------------------------------------------------- #
def tri_stage(total: Optional[int]) -> Optional[str]:
    """Map a TRI total (10–40) to a transition stage. None -> None.

    Bands from TRI v1.2: 10–18 stuck, 19–27 moving, 28–34 landing, 35–40 landed.
    Out-of-range totals clamp to the nearest band.
    """
    if total is None:
        return None
    if total >= 35:
        return "landed"
    if total >= 28:
        return "landing"
    if total >= 19:
        return "moving"
    return "stuck"


_RECOMMENDED_ACTION = {
    "stuck": "Pause tool expansion. Run an identity session. Review the ITM. Deploy or repeat bridging ritual 1.",
    "moving": "Continue current approach. Ensure the next bridging ritual is scheduled. Reinforce identity language.",
    "landing": "Begin sustaining mode. Introduce a peer-teaching opportunity. Consider an agent-graduation discussion.",
    "landed": "Document the transition. Archive the ITM. Treat the stakeholder as an internal-champion candidate.",
}


def recommended_action(stage: Optional[str]) -> Optional[str]:
    return _RECOMMENDED_ACTION.get((stage or "").lower())


# --- Comms frame catalog (compact) ----------------------------------------- #
# id -> (stage_group, title). stage_group: stuck | moving | landed.
FRAMES = {
    "S1": ("stuck", "Acknowledgment before ask"),
    "S2": ("stuck", "Loss naming (1:1 only)"),
    "S3": ("stuck", "Permission to move slowly"),
    "S4": ("stuck", "Responsiveness Gatekeeper: voice at scale"),
    "M1": ("moving", "Naming the shift"),
    "M2": ("moving", "Progress acknowledgment"),
    "M3": ("moving", "Elevating the identity"),
    "M4": ("moving", "High-Capacity Executor: capacity to leverage"),
    "M5": ("moving", "Authority Expert: authority amplified"),
    "L1": ("landed", "Transition acknowledgment"),
    "L2": ("landed", "Champion activation"),
    "L3": ("landed", "Champion as executive evidence"),
}

# Framings to avoid in all stages (Comms Library "Frames to avoid").
AVOID_FRAMES = (
    '"The AI will handle it"', '"This will save you time"', '"It\'s easy"',
    '"Don\'t worry, nothing will change"', '"The AI is just a tool"', '"Automation"',
)

# Quick selection matrix: archetype-key -> stage-key -> [frame ids].
# Stage key "landed" covers both Landing and Landed.
_MATRIX = {
    "responsiveness gatekeeper": {"stuck": ["S1", "S2", "S4"], "moving": ["M1", "M3"], "landed": ["L1", "L2"]},
    "high-capacity executor": {"stuck": ["S2", "S3"], "moving": ["M2", "M3", "M4"], "landed": ["L1", "L3"]},
    "authority expert": {"stuck": ["S1", "S2"], "moving": ["M5"], "landed": ["L1", "L2"]},
    "not yet mapped": {"stuck": ["S1", "S3"], "moving": ["M1", "M3"], "landed": ["L1"]},
}


def _archetype_key(archetype: Optional[str]) -> str:
    a = (archetype or "").strip().lower()
    return a if a in _MATRIX else "not yet mapped"


def _stage_key(stage: Optional[str]) -> str:
    s = (stage or "").strip().lower()
    if s in ("landing", "landed"):
        return "landed"
    if s in ("stuck", "moving"):
        return s
    return "stuck"  # unknown / at-risk default to the most cautious frames


def select_frames(archetype: Optional[str], stage: Optional[str]) -> list[dict]:
    """Recommend comms frames for a stakeholder by archetype × TRI stage.

    Returns [{id, title, stage_group}], the selection-matrix output. Always
    validate against the stakeholder's actual ITM loss diagnosis before sending,
    and adapt to their voice — never send verbatim (Comms Library v1.2).
    """
    ids = _MATRIX[_archetype_key(archetype)][_stage_key(stage)]
    out = []
    for fid in ids:
        grp, title = FRAMES[fid]
        out.append({"id": fid, "title": title, "stage_group": grp})
    return out
