"""
Reset APPHUB_THEME_SETTINGS _global rows back to empty so CSS defaults take over.
Presets are left untouched.
"""
import sys
sys.path.insert(0, ".")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

conn.execute("DELETE FROM dbo.APPHUB_THEME_SETTINGS WHERE app_id = '_global'")
print("Deleted all _global theme overrides. CSS defaults will now render cleanly.")
print("Presets are untouched.")
