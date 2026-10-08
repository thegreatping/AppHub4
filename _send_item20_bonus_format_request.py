"""Open the Item #20 (Bonus Calc Form format) request email in Outlook, addressed
to Molly, for Craig to review and send. Uses the Outlook COM approach so the
full inline-styled HTML is preserved (no browser copy/paste).
"""
import os

import win32com.client

html_path = os.path.join(os.path.dirname(__file__), "_email_item20_bonus_format_request.html")
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

outlook = win32com.client.Dispatch("Outlook.Application")
mail = outlook.CreateItem(0)
mail.To = "mblazier@peakmade.com"
mail.Subject = "Leadership Scorecard -- Fall Forecast export: Bonus Calc Form format"
mail.HTMLBody = html
mail.Display()

print("Draft opened in Outlook (To: mblazier@peakmade.com). Review and send.")
