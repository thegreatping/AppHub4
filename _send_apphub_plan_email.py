import win32com.client
import os

html_path = os.path.join(os.path.dirname(__file__), "apphub_project_plan_email.html")

with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

outlook = win32com.client.Dispatch("Outlook.Application")
mail = outlook.CreateItem(0)
mail.Subject = "AppHub 4.0 -- Project Plan & Status (Aug 11, 2026)"
mail.HTMLBody = html
mail.Display()

print("Email draft opened in Outlook.")
