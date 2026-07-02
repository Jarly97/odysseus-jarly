"""Phase 01 — stakeholder update/delete + portfolio summary (service, route, tool)."""
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
    tmp = tempfile.mkdtemp(prefix="odysseus_extras_test_")
    eng = create_engine("sqlite:///" + os.path.join(tmp, "x.db").replace("\\", "/"),
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
        request.state.current_user = request.headers.get("x-test-user") or None
        return await call_next(request)

    app.include_router(setup_client_routes())
    return TestClient(app)


def test_update_and_delete_stakeholder_service():
    c = svc.create_client("karl", "RVL")
    s = svc.add_stakeholder("karl", c["id"], "Amy", role="CGO")
    svc.upsert_itm("karl", s["id"], current_identity="x")  # creates child ITM
    assert svc.update_stakeholder("cto", s["id"], role="X") is None  # owner-scoped
    upd = svc.update_stakeholder("karl", s["id"], role="Chief Growth Officer", archetype="Authority Expert")
    assert upd["role"] == "Chief Growth Officer" and upd["archetype"] == "Authority Expert"
    assert svc.delete_stakeholder("cto", s["id"]) is False
    assert svc.delete_stakeholder("karl", s["id"]) is True
    assert svc.get_stakeholder("karl", s["id"]) is None
    assert svc.get_itm("karl", s["id"]) is None  # cascade removed the ITM


def test_portfolio_summary_service():
    c = svc.create_client("karl", "RVL")
    a = svc.add_stakeholder("karl", c["id"], "A")
    b = svc.add_stakeholder("karl", c["id"], "B")
    svc.upsert_itm("karl", a["id"], transition_stage="stuck", open_loss_flag=True)
    svc.upsert_itm("karl", b["id"], transition_stage="moving")
    summ = svc.portfolio_summary("karl")
    assert summ["stakeholders"] == 2
    assert summ["by_stage"].get("stuck") == 1 and summ["by_stage"].get("moving") == 1
    assert summ["open_loss"] == 1
    assert svc.portfolio_summary("cto") == {"clients": 0, "stakeholders": 0, "by_stage": {}, "open_loss": 0}


def test_routes(http):
    # Dedicated owner so the shared module DB from earlier tests doesn't skew counts.
    u = {"x-test-user": "rtuser"}
    cid = http.post("/api/clients", json={"name": "RVL"}, headers=u).json()["id"]
    sid = http.post(f"/api/clients/{cid}/stakeholders", json={"name": "Amy"}, headers=u).json()["id"]
    r = http.put(f"/api/clients/stakeholders/{sid}", json={"role": "CGO"}, headers=u)
    assert r.status_code == 200 and r.json()["role"] == "CGO"
    assert http.put(f"/api/clients/stakeholders/{sid}", json={"role": "X"}, headers={"x-test-user": "cto"}).status_code == 404
    summ = http.get("/api/clients/portfolio/summary", headers=u)
    assert summ.status_code == 200 and summ.json()["stakeholders"] == 1
    assert http.delete(f"/api/clients/stakeholders/{sid}", headers=u).status_code == 200


def test_tool_actions():
    def call(args, owner="karl"):
        return asyncio.run(do_manage_clients(json.dumps(args), owner=owner))
    cid = call({"action": "create_client", "name": "RVL"})["id"]
    sid = call({"action": "add_stakeholder", "client_id": cid, "name": "Amy"})["id"]
    assert call({"action": "update_stakeholder", "stakeholder_id": sid, "role": "CGO"})["role"] == "CGO"
    assert call({"action": "portfolio_summary"})["stakeholders"] >= 1
    # Deletes are refused at the tool layer (QA hardening); the service (UI path)
    # still deletes for a confirmed human.
    assert "not available to the agent" in call({"action": "delete_stakeholder", "stakeholder_id": sid})["error"]
    assert svc.delete_stakeholder("karl", sid) is True
