import sys, os, re
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Get all SP definitions that reference PROPERTY_0
cur = conn.execute("""
    SELECT m.definition, o.name
    FROM sys.sql_modules m
    JOIN sys.objects o ON m.object_id = o.object_id
    WHERE m.definition LIKE '%PROPERTY_0%'
    AND o.type IN ('P','FN','IF','TF','V','TR')
    ORDER BY o.name
""")
rows = cur.fetchall()
print(f"=== Objects referencing PROPERTY_0: {len(rows)} ===\n")

all_updated_cols = set()

for definition, name in rows:
    if not definition:
        continue
    
    # Find UPDATE...PROPERTY_0...SET blocks
    # Pattern: UPDATE ... PROPERTY_0 ... SET col1 = ..., col2 = ... WHERE
    segments = re.split(r'UPDATE\s+(?:\w+\.)*(?:\[?dbo\]?\.)?(?:\[?)?\s*PROPERTY_0', definition, flags=re.IGNORECASE)
    
    sp_cols = set()
    for seg in segments[1:]:  # after each UPDATE PROPERTY_0
        set_match = re.search(r'SET\s+(.*?)(?:\bWHERE\b|\bFROM\b|;\s*\n|\bUPDATE\b|\bINSERT\b|\bDELETE\b|\bEXEC\b|\bBEGIN\b)', seg, re.IGNORECASE | re.DOTALL)
        if set_match:
            set_block = set_match.group(1)
            cols = re.findall(r'\b(?:p\.)?\[?([A-Z][A-Z_0-9]+)\]?\s*=', set_block, re.IGNORECASE)
            for c in cols:
                c_upper = c.upper()
                if c_upper not in ('NULL', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'AND', 'OR', 'NOT', 'SELECT', 'FROM'):
                    sp_cols.add(c_upper)
                    all_updated_cols.add(c_upper)
    
    if sp_cols:
        print(f"  {name}:")
        for c in sorted(sp_cols):
            print(f"    -> {c}")
        print()

# Now also search local .py and .sql files for UPDATE PROPERTY_0
print("\n=== Searching local workspace files ===")
workspace = r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files"
for root, dirs, files in os.walk(workspace):
    # Skip .venv, node_modules, etc
    dirs[:] = [d for d in dirs if d not in ('.venv', 'node_modules', '__pycache__', '.git')]
    for fname in files:
        if fname.endswith(('.py', '.sql', '.txt')):
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                if 'PROPERTY_0' in content.upper() and 'UPDATE' in content.upper():
                    segments = re.split(r'UPDATE\s+(?:\w+\.)*(?:\[?dbo\]?\.)?(?:\[?)?\s*PROPERTY_0', content, flags=re.IGNORECASE)
                    file_cols = set()
                    for seg in segments[1:]:
                        set_match = re.search(r'SET\s+(.*?)(?:\bWHERE\b|\bFROM\b|;\s*\n|\bUPDATE\b|\bINSERT\b)', seg, re.IGNORECASE | re.DOTALL)
                        if set_match:
                            cols = re.findall(r'\[?([A-Z][A-Z_0-9]+)\]?\s*=', set_match.group(1), re.IGNORECASE)
                            for c in cols:
                                c_upper = c.upper()
                                if c_upper not in ('NULL','CASE','WHEN','THEN','ELSE','END','AND','OR','NOT','SELECT','FROM'):
                                    file_cols.add(c_upper)
                                    all_updated_cols.add(c_upper)
                    if file_cols:
                        rel = os.path.relpath(fpath, workspace)
                        print(f"  {rel}:")
                        for c in sorted(file_cols):
                            print(f"    -> {c}")
                        print()
            except:
                pass

print(f"\n{'='*60}")
print(f"TOTAL UNIQUE SYSTEM-UPDATED COLUMNS: {len(all_updated_cols)}")
print(f"{'='*60}")
for c in sorted(all_updated_cols):
    print(f"  {c}")

conn.close()
