import sys, json
sys.path.insert(0, ".")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
rows = conn.fetchall("SELECT app_id, theme, overrides, updated_by, updated_at FROM dbo.APPHUB_THEME_SETTINGS ORDER BY app_id, theme")
if not rows:
    print("No rows found.")
else:
    for r in rows:
        print(f"\n--- app_id={r[0]}  theme={r[1]}  by={r[3]}  at={r[4]}")
        try:
            parsed = json.loads(r[2] or '{}')
            for k, v in parsed.items():
                print(f"    {k}: {v}")
        except:
            print("    (could not parse overrides)")
