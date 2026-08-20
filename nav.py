"""Shared nav builder — always reads Flag_Active from DB so the sidebar is never stale."""
from flask import session
from modules import MODULES, APP_ID_MAP
from helpers import load_env, SafeConnection

_env = None
_ALWAYS_VISIBLE = {"rent_forecasting_2"}


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def build_nav_modules():
    """Return the list of modules to show in the left nav for the current user.

    Intersects the user's audience access (session) with Flag_Active=1 from DB.
    """
    user_modules = session.get("user_modules", [])
    is_developer  = session.get("is_developer", False)

    try:
        conn = SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)
        rows = conn.fetchall("SELECT App_ID FROM dbo.APP_LIST WHERE Flag_Active=1")
        active_ids = {APP_ID_MAP[r[0]] for r in rows if r[0] in APP_ID_MAP}
    except Exception:
        active_ids = None  # DB unavailable: fall back to session only

    if active_ids is None:
        if not user_modules:
            return sorted(MODULES, key=lambda m: m["name"].lower())
        allowed = {APP_ID_MAP[m["id"]] for m in user_modules if m["id"] in APP_ID_MAP}
        allowed |= _ALWAYS_VISIBLE
        return sorted(
            [m for m in MODULES if m["id"] in allowed],
            key=lambda m: m["name"].lower()
        )

    if is_developer:
        # Dev users see everything that's active — don't constrain by stale session list
        allowed = set(active_ids)
    elif user_modules:
        allowed = {APP_ID_MAP[m["id"]] for m in user_modules if m["id"] in APP_ID_MAP}
        allowed &= active_ids  # must be both in user's access AND active in DB
    else:
        allowed = set(active_ids)

    allowed |= _ALWAYS_VISIBLE
    return sorted(
        [m for m in MODULES if m["id"] in allowed],
        key=lambda m: m["name"].lower()
    )
