"""
usage_log.py — Fire-and-forget usage logging for AppHub 4.0.

Public API:
    log_request(user_email, user_name, module_id, route, method, status_code)

All DB errors are swallowed silently. The daemon thread never blocks the
response or app shutdown.

Connection strategy:
  - Production (Azure): fabric_db.get_connection() → Managed Identity token auth
  - Local dev: SafeConnection(env, "DB_APP_SUPPORT", direct=True) → SQL password auth
  The fallback ensures silent failure rather than a browser popup in a daemon thread.
"""

import threading
import sys
import os


def log_request(
    user_email: str,
    user_name: str,
    module_id: str,
    route: str,
    method: str,
    status_code: int,
) -> None:
    """Spawn a daemon thread to insert one row into dbo.APPHUB_USAGE_LOG.

    Returns immediately. Any exception inside the thread is suppressed.
    """
    t = threading.Thread(
        target=_write_log,
        args=(user_email, user_name, module_id, route, method, status_code),
        daemon=True,
    )
    t.start()


_INSERT_SQL = """
    INSERT INTO dbo.APPHUB_USAGE_LOG
        (user_email, user_name, module_id, route, http_method, status_code)
    VALUES (?, ?, ?, ?, ?, ?)
"""


def _get_conn():
    """Return a DB connection using the best available method for this environment."""
    # Production: Managed Identity via fabric_db
    if (os.environ.get("WEBSITE_INSTANCE_ID") or
            os.environ.get("CONTAINER_APP_NAME") or
            os.environ.get("IDENTITY_ENDPOINT")):
        from fabric_db import get_connection
        return get_connection("DB_APP_SUPPORT")

    # Local dev: SafeConnection (direct SQL auth, no browser popup)
    helpers_path = r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts"
    if helpers_path not in sys.path:
        sys.path.insert(0, helpers_path)
    from helpers import load_env, SafeConnection
    env = load_env()
    return SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)


def _write_log(user_email, user_name, module_id, route, method, status_code):
    try:
        conn = _get_conn()
        try:
            conn.execute(
                _INSERT_SQL,
                (user_email, user_name, module_id, route, method, status_code),
            )
        finally:
            conn.close()
    except Exception:
        pass  # never surface logging failures to users
