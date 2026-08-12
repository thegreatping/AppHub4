import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "WH_STAGING", None)

# Get ACTIVE_EMPS_FOR_AD_SP_TEST - see how it handles soft terminations
sp = conn.fetchall("SELECT definition FROM sys.sql_modules WHERE OBJECT_NAME(object_id) = 'ACTIVE_EMPS_FOR_AD_SP_TEST'")
text = sp[0][0]

# Find the soft termination handling
import re
for m in re.finditer(r'SOFT_TERM', text):
    ctx = text[max(0,m.start()-200):min(len(text),m.end()+300)]
    print(f"\n--- pos {m.start()} ---")
    print(ctx)
    print()

conn.close()
