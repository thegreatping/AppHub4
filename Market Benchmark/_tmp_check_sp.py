import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Max date in COMP_ASSIGNMENTS
rows = conn.execute("SELECT TOP 1 DATE_KEY FROM dbo.COMP_ASSIGNMENTS ORDER BY DATE_KEY DESC").fetchall()
print("Max DATE_KEY in COMP_ASSIGNMENTS:", rows)

# Check the SP definition
try:
    sp_text = conn.execute("""
        SELECT m.definition 
        FROM sys.sql_modules m
        JOIN sys.procedures p ON m.object_id = p.object_id
        WHERE p.name = 'MS_Comp_Assignment_Projector_SP'
    """).fetchone()
    if sp_text:
        print("\n--- SP DEFINITION ---")
        print(sp_text[0][:3000])
    else:
        print("SP not found in DB_APP_SUPPORT")
except Exception as e:
    print(f"Error: {e}")

# Check WEEKS for 20260726
rows2 = conn.execute("SELECT DATE_KEY, RELATIVE_WEEK FROM dbo.WEEKS WHERE DATE_KEY >= 20260719 ORDER BY DATE_KEY").fetchall()
print("\nWEEKS >= 20260719:", rows2[:5])
