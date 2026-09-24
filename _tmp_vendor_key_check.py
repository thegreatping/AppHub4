from helpers import load_env, SafeConnection
conn = SafeConnection(load_env(), "DB_APP_SUPPORT", None, direct=True)
r = conn.scalar("SELECT COLUMNPROPERTY(OBJECT_ID('dbo.VENDOR'), 'VENDOR_KEY', 'IsIdentity')")
print("VENDOR_KEY IsIdentity:", r)
print("Max VENDOR_KEY:", conn.scalar("SELECT MAX(VENDOR_KEY) FROM dbo.VENDOR"))
