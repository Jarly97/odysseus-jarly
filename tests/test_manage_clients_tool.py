"""Phase 01/04 — the manage_clients agent tool (src.tool_implementations.do_manage_clients).

Drives the tool the way the agent loop does: a JSON args string + owner, dispatched
by action. Verifies owner-scoping and the methodology wiring. Throwaway temp DB.
"""
import asyncio
import json
import os
import tempfile

import pytest
from sqlalchemy import create_engine

import core.database as _db
from src.tool_implementations import do_manage_clients


@pytest.fixture(autouse=True, scope="module")
def _fresh_db():
    tmp = tempfile.mkdtemp(prefix="odysseus_mc_tool_test_")
    eng = create_engine("sqlite:///" + os.path.join(tmp, "tool.db").replace("\\", "/"),
                        connect_args={"check_same_thread": False})
    _db.Base.metadata.create_all(eng)
    orig = _db.engine
    _db.SessionLocal.configure(bind=eng)
    yield
    _db.SessionLocal.configure(bind=orig)


def call(args, owner="karl"):
    return asyncio.run(do_manage_clients(json.dumps(args), owner=owner))


def test_create_list_and_owner_scope():
    c = call({"action": "create_client", "name": "RVL Pharma", "sector": "pharma"})
    assert c["id"] and c["model_policy"] == "local-sensitive"
    assert [x["name"] for x in call({"action": "list_clients"})["clients"]] == ["RVL Pharma"]
    # cross-owner isolation
    assert call({"action": "list_clients"}, owner="cto")["clients"] == []
    assert call({"action": "get_client", "client_id": c["id"]}, owner="cto") == {"error": "Client not found"}


def test_stakeholder_itm_tri_frames_portfolio():
    c = call({"action": "create_client", "name": "RVL"})
    s = call({"action": "add_stakeholder", "client_id": c["id"], "name": "Amy",
              "archetype": "Authority Expert"})
    assert s["name"] == "Amy"
    itm = call({"action": "upsert_itm", "stakeholder_id": s["id"],
                "current_identity": "growth visionary", "transition_stage": "moving"})
    assert itm["current_identity"] == "growth visionary"
    # TRI total auto-derives stage via methodology
    tri = call({"action": "add_tri", "stakeholder_id": s["id"], "total": 20, "tri_version": "v1.2"})
    assert tri["stage"] == "moving"
    # frames recommended from archetype + stage
    fr = call({"action": "recommend_frames", "stakeholder_id": s["id"]})
    assert [f["id"] for f in fr["frames"]] == ["M5"]
    # portfolio surfaces the stakeholder
    assert any(r["name"] == "Amy" for r in call({"action": "portfolio"})["portfolio"])


def test_bad_inputs():
    assert "Unknown action" in call({"action": "frobnicate"})["error"]
    assert call({"action": "create_client", "name": ""})["error"]  # ValueError -> error dict
    assert do_invalid_json() == {"error": "Invalid JSON arguments", "exit_code": 1}


def test_delete_actions_refused_and_nothing_deleted():
    """QA hardening: deletes are a prompt-injection data-loss vector — the agent
    tool must refuse them and the data must survive."""
    c = call({"action": "create_client", "name": "KeepMe"})
    s = call({"action": "add_stakeholder", "client_id": c["id"], "name": "Amy"})
    for args in (
        {"action": "delete_client", "client_id": c["id"]},
        {"action": "delete_stakeholder", "stakeholder_id": s["id"]},
        {"action": "delete_transcript", "transcript_id": "whatever"},
    ):
        out = call(args)
        assert "not available to the agent" in out.get("error", ""), args
    # Data untouched
    assert call({"action": "get_client", "client_id": c["id"]})["name"] == "KeepMe"
    names = [x["name"] for x in call({"action": "list_stakeholders", "client_id": c["id"]})["stakeholders"]]
    assert names == ["Amy"]


def test_delete_actions_not_in_tool_schema():
    # Import via agent_tools (the app's import order) — importing tool_schemas
    # first trips its circular import with agent_tools.
    from src.agent_tools import FUNCTION_TOOL_SCHEMAS
    tool = next(t for t in FUNCTION_TOOL_SCHEMAS if t["function"]["name"] == "manage_clients")
    actions = tool["function"]["parameters"]["properties"]["action"]["enum"]
    for banned in ("delete_client", "delete_stakeholder", "delete_transcript"):
        assert banned not in actions
    for kept in ("notion_ingest", "notion_push", "synthesize", "portfolio"):
        assert kept in actions


def test_manage_clients_blocked_for_non_admin():
    """Confidential client data: the tool is admin/single-user only until
    per-client RBAC exists (same class as manage_memory/manage_calendar)."""
    from src.tool_security import is_public_blocked_tool
    assert is_public_blocked_tool("manage_clients") is True


def do_invalid_json():
    return asyncio.run(do_manage_clients("{not json", owner="karl"))
