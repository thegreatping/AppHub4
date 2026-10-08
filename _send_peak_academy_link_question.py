"""Open the Peak Academy link question email in Outlook, addressed to Molly,
for Craig to review and send. Mirrors the existing _send_item20 pattern.
"""
import os

import win32com.client

html_path = os.path.join(os.path.dirname(__file__), "_email_peak_academy_link_question.html")
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

outlook = win32com.client.Dispatch("Outlook.Application")
mail = outlook.CreateItem(0)
mail.To = "mblazier@peakmade.com"
mail.Subject = "Leadership Scorecard -- Peak Academy link URL?"
mail.HTMLBody = html
mail.Display()

print("Draft opened in Outlook (To: mblazier@peakmade.com). Review and send.")
