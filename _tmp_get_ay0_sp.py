import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, 'WH_STAGING', None, direct=True)

for sp_name in ['dbo.AY_0_SP', 'dbo.ACADEMIC_YEAR_0_SP']:
    print(f"\n{'='*60}")
    print(f"  {sp_name}")
    print('='*60)
    rows = conn.fetchall(f"SELECT OBJECT_DEFINITION(OBJECT_ID('{sp_name}'))")
    if rows and rows[0][0]:
        print(rows[0][0])
    else:
        print("(not found)")
