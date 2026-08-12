"""
fabric_db.py — Production-grade Fabric SQL connection manager for AppHub 4.0.

Environment detection:
  - Azure (App Service / Container Apps): Uses Managed Identity via DefaultAzureCredential.
    Tokens auto-refresh; no secrets, no expiry, no manual intervention.
  - Local dev: Falls back to InteractiveBrowserCredential (browser popup on first use,
    cached refresh token for subsequent calls).

Usage:
    from fabric_db import get_connection

    conn = get_connection("DB_APP_SUPPORT")
    rows = conn.execute("SELECT TOP 5 * FROM dbo.PROPERTY_0").fetchall()
    conn.close()

Azure deployment prerequisites:
  1. Enable System-Assigned Managed Identity on your App Service / Container App.
  2. Grant that identity access to your Fabric SQL Database:
       CREATE USER [your-app-name] FROM EXTERNAL PROVIDER;
       ALTER ROLE db_datareader ADD MEMBER [your-app-name];
       ALTER ROLE db_datawriter ADD MEMBER [your-app-name];
  3. Set environment variables: FABRIC_DB_APP_SUPPORT (server endpoint), etc.
"""

import os
import struct
import time
import threading
import pyodbc

# Token cache: {db_name: {"token": str, "expires_on": float}}
_token_cache = {}
_cache_lock = threading.Lock()

# How many minutes before expiry to proactively refresh
_REFRESH_BUFFER_SECONDS = 300  # 5 minutes


def _is_azure():
    """Detect if running in Azure (App Service, Container Apps, etc.)."""
    return bool(os.environ.get("WEBSITE_INSTANCE_ID") or
                os.environ.get("CONTAINER_APP_NAME") or
                os.environ.get("IDENTITY_ENDPOINT"))


def _get_credential():
    """Return the appropriate Azure credential for the current environment."""
    from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential

    if _is_azure():
        # Production: Managed Identity (auto-refreshing, no secrets)
        return DefaultAzureCredential()
    else:
        # Local dev: try cached auth record, fall back to browser
        from azure.identity import TokenCachePersistenceOptions, AuthenticationRecord
        cache_options = TokenCachePersistenceOptions(name="apphub_dev")

        auth_record_path = os.path.join(
            os.path.dirname(__file__), ".auth_record.json"
        )
        if os.path.exists(auth_record_path):
            try:
                with open(auth_record_path) as f:
                    record = AuthenticationRecord.deserialize(f.read())
                return InteractiveBrowserCredential(
                    cache_persistence_options=cache_options,
                    authentication_record=record,
                    disable_automatic_authentication=True,
                )
            except Exception:
                pass

        # No cached record — will pop browser
        cred = InteractiveBrowserCredential(
            cache_persistence_options=cache_options,
        )
        # Eagerly authenticate to save the record for next time
        record = cred.authenticate(scopes=["https://database.windows.net/.default"])
        try:
            with open(auth_record_path, "w") as f:
                f.write(record.serialize())
        except Exception:
            pass
        return cred


def _get_token(force_refresh=False):
    """Get a valid access token, refreshing if expired or close to expiry."""
    with _cache_lock:
        cached = _token_cache.get("fabric")
        if cached and not force_refresh:
            if cached["expires_on"] > time.time() + _REFRESH_BUFFER_SECONDS:
                return cached["token"]

    credential = _get_credential()
    token = credential.get_token("https://database.windows.net/.default")

    with _cache_lock:
        _token_cache["fabric"] = {
            "token": token.token,
            "expires_on": token.expires_on,
        }
    return token.token


def _build_connection(server, database):
    """Build a pyodbc connection using the current token."""
    access_token = _get_token()
    token_bytes = access_token.encode("utf-16-le")
    token_struct = struct.pack(
        f"<I{len(token_bytes)}s", len(token_bytes), token_bytes
    )
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"Encrypt=yes;"
        f"Connection Timeout=120;"
    )
    conn = pyodbc.connect(conn_str, attrs_before={1256: token_struct}, timeout=120)
    conn.autocommit = True
    return conn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Map of logical DB names to env var keys for their server endpoints
_DB_ENDPOINTS = {
    "DB_APP_SUPPORT": "FABRIC_DB_APP_SUPPORT",
    "WH_STAGING": "FABRIC_WH_STAGING",
    "WH_PROD2": "FABRIC_WH_PROD2",
}


def get_connection(db_name, env=None):
    """
    Get a pyodbc connection to a Fabric SQL database.

    Args:
        db_name: Logical database name (e.g., "DB_APP_SUPPORT")
        env: Optional dict of env vars. If None, reads from os.environ.

    Returns:
        pyodbc.Connection with autocommit=True

    Raises:
        ValueError if no endpoint configured for db_name
        pyodbc.Error on connection failure (after one retry with fresh token)
    """
    env = env or os.environ

    endpoint_key = _DB_ENDPOINTS.get(db_name, f"FABRIC_{db_name}")
    server = env.get(endpoint_key)
    if not server:
        raise ValueError(
            f"No server endpoint for '{db_name}'. "
            f"Set {endpoint_key} in environment or .env file."
        )

    try:
        return _build_connection(server, db_name)
    except (pyodbc.InterfaceError, pyodbc.OperationalError):
        # Token might be stale in cache — force refresh and retry once
        _get_token(force_refresh=True)
        return _build_connection(server, db_name)


class FabricConnection:
    """
    Context-manager wrapper with auto-reconnect on token expiry.

    Usage:
        with FabricConnection("DB_APP_SUPPORT") as conn:
            rows = conn.fetchall("SELECT * FROM dbo.PROPERTY_0")
    """

    def __init__(self, db_name, env=None):
        self.db_name = db_name
        self.env = env
        self._conn = None

    def _ensure_connected(self):
        if self._conn is None:
            self._conn = get_connection(self.db_name, self.env)

    def __enter__(self):
        self._ensure_connected()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def execute(self, sql, params=None):
        self._ensure_connected()
        try:
            if params:
                return self._conn.execute(sql, params)
            return self._conn.execute(sql)
        except (pyodbc.InterfaceError, pyodbc.OperationalError):
            # Reconnect and retry once
            self._conn = get_connection(self.db_name, self.env)
            if params:
                return self._conn.execute(sql, params)
            return self._conn.execute(sql)

    def fetchall(self, sql, params=None):
        cursor = self.execute(sql, params)
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def fetchone(self, sql, params=None):
        cursor = self.execute(sql, params)
        cols = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        return dict(zip(cols, row)) if row else None

    def close(self):
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
