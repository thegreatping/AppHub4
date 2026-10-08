"""Who is looking, and which locations they may see.

Scope comes from the property hierarchy already in LMS_USERS (PM / RM / RVP emails
from PROPERTY), so no Power BI RLS and no separate mapping table:

    admin  (LMS_ADMIN_EMAILS)   every location
    RVP / RM / PM               the properties where their email is the RVP / RM / PM
    anyone else                 nothing
"""

from dataclasses import dataclass, field

from .metrics import UNASSIGNED_KEY

ROLE_RANK = ["admin", "rvp", "rm", "pm", "none"]


@dataclass
class Viewer:
    email: str
    role: str = "none"
    name: str = ""
    # None = unrestricted (admin); otherwise the PROPERTY_KEYs this viewer may see.
    allowed_keys: set = field(default_factory=set)

    @property
    def is_admin(self):
        return self.role == "admin"

    def can_see(self, property_key):
        return self.allowed_keys is None or property_key in self.allowed_keys


def resolve(email, users, admin_emails):
    email = (email or "").strip().lower()
    if not email:
        return Viewer(email="")
    name = ""
    match = users[users["EMAIL"].str.lower() == email]
    if len(match):
        name = match.iloc[0]["NAME_FULL"] or ""
    if email in admin_emails:
        return Viewer(email=email, role="admin", name=name, allowed_keys=None)

    keys, roles = set(), []
    for role, col in (("rvp", "RVP_EMAIL"), ("rm", "RM_EMAIL"), ("pm", "PM_EMAIL")):
        hit = users[users[col].fillna("").str.lower() == email]["PROPERTY_KEY"].dropna()
        if len(hit):
            roles.append(role)
            keys |= {int(k) for k in hit}
    keys.discard(UNASSIGNED_KEY)
    role = min(roles, key=ROLE_RANK.index) if roles else "none"
    return Viewer(email=email, role=role, name=name, allowed_keys=keys)


def sample_viewers(users, admin_emails, per_role=4):
    """For the dev "view as" switcher: a few real RVPs / RMs / PMs from the data."""
    out = [("admin", sorted(admin_emails)[0] if admin_emails else "admin@local")]
    for role, col, name_col in (("rvp", "RVP_EMAIL", "RVP_NAME"), ("rm", "RM_EMAIL", "RM_NAME"),
                                ("pm", "PM_EMAIL", "PM_NAME")):
        pairs = users[[col, name_col]].dropna().drop_duplicates().sort_values(name_col).head(per_role)
        out += [(f"{role}: {n.title()}", e) for e, n in pairs.itertuples(index=False)]
    return out
