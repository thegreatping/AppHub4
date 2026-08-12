import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "WH_STAGING", None)

sp = conn.fetchall("SELECT definition FROM sys.sql_modules WHERE OBJECT_NAME(object_id) = 'EMPLOYEE_F_COMBO_SP'")
text = sp[0][0]

# Find ALL occurrences of EMPLOYEE_TITLES
import re
for m in re.finditer(r'EMPLOYEE_TITLES', text):
    ctx = text[max(0,m.start()-80):min(len(text),m.end()+80)]
    print(f"  pos {m.start()}: ...{ctx}...")
    print()

conn.close()
