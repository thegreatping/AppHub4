import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'WH_STAGING', None, direct=True)

sql = open(r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\de_remediation\AY_CUTOVER_ACTIONFLOW_SP.sql', encoding='utf-8').read()
conn.execute(sql)
print("AY_CUTOVER_ACTIONFLOW_SP deployed to WH_STAGING.")

# Confirm it exists
rows = conn.fetchall("SELECT ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_NAME = 'AY_CUTOVER_ACTIONFLOW_SP'")
print("Verified:", rows[0][0] if rows else "NOT FOUND")
