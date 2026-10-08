"""Loads the LMS gold tables from WH_PROD2 and caches them.

The app never queries the warehouse per page view: it reads LMS_USERS and
LMS_ENROLLMENT_FACTS once, keeps them in memory, and pickles a copy to disk so a
restart doesn't hit Fabric again until the TTL lapses.
"""

import os
import pickle
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd

USERS_SQL = """
SELECT LMS_USER_ID, EMPLOYEE_CODE, EMAIL, NAME_FULL, JOB_TITLE, DEPARTMENT, GROUP_TYPE, OFFICE,
       PROPERTY_TYPE_LMS, MANAGER_EMAIL, DATETIME_HIRED, FLAG_DELETED, FLAG_EMPLOYEE_MATCH, EMPLOYEE_STATUS,
       PROPERTY_KEY, PROPERTY_NAME, FLAG_CORPORATE_LOCATION,
       PM_NAME, PM_EMAIL, RM_NAME, RM_EMAIL, RVP_NAME, RVP_EMAIL, DATETIME_SYNCED
FROM dbo.LMS_USERS
"""

FACTS_SQL = """
SELECT LMS_ENROLLMENT_ID, LMS_COURSE_ID, LMS_USER_ID, COURSE_TITLE, COURSE_TYPE,
       FLAG_LEARNER, FLAG_CANCELLED, REGISTRATION_STATUS, COURSE_PASSING_STATUS,
       DATETIME_REGISTERED, DATETIME_STARTED, DATETIME_COMPLETED, DATETIME_DUE, TRAINING_MINUTES,
       FLAG_MANDATORY, FLAG_COMPLIANCE_SCOPE, FLAG_COMPLETED, FLAG_PAST_DUE, FLAG_COMPLETED_LATE,
       FLAG_COMPLIANT, COMPLIANCE_STATUS, DAYS_PAST_DUE, DAYS_TO_DUE, DATE_AS_OF, DATETIME_SYNCED
FROM dbo.LMS_ENROLLMENT_FACTS
"""

COURSES_SQL = """
SELECT LMS_COURSE_ID, COURSE_TITLE, COURSE_TYPE, COURSE_DESCRIPTION, DURATION_IN_MINUTES,
       FLAG_PUBLISHED, FLAG_REQUIRED, FLAG_DELETED, FLAG_SHOW_IN_CATALOG, FLAG_HAS_CERTIFICATE,
       DATETIME_CREATED
FROM dbo.LMS_COURSES
"""

PLAN_COURSES_SQL = """
SELECT LMS_TRAINING_PLAN_ID, TRAINING_PLAN_TITLE, LMS_COURSE_ID, COURSE_TITLE, COURSE_ORDER
FROM dbo.LMS_TRAINING_PLAN_COURSES
"""

# Bump when Snapshot's shape changes so a stale disk cache is ignored, not unpickled into new code.
SNAPSHOT_VERSION = 2


@dataclass
class Snapshot:
    users: pd.DataFrame
    facts: pd.DataFrame
    loaded_at: datetime
    courses: pd.DataFrame = field(default_factory=pd.DataFrame)
    plan_courses: pd.DataFrame = field(default_factory=pd.DataFrame)
    version: int = SNAPSHOT_VERSION

    @property
    def as_of(self):
        """Eastern date the compliance flags were computed for (LMS_ENROLLMENTS_0_SP run)."""
        if self.facts.empty:
            return None
        return datetime.strptime(str(int(self.facts["DATE_AS_OF"].max())), "%Y%m%d").date()

    @property
    def synced_at(self):
        """When Rohit's extract last pulled from the Zensai API."""
        s = self.facts["DATETIME_SYNCED"].max() if not self.facts.empty else None
        return None if pd.isna(s) else s


def _query(conn, sql):
    cur = conn.execute(sql)
    cols = [d[0] for d in cur.description]
    return pd.DataFrame.from_records([tuple(r) for r in cur.fetchall()], columns=cols)


def _connect():
    """Read-only WH_PROD2 connection via AppHub's shared helpers.

    Uses AppHub's SafeConnection (ODBC Driver 18, autocommit on). WH_PROD2 is a
    Fabric Warehouse, so its datawarehouse endpoint is the correct one to read.
    """
    from helpers import load_env, SafeConnection, setup_logger
    return SafeConnection(load_env(), "WH_PROD2", setup_logger("peak_academy"))


def load_from_warehouse():
    conn = _connect()
    try:
        users = _query(conn, USERS_SQL)
        facts = _query(conn, FACTS_SQL)
        courses = _query(conn, COURSES_SQL)
        plan_courses = _query(conn, PLAN_COURSES_SQL)
    finally:
        conn.close()
    # PROD2 uses '--' as the "no RM/RVP" placeholder; treat it as missing.
    for col in ("PM_NAME", "PM_EMAIL", "RM_NAME", "RM_EMAIL", "RVP_NAME", "RVP_EMAIL"):
        users[col] = users[col].where(~users[col].isin(["--", ""]), None)
    return Snapshot(users=users, facts=facts, courses=courses, plan_courses=plan_courses,
                    loaded_at=datetime.now())


class Store:
    """Thread-safe snapshot holder with a TTL and a disk copy."""

    def __init__(self, cache_file, ttl_minutes, loader=load_from_warehouse):
        self.cache_file = cache_file
        self.ttl = timedelta(minutes=ttl_minutes)
        self.loader = loader
        self._snap = None
        self._lock = threading.Lock()

    def _fresh(self, snap):
        # Read the instance dict: a dataclass default would otherwise answer for an old pickle.
        return (snap is not None and vars(snap).get("version") == SNAPSHOT_VERSION
                and datetime.now() - snap.loaded_at < self.ttl)

    def get(self):
        if self._fresh(self._snap):
            return self._snap
        with self._lock:
            if self._fresh(self._snap):
                return self._snap
            disk = self._read_disk()
            self._snap = disk if self._fresh(disk) else self._reload()
            return self._snap

    def refresh(self):
        with self._lock:
            self._snap = self._reload()
            return self._snap

    def _reload(self):
        snap = self.loader()
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, "wb") as f:
                pickle.dump(snap, f)
        except OSError:
            pass
        return snap

    def _read_disk(self):
        try:
            with open(self.cache_file, "rb") as f:
                return pickle.load(f)
        except (OSError, pickle.UnpicklingError, EOFError, AttributeError):
            return None
