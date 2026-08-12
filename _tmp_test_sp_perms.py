"""Test FabricPipelineApp permissions against the PeakLink SharePoint list."""
import msal, requests, json

TENANT_ID     = "ea0cd29c-45e6-4ad1-94ff-2e9f36fb84b5"
CLIENT_ID     = "7fb6487d-d273-4a37-8e6c-cff84303fa7c"
CLIENT_SECRET = ""  # load from env
SITE_PATH     = "peakcampus.sharepoint.com:/sites/BaseCampApps"
LIST_ID       = "8524acb0-c727-46a2-bc90-c5160b4d5c98"

# 1. Get token
print("=== 1. Acquiring token (FabricPipelineApp) ===")
app = msal.ConfidentialClientApplication(
    CLIENT_ID,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    client_credential=CLIENT_SECRET,
)
result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
if "access_token" not in result:
    print("FAIL:", result.get("error_description", result))
    raise SystemExit(1)
print("OK — token acquired")

headers = {"Authorization": f"Bearer {result['access_token']}", "Content-Type": "application/json"}

# 2. Resolve site ID
print("\n=== 2. Resolving SharePoint site ID ===")
r = requests.get(f"https://graph.microsoft.com/v1.0/sites/{SITE_PATH}", headers=headers, timeout=15)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    site_id = r.json()["id"]
    print(f"Site ID: {site_id}")
else:
    print("FAIL:", r.text[:300])
    raise SystemExit(1)

# 3. Read list items (Sites.Read.All needed)
print("\n=== 3. Read list items (Sites.Read.All) ===")
r = requests.get(
    f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{LIST_ID}/items?$top=3&$expand=fields",
    headers=headers, timeout=15
)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    items = r.json().get("value", [])
    print(f"OK — got {len(items)} item(s). Read permission confirmed.")
    if items:
        fields = items[0].get("fields", {})
        readable = {k: v for k, v in fields.items() if not k.startswith("@")}
        print("Sample columns:", list(readable.keys())[:10])
else:
    print("FAIL:", r.text[:400])

# 4. Test write permission (Sites.ReadWrite.All needed)
print("\n=== 4. Write test (Sites.ReadWrite.All) ===")
test_fields = {
    "Suggestion_Type":    "_PERMISSION_TEST_DELETE_ME",
    "Suggestion_Details": "Automated permission test — safe to delete",
    "Employee_Name_Full": "test_script",
}
r = requests.post(
    f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{LIST_ID}/items",
    headers=headers,
    json={"fields": test_fields},
    timeout=15
)
print(f"Status: {r.status_code}")
if r.status_code == 201:
    new_id = r.json().get("id")
    print(f"OK — item created (id={new_id}). Write permission confirmed.")
    # Clean up test item
    r2 = requests.delete(
        f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{LIST_ID}/items/{new_id}",
        headers=headers, timeout=15
    )
    print(f"Cleanup delete status: {r2.status_code} ({'OK' if r2.status_code in (200,204) else 'FAILED'})")
else:
    body = r.json() if r.headers.get("content-type","").startswith("application/json") else r.text[:400]
    err = body.get("error", {}) if isinstance(body, dict) else body
    code = err.get("code","") if isinstance(err, dict) else ""
    msg  = err.get("message","") if isinstance(err, dict) else str(err)
    if "accessDenied" in code or "Forbidden" in str(r.status_code):
        print("DENIED — Sites.ReadWrite.All permission NOT granted (only Read is configured).")
    else:
        print(f"FAIL ({code}): {msg[:300]}")
