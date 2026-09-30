"""Shared nav builder — always reads Flag_Active from DB so the sidebar is never stale."""
from flask import session
from modules import MODULES, APP_ID_MAP
from helpers import load_env, SafeConnection

_env = None
_ALWAYS_VISIBLE = {"rent_forecasting_2"}

# Admin-only tools that should NOT show as ghost tiles for users who lack a
# grant -- they're skipped entirely instead. Live-tile behavior for granted
# users is unchanged.
_HIDE_WITHOUT_GRANT = {"apphub_maintenance"}


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def build_nav_modules():
    """Return the list of modules to show in the left nav for the current user.

    Every Flag_Active=1 module is returned. Each entry carries a `state`:
      - 'live'  : user has an audience grant (or is a developer) -> normal link
      - 'ghost' : no grant -> dimmed BETA-labeled tile, non-clickable (nav is
                  a roadmap; click is blocked in the template)

    Modules in _HIDE_WITHOUT_GRANT are omitted entirely when the user has no
    grant (admin-only utilities we don't want to advertise). Developers see
    everything as 'live'.
    """
    user_modules = session.get("user_modules", [])
    is_developer = session.get("is_developer", False)
    # Impersonating a real user? Treat the impersonated user's grants as the
    # source of truth for ghost/live decisions -- otherwise the developer
    # flag would shortcut everything to 'live' and we'd never see ghosts.
    is_impersonating = session.get("is_impersonating", False)
    treat_as_developer = is_developer and not is_impersonating

    try:
        conn = SafeConnection(_get_env(), "DB_APP_SUPPORT", None, direct=True)
        rows = conn.fetchall("SELECT App_ID, Flag_Active, Testing_Status FROM dbo.APP_LIST")
        active_ids = {APP_ID_MAP[r[0]] for r in rows if r[0] in APP_ID_MAP and r[1] == 1}
        testing_status = {APP_ID_MAP[r[0]]: r[2] for r in rows if r[0] in APP_ID_MAP}
    except Exception:
        active_ids = None
        testing_status = {}

    granted_ids = {APP_ID_MAP[m["id"]] for m in user_modules if m["id"] in APP_ID_MAP}
    granted_ids |= _ALWAYS_VISIBLE

    if active_ids is None:
        candidate_ids = granted_ids or {m["id"] for m in MODULES}
    else:
        candidate_ids = set(active_ids) | granted_ids

    def _decorate(m):
        out = dict(m)
        out["testing_status"] = testing_status.get(m["id"], "PENDING")
        if treat_as_developer or m["id"] in granted_ids:
            out["state"] = "live"
        else:
            out["state"] = "ghost"
        return out

    visible = []
    for m in sorted(MODULES, key=lambda x: x["name"].lower()):
        if m["id"] not in candidate_ids:
            continue
        if m["id"] in _HIDE_WITHOUT_GRANT and m["id"] not in granted_ids and not treat_as_developer:
            continue
        visible.append(_decorate(m))
    return visible
