import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Get the SP definitions to understand what they do
print("=== EMPLOYEE_PREHIRES_APPSUPPORT_SP ===")
sp = conn.fetchall("SELECT definition FROM sys.sql_modules WHERE OBJECT_NAME(object_id) = 'EMPLOYEE_PREHIRES_APPSUPPORT_SP'")
if sp:
    # Print first 2000 chars
    text = sp[0][0]
    print(text[:3000])

print("\n\n=== EMPLOYEE_SECURITY_ROLES_SP ===")
sp = conn.fetchall("SELECT definition FROM sys.sql_modules WHERE OBJECT_NAME(object_id) = 'EMPLOYEE_SECURITY_ROLES_SP'")
if sp:
    text = sp[0][0]
    print(text[:3000])

conn.close()
