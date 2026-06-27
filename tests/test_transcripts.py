"""Phase 03/04 — meeting transcripts + synthesis-context assembly.

Covers the service (src.clients transcript fns), the REST routes, and the
manage_clients tool actions. Throwaway temp DB; isolated module fixture.
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
from src.tool_implementations import do_manage_clients
from routes.client_routes import setup_client_routes


@pytest.fixture(autouse=True, scope="module")
def _fresh_db():
    tmp = tempfile.mkdtemp(prefix="odysseus_transcripts_test_")
    eng = create_engine("sqlite:///" + os.path.join(tmp, "tr.db").replace("\\", "/"),
                        connect_args={"check_same_thread": False})
    _db.Base.metadata.create_all(eng)
    orig = _db.engine
    _db.SessionLocal.configure(bind=eng)
    yield
    _db.SessionLocal.configure(bind=orig)


@pytest.fixture()
def http():
    app = FastAPI()

    @app.middleware("http")
    async def _set_user(request, call_next):
        u = request.headers.get("x-test-user")
        request.state.current_user = u if u else None
        return await call_next(request)

    app.include_router(setup_client_routes())
    return TestClient(app)


def test_transcript_service_and_scope():
    c = svc.create_client("karl", "RVL Pharma")
    # cross-owner can't attach a transcript
    assert svc.add_transcript("cto", c["id"], content="x") is None
    t = svc.add_transcript("karl", c["id"], content="meeting notes...", title="Kickoff", source="notion")
    assert t["title"] == "Kickoff" and t["source"] == "notion"
    assert [x["id"] for x in svc.list_transcripts("karl", c["id"])] == [t["id"]]
    assert svc.list_transcripts("cto", c["id"]) is None
    assert svc.get_transcript("cto", t["id"]) is None
    assert svc.delete_transcript("cto", t["id"]) is False
    assert svc.delete_transcript("karl", t["id"]) is True
    assert svc.get_transcript("karl", t["id"]) is None


def test_transcript_stakeholder_must_belong_to_client():
    a = svc.create_client("karl", "Client A")
    b = svc.create_client("karl", "Client B")
    sa = svc.add_stakeholder("karl", a["id"], "Amy")
    # stakeholder from client A can't be attached to a client-B transcript
    assert svc.add_transcript("karl", b["id"], content="x", stakeholder_id=sa["id"]) is None
    ok = svc.add_transcript("karl", a["id"], content="x", stakeholder_id=sa["id"])
    assert ok["stakeholder_id"] == sa["id"]


def test_build_synthesis_context():
    c = svc.create_client("karl", "RVL Pharma", sector="pharma")
    s = svc.add_stakeholder("karl", c["id"], "Amy", archetype="Authority Expert")
    svc.upsert_itm("karl", s["id"], current_identity="growth visionary", transition_stage="moving")
    svc.add_tri("karl", s["id"], total=20)  # moving
    t = svc.add_transcript("karl", c["id"], content="they said...", stakeholder_id=s["id"])
    ctx = svc.build_synthesis_context("karl", t["id"])
    assert ctx["transcript"]["id"] == t["id"]
    assert ctx["client"]["name"] == "RVL Pharma"
    assert ctx["stakeholder"]["name"] == "Amy"
    assert ctx["itm"]["current_identity"] == "growth visionary"
    assert [f["id"] for f in ctx["recommended_frames"]] == ["M5"]
    assert len(ctx["methodology"]["itm_dimensions"]) == 5
    # owner-scoped
    assert svc.build_synthesis_context("cto", t["id"]) is None


def test_transcript_routes(http):
    cid = http.post("/api/clients", json={"name": "RVL"}, headers={"x-test-user": "karl"}).json()["id"]
    t = http.post(f"/api/clients/{cid}/transcripts", json={"content": "notes", "title": "Kickoff"},
                  headers={"x-test-user": "karl"})
    assert t.status_code == 200, t.text
    tid = t.json()["id"]
    # synthesis-context route resolves (not shadowed by /{client_id})
    ctx = http.get(f"/api/clients/transcripts/{tid}/synthesis-context", headers={"x-test-user": "karl"})
    assert ctx.status_code == 200 and ctx.json()["transcript"]["id"] == tid
    # cross-owner 404
    assert http.get(f"/api/clients/transcripts/{tid}", headers={"x-test-user": "cto"}).status_code == 404


def test_transcript_tool_actions():
    def call(args, owner="karl"):
        return asyncio.run(do_manage_clients(json.dumps(args), owner=owner))
    cid = call({"action": "create_client", "name": "RVL"})["id"]
    t = call({"action": "add_transcript", "client_id": cid, "content": "notes", "title": "Kickoff"})
    assert t["title"] == "Kickoff"
    assert [x["id"] for x in call({"action": "list_transcripts", "client_id": cid})["transcripts"]] == [t["id"]]
    ctx = call({"action": "synthesis_context", "transcript_id": t["id"]})
    assert ctx["transcript"]["id"] == t["id"]
