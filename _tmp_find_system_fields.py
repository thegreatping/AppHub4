import sys, os, re
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()

# 1. Check stored procedures in DB_APP_SUPPORT that reference PROPERTY_0
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
cur = conn.execute("""
    SELECT ROUTINE_NAME 
    FROM INFORMATION_SCHEMA.ROUTINES 
    WHERE ROUTINE_DEFINITION LIKE '%PROPERTY_0%'
    ORDER BY ROUTINE_NAME
""")
sps = cur.fetchall()
print(f"=== Stored Procedures referencing PROPERTY_0 ({len(sps)}) ===")
for sp in sps:
    print(f"  {sp[0]}")

# 2. For each SP, find UPDATE/INSERT statements and extract column names
print("\n=== Columns UPDATED by each SP ===")
for sp in sps:
    cur2 = conn.execute(f"EXEC sp_helptext '{sp[0]}'")
    lines = [r[0] for r in cur2.fetchall()]
    sp_text = ''.join(lines)
    
    # Find UPDATE ... SET column = patterns
    update_cols = re.findall(r'(?:SET|,)\s+\[?(\w+)\]?\s*=', sp_text, re.IGNORECASE)
    # Filter to likely PROPERTY_0 updates (rough - look for UPDATE.*PROPERTY_0 context)
    if 'UPDATE' in sp_text.upper() and 'PROPERTY_0' in sp_text.upper():
        # Get all SET columns after UPDATE...PROPERTY_0
        segments = re.split(r'UPDATE\s+.*?PROPERTY_0', sp_text, flags=re.IGNORECASE)
        for seg in segments[1:]:  # after each UPDATE PROPERTY_0
            set_match = re.search(r'SET\s+(.*?)(?:WHERE|FROM|;|\bUPDATE\b|\bINSERT\b)', seg, re.IGNORECASE | re.DOTALL)
            if set_match:
                set_block = set_match.group(1)
                cols = re.findall(r'\[?(\w+)\]?\s*=', set_block)
                if cols:
                    print(f"\n  SP: {sp[0]}")
                    for c in cols:
                        print(f"    -> {c}")

conn.close()
