"""Phase 01 — Client workspace service layer (src/clients.py).

Owner-scoped CRUD, ITM upsert, TRI/ritual creation, cross-owner isolation, and
the portfolio roll-up ordering. Throwaway temp DB; never touches data/app.db.
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine

import core.database as _db
from src import clients as svc


@pytest.fixture(autouse=True, scope="module")
def _fresh_db():
    """Bind SessionLocal to a throwaway DB for this module, then restore — so the
    suite stays isolated regardless of import order, without polluting other tests."""
    tmp = tempfile.mkdtemp(prefix="odysseus_clients_test_")
    eng = create_engine("sqlite:///" + os.path.join(tmp, "svc.db").replace("\\", "/"),
                        connect_args={"check_same_thread": False})
    _db.Base.metadata.create_all(eng)
    orig = _db.engine
    _db.SessionLocal.configure(bind=eng)
    yield
    _db.SessionLocal.configure(bind=orig)


def test_create_and_owner_isolation():
    a = svc.create_client("karl", "RVL Pharma", sector="pharma")
    svc.create_client("cto", "Other Co")
    # Karl sees only his own client (strict scoping — no shared fall-through).
    karl = svc.list_clients("karl")
    assert [c["name"] for c in karl] == ["RVL Pharma"]
    assert a["model_policy"] == "local-sensitive"  # confidential default
    # CTO cannot fetch Karl's client.
    assert svc.get_client("cto", a["id"]) is None
    assert svc.get_client("karl", a["id"])["name"] == "RVL Pharma"


def test_stakeholder_requires_owned_client():
    c = svc.create_client("karl", "RVL Pharma")
    # Wrong owner can't attach a stakeholder.
    assert svc.add_stakeholder("cto", c["id"], "Amy Shah") is None
    s = svc.add_stakeholder("karl", c["id"], "Amy Shah", role="CGO",
                            archetype="Authority Expert")
    assert s["name"] == "Amy Shah"
    assert svc.list_stakeholders("karl", c["id"])[0]["id"] == s["id"]
    assert svc.list_stakeholders("cto", c["id"]) is None


def test_itm_upsert_and_stage_sync():
    c = svc.create_client("karl", "RVL Pharma")
    s = svc.add_stakeholder("karl", c["id"], "Amy Shah")
    itm1 = svc.upsert_itm("karl", s["id"], current_identity="growth visionary",
                          expected_loss="rainmaker loop", open_loss_flag=True)
    assert itm1["current_identity"] == "growth visionary"
    # Second upsert updates the same record (no duplicate) and syncs stage.
    itm2 = svc.upsert_itm("karl", s["id"], transition_stage="moving",
                          target_identity="AI-amplified growth architect")
    assert itm1["id"] == itm2["id"]
    assert itm2["transition_stage"] == "moving"
    assert svc.list_stakeholders("karl", c["id"])[0]["transition_stage"] == "moving"
    assert svc.get_itm("cto", s["id"]) is None  # cross-owner blocked


def test_tri_sets_stage_and_lists():
    c = svc.create_client("karl", "RVL Pharma")
    s = svc.add_stakeholder("karl", c["id"], "Amy Shah")
    t = svc.add_tri("karl", s["id"], cycle="Day 0", total=14, stage="stuck",
                    direction="flat", tri_version="v1.2",
                    scores={"1": {"score": 1}})
    assert t["tri_version"] == "v1.2"
    assert svc.list_stakeholders("karl", c["id"])[0]["transition_stage"] == "stuck"
    assert len(svc.list_tri("karl", s["id"])) == 1
    assert svc.add_tri("cto", s["id"], cycle="Day 0") is None


def test_rituals():
    c = svc.create_client("karl", "RVL Pharma")
    s = svc.add_stakeholder("karl", c["id"], "Amy Shah")
    r = svc.add_ritual("karl", s["id"], "first artefact in her voice")
    assert r["acknowledged"] is False and r["completed_at"] is None
    done = svc.complete_ritual("karl", r["id"], acknowledged=True)
    assert done["acknowledged"] is True and done["completed_at"] is not None
    assert svc.complete_ritual("cto", r["id"]) is None


def test_portfolio_ordering():
    # Stuck sorts before moving; within a stage, soonest next_ritual_due first.
    c = svc.create_client("karl", "RVL Pharma")
    moving = svc.add_stakeholder("karl", c["id"], "Trill", transition_stage="moving")
    stuck_late = svc.add_stakeholder("karl", c["id"], "Becky")
    stuck_soon = svc.add_stakeholder("karl", c["id"], "Tracy")
    svc.upsert_itm("karl", stuck_late["id"], transition_stage="stuck",
                   next_ritual_due=datetime.utcnow() + timedelta(days=10))
    svc.upsert_itm("karl", stuck_soon["id"], transition_stage="stuck",
                   next_ritual_due=datetime.utcnow() + timedelta(days=1))
    svc.upsert_itm("karl", moving["id"], transition_stage="moving")

    names = [r["name"] for r in svc.portfolio("karl")]
    # Both stuck before the moving one; soonest-due stuck first.
    assert names.index("Tracy") < names.index("Becky") < names.index("Trill")
    # Portfolio is owner-scoped.
    assert svc.portfolio("cto") == []
