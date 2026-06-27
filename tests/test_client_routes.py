"""Phase 01 — Client workspace REST routes (routes/client_routes.py).

Mounts only the client router on a bare FastAPI app (no full app.py / lifespan),
injects the current user via a header so owner-scoping is exercised end-to-end.
Throwaway temp DB; never touches data/app.db.
"""
import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

import core.database as _db
from routes.client_routes import setup_client_routes


@pytest.fixture(autouse=True, scope="module")
def _fresh_db():
    """Bind SessionLocal to a throwaway DB for this module, then restore."""
    tmp = tempfile.mkdtemp(prefix="odysseus_client_routes_test_")
    eng = create_engine("sqlite:///" + os.path.join(tmp, "routes.db").replace("\\", "/"),
                        connect_args={"check_same_thread": False})
    _db.Base.metadata.create_all(eng)
    orig = _db.engine
    _db.SessionLocal.configure(bind=eng)
    yield
    _db.SessionLocal.configure(bind=orig)


@pytest.fixture()
def client():
    app = FastAPI()

    @app.middleware("http")
    async def _set_user(request, call_next):
        u = request.headers.get("x-test-user")
        request.state.current_user = u if u else None
        return await call_next(request)

    app.include_router(setup_client_routes())
    return TestClient(app)


def _h(user):
    return {"x-test-user": user}


def test_unauthenticated_is_rejected(client):
    assert client.get("/api/clients").status_code == 401


def test_crud_and_owner_isolation(client):
    # Create as karl
    r = client.post("/api/clients", json={"name": "RVL Pharma", "sector": "pharma"}, headers=_h("karl"))
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert r.json()["model_policy"] == "local-sensitive"

    # karl lists his client; cto sees none
    assert [c["name"] for c in client.get("/api/clients", headers=_h("karl")).json()["clients"]] == ["RVL Pharma"]
    assert client.get("/api/clients", headers=_h("cto")).json()["clients"] == []

    # cto cannot read karl's client (404, not 403 — don't leak existence)
    assert client.get(f"/api/clients/{cid}", headers=_h("cto")).status_code == 404
    assert client.get(f"/api/clients/{cid}", headers=_h("karl")).status_code == 200

    # update + delete are owner-scoped
    assert client.put(f"/api/clients/{cid}", json={"status": "paused"}, headers=_h("cto")).status_code == 404
    assert client.put(f"/api/clients/{cid}", json={"status": "paused"}, headers=_h("karl")).json()["status"] == "paused"
    assert client.delete(f"/api/clients/{cid}", headers=_h("cto")).status_code == 404
    assert client.delete(f"/api/clients/{cid}", headers=_h("karl")).status_code == 200
    assert client.get(f"/api/clients/{cid}", headers=_h("karl")).status_code == 404


def test_stakeholder_itm_tri_ritual_flow(client):
    cid = client.post("/api/clients", json={"name": "RVL Pharma"}, headers=_h("karl")).json()["id"]
    # cross-owner can't add a stakeholder
    assert client.post(f"/api/clients/{cid}/stakeholders", json={"name": "Amy"}, headers=_h("cto")).status_code == 404
    sid = client.post(f"/api/clients/{cid}/stakeholders",
                      json={"name": "Amy Shah", "role": "CGO", "archetype": "Authority Expert"},
                      headers=_h("karl")).json()["id"]

    # ITM upsert (and stage sync)
    itm = client.put(f"/api/clients/stakeholders/{sid}/itm",
                     json={"current_identity": "growth visionary", "transition_stage": "moving",
                           "open_loss_flag": True}, headers=_h("karl"))
    assert itm.status_code == 200
    assert itm.json()["current_identity"] == "growth visionary"
    sk = client.get(f"/api/clients/{cid}/stakeholders", headers=_h("karl")).json()["stakeholders"][0]
    assert sk["transition_stage"] == "moving"

    # TRI
    tri = client.post(f"/api/clients/stakeholders/{sid}/tri",
                      json={"cycle": "Day 0", "total": 14, "stage": "stuck", "tri_version": "v1.2"},
                      headers=_h("karl"))
    assert tri.status_code == 200 and tri.json()["tri_version"] == "v1.2"
    assert len(client.get(f"/api/clients/stakeholders/{sid}/tri", headers=_h("karl")).json()["scorecards"]) == 1

    # Ritual create + complete
    rid = client.post(f"/api/clients/stakeholders/{sid}/rituals",
                      json={"name": "first artefact in her voice"}, headers=_h("karl")).json()["id"]
    done = client.post(f"/api/clients/rituals/{rid}/complete", json={"acknowledged": True}, headers=_h("karl"))
    assert done.status_code == 200 and done.json()["acknowledged"] is True
    # cross-owner can't complete
    assert client.post(f"/api/clients/rituals/{rid}/complete", json={}, headers=_h("cto")).status_code == 404


def test_portfolio_route_not_shadowed_by_client_id(client):
    cid = client.post("/api/clients", json={"name": "RVL Pharma"}, headers=_h("karl")).json()["id"]
    client.post(f"/api/clients/{cid}/stakeholders", json={"name": "Amy"}, headers=_h("karl"))
    r = client.get("/api/clients/portfolio", headers=_h("karl"))
    assert r.status_code == 200, r.text  # not captured by GET /{client_id}
    names = [row["name"] for row in r.json()["portfolio"]]
    assert "Amy" in names
    assert client.get("/api/clients/portfolio", headers=_h("cto")).json()["portfolio"] == []
