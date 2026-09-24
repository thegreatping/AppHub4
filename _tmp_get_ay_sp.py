import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)

# Get the SP definition
rows = conn.fetchall("""
    SELECT OBJECT_DEFINITION(OBJECT_ID('dbo.APP_PROPERTY_AY_SYNC_SP'))
""")
if rows and rows[0][0]:
    print(rows[0][0])
else:
    print("(not found or no definition)")
