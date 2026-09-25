from sqlalchemy.orm import Session
from komicove_backend.accounts.models import AdminAuditLog, User

def record(db: Session, actor: User, action: str, *, target: User | None = None,
           reason: str | None = None, details: str | None = None) -> AdminAuditLog:
    entry = AdminAuditLog(actor_user_id=actor.id, actor_username=actor.username,
        target_user_id=target.id if target else None,
        target_username=target.username if target else None,
        action=action, reason=reason, details=details)
    db.add(entry); db.flush(); return entry
