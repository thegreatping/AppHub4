import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()

conn = SafeConnection(env, "WH_STAGING", None)

# Deep dive: EMPLOYEE_F_COMBO_SP - does it JOIN EMPLOYEE_TITLE_GROUPS_0 anywhere?
sp = conn.fetchall("SELECT definition FROM sys.sql_modules WHERE OBJECT_NAME(object_id) = 'EMPLOYEE_F_COMBO_SP'")
text = sp[0][0]

# Check if EMPLOYEE_TITLE_GROUPS_0 is in this SP at all
if 'EMPLOYEE_TITLE_GROUPS_0' in text:
    idx = text.find('EMPLOYEE_TITLE_GROUPS_0')
    print(f"Found at pos {idx}:")
    print(text[max(0,idx-200):idx+400])
else:
    print("EMPLOYEE_TITLE_GROUPS_0 is NOT referenced in EMPLOYEE_F_COMBO_SP")

# Now find how EMPLOYEE_TITLES_0 is INSERT-ed (what columns/sources)
idx = text.find('INTO [dbo].[EMPLOYEE_TITLES_0]')
if idx < 0:
    idx = text.find('INTO EMPLOYEE_TITLES_0')
if idx < 0:
    idx = text.find('[EMPLOYEE_TITLES_0]')
    # search for INSERT context
    while idx > 0 and 'INSERT' not in text[max(0,idx-100):idx]:
        idx = text.find('[EMPLOYEE_TITLES_0]', idx+1)

if idx >= 0:
    start = max(0, idx - 200)
    end = min(len(text), idx + 1000)
    print(f"\n=== INSERT into EMPLOYEE_TITLES_0 ===")
    print(text[start:end])

conn.close()
