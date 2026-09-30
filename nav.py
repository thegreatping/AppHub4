"""Shared nav builder — always reads Flag_Active from DB so the sidebar is never stale."""
from flask import session
from modules import MODULES, APP_ID_MAP
from helpers import load_env, SafeConnection

_env = None

# BETA GATE (2026-09-30): during the AppHub 4.0 limited beta, non-developer
# users only ever see the modules listed here. Developers (cpell@peakmade.com
# and anyone else with GRANT_TYPE='developer' on module 0) still see
# everything. When more modules open beta, add them here. When we go fully
# GA, set _BETA_MODE=False (or delete the gate).
_BETA_MODE = True
_BETA_ALLOWED_MODULES = {"leadership_scorecard"}

_ALWAYS_VISIBLE = {"rent_forecasting_2"}
_HIDE_WITHOUT_GRANT = {"apphub_maintenance"}


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def build_nav_modules():
    """Return the list of modules to show in the left nav for the current user.

    BETA MODE: non-developers see ONLY modules in _BETA_ALLOWED_MODULES.
    Developers see every Flag_Active=1 module (unchanged).

    Every returned entry carries a `state` = 'live' (kept for template compat;
    nothing renders as ghost during beta).
    """
    user_modules = session.get("user_modules", [])
    is_developer = session.get("is_developer", False)
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
        out["state"] = "live"
        return out

    visible = []
    for m in sorted(MODULES, key=lambda x: x["name"].lower()):
        if m["id"] not in candidate_ids:
            continue
        if m["id"] in _HIDE_WITHOUT_GRANT and m["id"] not in granted_ids and not treat_as_developer:
            continue
        # BETA GATE: non-devs only see whitelisted modules.
        if _BETA_MODE and not treat_as_developer and m["id"] not in _BETA_ALLOWED_MODULES:
            continue
        visible.append(_decorate(m))
    return visible
