import sys
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import load_env, SafeConnection
env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)
rows = conn.fetchall('SELECT * FROM dbo.APP_LIST WHERE App_ID = 9')
print(rows)
# Get column names
cols = conn.fetchall("""SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='APP_LIST' ORDER BY ORDINAL_POSITION""")
print([c[0] for c in cols])
conn.close()
