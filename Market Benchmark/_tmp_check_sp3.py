import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

sp_text = conn.execute("""
    SELECT m.definition 
    FROM sys.sql_modules m
    JOIN sys.procedures p ON m.object_id = p.object_id
    WHERE p.name = 'MS_Comp_Assignment_Projector_SP'
""").fetchone()

if sp_text:
    print(sp_text[0])
