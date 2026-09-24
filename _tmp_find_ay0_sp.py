import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from helpers import load_env, SafeConnection

env = load_env()

# Search DB_APP_SUPPORT
print("=== DB_APP_SUPPORT ===")
conn1 = SafeConnection(env, 'DB_APP_SUPPORT', None, direct=True)
rows = conn1.fetchall("""
    SELECT r.ROUTINE_SCHEMA, r.ROUTINE_NAME, 
           OBJECT_DEFINITION(OBJECT_ID(r.ROUTINE_SCHEMA+'.'+r.ROUTINE_NAME)) AS def
    FROM INFORMATION_SCHEMA.ROUTINES r
    WHERE r.ROUTINE_TYPE = 'PROCEDURE'
""")
for schema, name, defn in rows:
    if defn and 'AY_0' in defn:
        print(f"  {schema}.{name}")

# Search WH_STAGING
print("\n=== WH_STAGING ===")
conn2 = SafeConnection(env, 'WH_STAGING', None, direct=True)
rows2 = conn2.fetchall("""
    SELECT r.ROUTINE_SCHEMA, r.ROUTINE_NAME,
           OBJECT_DEFINITION(OBJECT_ID(r.ROUTINE_SCHEMA+'.'+r.ROUTINE_NAME)) AS def
    FROM INFORMATION_SCHEMA.ROUTINES r
    WHERE r.ROUTINE_TYPE = 'PROCEDURE'
""")
for schema, name, defn in rows2:
    if defn and 'AY_0' in defn:
        print(f"  {schema}.{name}")
