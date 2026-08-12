import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "WH_STAGING", None)

# Get EMPLOYEE_SOFT_TERMINATIONS_SP definition
print("=== EMPLOYEE_SOFT_TERMINATIONS_SP (full) ===")
sp = conn.fetchall("SELECT definition FROM sys.sql_modules WHERE OBJECT_NAME(object_id) = 'EMPLOYEE_SOFT_TERMINATIONS_SP'")
if sp:
    print(sp[0][0][:3000])
    print("...")

# Get ACTIVE_EMPS_FOR_AD_SP definition (first 3000 chars)
print("\n\n=== ACTIVE_EMPS_FOR_AD_SP (first 4000 chars) ===")
sp = conn.fetchall("SELECT definition FROM sys.sql_modules WHERE OBJECT_NAME(object_id) = 'ACTIVE_EMPS_FOR_AD_SP'")
if sp:
    text = sp[0][0]
    print(text[:4000])
    # Find where SOFT_TERM is referenced
    idx = text.find('SOFT_TERM')
    if idx > 0:
        print(f"\n... SOFT_TERM context at position {idx} ...")
        print(text[max(0,idx-300):idx+500])

conn.close()
