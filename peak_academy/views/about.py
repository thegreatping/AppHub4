"""Definitions: how every number is computed, and which rules still need sign-off."""

from flask import render_template

from .. import metrics
from . import bp

# (term, definition, confirmed?) Unconfirmed rows are the ones waiting on Sarah (RESEARCH_AGENDA.md).
DEFINITIONS = [
    ("Mandatory assignment",
     "An enrollment that has a due date, for a learner, not cancelled, and a course rather than a CORE plan. "
     "Courses associates enroll themselves in have no due date, so they never count. (Zensai's own report "
     "uses the same due-date test; the LMS \"required\" flag is off on every course.)",
     True),
    ("Compliance %",
     "Mandatory assignments not past due ÷ all mandatory assignments (Sarah's formula). "
     "Example: 3 of 4 not past due = 75%.", True),
    ("Past due / Not compliant",
     "A mandatory assignment that is not completed and whose due date (Eastern time) is before today.", True),
    ("Completed on time",
     "Completed on or before its due date. Counts as compliant.", True),
    ("Completed late",
     "Completed after its due date. Still counts as compliant: once it's done, it is no longer past due. "
     "The late flag stays visible. Zensai labels this \"Not Compliant - Completed\".", True),
    ("Compliance achievable",
     "Open, and due today or later.", True),
    ("Compliant associate (Overview)",
     "An associate with at least one mandatory assignment and none past due.", False),
    ("Associates / headcount",
     "LMS users matched to an Active or On Leave Paycom employee. Service accounts, deleted users and "
     "unmatched logins are excluded.", False),
    ("Location",
     "The associate's Paycom work location, mapped to the property list. Corporate associates roll up "
     "to their department (e.g. OPERATIONS - NOPS, ACCOUNTING); users with no match show as Unassigned.",
     False),
    ("Role",
     "The LMS \"group type\" (Leasing Consultant, Maintenance Technician, Property Manager, …).", False),
    ("Training hours",
     "Each completed course's catalog duration, credited once on its completion date. This is not "
     "measured seat time, which the LMS only reports for some content types.", False),
    ("CORE progress",
     "Courses in the learner's CORE plan they have completed ÷ courses in the plan. A course counts "
     "whether it was completed through the plan or separately.", False),
    ("CORE behind (red bar)",
     f"A CORE learner is flagged when the expected time of the plan courses they haven't finished is more than "
     f"{metrics.core_budget_label()} per workday (Mon–Fri) between today and the plan's due date, or the due date "
     f"has passed. Expected time is each course's listed duration; a course with none counts as the average of "
     f"its plan's other courses. Plans with no due date are never flagged. The {metrics.core_budget_label()} is a "
     f"placeholder until L&D sets the number.", False),
    ("Upcoming",
     "Open assignments due in the next 30 days.", True),
    ("Date range filter",
     "Applies only to course completions and training hours. Compliance, past due and upcoming always "
     "include every open assignment, whatever the range. Defaults to All time.", True),
    ("Dates",
     "All LMS timestamps are converted from UTC to Eastern time.", True),
    ("Who sees what",
     "Admins see every location. RVPs, RMs and PMs see the properties they are listed on in the property "
     "master. Everyone else sees nothing.", False),
    ("Data freshness",
     "The LMS is extracted nightly. The warehouse tables are rebuilt after that, and the app re-reads "
     "them every few hours (admins can refresh on demand).", False),
]

BLOCKED = [
    ("Training Category filter", "Categories and tags exist in the LMS, but the extract has nothing linking a "
                                 "course to its category."),
    ("Training hours budget (QTD)", "Shown on the mockup; no budget figure exists in any source yet."),
    ("Exceptions report", "No admin-exclusion data in the extract."),
    ("Questions & Answers report", "Quiz question text is truncated by the extract."),
]


@bp.route("/definitions")
def definitions():
    return render_template("definitions.html", definitions=DEFINITIONS, blocked=BLOCKED)
