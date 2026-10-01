"""Open the Scorecard beta Testing Plan + Training Plan as Outlook drafts.
Follows the win32com HTMLBody + Display() pattern from CS_App/_send_stakeholder_email.py."""
import os
import win32com.client

HERE = os.path.dirname(__file__)
TESTING_HTML = os.path.join(HERE, "scorecard_testing_plan.html")
TRAINING_HTML = os.path.join(HERE, "scorecard_training_plan.html")

outlook = win32com.client.Dispatch("Outlook.Application")

with open(TESTING_HTML, "r", encoding="utf-8") as f:
    testing_body = f.read()
m1 = outlook.CreateItem(0)
m1.Subject = "Leadership Scorecard - Beta Testing Plan (role-by-role)"
m1.HTMLBody = testing_body
m1.Display()
print("Opened: Testing Plan draft")

with open(TRAINING_HTML, "r", encoding="utf-8") as f:
    training_body = f.read()
m2 = outlook.CreateItem(0)
m2.Subject = "Leadership Scorecard - Training Plan + Data Delivery Calendar"
m2.HTMLBody = training_body
m2.Display()
print("Opened: Training Plan draft")
