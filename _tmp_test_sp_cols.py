"""Confirm write access and get real column internal names."""
import msal, requests

TENANT_ID     = "ea0cd29c-45e6-4ad1-94ff-2e9f36fb84b5"
CLIENT_ID     = "7fb6487d-d273-4a37-8e6c-cff84303fa7c"
CLIENT_SECRET = ""  # load from env
SITE_ID       = "peakcampus.sharepoint.com,f83f37af-e64c-4dbc-9457-68c9484ee93b,f65502be-a283-4eae-a759-a23b23603fbb"
LIST_ID       = "8524acb0-c727-46a2-bc90-c5160b4d5c98"

app = msal.ConfidentialClientApplication(
    CLIENT_ID,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    client_credential=CLIENT_SECRET,
)
token = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])["access_token"]
hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Get column definitions
print("=== SharePoint List Columns ===")
r = requests.get(f"https://graph.microsoft.com/v1.0/sites/{SITE_ID}/lists/{LIST_ID}/columns", headers=hdrs, timeout=15)
for col in r.json().get("value", []):
    if col.get("hidden") or col.get("readOnly"):
        continue
    name = col.get("name")
    display = col.get("displayName")
    col_type = "choice" if col.get("choice") else ("text" if col.get("text") else ("dateTime" if col.get("dateTime") else "other"))
    choices = col.get("choice", {}).get("choices", []) if col.get("choice") else []
    choice_str = " | choices: " + ", ".join(choices) if choices else ""
    print(f"  internal={name!r:35s}  display={display!r:35s}  type={col_type}{choice_str}")

# Confirm write with Title field (exists on every list)
print("\n=== Write test using Title field ===")
r = requests.post(
    f"https://graph.microsoft.com/v1.0/sites/{SITE_ID}/lists/{LIST_ID}/items",
    headers=hdrs,
    json={"fields": {"Title": "_PERMISSION_TEST_DELETE_ME"}},
    timeout=15
)
print(f"Status: {r.status_code}")
if r.status_code == 201:
    new_id = r.json().get("id")
    print(f"WRITE CONFIRMED — item created id={new_id}")
    r2 = requests.delete(
        f"https://graph.microsoft.com/v1.0/sites/{SITE_ID}/lists/{LIST_ID}/items/{new_id}",
        headers=hdrs, timeout=15
    )
    print(f"Cleanup: {r2.status_code}")
else:
    print("FAIL:", r.text[:400])
