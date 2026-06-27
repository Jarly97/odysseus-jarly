# routes/client_routes.py
"""Client workspace API (Buildout Phase 01).

Owner-scoped REST surface over src.clients for the methodology-native model:
Client -> Stakeholder -> ITM / TRI / Bridging Ritual, plus the portfolio
roll-up. Client data is confidential, so every handler resolves the caller via
require_user and the service layer scopes strictly to that owner. A row the
caller doesn't own returns 404 (never leak existence).
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.auth_helpers import require_user
from src import clients as svc
from src import methodology

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #
class ClientCreate(BaseModel):
    name: str
    sponsor: Optional[str] = None
    sector: Optional[str] = None
    model_policy: str = "local-sensitive"
    notes: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    sponsor: Optional[str] = None
    sector: Optional[str] = None
    status: Optional[str] = None
    model_policy: Optional[str] = None
    notes: Optional[str] = None


class StakeholderCreate(BaseModel):
    name: str
    role: Optional[str] = None
    archetype: Optional[str] = None
    transition_stage: str = "unknown"


class ITMUpsert(BaseModel):
    current_identity: Optional[str] = None
    target_identity: Optional[str] = None
    expected_loss: Optional[str] = None
    target_gain: Optional[str] = None
    bridging_rituals: Optional[str] = None
    transition_stage: Optional[str] = None
    open_loss_flag: Optional[bool] = None
    operator: Optional[str] = None
    assessment_note: Optional[str] = None
    next_ritual_due: Optional[str] = None  # ISO datetime
    date_completed: Optional[str] = None   # ISO datetime


class TRICreate(BaseModel):
    cycle: Optional[str] = None
    scores: Optional[dict] = None
    total: Optional[int] = None
    stage: Optional[str] = None
    direction: Optional[str] = None
    tri_version: Optional[str] = None
    operator: Optional[str] = None
    priority_action: Optional[str] = None


class RitualCreate(BaseModel):
    name: str
    scheduled_at: Optional[str] = None  # ISO datetime
    note: Optional[str] = None


class RitualComplete(BaseModel):
    acknowledged: bool = False


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise HTTPException(400, f"Invalid datetime: {value!r} (expected ISO 8601)")


def setup_client_routes():
    router = APIRouter(prefix="/api/clients", tags=["clients"])

    # ----- Portfolio roll-up (declare BEFORE /{client_id} so it isn't captured) -----
    @router.get("/portfolio")
    def get_portfolio(request: Request):
        user = require_user(request)
        return {"portfolio": svc.portfolio(user)}

    # ----- Methodology reference (declare BEFORE /{client_id}) -----
    @router.get("/methodology")
    def methodology_reference(request: Request):
        require_user(request)
        return {
            "itm_dimensions": list(methodology.ITM_DIMENSIONS),
            "stages": list(methodology.STAGES),
            "archetypes": list(methodology.ARCHETYPES),
            "frames": {fid: {"stage_group": g, "title": t}
                       for fid, (g, t) in methodology.FRAMES.items()},
            "avoid_frames": list(methodology.AVOID_FRAMES),
        }

    @router.get("/methodology/frames")
    def methodology_frames(request: Request, archetype: Optional[str] = None,
                           stage: Optional[str] = None):
        require_user(request)
        return {
            "archetype": archetype, "stage": stage,
            "frames": methodology.select_frames(archetype, stage),
            "avoid": list(methodology.AVOID_FRAMES),
        }

    @router.get("/methodology/tri/{total}")
    def methodology_tri(request: Request, total: int):
        require_user(request)
        stage = methodology.tri_stage(total)
        return {"total": total, "stage": stage,
                "recommended_action": methodology.recommended_action(stage)}

    # ----- Clients -----
    @router.get("")
    def list_clients(request: Request):
        user = require_user(request)
        return {"clients": svc.list_clients(user)}

    @router.post("")
    def create_client(request: Request, body: ClientCreate):
        user = require_user(request)
        try:
            return svc.create_client(user, body.name, sponsor=body.sponsor,
                                     sector=body.sector, model_policy=body.model_policy,
                                     notes=body.notes)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @router.get("/{client_id}")
    def get_client(request: Request, client_id: str):
        user = require_user(request)
        c = svc.get_client(user, client_id)
        if not c:
            raise HTTPException(404, "Client not found")
        return c

    @router.put("/{client_id}")
    def update_client(request: Request, client_id: str, body: ClientUpdate):
        user = require_user(request)
        c = svc.update_client(user, client_id, **body.model_dump(exclude_unset=True))
        if not c:
            raise HTTPException(404, "Client not found")
        return c

    @router.delete("/{client_id}")
    def delete_client(request: Request, client_id: str):
        user = require_user(request)
        if not svc.delete_client(user, client_id):
            raise HTTPException(404, "Client not found")
        return {"ok": True}

    # ----- Stakeholders -----
    @router.get("/{client_id}/stakeholders")
    def list_stakeholders(request: Request, client_id: str):
        user = require_user(request)
        rows = svc.list_stakeholders(user, client_id)
        if rows is None:
            raise HTTPException(404, "Client not found")
        return {"stakeholders": rows}

    @router.post("/{client_id}/stakeholders")
    def add_stakeholder(request: Request, client_id: str, body: StakeholderCreate):
        user = require_user(request)
        try:
            s = svc.add_stakeholder(user, client_id, body.name, role=body.role,
                                    archetype=body.archetype,
                                    transition_stage=body.transition_stage)
        except ValueError as e:
            raise HTTPException(400, str(e))
        if s is None:
            raise HTTPException(404, "Client not found")
        return s

    # ----- ITM (one per stakeholder) -----
    @router.get("/stakeholders/{stakeholder_id}/itm")
    def get_itm(request: Request, stakeholder_id: str):
        user = require_user(request)
        # Distinguish "no ITM yet" (200 null) from "not your stakeholder" (404)
        # by checking ownership via the stakeholder list path is overkill; the
        # service returns None for both, so treat missing as 404 only when the
        # stakeholder itself is inaccessible. get_itm returns None in both cases;
        # callers create via PUT, so a plain null here is acceptable.
        itm = svc.get_itm(user, stakeholder_id)
        return itm or {}

    @router.put("/stakeholders/{stakeholder_id}/itm")
    def upsert_itm(request: Request, stakeholder_id: str, body: ITMUpsert):
        user = require_user(request)
        fields = body.model_dump(exclude_unset=True)
        if "next_ritual_due" in fields:
            fields["next_ritual_due"] = _parse_dt(fields["next_ritual_due"])
        if "date_completed" in fields:
            fields["date_completed"] = _parse_dt(fields["date_completed"])
        itm = svc.upsert_itm(user, stakeholder_id, **fields)
        if itm is None:
            raise HTTPException(404, "Stakeholder not found")
        return itm

    # ----- TRI scorecards -----
    @router.get("/stakeholders/{stakeholder_id}/tri")
    def list_tri(request: Request, stakeholder_id: str):
        user = require_user(request)
        rows = svc.list_tri(user, stakeholder_id)
        if rows is None:
            raise HTTPException(404, "Stakeholder not found")
        return {"scorecards": rows}

    @router.post("/stakeholders/{stakeholder_id}/tri")
    def add_tri(request: Request, stakeholder_id: str, body: TRICreate):
        user = require_user(request)
        t = svc.add_tri(user, stakeholder_id, cycle=body.cycle, scores=body.scores,
                        total=body.total, stage=body.stage, direction=body.direction,
                        tri_version=body.tri_version, operator=body.operator,
                        priority_action=body.priority_action)
        if t is None:
            raise HTTPException(404, "Stakeholder not found")
        return t

    # ----- Recommended comms frames for a stakeholder -----
    @router.get("/stakeholders/{stakeholder_id}/frames")
    def stakeholder_frames(request: Request, stakeholder_id: str):
        user = require_user(request)
        rec = svc.recommend_frames(user, stakeholder_id)
        if rec is None:
            raise HTTPException(404, "Stakeholder not found")
        return rec

    # ----- Bridging rituals -----
    @router.post("/stakeholders/{stakeholder_id}/rituals")
    def add_ritual(request: Request, stakeholder_id: str, body: RitualCreate):
        user = require_user(request)
        try:
            r = svc.add_ritual(user, stakeholder_id, body.name,
                               scheduled_at=_parse_dt(body.scheduled_at), note=body.note)
        except ValueError as e:
            raise HTTPException(400, str(e))
        if r is None:
            raise HTTPException(404, "Stakeholder not found")
        return r

    @router.post("/rituals/{ritual_id}/complete")
    def complete_ritual(request: Request, ritual_id: str, body: RitualComplete):
        user = require_user(request)
        r = svc.complete_ritual(user, ritual_id, acknowledged=body.acknowledged)
        if r is None:
            raise HTTPException(404, "Ritual not found")
        return r

    return router
