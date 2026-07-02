"""Notion sync (src/notion_sync.py) + client-workspace integration.

Pure-unit tests for id parsing/chunking/config, mocked-API tests for page
fetch/create, and service/route tests with the Notion layer stubbed. Throwaway
temp config file + DB; no network.
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
from src import notion_sync
from src import clients as svc
from routes.client_routes import setup_client_routes


@pytest.fixture(autouse=True)
def _sandbox_cfg(monkeypatch, tmp_path):
    monkeypatch.setattr(notion_sync, "_CFG_FILE", str(tmp_path / "notion.json"))
    monkeypatch.delenv("NOTION_TOKEN", raising=False)


@pytest.fixture(autouse=True, scope="module")
def _fresh_db():
    tmp = tempfile.mkdtemp(prefix="odysseus_notion_test_")
    eng = create_engine("sqlite:///" + os.path.join(tmp, "n.db").replace("\\", "/"),
                        connect_args={"check_same_thread": False})
    _db.Base.metadata.create_all(eng)
    orig = _db.engine
    _db.SessionLocal.configure(bind=eng)
    yield
    _db.SessionLocal.configure(bind=orig)


# ── Unit: page-id parsing ───────────────────────────────────────────────────
def test_extract_page_id_forms():
    dashed = "3496bfbd-dc62-8027-aa14-c5f50d5cace9"
    bare = "3496bfbddc628027aa14c5f50d5cace9"
    url = "https://www.notion.so/CM-Strategy-3496bfbddc628027aa14c5f50d5cace9?source=copy_link"
    assert notion_sync.extract_page_id(dashed) == dashed
    assert notion_sync.extract_page_id(bare) == dashed
    assert notion_sync.extract_page_id(url) == dashed
    with pytest.raises(notion_sync.NotionError):
        notion_sync.extract_page_id("https://www.notion.so/no-id-here")
    with pytest.raises(notion_sync.NotionError):
        notion_sync.extract_page_id("")


# ── Unit: block chunking respects Notion limits ─────────────────────────────
def test_chunk_paragraphs_limits():
    blocks = notion_sync._chunk_paragraphs("a" * 4500)  # > 2 * 2000
    assert len(blocks) == 3
    for b in blocks:
        assert b["type"] == "paragraph"
        rt = b["paragraph"]["rich_text"]
        assert not rt or len(rt[0]["text"]["content"]) <= 2000
    # newlines split paragraphs
    assert len(notion_sync._chunk_paragraphs("one\ntwo")) == 2


# ── Unit: config store (token encrypted, never echoed) ─────────────────────
def test_config_roundtrip_and_secrecy():
    assert notion_sync.get_config("karl") == {"configured": False, "parent": None}
    out = notion_sync.set_config("karl", token="secret_abc123", parent="https://notion.so/P-" + "a" * 32)
    assert out["configured"] is True
    assert "secret_abc123" not in json.dumps(out)
    # On disk the token is encrypted (or at minimum not plaintext)
    raw = open(notion_sync._CFG_FILE, encoding="utf-8").read()
    assert "secret_abc123" not in raw
    # Clearing the token deconfigures
    assert notion_sync.set_config("karl", token="")["configured"] is False
    # Per-user isolation
    assert notion_sync.get_config("cto")["configured"] is False


def test_missing_token_raises_helpful_error():
    with pytest.raises(notion_sync.NotionError, match="not connected"):
        notion_sync._get_token("karl")


# ── Mocked-API: fetch_page flattens blocks; create_page batches ────────────
def test_fetch_page_flattens_blocks(monkeypatch):
    notion_sync.set_config("karl", token="tok")
    pid = "3496bfbd-dc62-8027-aa14-c5f50d5cace9"

    async def fake_request(method, path, token, json_body=None, params=None):
        if path.startswith("/pages/"):
            return {"url": "https://notion.so/x", "properties": {
                "title": {"type": "title", "title": [{"plain_text": "S1 — Tech Learning"}]}}}
        return {"results": [
            {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Notes"}]}, "has_children": False},
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Amy said hello."}]}, "has_children": False},
            {"type": "to_do", "to_do": {"checked": True, "rich_text": [{"plain_text": "follow up"}]}, "has_children": False},
            {"type": "image", "image": {}},  # unsupported -> skipped
        ], "has_more": False}

    monkeypatch.setattr(notion_sync, "_request", fake_request)
    page = asyncio.run(notion_sync.fetch_page("karl", pid))
    assert page["title"] == "S1 — Tech Learning"
    assert page["text"] == "# Notes\nAmy said hello.\n[x] follow up"
    assert page["page_id"] == pid


def test_create_page_batches_blocks(monkeypatch):
    notion_sync.set_config("karl", token="tok", parent="b" * 32)
    calls = []

    async def fake_request(method, path, token, json_body=None, params=None):
        calls.append((method, path, len((json_body or {}).get("children", []))))
        return {"id": "new-page", "url": "https://notion.so/new"}

    monkeypatch.setattr(notion_sync, "_request", fake_request)
    content = "\n".join(f"line {i}" for i in range(250))  # 250 blocks -> 100+100+50
    out = asyncio.run(notion_sync.create_page("karl", "Artifact", content))
    assert out == {"page_id": "new-page", "url": "https://notion.so/new"}
    assert calls[0][0] == "POST" and calls[0][2] == 100
    assert [c[2] for c in calls[1:]] == [100, 50]
    assert all(c[0] == "PATCH" for c in calls[1:])


def test_create_page_requires_parent():
    notion_sync.set_config("karl", token="tok")  # no parent configured
    with pytest.raises(notion_sync.NotionError, match="parent page"):
        asyncio.run(notion_sync.create_page("karl", "T", "content"))


# ── Service: ingest dedups by external_ref; owner-scoped ───────────────────
def test_ingest_notion_transcript_dedup(monkeypatch):
    c = svc.create_client("karl", "RVL Pharma")

    async def fake_fetch(owner, ref):
        return {"page_id": "pid-1", "title": "S1", "text": "v1 text", "url": "u"}

    monkeypatch.setattr(notion_sync, "fetch_page", fake_fetch)
    t1 = asyncio.run(svc.ingest_notion_transcript("karl", c["id"], "https://notion.so/x-" + "c" * 32))
    assert t1["updated"] is False and t1["source"] == "notion" and t1["external_ref"] == "pid-1"

    async def fake_fetch2(owner, ref):
        return {"page_id": "pid-1", "title": "S1", "text": "v2 text", "url": "u"}

    monkeypatch.setattr(notion_sync, "fetch_page", fake_fetch2)
    t2 = asyncio.run(svc.ingest_notion_transcript("karl", c["id"], "pid-ignored-" + "c" * 32))
    assert t2["updated"] is True and t2["id"] == t1["id"] and t2["content"] == "v2 text"
    assert len(svc.list_transcripts("karl", c["id"])) == 1
    # cross-owner -> None (client not owned)
    assert asyncio.run(svc.ingest_notion_transcript("cto", c["id"], "x")) is None


# ── Routes: config + ingest + push error paths ──────────────────────────────
@pytest.fixture()
def http():
    app = FastAPI()

    @app.middleware("http")
    async def _set_user(request, call_next):
        request.state.current_user = request.headers.get("x-test-user") or None
        return await call_next(request)

    app.include_router(setup_client_routes())
    return TestClient(app)


def test_notion_routes(http, monkeypatch):
    h = {"x-test-user": "karl"}
    # status: unconfigured
    assert http.get("/api/clients/notion/config", headers=h).json() == {"configured": False, "parent": None}
    # save config (token write-only)
    out = http.post("/api/clients/notion/config", json={"token": "tok", "parent": "p-" + "d" * 32}, headers=h).json()
    assert out["configured"] is True and "tok" not in json.dumps(out)
    # ingest without a reachable API -> stub fetch_page at the service boundary
    cid = http.post("/api/clients", json={"name": "RVL"}, headers=h).json()["id"]

    async def fake_fetch(owner, ref):
        return {"page_id": "pid-9", "title": "T", "text": "body", "url": "u"}

    monkeypatch.setattr(notion_sync, "fetch_page", fake_fetch)
    t = http.post(f"/api/clients/{cid}/transcripts/notion", json={"page": "e" * 32}, headers=h)
    assert t.status_code == 200 and t.json()["source"] == "notion"
    # push with no token for another user -> 400 with guidance
    r = http.post("/api/clients/notion/push", json={"title": "A", "content": "x"},
                  headers={"x-test-user": "cto"})
    assert r.status_code == 400 and "not connected" in r.json()["detail"]
