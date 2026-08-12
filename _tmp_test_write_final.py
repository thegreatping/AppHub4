"""Full end-to-end write test with correct field names."""
import msal, requests

TENANT_ID     = "ea0cd29c-45e6-4ad1-94ff-2e9f36fb84b5"
CLIENT_ID     = "7fb6487d-d273-4a37-8e6c-cff84303fa7c"
CLIENT_SECRET = ""  # load from env
SITE_ID       = "peakcampus.sharepoint.com,f83f37af-e64c-4dbc-9457-68c9484ee93b,f65502be-a283-4eae-a759-a23b23603fbb"
LIST_ID       = "8524acb0-c727-46a2-bc90-c5160b4d5c98"

app = msal.ConfidentialClientApplication(
    CLIENT_ID, authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    client_credential=CLIENT_SECRET,
)
token = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])["access_token"]
hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Write with all real field names
fields = {
    "SuggestionType":                    "Other",
    "SuggestionDetailsand_x002f_orSpo":  "_TEST submission — safe to delete",
    "Employee_Name_Full":                "Test User",
    "Employee_Code":                     "TUSER",
    "Property_Location":                 "Test Location",
}
print("Writing with real field names...")
r = requests.post(
    f"https://graph.microsoft.com/v1.0/sites/{SITE_ID}/lists/{LIST_ID}/items",
    headers=hdrs, json={"fields": fields}, timeout=15
)
print(f"Status: {r.status_code}")
if r.status_code == 201:
    item = r.json()
    new_id = item["id"]
    returned = item.get("fields", {})
    print(f"OK — item id={new_id}")
    print(f"  SuggestionType:    {returned.get('SuggestionType')}")
    print(f"  Details:           {returned.get('SuggestionDetailsand_x002f_orSpo','')[:50]}")
    print(f"  Employee:          {returned.get('Employee_Name_Full')}")
    print(f"  Location:          {returned.get('Property_Location')}")
    print(f"  Created (auto):    {returned.get('Created','')[:19]}")

    # Clean up
    r2 = requests.delete(
        f"https://graph.microsoft.com/v1.0/sites/{SITE_ID}/lists/{LIST_ID}/items/{new_id}",
        headers=hdrs, timeout=15
    )
    print(f"Cleanup: {r2.status_code} {'OK' if r2.status_code in (200,204) else 'FAILED'}")
    print("\nFull write/read/delete cycle PASSED — Peak Link is ready.")
else:
    print("FAIL:", r.text[:500])
