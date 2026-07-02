"""Notion sync for the CM client workspace (Buildout Phase 03).

Two flows, matching the vision's Notion-as-hub model:
  - INGEST: fetch a Notion page (meeting transcript) as plain text so it can be
    saved as a MeetingTranscript for a client.
  - PUSH: create a Notion page under a parent with a synthesized artifact's
    content, so the team sees deliverables in the shared workspace.

Config is per-user in data/notion.json — the integration token is encrypted at
rest via src.secret_storage (same approach as the Cookbook HF token) and is
write-only through the API (status endpoints never return it). Falls back to
the NOTION_TOKEN env var when no per-user token is stored.

The Notion REST API host is a fixed constant (never user-supplied), so no SSRF
surface is introduced here.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

import httpx

from core.atomic_io import atomic_write_json
from core.constants import DATA_DIR
from src.secret_storage import encrypt, decrypt

logger = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
_CFG_FILE = os.path.join(DATA_DIR, "notion.json")

# Notion hard limits.
_MAX_RICH_TEXT = 2000      # chars per rich_text object
_MAX_BLOCKS_PER_REQ = 100  # blocks per create/append request
_MAX_DEPTH = 3             # how deep we recurse into nested blocks on ingest


class NotionError(ValueError):
    """User-facing Notion failure (config, auth, or API) — maps to HTTP 400."""


# ── Config (per-user, token encrypted at rest) ─────────────────────────────
def _load_cfg() -> dict:
    try:
        with open(_CFG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def set_config(owner: str, token: Optional[str] = None, parent: Optional[str] = None) -> dict:
    """Store the user's Notion token (encrypted) and/or default parent page.
    Empty-string token clears it. Returns the public status dict."""
    cfg = _load_cfg()
    entry = cfg.get(owner or "", {})
    if token is not None:
        entry["token"] = encrypt(token) if token else ""
    if parent is not None:
        entry["parent"] = parent.strip()
    cfg[owner or ""] = entry
    atomic_write_json(_CFG_FILE, cfg, indent=2)
    return get_config(owner)


def get_config(owner: str) -> dict:
    """Public status only — never returns the token itself."""
    entry = _load_cfg().get(owner or "", {})
    has_token = bool(entry.get("token")) or bool(os.getenv("NOTION_TOKEN"))
    return {"configured": has_token, "parent": entry.get("parent") or None}


def _get_token(owner: str) -> str:
    entry = _load_cfg().get(owner or "", {})
    tok = decrypt(entry.get("token") or "") or os.getenv("NOTION_TOKEN", "")
    if not tok:
        raise NotionError(
            "Notion is not connected. Add your Notion integration token in the "
            "Clients panel settings (gear icon), and share the relevant pages "
            "with that integration in Notion.")
    return tok


def _default_parent(owner: str) -> Optional[str]:
    return _load_cfg().get(owner or "", {}).get("parent") or None


# ── Page-id parsing ─────────────────────────────────────────────────────────
_HEX32 = re.compile(r"([0-9a-f]{32})", re.IGNORECASE)
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


def extract_page_id(url_or_id: str) -> str:
    """Accept a notion.so/notion.site URL, a dashed UUID, or a bare 32-hex id
    and return the dashed UUID form the API expects."""
    s = (url_or_id or "").strip()
    if not s:
        raise NotionError("A Notion page URL or id is required")
    if _UUID.match(s):
        return s.lower()
    # URLs put the 32-hex id at the tail of the slug; query params may follow.
    m = None
    for m in _HEX32.finditer(s.split("?")[0].replace("-", "")):
        pass  # keep the LAST match — titles can contain hex-looking runs
    if not m:
        raise NotionError(f"Could not find a Notion page id in: {url_or_id!r}")
    h = m.group(1).lower()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


# ── HTTP core ───────────────────────────────────────────────────────────────
def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


async def _request(method: str, path: str, token: str, json_body: Optional[dict] = None,
                   params: Optional[dict] = None) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.request(method, f"{NOTION_API}{path}", headers=_headers(token),
                                   json=json_body, params=params)
    if res.status_code == 401:
        raise NotionError("Notion rejected the token (401) — re-create the integration token.")
    if res.status_code == 404:
        raise NotionError("Notion page not found (404) — check the link, and make sure the "
                          "page is shared with your integration (Share → Add connections).")
    if res.status_code >= 400:
        try:
            msg = res.json().get("message", "")
        except Exception:
            msg = res.text[:200]
        raise NotionError(f"Notion API error ({res.status_code}): {msg}")
    return res.json()


# ── Ingest: page -> plain text ──────────────────────────────────────────────
def _rich_text_to_str(rich: list) -> str:
    return "".join((r.get("plain_text") or "") for r in (rich or []))


_BLOCK_PREFIX = {
    "heading_1": "# ",
    "heading_2": "## ",
    "heading_3": "### ",
    "bulleted_list_item": "- ",
    "numbered_list_item": "- ",
    "quote": "> ",
    "toggle": "- ",
    "callout": "> ",
}


def _block_to_line(block: dict) -> Optional[str]:
    btype = block.get("type") or ""
    payload = block.get(btype) or {}
    if btype == "to_do":
        mark = "[x]" if payload.get("checked") else "[ ]"
        return f"{mark} {_rich_text_to_str(payload.get('rich_text'))}"
    if btype == "code":
        return _rich_text_to_str(payload.get("rich_text"))
    if btype == "divider":
        return "---"
    if btype in ("child_page",):
        return None  # don't inline child pages into a transcript
    rich = payload.get("rich_text")
    if rich is None:
        return None  # unsupported block types (images, embeds, ...) are skipped
    text = _rich_text_to_str(rich)
    return (_BLOCK_PREFIX.get(btype, "") + text) if text else None


async def _fetch_children_text(token: str, block_id: str, depth: int = 0) -> list:
    lines: list = []
    cursor = None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        data = await _request("GET", f"/blocks/{block_id}/children", token, params=params)
        for block in data.get("results", []):
            line = _block_to_line(block)
            if line is not None:
                lines.append(("  " * depth) + line if depth else line)
            if block.get("has_children") and depth < _MAX_DEPTH and block.get("type") != "child_page":
                lines.extend(await _fetch_children_text(token, block["id"], depth + 1))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return lines


def _page_title(page: dict) -> str:
    for prop in (page.get("properties") or {}).values():
        if prop.get("type") == "title":
            return _rich_text_to_str(prop.get("title")) or "Untitled"
    return "Untitled"


async def fetch_page(owner: str, url_or_id: str) -> dict:
    """Fetch a Notion page as {'page_id', 'title', 'text', 'url'}."""
    token = _get_token(owner)
    page_id = extract_page_id(url_or_id)
    page = await _request("GET", f"/pages/{page_id}", token)
    lines = await _fetch_children_text(token, page_id)
    return {
        "page_id": page_id,
        "title": _page_title(page),
        "text": "\n".join(lines).strip(),
        "url": page.get("url") or url_or_id,
    }


# ── Push: artifact -> new Notion page ───────────────────────────────────────
def _chunk_paragraphs(content: str) -> list:
    """Split artifact text into Notion paragraph blocks respecting the
    2000-char rich_text limit (splitting on newlines first)."""
    blocks = []
    for para in (content or "").split("\n"):
        seg = para
        while True:
            piece, seg = seg[:_MAX_RICH_TEXT], seg[_MAX_RICH_TEXT:]
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": piece}}] if piece else []},
            })
            if not seg:
                break
    return blocks


async def create_page(owner: str, title: str, content: str,
                      parent: Optional[str] = None) -> dict:
    """Create a Notion page under `parent` (or the configured default) holding
    `content` as paragraphs. Returns {'page_id', 'url'}."""
    token = _get_token(owner)
    parent_ref = parent or _default_parent(owner)
    if not parent_ref:
        raise NotionError(
            "No Notion parent page set. Pass one, or save a default parent page "
            "in the Clients panel settings (gear icon).")
    parent_id = extract_page_id(parent_ref)
    blocks = _chunk_paragraphs(content)
    first, rest = blocks[:_MAX_BLOCKS_PER_REQ], blocks[_MAX_BLOCKS_PER_REQ:]
    page = await _request("POST", "/pages", token, json_body={
        "parent": {"page_id": parent_id},
        "properties": {"title": {"title": [{"type": "text", "text": {"content": (title or "Untitled")[:200]}}]}},
        "children": first,
    })
    page_id = page.get("id")
    while rest:
        batch, rest = rest[:_MAX_BLOCKS_PER_REQ], rest[_MAX_BLOCKS_PER_REQ:]
        await _request("PATCH", f"/blocks/{page_id}/children", token, json_body={"children": batch})
    return {"page_id": page_id, "url": page.get("url")}
