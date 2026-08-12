import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "WH_STAGING", None)

# Get how EMPLOYEE_F_COMBO_SP uses these tables
sp = conn.fetchall("SELECT definition FROM sys.sql_modules WHERE OBJECT_NAME(object_id) = 'EMPLOYEE_F_COMBO_SP'")
text = sp[0][0]

# Find references to each table
for tbl in ['EMP_TITLE_GROUP_MGMT', 'EMPLOYEE_TITLES_0', 'EMP_ENTRATA_TITLE_GROUP_MAPPING']:
    idx = text.find(tbl)
    if idx >= 0:
        start = max(0, idx - 300)
        end = min(len(text), idx + 400)
        print(f"\n=== {tbl} in EMPLOYEE_F_COMBO_SP ===")
        print(text[start:end])
        print("---")

conn.close()
