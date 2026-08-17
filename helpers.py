"""
helpers.py
Connection + auth utilities for the helpdesk ticket-triage workspace.

Adapted from C:\\validation\\scripts\\helpers.py — kept the connection layer,
token caching, and SafeConnection wrapper; dropped migration-specific
registry/dashboard code.

Public API:
    load_env()                      -> dict from C:\\helpdesk\\.env
    get_prod_connection(env, db)    -> pyodbc connection to legacy SQL Server
    get_fabric_connection(env, db)  -> pyodbc connection to a Fabric WH or DB
    get_bisupport_write_connection(env, log) -> DIRECT pyodbc connection to
                                       DB_BI_SUPPORT (GUID-suffixed name) for
                                       writes — the WH_STAGING tunnel is
                                       read-only for cross-DB
    force_reauth(env)               -> fresh browser login, refreshes caches
    SafeConnection(env, db, log)    -> auto-reconnecting wrapper, supports
                                       cross-DB tunneling for Fabric SQL DBs
    TriageLog(env, log)             -> ticket-intelligence logging into
                                       [DB_BI_SUPPORT].[hd].* (open_ticket /
                                       add_object / close_ticket /
                                       add_known_issue / find_similar)
    setup_logger(name)              -> file + console logger
    get_triage_db()                 -> DEPRECATED sqlite triage_log.db handle
                                       (kept only for the one-time migration)
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime

# Workspace root = the parent of this file's directory (i.e. <root>/scripts/..).
# Derived from __file__ so the kit runs from any install location, not just
# C:\helpdesk. Override with the HELPDESK_HOME env var if the layout differs.
BASE_DIR = os.environ.get("HELPDESK_HOME") or \
    os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
TRIAGE_DB_PATH = os.path.join(BASE_DIR, "triage_log.db")
LOG_DIR = os.path.join(BASE_DIR, "logs")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
TICKET_DIR = os.path.join(BASE_DIR, "tickets")

# Legacy prod name -> Fabric name. Kept for cross-reference when a ticket
# asks "what does the old system say?" vs "what does Fabric say?".
DB_MAP = {
    "DW_ODS": "WH_ODS",
    "DW_STAGING2": "WH_STAGING",
    "DW_PROD2": "WH_PROD2",
    "DW_APP_SUPPORT": "DB_APP_SUPPORT",
}
DB_MAP_REVERSE = {v: k for k, v in DB_MAP.items()}


# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------

def load_env():
    """Load .env file and return a dict of key=value pairs.

    Falls back to os.environ when no .env file exists (e.g. Azure App Service).
    """
    if not os.path.exists(ENV_PATH):
        return dict(os.environ)
    env = {}
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


# ---------------------------------------------------------------------------
# Database connections
# ---------------------------------------------------------------------------

def get_prod_connection(env, database):
    """Connect to a legacy production SQL Server database using SQL auth."""
    import pyodbc
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={env['PROD_SERVER']};"
        f"DATABASE={database};"
        f"UID={env['PROD_USER']};"
        f"PWD={env['PROD_PASSWORD']};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=yes;"
        f"Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str, timeout=30)


_fabric_token_cache = {}
_AUTH_RECORD_PATH = os.path.join(BASE_DIR, ".auth_record.json")
_TOKEN_CACHE_PATH = os.path.join(BASE_DIR, ".fabric_token.json")
_MSAL_CACHE_PATH = os.path.join(BASE_DIR, ".msal_cache.json")
_MSAL_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"  # Azure CLI public client
_MSAL_SCOPES = ["https://database.windows.net/.default"]


def _msal_silent_refresh(env, scopes=None, cache_to_disk=True):
    """Silent token refresh using the persisted MSAL cache. Returns token or None.

    scopes defaults to the SQL scope. Pass e.g.
    ["https://api.fabric.microsoft.com/.default"] for Fabric REST — the same
    refresh token mints tokens for any scope of this client.
    """
    import time as _time
    if not os.path.exists(_MSAL_CACHE_PATH):
        return None
    try:
        import msal
    except ImportError:
        return None
    cache = msal.SerializableTokenCache()
    try:
        with open(_MSAL_CACHE_PATH) as f:
            cache.deserialize(f.read())
    except Exception:
        return None
    tenant = env.get("PBI_TENANT_ID")
    if not tenant:
        return None
    app = msal.PublicClientApplication(
        _MSAL_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{tenant}",
        token_cache=cache,
    )
    accounts = app.get_accounts()
    if not accounts:
        return None
    result = app.acquire_token_silent(scopes or _MSAL_SCOPES, account=accounts[0])
    if not result or "access_token" not in result:
        return None
    if cache.has_state_changed:
        try:
            with open(_MSAL_CACHE_PATH, "w") as f:
                f.write(cache.serialize())
        except Exception:
            pass
    if cache_to_disk:
        expires_on = int(_time.time()) + int(result.get("expires_in", 3600))
        try:
            with open(_TOKEN_CACHE_PATH, "w") as f:
                json.dump({"token": result["access_token"], "expires_on": expires_on}, f)
        except Exception:
            pass
    return result["access_token"]


_FABRIC_API_TOKEN_CACHE_PATH = os.path.join(BASE_DIR, ".fabric_api_token.json")


def _get_fabric_api_token(env):
    """Token for the Fabric REST API (NOT the SQL endpoint).

    Priority:
      1. In-memory cache (not expired)
      2. .fabric_api_token.json disk cache (not expired)
      3. MSAL silent refresh (.msal_cache.json)
      4. azure.identity silent via auth record
      5. Interactive browser login (last resort)
    """
    import time as _time
    scope = "https://api.fabric.microsoft.com/.default"

    # 1. In-memory cache
    cache_key = "fabric_api_token"
    if cache_key in _fabric_token_cache:
        tok = _fabric_token_cache[cache_key]
        expires = tok.expires_on if hasattr(tok, "expires_on") else tok.get("expires_on", 0)
        val = tok.token if hasattr(tok, "token") else tok.get("token")
        if expires > _time.time() + 300:
            return val

    # 2. Disk cache
    if os.path.exists(_FABRIC_API_TOKEN_CACHE_PATH):
        try:
            with open(_FABRIC_API_TOKEN_CACHE_PATH) as f:
                cached = json.load(f)
            if cached.get("expires_on", 0) > _time.time() + 300:
                _fabric_token_cache[cache_key] = {"token": cached["token"], "expires_on": cached["expires_on"]}
                return cached["token"]
        except Exception:
            pass

    # 3. MSAL silent refresh
    token = _msal_silent_refresh(env, scopes=[scope], cache_to_disk=False)
    if token:
        expires_on = int(_time.time()) + 3600
        _fabric_token_cache[cache_key] = {"token": token, "expires_on": expires_on}
        try:
            with open(_FABRIC_API_TOKEN_CACHE_PATH, "w") as f:
                json.dump({"token": token, "expires_on": expires_on}, f)
        except Exception:
            pass
        return token

    # 4 & 5. azure.identity — silent via auth record, then interactive
    from azure.identity import InteractiveBrowserCredential, TokenCachePersistenceOptions
    cache_options = TokenCachePersistenceOptions(name="helpdesk_triage")
    kwargs = {"cache_persistence_options": cache_options}
    if os.path.exists(_AUTH_RECORD_PATH):
        try:
            from azure.identity import AuthenticationRecord
            with open(_AUTH_RECORD_PATH) as f:
                kwargs["authentication_record"] = AuthenticationRecord.deserialize(f.read())
        except Exception:
            pass
    credential = InteractiveBrowserCredential(login_hint=env.get("FABRIC_USER", ""), **kwargs)
    tok = credential.get_token(scope)
    _fabric_token_cache[cache_key] = tok
    try:
        with open(_FABRIC_API_TOKEN_CACHE_PATH, "w") as f:
            json.dump({"token": tok.token, "expires_on": tok.expires_on}, f)
    except Exception:
        pass
    return tok.token


def _get_fabric_token(env):
    """Get an AAD access token, reusing disk caches across processes.

    Priority:
      1. In-memory cache (not expired)
      2. .fabric_token.json (not expired)
      3. MSAL client credentials (AZURE_CLIENT_ID/SECRET/TENANT_ID) — works on Azure App Service
      4. MSAL silent refresh (.msal_cache.json refresh token)
      5. az cli  (az account get-access-token) — silent, works in local dev
      6. azure.identity silent refresh (.auth_record.json)
      7. Interactive browser login
    """
    import time as _time

    cache_key = "fabric_token"
    if cache_key in _fabric_token_cache:
        token = _fabric_token_cache[cache_key]
        if token.expires_on > _time.time() + 600:  # 10-min margin
            return token.token
        # Expired or near-expiry — evict so we fetch fresh below
        del _fabric_token_cache[cache_key]
        # Also remove disk cache so step 2 below doesn't serve the same stale token
        try:
            if os.path.exists(_TOKEN_CACHE_PATH):
                os.remove(_TOKEN_CACHE_PATH)
        except Exception:
            pass

    if os.path.exists(_TOKEN_CACHE_PATH):
        try:
            with open(_TOKEN_CACHE_PATH, encoding='utf-8') as f:
                cached = json.load(f)
            if cached.get('expires_on', 0) > _time.time() + 600:  # 10-min margin
                return cached['token']
        except Exception:
            pass

    # Client credentials: works on Azure App Service (no browser/az CLI needed)
    try:
        import msal as _msal
        import time as _time_cc
        _cc_id = env.get("AZURE_CLIENT_ID")
        _cc_secret = env.get("AZURE_CLIENT_SECRET")
        _cc_tenant = env.get("AZURE_TENANT_ID")
        if _cc_id and _cc_secret and _cc_tenant:
            _cc_app = _msal.ConfidentialClientApplication(
                _cc_id,
                client_credential=_cc_secret,
                authority=f"https://login.microsoftonline.com/{_cc_tenant}",
            )
            _cc_result = _cc_app.acquire_token_for_client(
                scopes=["https://database.windows.net/.default"]
            )
            if _cc_result and "access_token" in _cc_result:
                _cc_exp = int(_time_cc.time()) + int(_cc_result.get("expires_in", 3600))
                class _TCC:
                    def __init__(self, t, e): self.token = t; self.expires_on = e
                _fabric_token_cache[cache_key] = _TCC(_cc_result["access_token"], _cc_exp)
                try:
                    with open(_TOKEN_CACHE_PATH, "w", encoding="utf-8") as f:
                        json.dump({"token": _cc_result["access_token"], "expires_on": _cc_exp}, f)
                except Exception:
                    pass
                return _cc_result["access_token"]
    except Exception:
        pass

    silent = _msal_silent_refresh(env)
    if silent:
        import time as _time2
        expires_on = int(_time2.time()) + 3600
        # Update in-memory cache so the stale Token object is replaced
        class _T:
            def __init__(self, t, e): self.token = t; self.expires_on = e
        _fabric_token_cache[cache_key] = _T(silent, expires_on)
        try:
            with open(_TOKEN_CACHE_PATH, "w") as f:
                json.dump({'token': silent, 'expires_on': expires_on}, f)
        except Exception:
            pass
        return silent

    # ── AzureCliCredential fallback: works silently in local dev without browser popup ──
    try:
        import time as _time3
        from azure.identity import AzureCliCredential as _AzCliCred
        _az_tok = _AzCliCred().get_token("https://database.windows.net/.default")
        az_token = _az_tok.token
        az_exp = int(_az_tok.expires_on)
        if az_token:
            class _T2:
                def __init__(self, t, e): self.token = t; self.expires_on = e
            _fabric_token_cache[cache_key] = _T2(az_token, az_exp)
            try:
                with open(_TOKEN_CACHE_PATH, "w", encoding="utf-8", newline="\n") as f:
                    json.dump({'token': az_token, 'expires_on': az_exp}, f)
            except Exception:
                pass
            return az_token
    except Exception:
        pass

    from azure.identity import InteractiveBrowserCredential, TokenCachePersistenceOptions
    cache_options = TokenCachePersistenceOptions(name="helpdesk_triage")

    auth_record = None
    if os.path.exists(_AUTH_RECORD_PATH):
        try:
            from azure.identity import AuthenticationRecord
            with open(_AUTH_RECORD_PATH) as f:
                auth_record = AuthenticationRecord.deserialize(f.read())
        except Exception:
            pass

    if auth_record:
        try:
            credential = InteractiveBrowserCredential(
                cache_persistence_options=cache_options,
                authentication_record=auth_record,
                disable_automatic_authentication=True,
            )
            token = credential.get_token("https://database.windows.net/.default")
            _fabric_token_cache[cache_key] = token
            try:
                with open(_TOKEN_CACHE_PATH, "w") as f:
                    json.dump({'token': token.token, 'expires_on': token.expires_on}, f)
            except Exception:
                pass
            return token.token
        except Exception:
            pass

    credential = InteractiveBrowserCredential(
        login_hint=env.get("FABRIC_USER", ""),
        cache_persistence_options=cache_options,
    )
    record = credential.authenticate(scopes=["https://database.windows.net/.default"])
    try:
        with open(_AUTH_RECORD_PATH, "w") as f:
            f.write(record.serialize())
    except Exception:
        pass
    token = credential.get_token("https://database.windows.net/.default")
    _fabric_token_cache[cache_key] = token
    try:
        with open(_TOKEN_CACHE_PATH, "w") as f:
            json.dump({'token': token.token, 'expires_on': token.expires_on}, f)
    except Exception:
        pass
    return token.token


def force_reauth(env):
    """Force a fresh browser login, save token and auth record to disk."""
    import time as _time
    from azure.identity import InteractiveBrowserCredential, TokenCachePersistenceOptions

    for p in (_TOKEN_CACHE_PATH, _AUTH_RECORD_PATH):
        if os.path.exists(p):
            os.remove(p)

    cache_options = TokenCachePersistenceOptions(name="helpdesk_triage")
    credential = InteractiveBrowserCredential(
        login_hint=env.get("FABRIC_USER", ""),
        cache_persistence_options=cache_options,
    )
    record = credential.authenticate(scopes=["https://database.windows.net/.default"])
    with open(_AUTH_RECORD_PATH, "w") as f:
        f.write(record.serialize())
    token = credential.get_token("https://database.windows.net/.default")
    _fabric_token_cache["fabric_token"] = token
    with open(_TOKEN_CACHE_PATH, "w") as f:
        json.dump({'token': token.token, 'expires_on': token.expires_on}, f)
    expires_min = (token.expires_on - _time.time()) / 60
    return token.token, expires_min


def get_fabric_connection(env, fabric_db_name):
    """Connect to a Fabric warehouse or SQL database using a cached AAD token."""
    import pyodbc
    import struct

    endpoint_key = f"FABRIC_{fabric_db_name}"
    server = env.get(endpoint_key)
    if not server:
        raise ValueError(f"No endpoint found in .env for {endpoint_key}")

    access_token = _get_fabric_token(env)
    token_bytes = access_token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={server};"
        f"DATABASE={fabric_db_name};"
        f"Encrypt=yes;"
        f"Connection Timeout=120;"
    )
    return pyodbc.connect(conn_str, attrs_before={1256: token_struct}, timeout=120)


# ---------------------------------------------------------------------------
# DB_BI_SUPPORT direct write connection
#
# The WH_STAGING cross-DB tunnel is READ-ONLY (INSERT/CREATE denied). Writes
# must connect directly to the SQL endpoint, whose database name is
# GUID-suffixed (e.g. "DB_BI_Support-56ab...-...e61"). The name is cached in
# .env as FABRIC_DB_BI_SUPPORT_DBNAME and re-resolved via Fabric REST if the
# connect fails (the GUID changes if the item is ever recreated).
# ---------------------------------------------------------------------------

_BISUPPORT_DBNAME_KEY = "FABRIC_DB_BI_SUPPORT_DBNAME"
_BISUPPORT_DISPLAY = "DB_BI_Support"


def _resolve_bisupport_dbname(env):
    """Find the GUID-suffixed DB_BI_Support database name via Fabric REST."""
    import requests
    headers = {"Authorization": f"Bearer {_get_fabric_api_token(env)}"}
    api = "https://api.fabric.microsoft.com/v1"
    ws_list = requests.get(f"{api}/workspaces", headers=headers, timeout=60)\
        .json().get("value", [])
    for w in ws_list:
        r = requests.get(f"{api}/workspaces/{w['id']}/sqlDatabases",
                         headers=headers, timeout=60)
        if r.status_code != 200:
            continue
        for it in r.json().get("value", []):
            if it.get("displayName", "").lower() == _BISUPPORT_DISPLAY.lower():
                return it.get("properties", {}).get("databaseName")
    raise RuntimeError(f"SQL database '{_BISUPPORT_DISPLAY}' not found in any workspace")


def _save_env_key(key, value):
    """Persist/replace a single key in C:\\helpdesk\\.env."""
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            lines = f.read().splitlines()
    lines = [l for l in lines if not l.strip().startswith(f"{key}=")]
    lines.append(f"{key}={value}")
    with open(ENV_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")


def get_bisupport_write_connection(env, log=None):
    """DIRECT pyodbc connection to DB_BI_SUPPORT for writes (hd.* tables).

    Uses the GUID-suffixed database name from .env; self-heals by re-resolving
    it via Fabric REST if the cached name no longer connects.
    """
    import pyodbc
    server = env.get("FABRIC_DB_BI_SUPPORT")
    if not server:
        raise ValueError("FABRIC_DB_BI_SUPPORT missing from .env")

    def _connect(dbname):
        import struct
        token_bytes = _get_fabric_token(env).encode("utf-16-le")
        ts = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
        cs = (f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};"
              f"DATABASE={dbname};Encrypt=yes;Connection Timeout=60;")
        cn = pyodbc.connect(cs, attrs_before={1256: ts}, timeout=60)
        cn.autocommit = True
        return cn

    dbname = env.get(_BISUPPORT_DBNAME_KEY)
    if dbname:
        try:
            return _connect(dbname)
        except Exception as e:
            if log:
                log.info(f"    [DB_BI_SUPPORT direct] cached name failed ({e}); re-resolving GUID name...")
    dbname = _resolve_bisupport_dbname(env)
    if log:
        log.info(f"    [DB_BI_SUPPORT direct] resolved database name: {dbname}")
    _save_env_key(_BISUPPORT_DBNAME_KEY, dbname)
    env[_BISUPPORT_DBNAME_KEY] = dbname
    return _connect(dbname)


def get_appsupport_direct_connection(env, log=None):
    """DIRECT pyodbc connection to DB_APP_SUPPORT (Fabric SQL Database).

    Uses the .database.fabric.microsoft.com endpoint and GUID-suffixed DB name
    from .env for full read/write access including DDL.
    """
    import pyodbc, struct
    server = env.get("FABRIC_DB_APP_SUPPORT")
    if not server:
        raise ValueError("FABRIC_DB_APP_SUPPORT missing from .env")
    dbname = env.get("FABRIC_DB_APP_SUPPORT_DBNAME")
    if not dbname:
        raise ValueError("FABRIC_DB_APP_SUPPORT_DBNAME missing from .env")
    if log:
        log.info(f"    [DB_APP_SUPPORT direct] connecting to {dbname}...")
    token_bytes = _get_fabric_token(env).encode("utf-16-le")
    ts = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    cs = (f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};"
          f"DATABASE={dbname};Encrypt=yes;Connection Timeout=60;")
    cn = pyodbc.connect(cs, attrs_before={1256: ts}, timeout=60)
    cn.autocommit = True
    if log:
        log.info(f"    [DB_APP_SUPPORT direct] Connected.")
    return cn


# ---------------------------------------------------------------------------
# Resilient connection wrapper
# ---------------------------------------------------------------------------

class SafeConnection:
    """Auto-reconnecting database connection wrapper.

    Usage:
        conn = SafeConnection(env, 'WH_PROD2', log)       # Fabric warehouse
        conn = SafeConnection(env, 'DW_PROD2', log)       # legacy prod
        conn = SafeConnection(env, 'DB_APP_SUPPORT', log) # Fabric SQL DB
                                                          #   tunnels via WH_STAGING

    KEY GOTCHAS for Fabric SQL Databases (DB_APP_SUPPORT, DB_BI_SUPPORT):
      - The WH_STAGING cross-DB tunnel ([DB_BI_SUPPORT].[schema].[tbl]) only
        exposes mirrored TABLES (the SQL DB's analytics endpoint) — VIEWS are
        never visible there, new tables lag while mirroring, and the tunnel is
        READ-ONLY.
      - For views (obs.vw_*, hd.vw_*) or writes, use a DIRECT connection:
        SafeConnection(env, 'DB_BI_SUPPORT', direct=True) — connects to the
        GUID-suffixed database itself (read+write, sees everything).
    Use .qualify() to get the correctly-formed reference either way.
    """

    PROD_DBS = {'DW_ODS', 'DW_STAGING2', 'DW_PROD2', 'DW_APP_SUPPORT'}
    CROSSDB_VIA_STAGING = {'DB_APP_SUPPORT', 'DB_BI_SUPPORT'}

    def __init__(self, env, db_name, log=None, direct=False):
        self.env = env
        self.db_name = db_name
        self.log = log
        self.is_direct = direct and db_name in ('DB_BI_SUPPORT', 'DB_APP_SUPPORT')
        self.is_prod = db_name in self.PROD_DBS
        self.is_crossdb = (db_name in self.CROSSDB_VIA_STAGING) and not self.is_direct
        self._conn = None
        self._connect()

    def _connect(self, _retry=True):
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
        if self.log:
            self.log.info(f"    [{self.db_name}] Connecting...")
        try:
            if self.is_direct and self.db_name == 'DB_BI_SUPPORT':
                self._conn = get_bisupport_write_connection(self.env, self.log)
            elif self.is_direct and self.db_name == 'DB_APP_SUPPORT':
                self._conn = get_appsupport_direct_connection(self.env, self.log)
            elif self.is_prod:
                self._conn = get_prod_connection(self.env, self.db_name)
            elif self.is_crossdb:
                self._conn = get_fabric_connection(self.env, 'WH_STAGING')
            else:
                self._conn = get_fabric_connection(self.env, self.db_name)
        except Exception as e:
            if _retry and self._is_auth_error(str(e)):
                if self.log:
                    self.log.info(f"    [{self.db_name}] Auth error on connect, evicting token and retrying...")
                _fabric_token_cache.pop('fabric_token', None)
                # Also nuke the disk cache so _get_fabric_token doesn't serve the stale file
                try:
                    if os.path.exists(_TOKEN_CACHE_PATH):
                        os.remove(_TOKEN_CACHE_PATH)
                except Exception:
                    pass
                self._connect(_retry=False)
                return
            raise
        # pyodbc defaults to autocommit=False, which silently rolls back EXEC
        # writes on close. Force autocommit so DML/SP work persists.
        try:
            self._conn.autocommit = True
        except Exception:
            pass
        if self.log:
            self.log.info(f"    [{self.db_name}] Connected.")

    def _is_connection_error(self, err_str):
        markers = ['Communication link', '08S01', '08001', 'TCP Provider',
                   'connection was forcibly closed', 'Login timeout',
                   'Connection is busy', 'server closed the connection']
        return any(m.lower() in err_str.lower() for m in markers)

    def _is_auth_error(self, err_str):
        """Detect expired/invalid AAD token errors (28000 / Login failed)."""
        markers = ['28000', 'token-identified principal', 'Login failed',
                   'Validation of user', 'Invalid connection string attribute']
        return any(m.lower() in err_str.lower() for m in markers)

    def execute(self, sql, params=None):
        for attempt in range(2):
            try:
                self._conn.timeout = getattr(self, 'query_timeout', 300)
                cur = self._conn.cursor()
                if params:
                    cur.execute(sql, params)
                else:
                    cur.execute(sql)
                return cur
            except Exception as e:
                err = str(e)
                if attempt == 0 and (self._is_connection_error(err) or self._is_auth_error(err)):
                    if self.log:
                        self.log.info(f"    [{self.db_name}] {'Auth' if self._is_auth_error(err) else 'Connection'} error, refreshing token and reconnecting...")
                    # Force evict the cached token so _get_fabric_token fetches a new one
                    _fabric_token_cache.pop('fabric_token', None)
                    self._connect()
                    continue
                raise

    def commit(self):
        self._conn.commit()

    def scalar(self, sql, params=None):
        cur = self.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None

    def fetchall(self, sql, params=None):
        cur = self.execute(sql, params)
        return cur.fetchall()

    def count(self, table, schema="dbo"):
        return self.scalar(self.qualify(table, schema, count=True))

    def qualify(self, table, schema="dbo", count=False):
        if self.is_crossdb:
            ref = f"[{self.db_name}].[{schema}].[{table}]"
        else:
            ref = f"[{schema}].[{table}]"
        if count:
            return f"SELECT COUNT(*) FROM {ref}"
        return ref

    def close(self):
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logger(name):
    """Create a logger that writes to both console and a timestamped log file."""
    os.makedirs(LOG_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(LOG_DIR, f"{timestamp}_{name}.log")

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
    logger.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)

    logger.info(f"Log file: {log_file}")
    return logger


# ---------------------------------------------------------------------------
# TriageLog — ticket intelligence in [DB_BI_SUPPORT].[hd].*
#
# Replaces the old SQLite triage_log.db. No step-by-step findings log: one
# knowledge write per ticket at close (what was broken, why, the fix, and the
# one query that proves it). All logging is AUTONOMOUS — open_ticket at
# intake, close_ticket before a ticket is considered done.
# ---------------------------------------------------------------------------

class TriageLog:
    """Logger + knowledge-base reader for hd.* in DB_BI_SUPPORT.

    Everything runs on a DIRECT connection (lazy) — the WH_STAGING tunnel
    cannot see views and cannot write, so it is useless for hd.* work.

        tri = TriageLog(env, log)
        tri.open_ticket("INC-276700", summary="...", report_name="...",
                        requester="...", target_metric="...")
        ... investigate ...
        tri.add_object("INC-276700", "measure", "Flag Fall Total", "affected")
        tri.close_ticket("INC-276700", status="resolved",
                         problem_category="ETL_BUG",
                         root_cause="...", solution="...",
                         ticket_response="...", keywords="lease count, canada",
                         validation_query="SELECT ...",
                         matched_flag_type="NONE")
    """

    TICKET_FIELDS = {
        "opened_date", "requester", "summary", "report_name", "dataset_name",
        "target_metric", "target_db", "target_object", "expected_value",
        "reported_value", "status", "freshdesk_url",
    }
    CLOSE_FIELDS = {
        "problem_category", "root_cause", "solution", "ticket_response",
        "keywords", "validation_query", "matched_flag_type", "recurrence_of",
        "freshdesk_url", "closed_date",
    }

    def __init__(self, env, log=None):
        self.env = env
        self.log = log
        self._write = None   # direct connection (lazy)

    # -- connections --------------------------------------------------------
    def _w(self):
        if self._write is None:
            self._write = get_bisupport_write_connection(self.env, self.log)
        return self._write

    @staticmethod
    def _dicts(cur):
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def _exec(self, sql, params=()):
        cur = self._w().cursor()
        cur.execute(sql, params)
        return cur

    # -- writes (autonomous) -------------------------------------------------
    def open_ticket(self, ticket_id, **fields):
        """Upsert the intake row. Call at Phase 1, always."""
        bad = set(fields) - self.TICKET_FIELDS
        if bad:
            raise ValueError(f"Unknown ticket fields: {bad}")
        fields.setdefault("opened_date", datetime.now().strftime("%Y-%m-%d"))
        exists = self._exec(
            "SELECT 1 FROM hd.tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
        if exists:
            sets = ", ".join(f"{k} = ?" for k in fields)
            self._exec(
                f"UPDATE hd.tickets SET {sets}, updated_at_utc = SYSUTCDATETIME() "
                f"WHERE ticket_id = ?",
                (*fields.values(), ticket_id))
        else:
            cols = ", ".join(["ticket_id", *fields])
            marks = ", ".join("?" * (len(fields) + 1))
            self._exec(
                f"INSERT INTO hd.tickets ({cols}) VALUES ({marks})",
                (ticket_id, *fields.values()))
        if self.log:
            self.log.info(f"    [hd.tickets] upserted {ticket_id}")

    def add_object(self, ticket_id, object_type, object_name, role="affected"):
        """Tag an affected/root-cause object (dataset|report|measure|table|column|sp|dataflow|source_system)."""
        dup = self._exec(
            "SELECT 1 FROM hd.ticket_objects WHERE ticket_id = ? AND object_type = ? "
            "AND object_name = ? AND role = ?",
            (ticket_id, object_type, object_name, role)).fetchone()
        if dup:
            return
        self._exec(
            "INSERT INTO hd.ticket_objects (ticket_id, object_type, object_name, role) "
            "VALUES (?, ?, ?, ?)",
            (ticket_id, object_type, object_name, role))

    def close_ticket(self, ticket_id, status="resolved", **fields):
        """THE knowledge write. A ticket is not done until this has succeeded.

        Expected fields: problem_category, root_cause, solution,
        ticket_response, keywords, validation_query, matched_flag_type
        ('NONE' if health flags were checked and clear), recurrence_of.
        """
        bad = set(fields) - self.CLOSE_FIELDS
        if bad:
            raise ValueError(f"Unknown close fields: {bad}")
        missing = [k for k in ("problem_category", "root_cause", "solution")
                   if not fields.get(k)]
        if missing and self.log:
            self.log.info(f"    [hd.tickets] WARNING: closing {ticket_id} "
                          f"without {missing} — knowledge base value is low")
        fields.setdefault("closed_date", datetime.now().strftime("%Y-%m-%d"))
        exists = self._exec(
            "SELECT 1 FROM hd.tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
        if not exists:
            self._exec("INSERT INTO hd.tickets (ticket_id, opened_date) VALUES (?, ?)",
                       (ticket_id, datetime.now().strftime("%Y-%m-%d")))
        sets = ", ".join(f"{k} = ?" for k in fields)
        self._exec(
            f"UPDATE hd.tickets SET status = ?, {sets}, "
            f"updated_at_utc = SYSUTCDATETIME() WHERE ticket_id = ?",
            (status, *fields.values(), ticket_id))
        if self.log:
            self.log.info(f"    [hd.tickets] closed {ticket_id} ({status})")

    def add_known_issue(self, title, description, guidance=None,
                        object_names=None, keywords=None, source_tickets=None):
        """Promote a reusable pattern. Upserts on title."""
        exists = self._exec(
            "SELECT issue_id FROM hd.known_issues WHERE title = ?", (title,)).fetchone()
        if exists:
            self._exec(
                "UPDATE hd.known_issues SET description = ?, guidance = ?, "
                "object_names = ?, keywords = ?, source_tickets = ?, "
                "updated_at_utc = SYSUTCDATETIME() WHERE title = ?",
                (description, guidance, object_names, keywords, source_tickets, title))
        else:
            self._exec(
                "INSERT INTO hd.known_issues (title, description, guidance, "
                "object_names, keywords, source_tickets) VALUES (?, ?, ?, ?, ?, ?)",
                (title, description, guidance, object_names, keywords, source_tickets))
        if self.log:
            self.log.info(f"    [hd.known_issues] upserted: {title}")

    # -- reads (knowledge-base-first triage) ---------------------------------
    def find_similar(self, terms):
        """Search known issues + past-ticket knowledge for any of `terms`.

        Returns {'known_issues': [...], 'tickets': [...]} of dict rows.
        """
        if isinstance(terms, str):
            terms = [terms]
        terms = [t.upper().replace("'", "''") for t in terms if t]
        if not terms:
            return {"known_issues": [], "tickets": []}

        def _like(cols):
            return " OR ".join(
                f"UPPER(COALESCE({c}, '')) LIKE '%{t}%'" for c in cols for t in terms)

        ki = self._exec(
            f"SELECT title, description, guidance, object_names, source_tickets "
            f"FROM hd.vw_known_issues "
            f"WHERE {_like(['title', 'description', 'keywords', 'object_names'])}")
        known = self._dicts(ki)
        tk = self._exec(
            f"SELECT ticket_id, closed_date, status, report_name, dataset_name, "
            f"target_metric, summary, problem_category, root_cause, solution, "
            f"validation_query, recurrence_of, objects "
            f"FROM hd.vw_ticket_knowledge "
            f"WHERE {_like(['summary', 'keywords', 'root_cause', 'solution', 'target_metric', 'target_object', 'report_name', 'objects'])} "
            f"ORDER BY closed_date DESC")
        tickets = self._dicts(tk)
        if self.log:
            self.log.info(f"    [knowledge base] {len(known)} known issues, "
                          f"{len(tickets)} past tickets match {terms}")
        return {"known_issues": known, "tickets": tickets}

    def close(self):
        if self._write is not None:
            try:
                self._write.close()
            except Exception:
                pass
        self._write = None


# ---------------------------------------------------------------------------
# DEPRECATED: SQLite triage log. Ticket intelligence now lives in
# [DB_BI_SUPPORT].[hd].* via TriageLog. Kept read-only for the one-time
# migration (scripts/migrate_triage_log.py).
# ---------------------------------------------------------------------------

def get_triage_db(path=None):
    """DEPRECATED — opens the legacy SQLite file read-only-ish for migration."""
    p = path or TRIAGE_DB_PATH
    if not os.path.exists(p):
        raise FileNotFoundError(
            f"{p} not found. The SQLite triage log is retired — use TriageLog(env).")
    conn = sqlite3.connect(p)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn
