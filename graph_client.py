"""Microsoft Graph API client helper for AppHub 4.0.

Uses MSAL client-credentials flow. Requires the app registration to have
'Sites.ReadWrite.All' (application permission) consented in Azure AD.

Env vars (same as Flask config):
    AZURE_TENANT_ID
    AZURE_CLIENT_ID
    AZURE_CLIENT_SECRET
"""
import time
import msal
import requests
from flask import current_app

_token_cache: dict = {}  # {access_token, expires_at}


def _get_token() -> str:
    """Acquire (or re-use cached) app-only Graph token. Refreshes 60s before expiry."""
    cached = _token_cache.get("access_token")
    if cached and time.time() < _token_cache.get("expires_at", 0) - 60:
        return cached

    tenant_id = current_app.config.get("GRAPH_TENANT_ID", "")
    client_id = current_app.config.get("GRAPH_CLIENT_ID", "")
    client_secret = current_app.config.get("GRAPH_CLIENT_SECRET", "")

    if not (tenant_id and client_id and client_secret):
        raise RuntimeError(
            "Graph API credentials not configured. "
            "Set GRAPH_TENANT_ID, GRAPH_CLIENT_ID, and GRAPH_CLIENT_SECRET "
            "(FabricPipelineApp service principal)."
        )

    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        err = result.get("error_description", result.get("error", "unknown"))
        raise RuntimeError(f"MSAL token acquisition failed: {err}")

    _token_cache["access_token"] = result["access_token"]
    _token_cache["expires_at"] = time.time() + result.get("expires_in", 3600)
    return result["access_token"]


def _headers() -> dict:
    return {"Authorization": f"Bearer {_get_token()}", "Content-Type": "application/json"}


# ─── SITE RESOLUTION ────────────────────────────────────────────────────────────

_site_id_cache: dict = {}


def get_site_id(site_path: str) -> str:
    """Resolve a SharePoint site path to a Graph site ID.

    Args:
        site_path: e.g. 'peakcampus.sharepoint.com:/sites/BaseCampApps'
    """
    if site_path in _site_id_cache:
        return _site_id_cache[site_path]

    url = f"https://graph.microsoft.com/v1.0/sites/{site_path}"
    r = requests.get(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    site_id = r.json()["id"]
    _site_id_cache[site_path] = site_id
    return site_id


# ─── LIST OPERATIONS ─────────────────────────────────────────────────────────────

def list_items(site_id: str, list_id: str, fields: list[str] | None = None, top: int = 500) -> list[dict]:
    """Fetch items from a SharePoint list.

    Args:
        site_id:  Graph site ID (from get_site_id)
        list_id:  SharePoint list GUID
        fields:   optional list of field names to select ($select)
        top:      max items per page (Graph max is 5000, but keep reasonable)

    Returns list of field dicts (each item's 'fields' sub-object).
    """
    select = ""
    if fields:
        select = f"&$select={','.join(fields)}"

    results = []
    url = (
        f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}"
        f"/items?$top={top}&$expand=fields{select}"
    )
    while url:
        r = requests.get(url, headers=_headers(), timeout=30)
        r.raise_for_status()
        data = r.json()
        for item in data.get("value", []):
            row = item.get("fields", {})
            row["_item_id"] = item["id"]  # SharePoint item ID
            results.append(row)
        url = data.get("@odata.nextLink")

    return results


def create_item(site_id: str, list_id: str, fields: dict) -> dict:
    """Create a new item in a SharePoint list.

    Args:
        fields: dict of SharePoint column internal names → values

    Returns the created item's fields dict (includes _item_id for attachment use).
    """
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items"
    payload = {"fields": fields}
    r = requests.post(url, headers=_headers(), json=payload, timeout=15)
    r.raise_for_status()
    item = r.json()
    result = item.get("fields", {})
    result["_item_id"] = item.get("id", "")  # numeric SP item ID as string
    return result


# ─── SHAREPOINT REST API (ATTACHMENTS) ───────────────────────────────────────────

_sp_token_cache: dict = {}


def _get_sp_token(hostname: str = "peakcampus.sharepoint.com") -> str:
    """Acquire an app-only token scoped to SharePoint REST API (not Graph)."""
    cached = _sp_token_cache.get(hostname)
    if cached and time.time() < _sp_token_cache.get(f"{hostname}_expires_at", 0) - 60:
        return cached

    tenant_id = current_app.config.get("GRAPH_TENANT_ID", "")
    client_id = current_app.config.get("GRAPH_CLIENT_ID", "")
    client_secret = current_app.config.get("GRAPH_CLIENT_SECRET", "")

    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(scopes=[f"https://{hostname}/.default"])
    if "access_token" not in result:
        err = result.get("error_description", result.get("error", "unknown"))
        raise RuntimeError(f"SP token acquisition failed: {err}")

    _sp_token_cache[hostname] = result["access_token"]
    _sp_token_cache[f"{hostname}_expires_at"] = time.time() + result.get("expires_in", 3600)
    return result["access_token"]


def add_sp_attachment(site_base_url: str, list_guid: str, item_id: str, filename: str, file_bytes: bytes) -> dict:
    """Upload a file as a SharePoint list item attachment via SP REST API.

    Args:
        site_base_url: e.g. 'https://peakcampus.sharepoint.com/sites/BaseCampApps'
        list_guid:     SP list GUID (without braces)
        item_id:       SP item ID (string, e.g. '1')
        filename:      destination filename on SP
        file_bytes:    raw file content
    """
    import urllib.parse
    hostname = urllib.parse.urlparse(site_base_url).netloc
    token = _get_sp_token(hostname)
    safe_name = urllib.parse.quote(filename, safe="")
    url = (
        f"{site_base_url}/_api/web/lists(guid'{list_guid}')"
        f"/items({item_id})/AttachmentFiles/add(FileName='{safe_name}')"
    )
    r = requests.post(
        url,
        data=file_bytes,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json;odata=verbose",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def get_list_columns(site_id: str, list_id: str) -> list[dict]:
    """Fetch column definitions for a SharePoint list (for introspection/debugging)."""
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/columns"
    r = requests.get(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json().get("value", [])
