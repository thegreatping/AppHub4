import sys; sys.path.insert(0,'.')
from dotenv import load_dotenv; load_dotenv()
from helpers import load_env, SafeConnection

conn = SafeConnection(load_env(), 'WH_STAGING', None, direct=True)
rows = conn.fetchall("SELECT OBJECT_DEFINITION(OBJECT_ID('dbo.AY_CUTOVER_ACTIONFLOW_SP'))")
defn = rows[0][0] if rows and rows[0][0] else None

if not defn:
    print("NOT FOUND")
elif 'BEGIN TRY' in defn or 'BEGIN TRANSACTION' in defn:
    print("WARNING: old version still deployed (TRY/TRANSACTION found)")
    print(defn)
else:
    print("CONFIRMED: clean version deployed (no TRY/TRANSACTION)")
    print(defn)
