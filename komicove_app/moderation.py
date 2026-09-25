MODERATOR_ROLES={"moderator","admin","owner"}
def can_moderate(user): return bool(user) and (getattr(user,"role","user") in MODERATOR_ROLES or getattr(user,"is_moderator",False))
