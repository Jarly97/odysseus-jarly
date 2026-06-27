"""Client workspace service layer (Buildout Phase 01).

Owner-scoped CRUD over the methodology-native data model (Client / Stakeholder /
ITM / TRI / Bridging Ritual) plus the portfolio roll-up the operator triages
from. Client data is confidential, so scoping here is STRICT (creator-owned, no
null-owner "shared" fall-through) — unlike the default app-wide owner_filter.
Per-client team membership/RBAC (so a teammate can be granted access) is the
next layer and is intentionally not here yet.

All functions take the resolved username `user` for scoping. An empty `user`
(single-user / AUTH_ENABLED=false) disables scoping, matching the rest of the app.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from core.database import (
    get_db_session,
    Client,
    ClientStakeholder,
    ITMRecord,
    TRIScorecard,
    BridgingRitual,
)
from src import methodology

# Stage ordering for the portfolio roll-up: stuck first, unknown last.
_STAGE_ORDER = {"stuck": 0, "at-risk": 1, "moving": 2, "landing": 3, "landed": 4, "unknown": 5}


def _new_id() -> str:
    return uuid.uuid4().hex


def _scoped(query, model_cls, user: str):
    """Strict owner scope: only the user's own rows. No-op in single-user mode."""
    if not user:
        return query
    return query.filter(model_cls.owner == user)


