import sys, os
sys.path.insert(0, r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts')
from helpers import SafeConnection
from dotenv import load_dotenv
load_dotenv(r'C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts\.env')
env = os.environ
conn = SafeConnection(env, "WH_STAGING", None)
rows = conn.fetchall("SELECT TOP 5 NAME_FULL, EMAIL FROM dbo.EMPLOYEE_F WHERE FLAG_ACTIVE = 1 AND NAME_FULL LIKE '%Pell%'")
print(f"LIKE Pell: {rows}")
rows2 = conn.fetchall("SELECT TOP 5 NAME_FULL, EMAIL FROM dbo.EMPLOYEE_F WHERE FLAG_ACTIVE = 1 AND EMAIL LIKE '%cpell%'")
print(f"EMAIL cpell: {rows2}")
conn.close()
