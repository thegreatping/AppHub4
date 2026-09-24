import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'WH_STAGING', None, direct=True)

rows = conn.fetchall("SELECT * FROM [dbo].[AY_0] ORDER BY AY_KEY")
if rows:
    # print header from first row keys
    cols = [d[0] for d in conn._cursor.description] if hasattr(conn, '_cursor') else None
    for r in rows:
        print(r)
else:
    print("(empty)")
