"""Inspect the PeakLink SharePoint list schema and choice values."""
import sys, json
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env

env = load_env()
import requests, msal

TENANT_ID     = env.get("AZURE_TENANT_ID") or env.get("tenant_id")
CLIENT_ID     = env.get("AZURE_CLIENT_ID") or env.get("client_id")
CLIENT_SECRET = env.get("AZURE_CLIENT_SECRET") or env.get("client_secret")

SITE_URL   = "https://peakcampus.sharepoint.com/sites/BaseCampApps"
LIST_GUID  = "8524acb0-c727-46a2-bc90-c5160b4d5c98"

# Get token
app = msal.ConfidentialClientApplication(
    CLIENT_ID,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    client_credential=CLIENT_SECRET
)
result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
if "access_token" not in result:
    print("Token error:", result.get("error_description"))
    sys.exit(1)

headers = {"Authorization": f"Bearer {result['access_token']}", "Accept": "application/json"}

# Get site ID
r = requests.get(
    f"https://graph.microsoft.com/v1.0/sites/peakcampus.sharepoint.com:/sites/BaseCampApps",
    headers=headers
)
site_id = r.json().get("id")
print(f"Site ID: {site_id}")

# Get list columns
r = requests.get(
    f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{LIST_GUID}/columns",
    headers=headers
)
cols = r.json().get("value", [])
print(f"\n=== PeakLink List Columns ({len(cols)}) ===")
for c in cols:
    name = c.get("name")
    dtype = c.get("text") or c.get("number") or c.get("choice") or c.get("dateTime") or c.get("boolean") or "?"
    display = c.get("displayName")
    choices = None
    if c.get("choice"):
        choices = c["choice"].get("choices", [])
    print(f"  {name:40s} display='{display}'")
    if choices:
        print(f"    choices: {choices}")

# Get sample items
r = requests.get(
    f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{LIST_GUID}/items?$top=3&$expand=fields",
    headers=headers
)
items = r.json().get("value", [])
print(f"\n=== Sample items ({len(items)}) ===")
for item in items:
    print(json.dumps(item.get("fields", {}), indent=2, default=str)[:600])
    print("---")