def _client_dict(c: Client) -> dict:
    return {
        "id": c.id, "name": c.name, "sponsor": c.sponsor, "sector": c.sector,
        "status": c.status, "model_policy": c.model_policy, "notes": c.notes,
        "owner": c.owner,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _stakeholder_dict(s: ClientStakeholder) -> dict:
    return {
        "id": s.id, "client_id": s.client_id, "name": s.name, "role": s.role,
        "archetype": s.archetype, "transition_stage": s.transition_stage,
        "owner": s.owner,
    }


def _itm_dict(i: ITMRecord) -> dict:
    return {
        "id": i.id, "stakeholder_id": i.stakeholder_id, "client_id": i.client_id,
        "current_identity": i.current_identity, "target_identity": i.target_identity,
        "expected_loss": i.expected_loss, "target_gain": i.target_gain,
        "bridging_rituals": i.bridging_rituals, "transition_stage": i.transition_stage,
        "date_completed": i.date_completed.isoformat() if i.date_completed else None,
        "last_reviewed": i.last_reviewed.isoformat() if i.last_reviewed else None,
        "next_ritual_due": i.next_ritual_due.isoformat() if i.next_ritual_due else None,
        "open_loss_flag": i.open_loss_flag, "operator": i.operator,
        "assessment_note": i.assessment_note, "owner": i.owner,
    }


def _tri_dict(t: TRIScorecard) -> dict:
    return {
        "id": t.id, "stakeholder_id": t.stakeholder_id, "client_id": t.client_id,
        "cycle": t.cycle,
        "administered_at": t.administered_at.isoformat() if t.administered_at else None,
        "scores": t.scores, "total": t.total, "stage": t.stage, "direction": t.direction,
        "tri_version": t.tri_version, "operator": t.operator,
        "priority_action": t.priority_action, "owner": t.owner,
    }


def _ritual_dict(r: BridgingRitual) -> dict:
    return {
        "id": r.id, "stakeholder_id": r.stakeholder_id, "client_id": r.client_id,
        "name": r.name,
        "designed_at": r.designed_at.isoformat() if r.designed_at else None,
        "scheduled_at": r.scheduled_at.isoformat() if r.scheduled_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "acknowledged": r.acknowledged, "note": r.note, "owner": r.owner,
    }


# --------------------------------------------------------------------------- #
# Clients
# --------------------------------------------------------------------------- #
def create_client(user: str, name: str, sponsor: Optional[str] = None,
                  sector: Optional[str] = None, model_policy: str = "local-sensitive",
                  notes: Optional[str] = None) -> dict:
    if not name or not name.strip():
        raise ValueError("Client name is required")
    with get_db_session() as db:
        c = Client(id=_new_id(), name=name.strip(), sponsor=sponsor, sector=sector,
                   status="active", model_policy=model_policy, notes=notes,
                   owner=(user or None))
        db.add(c)
        db.flush()
        return _client_dict(c)


def list_clients(user: str) -> list[dict]:
    with get_db_session() as db:
        q = _scoped(db.query(Client), Client, user).order_by(Client.name)
        return [_client_dict(c) for c in q.all()]


def get_client(user: str, client_id: str) -> Optional[dict]:
    with get_db_session() as db:
        c = _scoped(db.query(Client).filter(Client.id == client_id), Client, user).first()
        return _client_dict(c) if c else None


def _owned_client(db, user: str, client_id: str) -> Optional[Client]:
    return _scoped(db.query(Client).filter(Client.id == client_id), Client, user).first()


def update_client(user: str, client_id: str, **fields) -> Optional[dict]:
    allowed = {"name", "sponsor", "sector", "status", "model_policy", "notes"}
    with get_db_session() as db:
        c = _owned_client(db, user, client_id)
        if not c:
            return None
        for k, v in fields.items():
            if k in allowed and v is not None:
                setattr(c, k, v)
        db.flush()
        return _client_dict(c)


def delete_client(user: str, client_id: str) -> bool:
    with get_db_session() as db:
        c = _owned_client(db, user, client_id)
        if not c:
            return False
        db.delete(c)  # FK cascade removes stakeholders + their ITM/TRI/rituals
        return True


# --------------------------------------------------------------------------- #
# Stakeholders
# --------------------------------------------------------------------------- #
def add_stakeholder(user: str, client_id: str, name: str, role: Optional[str] = None,
                    archetype: Optional[str] = None, transition_stage: str = "unknown") -> Optional[dict]:
    if not name or not name.strip():
        raise ValueError("Stakeholder name is required")
    with get_db_session() as db:
        if not _owned_client(db, user, client_id):
            return None  # client not found / not owned
        s = ClientStakeholder(id=_new_id(), client_id=client_id, name=name.strip(),
                              role=role, archetype=archetype,
                              transition_stage=transition_stage, owner=(user or None))
        db.add(s)
        db.flush()
        return _stakeholder_dict(s)


def list_stakeholders(user: str, client_id: str) -> Optional[list[dict]]:
    with get_db_session() as db:
        if not _owned_client(db, user, client_id):
            return None
        q = db.query(ClientStakeholder).filter(ClientStakeholder.client_id == client_id)
        return [_stakeholder_dict(s) for s in q.order_by(ClientStakeholder.name).all()]


def _owned_stakeholder(db, user: str, stakeholder_id: str) -> Optional[ClientStakeholder]:
    return _scoped(
        db.query(ClientStakeholder).filter(ClientStakeholder.id == stakeholder_id),
        ClientStakeholder, user,
    ).first()


# --------------------------------------------------------------------------- #
# ITM — one per stakeholder (upsert)
# --------------------------------------------------------------------------- #
_ITM_FIELDS = {"current_identity", "target_identity", "expected_loss", "target_gain",
               "bridging_rituals", "transition_stage", "open_loss_flag", "operator",
               "assessment_note", "next_ritual_due", "date_completed"}


def upsert_itm(user: str, stakeholder_id: str, **fields) -> Optional[dict]:
    with get_db_session() as db:
        s = _owned_stakeholder(db, user, stakeholder_id)
        if not s:
            return None
        itm = db.query(ITMRecord).filter(ITMRecord.stakeholder_id == stakeholder_id).first()
        if not itm:
            itm = ITMRecord(id=_new_id(), stakeholder_id=stakeholder_id,
                            client_id=s.client_id, owner=(user or None))
            db.add(itm)
        for k, v in fields.items():
            if k in _ITM_FIELDS and v is not None:
                setattr(itm, k, v)
        itm.last_reviewed = datetime.utcnow()
        # Keep the stakeholder's denormalized stage in sync with the ITM.
        if fields.get("transition_stage"):
            s.transition_stage = fields["transition_stage"]
        db.flush()
        return _itm_dict(itm)


def get_itm(user: str, stakeholder_id: str) -> Optional[dict]:
    with get_db_session() as db:
        if not _owned_stakeholder(db, user, stakeholder_id):
            return None
        itm = db.query(ITMRecord).filter(ITMRecord.stakeholder_id == stakeholder_id).first()
        return _itm_dict(itm) if itm else None


# --------------------------------------------------------------------------- #
# TRI scorecards
# --------------------------------------------------------------------------- #
def add_tri(user: str, stakeholder_id: str, cycle: Optional[str] = None,
            scores: Optional[dict] = None, total: Optional[int] = None,
            stage: Optional[str] = None, direction: Optional[str] = None,
            tri_version: Optional[str] = None, operator: Optional[str] = None,
            priority_action: Optional[str] = None) -> Optional[dict]:
    with get_db_session() as db:
        s = _owned_stakeholder(db, user, stakeholder_id)
        if not s:
            return None
        # Derive the stage from the TRI total when the caller didn't supply one
        # (TRI v1.2 scoring bands), so the scorecard and stakeholder stay in sync.
        if stage is None and total is not None:
            stage = methodology.tri_stage(total)
        t = TRIScorecard(id=_new_id(), stakeholder_id=stakeholder_id, client_id=s.client_id,
                         cycle=cycle, administered_at=datetime.utcnow(),
                         scores=scores or {}, total=total, stage=stage, direction=direction,
                         tri_version=tri_version, operator=operator,
                         priority_action=priority_action, owner=(user or None))
        db.add(t)
        if stage:
            s.transition_stage = stage  # latest TRI stage drives the stakeholder's stage
        db.flush()
        return _tri_dict(t)


def list_tri(user: str, stakeholder_id: str) -> Optional[list[dict]]:
    with get_db_session() as db:
        if not _owned_stakeholder(db, user, stakeholder_id):
            return None
        q = db.query(TRIScorecard).filter(TRIScorecard.stakeholder_id == stakeholder_id)
        return [_tri_dict(t) for t in q.order_by(TRIScorecard.administered_at).all()]


# --------------------------------------------------------------------------- #
# Bridging rituals
# --------------------------------------------------------------------------- #
def add_ritual(user: str, stakeholder_id: str, name: str,
               scheduled_at: Optional[datetime] = None, note: Optional[str] = None) -> Optional[dict]:
    if not name or not name.strip():
        raise ValueError("Ritual name is required")
    with get_db_session() as db:
        s = _owned_stakeholder(db, user, stakeholder_id)
        if not s:
            return None
        r = BridgingRitual(id=_new_id(), stakeholder_id=stakeholder_id, client_id=s.client_id,
                           name=name.strip(), designed_at=datetime.utcnow(),
                           scheduled_at=scheduled_at, note=note, owner=(user or None))
        db.add(r)
        db.flush()
        return _ritual_dict(r)


def complete_ritual(user: str, ritual_id: str, acknowledged: bool = False) -> Optional[dict]:
    with get_db_session() as db:
        r = _scoped(db.query(BridgingRitual).filter(BridgingRitual.id == ritual_id),
                    BridgingRitual, user).first()
        if not r:
            return None
        r.completed_at = datetime.utcnow()
        r.acknowledged = acknowledged
        db.flush()
        return _ritual_dict(r)


# --------------------------------------------------------------------------- #
# Methodology — comms frame recommendation for a stakeholder
# --------------------------------------------------------------------------- #
def recommend_frames(user: str, stakeholder_id: str) -> Optional[dict]:
    """Recommend comms frames for a stakeholder from their archetype + current
    stage (Comms Library selection matrix). None if not owned/found."""
    with get_db_session() as db:
        s = _owned_stakeholder(db, user, stakeholder_id)
        if not s:
            return None
        return {
            "stakeholder_id": s.id,
            "archetype": s.archetype,
            "stage": s.transition_stage,
            "frames": methodology.select_frames(s.archetype, s.transition_stage),
            "avoid": list(methodology.AVOID_FRAMES),
        }


# --------------------------------------------------------------------------- #
# Portfolio roll-up — the view the operator triages from (ITM Template v1.2:
# "sort by transition stage (stuck first), then next ritual due (soonest first)").
# --------------------------------------------------------------------------- #
def portfolio(user: str) -> list[dict]:
    with get_db_session() as db:
        sk_q = _scoped(db.query(ClientStakeholder), ClientStakeholder, user)
        stakeholders = sk_q.all()
        clients = {c.id: c for c in _scoped(db.query(Client), Client, user).all()}
        rows = []
        for s in stakeholders:
            itm = db.query(ITMRecord).filter(ITMRecord.stakeholder_id == s.id).first()
            next_due = itm.next_ritual_due if itm else None
            client = clients.get(s.client_id)
            rows.append({
                "stakeholder_id": s.id,
                "name": s.name,
                "role": s.role,
                "archetype": s.archetype,
                "client_id": s.client_id,
                "client_name": client.name if client else None,
                "transition_stage": s.transition_stage or "unknown",
                "next_ritual_due": next_due.isoformat() if next_due else None,
                "open_loss_flag": bool(itm.open_loss_flag) if itm else False,
            })

        def sort_key(row):
            stage_rank = _STAGE_ORDER.get((row["transition_stage"] or "unknown").lower(), 5)
            # Soonest ritual first; rows with no due date sort last.
            due = row["next_ritual_due"] or "9999-12-31"
            return (stage_rank, due)

        rows.sort(key=sort_key)
        return rows
