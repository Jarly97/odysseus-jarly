"""Phase 04 — methodology synthesis (src/synthesis.py).

Prompt builder is tested deterministically (no DB); synthesize() is tested with a
mocked LLM against a seeded throwaway DB.
"""
import asyncio
import os
import tempfile

import pytest
from sqlalchemy import create_engine

import core.database as _db
from src import clients as svc
from src import synthesis


@pytest.fixture(autouse=True, scope="module")
def _fresh_db():
    tmp = tempfile.mkdtemp(prefix="odysseus_synthesis_test_")
    eng = create_engine("sqlite:///" + os.path.join(tmp, "syn.db").replace("\\", "/"),
                        connect_args={"check_same_thread": False})
    _db.Base.metadata.create_all(eng)
    orig = _db.engine
    _db.SessionLocal.configure(bind=eng)
    yield
    _db.SessionLocal.configure(bind=orig)


def _context():
    return {
        "transcript": {"id": "t1", "content": "Amy said she fears being commoditised.", "stakeholder_id": "s1"},
        "client": {"id": "c1", "name": "RVL Pharma", "sector": "pharma"},
        "stakeholder": {"name": "Amy", "role": "CGO", "archetype": "Authority Expert", "transition_stage": "moving"},
        "itm": {"current_identity": "growth visionary", "expected_loss": "rainmaker validation loop"},
        "recommended_frames": [{"id": "M5", "title": "Authority Expert: authority amplified"}],
        "methodology": {"itm_dimensions": list(synthesis.clients.methodology.ITM_DIMENSIONS),
                        "avoid_frames": ['"Automation"']},
    }


def test_build_prompt_is_grounded():
    msgs = synthesis.build_synthesis_prompt(_context(), "comms_draft")
    assert msgs[0]["role"] == "system" and "Path 1" in msgs[0]["content"]
    user = msgs[1]["content"]
    assert "Stakeholder comms draft" in user
    assert "rainmaker validation loop" in user      # ITM expected loss is present
    assert "M5" in user                              # recommended frame offered
    assert "Amy said she fears" in user             # transcript content present
    assert '"Automation"' in user                   # avoid-list present


def test_build_prompt_unknown_kind():
    with pytest.raises(ValueError):
        synthesis.build_synthesis_prompt(_context(), "nope")


def test_synthesize_with_mocked_llm(monkeypatch):
    c = svc.create_client("karl", "RVL Pharma", sector="pharma")
    s = svc.add_stakeholder("karl", c["id"], "Amy", archetype="Authority Expert")
    svc.upsert_itm("karl", s["id"], expected_loss="rainmaker loop", transition_stage="moving")
    t = svc.add_transcript("karl", c["id"], content="meeting...", stakeholder_id=s["id"])

    captured = {}

    async def fake_llm(url, model, messages, **kwargs):
        captured["model"] = model
        captured["messages"] = messages
        return "DRAFT ARTIFACT"

    monkeypatch.setattr("src.llm_core.llm_call_async", fake_llm)

    out = asyncio.run(synthesis.synthesize("karl", t["id"], "comms_draft",
                                           endpoint_url="http://x/v1/chat/completions", model="m1"))
    assert out["content"] == "DRAFT ARTIFACT"
    assert out["artifact_kind"] == "comms_draft"
    assert out["client_id"] == c["id"] and out["stakeholder_id"] == s["id"]
    # prompt actually carried the methodology grounding to the model
    assert any("rainmaker loop" in mtext["content"] for mtext in captured["messages"])

    # owner-scoped + missing transcript -> None
    assert asyncio.run(synthesis.synthesize("cto", t["id"], "comms_draft",
                                            endpoint_url="http://x", model="m1")) is None
