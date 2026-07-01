"""Phase 04 — methodology synthesis (src/synthesis.py).

Prompt builder is tested deterministically (no DB); synthesize() is tested with a
mocked LLM against a seeded throwaway DB.
"""
import asyncio
import json
import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

import core.database as _db
from src import clients as svc
from src import synthesis
from src.tool_implementations import do_manage_clients
from routes.client_routes import setup_client_routes


def _patch_llm(monkeypatch, captured=None):
    """Point the resolved-synthesis path at a fake endpoint + fake LLM."""
    monkeypatch.setattr("src.endpoint_resolver.resolve_endpoint",
                        lambda name: ("http://x/v1/chat/completions", "m1", {}))
    monkeypatch.setattr("src.endpoint_resolver.resolve_chat_fallback_candidates",
                        lambda owner=None: [])

    async def fake_llm(candidates, messages, **kw):
        if captured is not None:
            captured["candidates"] = candidates
            captured["messages"] = messages
        return "RESOLVED ARTIFACT"

    monkeypatch.setattr("src.llm_core.llm_call_async_with_fallback", fake_llm)


def _seed_transcript(owner="karl"):
    c = svc.create_client(owner, "RVL Pharma", sector="pharma")
    s = svc.add_stakeholder(owner, c["id"], "Amy", archetype="Authority Expert")
    svc.upsert_itm(owner, s["id"], expected_loss="rainmaker loop", transition_stage="moving")
    return c, s, svc.add_transcript(owner, c["id"], content="notes", stakeholder_id=s["id"])


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


def test_synthesize_resolved(monkeypatch):
    c, s, t = _seed_transcript("karl")
    captured = {}
    _patch_llm(monkeypatch, captured)
    out = asyncio.run(synthesis.synthesize_resolved("karl", t["id"], "session_summary"))
    assert out["content"] == "RESOLVED ARTIFACT" and out["artifact_kind"] == "session_summary"
    # the resolved primary endpoint was prepended to the candidate list
    assert captured["candidates"][0] == ("http://x/v1/chat/completions", "m1", {})
    # the prompt carried the methodology grounding
    assert any("rainmaker loop" in m["content"] for m in captured["messages"])
    # not owned -> None
    assert asyncio.run(synthesis.synthesize_resolved("cto", t["id"], "session_summary")) is None


def test_synthesize_resolved_no_endpoint(monkeypatch):
    c, s, t = _seed_transcript("karl")
    monkeypatch.setattr("src.endpoint_resolver.resolve_endpoint", lambda name: (None, None, None))
    out = asyncio.run(synthesis.synthesize_resolved("karl", t["id"], "session_summary"))
    assert out and out.get("error")


def test_synthesize_route(monkeypatch):
    _patch_llm(monkeypatch)
    app = FastAPI()

    @app.middleware("http")
    async def _set_user(request, call_next):
        request.state.current_user = request.headers.get("x-test-user") or None
        return await call_next(request)

    app.include_router(setup_client_routes())
    http = TestClient(app)
    _, _, t = _seed_transcript("routeuser")
    r = http.post(f"/api/clients/transcripts/{t['id']}/synthesize",
                  json={"artifact_kind": "comms_draft"}, headers={"x-test-user": "routeuser"})
    assert r.status_code == 200, r.text
    assert r.json()["content"] == "RESOLVED ARTIFACT"
    # cross-owner -> 404
    assert http.post(f"/api/clients/transcripts/{t['id']}/synthesize",
                     json={"artifact_kind": "comms_draft"}, headers={"x-test-user": "nope"}).status_code == 404


def test_synthesize_tool(monkeypatch):
    _patch_llm(monkeypatch)
    _, _, t = _seed_transcript("tooluser")
    out = asyncio.run(do_manage_clients(
        json.dumps({"action": "synthesize", "transcript_id": t["id"], "artifact_kind": "risk_log"}),
        owner="tooluser"))
    assert out["content"] == "RESOLVED ARTIFACT" and out["artifact_kind"] == "risk_log"
