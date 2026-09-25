from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from komicove_backend.accounts.models import User
from komicove_backend.db import Base
from komicove_backend.moderation.models import (
    ModerationResult, ModerationStatus, RiskLevel,
)
from komicove_backend.moderation.storage import SqlAlchemyModerationStore


def test_sql_store_round_trip():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session.begin() as db:
        user = User(
            username="moderado", display_name="Moderado",
            password_hash="hash", password_salt="salt",
        )
        db.add(user)
        db.flush()
        result = ModerationResult(
            submission_user_id=user.id,
            status=ModerationStatus.PENDING_REVIEW,
            risk_level=RiskLevel.MEDIUM,
            confidence=0.5,
            internal_justification="teste",
            findings=[],
        )
        store = SqlAlchemyModerationStore(db)
        saved = store.save(result, "Obra")
        assert store.get(saved.record_id) == saved
        assert store.list_by_user(user.id) == [saved]
