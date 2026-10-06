import secrets
from datetime import timedelta
from sqlalchemy import select, update
from komicove_backend.accounts.models import ContributorInvite, User, _now
from komicove_backend.accounts.moderator_invites import token_hash


def generate(db, creator, valid_hours):
    secret = "kmc_contributor_" + secrets.token_urlsafe(32)
    invite = ContributorInvite(token_hash=token_hash(secret), created_by_user_id=creator.id,
        created_by_username=creator.username, expires_at=_now() + timedelta(hours=valid_hours))
    db.add(invite)
    db.flush()
    return invite, secret


def consume(db, user, secret):
    # Lock the account first as well as conditionally claiming the token. Two
    # concurrent claims cannot consume two invitations for the same promotion.
    now = _now()
    with db.begin_nested() as transaction:
        claimed = db.execute(update(User).where(User.id == user.id, User.role == "user",
            User.is_active.is_(True), User.deleted_at.is_(None),
            User.suspended_until.is_(None) | (User.suspended_until <= now))
            .values(role="contributor", is_moderator=False).execution_options(synchronize_session=False))
        if claimed.rowcount != 1:
            transaction.rollback()
            return None
        result = db.execute(update(ContributorInvite).where(
            ContributorInvite.token_hash == token_hash(secret), ContributorInvite.used_at.is_(None),
            ContributorInvite.revoked_at.is_(None), ContributorInvite.expires_at > now)
            .values(used_at=now, used_by_user_id=user.id, used_by_username=user.username)
            .execution_options(synchronize_session=False))
        if result.rowcount != 1:
            transaction.rollback()
            return None
    db.refresh(user)
    return db.scalar(select(ContributorInvite).where(ContributorInvite.token_hash == token_hash(secret))
        .execution_options(populate_existing=True))
