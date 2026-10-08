"""Open Questions: what L&D still needs to decide, so Sarah can answer async. Admin only.

Mirrors the Sarah section of docs/RESEARCH_AGENDA.md (same S-numbers). When one is
answered, record it in LMS_PROJECT.md and delete it from both places.
"""

from flask import render_template

from . import bp, export, require_admin, wants_export

# (heading, [(id, topic, question, what the app does today)])
QUESTIONS = [
    ("Before property managers get access (Wed 10/14)", [
        ("S13", "Admins",
         "Who should see every location? Admins also get the admin-only reports (Exclusions, Zero Training "
         "Assignments). For example: you, Erica and the BI team.",
         "Not set up yet."),
        ("S12", "Who sees a property",
         "Each property is visible to the PM, RM and RVP listed for it in the property master. Should anyone "
         "else see a property's data, such as assistant managers or leasing managers?",
         "PM, RM and RVP only. Anyone else sees no data."),
        ("S5", "Compliant associate",
         "The Overview donut counts an associate as compliant when none of their mandatory training is past "
         "due. Is that right?",
         "As described."),
        ("S4", "Corporate associates",
         "Corporate associates are grouped by department (Accounting, Operations - NOPS, Technology…), which "
         "show up as locations in the company-wide views. Is that how you want them reported?",
         "Grouped by department."),
    ]),
    ("Before the first month-end (10/31)", [
        ("S24", "Month-end compliance",
         "You report location compliance as of 11:59 pm on the last day of the month. To get that exactly, we "
         "need to save each location's compliance every day, starting this month. Is 11:59 pm Eastern on the "
         "last calendar day the official cut-off? September can't be recreated, since it was before go-live.",
         "Shows current compliance only."),
        ("S25", "Due-date time zone",
         "Most October training (e.g. Harassment Prevention, Fair Housing) is due at 12:30 am Eastern on 11/1, "
         "which is 11:30 pm on 10/31 Central. Does Zensai show these as due 10/31? "
         "If so, which time zone is your Zensai site set to? That decides which day they first count as past due.",
         "Shows Eastern time, so these read as due 11/1 and first count as past due on 11/2."),
        ("S3", "CORE plan due dates",
         "A CORE plan has its own due date. If a learner hasn't finished their plan by then, should that count "
         "against their location's compliance?",
         "Plan due dates don't affect compliance. Only individual courses with a due date count."),
        ("S6", "People who have left",
         "If someone leaves the company but their LMS account is still active, should their open training "
         "still count against their property's compliance?",
         "It counts until the LMS account is removed."),
        ("S20", "Fair Housing gaps",
         "As of 10/2, 11 Leasing Consultants and 8 Maintenance Technicians had no Fair Housing assignment. Is "
         "that intended? It's due 11/1 for everyone else.",
         "Shown as assigned in the LMS."),
        ("S21", "Until the 10/31 due dates",
         "Nearly all training is due 10/31–11/1, so compliance reads close to 100% until then. In the meantime, "
         "would a \"progress toward this month's due training\" view help (for example, 40% of training due "
         "10/31 is done)?",
         "Compliance only."),
    ]),
    ("When you get a chance", [
        ("S22", "CORE on-track flag",
         "A CORE learner's progress bar turns red when the course time left in their plan, spread over the "
         "workdays left before the due date, is more than 1 hour a day. The 1 hour is a placeholder: how many "
         "hours of training per workday should we assume? Also, 11 CORE courses have no length in the LMS "
         "catalog (e.g. Introduction to Entrata, Portals, Message Center Training). Until they're filled in, "
         "each counts as its plan's average course length.",
         "Built, with 1 hour per workday as a placeholder."),
        ("S23", "Upcoming tile",
         "At company level, what would you rather see in place of the Upcoming Courses tile? It stays as is "
         "for property managers.",
         "Upcoming (due in the next 30 days)."),
        ("S7", "Training hours",
         "Training hours use each course's listed duration, counted when the course is completed. Is that the "
         "official definition, or do you need actual time spent? The LMS only tracks that for some course "
         "types.",
         "Listed course duration."),
        ("S8", "Training hours budget",
         "The mockup shows a quarterly training hours budget. What is the number, is it per associate or "
         "company-wide, and who owns it?",
         "Tile shows \"–\"."),
        ("S9", "Training category filter",
         "Which categories should the Training Category filter offer? The LMS has 165 categories and 120 tags, "
         "but the data we receive doesn't link courses to them yet.",
         "Filter shown but disabled."),
        ("S10", "CORE grouping",
         "CORE progress is shown by role-based plan (CORE - Leasing Manager, …). Your mockup grouped it by "
         "phase (Company Orientation, Policies & Procedures…). Is by plan right?",
         "By plan."),
        ("S11", "Associate role filter",
         "The Associate role filter uses the LMS group type (about 33 roles). Would you rather filter by job "
         "title (about 165)?",
         "LMS group type."),
        ("S14", "Exclusions report",
         "We built Exclusions as every overdue assignment, with days overdue. In Grace Hill, did "
         "\"exclusions\" mean something else?",
         "Every overdue assignment."),
        ("S15", "Exceptions report",
         "Where in Zensai does an admin exclude someone from a training? We can't find it in the data we "
         "receive.",
         "Report blocked."),
        ("S16", "Questions & Answers report",
         "Do you still need the quiz Questions & Answers report from BI, or does Learn365's automation center "
         "cover it?",
         "Report blocked."),
        ("S19", "Temporary and part-time staff",
         "Temporary and part-time employees don't have LMS accounts, so no report includes them. Is that "
         "intended?",
         "Not included."),
        ("S18", "Grace Hill samples",
         "Could you share the \"Peak Academy BI Report\" OneDrive folder (or a zip) with Ryan, so the reports "
         "can match the old layouts?",
         "–"),
    ]),
]


@bp.route("/questions")
def questions():
    require_admin()
    if wants_export():
        rows = [{"id": q[0], "when": heading, "topic": q[1], "question": q[2], "today": q[3], "answer": ""}
                for heading, items in QUESTIONS for q in items]
        cols = [("id", "#"), ("when", "Needed"), ("topic", "Topic"), ("question", "Question"),
                ("today", "What the app does today"), ("answer", "Your answer")]
        return export(rows, cols, "open_questions")
    return render_template("questions.html", sections=QUESTIONS,
                           total=sum(len(items) for _, items in QUESTIONS))
