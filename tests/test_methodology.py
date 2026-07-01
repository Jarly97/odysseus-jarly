"""Phase 04 core — methodology rules (src/methodology.py). Pure, no DB."""
from src import methodology as m


def test_tri_stage_bands():
    assert m.tri_stage(None) is None
    assert m.tri_stage(10) == "stuck"
    assert m.tri_stage(18) == "stuck"
    assert m.tri_stage(19) == "moving"
    assert m.tri_stage(27) == "moving"
    assert m.tri_stage(28) == "landing"
    assert m.tri_stage(34) == "landing"
    assert m.tri_stage(35) == "landed"
    assert m.tri_stage(40) == "landed"


def test_recommended_action():
    assert "identity session" in m.recommended_action("stuck").lower()
    assert m.recommended_action("landed").lower().startswith("document")
    assert m.recommended_action(None) is None
    assert m.recommended_action("bogus") is None


def test_select_frames_by_archetype_and_stage():
    # Authority Expert, moving -> M5 (authority amplified)
    ids = [f["id"] for f in m.select_frames("Authority Expert", "moving")]
    assert ids == ["M5"]
    # Responsiveness Gatekeeper, stuck -> S1, S2, S4
    ids = [f["id"] for f in m.select_frames("Responsiveness Gatekeeper", "stuck")]
    assert ids == ["S1", "S2", "S4"]
    # Landing and Landed resolve to the same column
    assert m.select_frames("Authority Expert", "landing") == m.select_frames("Authority Expert", "landed")
    # Each frame carries a title.
    assert all(f["title"] for f in m.select_frames("High-Capacity Executor", "moving"))


def test_select_frames_unknown_archetype_falls_back():
    # Unknown/None archetype -> "not yet mapped" row; unknown stage -> cautious (stuck).
    ids = [f["id"] for f in m.select_frames(None, None)]
    assert ids == ["S1", "S3"]
    ids = [f["id"] for f in m.select_frames("something weird", "moving")]
    assert ids == ["M1", "M3"]


def test_avoid_frames_present():
    assert any("Automation" in a for a in m.AVOID_FRAMES)
    assert len(m.ITM_DIMENSIONS) == 5
