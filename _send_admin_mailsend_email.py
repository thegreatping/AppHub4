"""Open the Mail.Send admin-request email as an Outlook draft (COM).

Writes nothing to the network -- just composes a draft and Displays it so
Craig can set the recipient and hit Send himself.
"""
import os
import win32com.client

HERE = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(HERE, "_admin_email_mailsend_request.html")

with open(HTML_PATH, "r", encoding="utf-8") as fh:
    html_body = fh.read()

outlook = win32com.client.Dispatch("Outlook.Application")
mail = outlook.CreateItem(0)
mail.Subject = "Action needed: enable Mail.Send (delegated) for AppHub Scorecard"
mail.HTMLBody = html_body
mail.Display()  # shows the draft; does not send
print("Draft opened in Outlook. Set the recipient and send when ready.")
