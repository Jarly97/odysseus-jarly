"""Phase 01 — Client workspace methodology-native data model.

Verifies the new Client/Stakeholder/ITM/TRI/BridgingRitual schema: relationships,
methodology-native fields, owner-scoping, and FK cascade. Uses a throwaway temp
DB so it never touches the real data/app.db.
"""
import os
import tempfile

# Point the DB at a throwaway file BEFORE importing core.database (engine binds at import).
_TMPDIR = tempfile.mkdtemp(prefix="odysseus_cw_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_TMPDIR, "cw_test.db").replace("\\", "/")

from sqlalchemy import text  # noqa: E402
from core.database import (  # noqa: E402
    SessionLocal,
    Client,
    ClientStakeholder,
    ITMRecord,
    TRIScorecard,
    BridgingRitual,
)


def _seed(db, owner="karl", client_id="c1", sk_id="s1"):
    db.add(Client(id=client_id, name="RVL Pharma", sector="pharma",
                  model_policy="local-sensitive", owner=owner))
    db.flush()
    db.add(ClientStakeholder(id=sk_id, client_id=client_id, name="Amy Shah",
                             role="Chief Growth Officer", archetype="Authority Expert",
                             transition_stage="stuck", owner=owner))
    db.flush()
    db.add(ITMRecord(id="itm-" + sk_id, stakeholder_id=sk_id, client_id=client_id,
                     current_identity="growth visionary whose instinct drives revenue",
                     expected_loss="rainmaker validation loop",
                     open_loss_flag=True, operator=owner, owner=owner))
    db.add(TRIScorecard(id="tri-" + sk_id, stakeholder_id=sk_id, client_id=client_id,
                        cycle="Day 0", total=14, stage="stuck", direction="flat",
                        tri_version="v1.2", operator=owner, owner=owner,
                        scores={"1": {"score": 1, "note": "describes tasks she executes"}}))
    db.add(BridgingRitual(id="rit-" + sk_id, stakeholder_id=sk_id, client_id=client_id,
                          name="first AI-amplified growth artefact in her voice",
                          owner=owner))
    db.commit()


def test_schema_relationships_and_methodology_fields():
    db = SessionLocal()
    try:
        _seed(db)
        sk = db.query(ClientStakeholder).filter_by(id="s1").one()
        assert sk.client.name == "RVL Pharma"
        assert sk.archetype == "Authority Expert"
        assert len(sk.itm_records) == 1
        assert sk.itm_records[0].open_loss_flag is True
        # TRI version is required for comparability (TRI v1.2 rule).
        assert sk.tri_scorecards[0].tri_version == "v1.2"
        assert sk.tri_scorecards[0].scores["1"]["score"] == 1
        assert sk.bridging_rituals[0].acknowledged is False
        # Per-client model policy exists for the sensitivity-routing layer.
        assert sk.client.model_policy == "local-sensitive"
    finally:
        db.close()


def test_owner_scoping_isolates_clients():
    db = SessionLocal()
    try:
        _seed(db, owner="karl", client_id="ca", sk_id="sa")
        _seed(db, owner="cto", client_id="cb", sk_id="sb")
        assert db.query(Client).filter(Client.owner == "karl").count() >= 1
        assert db.query(Client).filter(Client.owner == "stranger").count() == 0
        # Karl cannot see the CTO's client by owner filter.
        karl_ids = {c.id for c in db.query(Client).filter(Client.owner == "karl").all()}
        assert "cb" not in karl_ids
    finally:
        db.close()


def test_fk_cascade_deletes_children():
    db = SessionLocal()
    try:
        _seed(db, owner="z", client_id="cz", sk_id="sz")
        # DB-level ON DELETE CASCADE (PRAGMA foreign_keys=ON is set on connect).
        db.execute(text("DELETE FROM clients WHERE id = 'cz'"))
        db.commit()
        assert db.query(ClientStakeholder).filter_by(id="sz").count() == 0
        assert db.query(ITMRecord).filter_by(stakeholder_id="sz").count() == 0
        assert db.query(TRIScorecard).filter_by(stakeholder_id="sz").count() == 0
        assert db.query(BridgingRitual).filter_by(stakeholder_id="sz").count() == 0
    finally:
        db.close()
