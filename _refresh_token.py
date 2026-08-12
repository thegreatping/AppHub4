"""Refresh the Fabric SQL token via azure.identity.AzureCliCredential and save it BOM-free."""
import json, os, time

TOKEN_PATH = r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts\.fabric_token.json"

from azure.identity import AzureCliCredential
cred = AzureCliCredential()
tok = cred.get_token("https://database.windows.net/.default")

out = {"token": tok.token, "expires_on": int(tok.expires_on)}
with open(TOKEN_PATH, "w", encoding="utf-8", newline="\n") as f:
    json.dump(out, f)

margin = (int(tok.expires_on) - time.time()) / 60
print(f"Token saved. expires_on={tok.expires_on}, margin={margin:.1f} min, length={len(tok.token)}")

# Quick read-back check
with open(TOKEN_PATH, encoding="utf-8") as f:
    check = json.load(f)
print(f"Read-back OK. Token starts: {check['token'][:20]}...")
