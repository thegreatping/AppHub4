import sys
sys.path.insert(0, '../Help Ticket Triage/bi-triage-agent/scripts')
from helpers import load_env, _msal_silent_refresh

env = load_env()
token = _msal_silent_refresh(env)
if token:
    print("Token acquired successfully:", token[:20], "...")
else:
    print("Silent refresh failed - need interactive login")
    print("Run: az login  OR  use the Azure CLI to refresh")
