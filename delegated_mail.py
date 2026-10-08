"""Signed-in-user Graph mail with encrypted server-side MSAL caches."""
import base64
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import secrets
import sqlite3
import time

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, request, session
import msal
import requests

MAIL_SCOPES = ["Mail.Send"]
_MAX_AGE = 7 * 24 * 60 * 60


class MailUnavailable(Exception):
    pass


def _cipher():
    secret = current_app.config.get("SECRET_KEY")
    if not secret or secret == "dev-key-change-in-production":
        raise MailUnavailable("Email requires a configured FLASK_SECRET_KEY.")
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret).digest()))


@contextmanager
def _db():
    default_dir = Path("/home/data/apphub") if os.environ.get("WEBSITE_SITE_NAME") else Path(current_app.instance_path)
    path = Path(current_app.config.get("MAIL_CACHE_PATH") or default_dir / "delegated_mail.sqlite3")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    conn = sqlite3.connect(str(path), timeout=30)
    if os.name != "nt":
        path.chmod(0o600)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS caches (handle TEXT PRIMARY KEY, oid TEXT NOT NULL, payload BLOB NOT NULL, updated REAL NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS sends (send_key TEXT PRIMARY KEY, status TEXT NOT NULL, created REAL NOT NULL)")
        conn.execute("DELETE FROM caches WHERE updated < ?", (time.time() - _MAX_AGE,))
        conn.execute("DELETE FROM sends WHERE created < ?", (time.time() - _MAX_AGE,))
        conn.commit()
        with conn:
            yield conn
    finally:
        conn.close()


def discard_mail_cache():
    handle = session.pop("mail_cache_handle", None)
    if handle:
        with _db() as conn:
            conn.execute("DELETE FROM caches WHERE handle=?", (handle,))


def store_mail_cache(cache, oid):
    if not oid:
        raise MailUnavailable("Sign in again before using email.")
    payload = _cipher().encrypt(cache.serialize().encode("utf-8"))
    discard_mail_cache()
    handle = secrets.token_urlsafe(32)
    with _db() as conn:
        conn.execute("INSERT INTO caches VALUES (?, ?, ?, ?)", (handle, oid, payload, time.time()))
    session["mail_cache_handle"] = handle


def mail_block_reason():
    if current_app.config.get("LOCAL_AUTH_BYPASS") or os.environ.get("DEV_BYPASS", "").lower() == "true":
        return "Email is disabled during local authentication bypass."
    if session.get("is_impersonating") or any(session.get(key) for key in (
        "sc_view_as_email", "sc_view_as_pm_property_key", "sc_view_as_rvp_email", "sc_view_as_ed_email"
    )):
        return "Exit impersonation or View As before sending email."
    user = session.get("user") or {}
    if not user.get("oid") or user.get("oid") == "dev-mode" or not session.get("mail_cache_handle"):
        return "Sign out and sign in again to enable delegated email."
    return None


def _mail_token():
    reason = mail_block_reason()
    if reason:
        raise MailUnavailable(reason)
    handle = session["mail_cache_handle"]
    oid = session["user"]["oid"]
    with _db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT oid, payload FROM caches WHERE handle=?", (handle,)).fetchone()
        if not row or row[0] != oid:
            raise MailUnavailable("Sign out and sign in again to enable delegated email.")
        cache = msal.SerializableTokenCache()
        try:
            cache.deserialize(_cipher().decrypt(row[1]).decode("utf-8"))
        except InvalidToken:
            raise MailUnavailable("Sign out and sign in again to enable delegated email.") from None
        client = msal.ConfidentialClientApplication(
            current_app.config["AZURE_CLIENT_ID"],
            authority=current_app.config["AZURE_AUTHORITY"],
            client_credential=current_app.config["AZURE_CLIENT_SECRET"],
            token_cache=cache,
        )
        account = next((account for account in client.get_accounts() if account.get("local_account_id") == oid), None)
        if not account:
            raise MailUnavailable("Sign out and sign in again to enable delegated email.")
        result = client.acquire_token_silent(MAIL_SCOPES, account=account)
        if cache.has_state_changed:
            conn.execute("UPDATE caches SET payload=?, updated=? WHERE handle=?", (
                _cipher().encrypt(cache.serialize().encode("utf-8")), time.time(), handle
            ))
    if not result or not result.get("access_token"):
        raise MailUnavailable("Email consent or sign-in has expired. Sign out and sign in again.")
    return result["access_token"]


def mail_status():
    try:
        _mail_token()
        return {"available": True, "reason": None}
    except MailUnavailable as exc:
        return {"available": False, "reason": str(exc)}
    except Exception:
        current_app.logger.warning("Delegated email authentication unavailable")
        return {"available": False, "reason": "Email authentication is unavailable. Try signing in again."}


def mail_request_allowed():
    return request.headers.get("X-AppHub-Mail") == "1" and request.is_json


def send_mail(recipients, subject, html_body, dedupe_key):
    token = _mail_token()
    if not recipients or len(recipients) > 50:
        raise MailUnavailable("Email requires between 1 and 50 authorized recipients.")
    send_key = hashlib.sha256((session["mail_cache_handle"] + ":" + dedupe_key).encode()).hexdigest()
    with _db() as conn:
        row = conn.execute("SELECT status FROM sends WHERE send_key=?", (send_key,)).fetchone()
        if row:
            return {"status": row[0], "duplicate": True}
        try:
            conn.execute("INSERT INTO sends VALUES (?, 'pending', ?)", (send_key, time.time()))
        except sqlite3.IntegrityError:
            return {"status": "pending", "duplicate": True}
    message = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": html_body},
        "toRecipients": [{"emailAddress": {"address": email}} for email in recipients],
    }
    try:
        response = requests.post(
            "https://graph.microsoft.com/v1.0/me/sendMail",
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            json={"message": message, "saveToSentItems": True}, timeout=30,
        )
        status = "accepted" if response.status_code == 202 else "rejected"
        if status == "rejected":
            current_app.logger.warning("Graph mail rejected (HTTP %s)", response.status_code)
    except requests.RequestException:
        status = "unknown"
        current_app.logger.warning("Graph mail result unknown; not automatically retried")
    with _db() as conn:
        conn.execute("UPDATE sends SET status=? WHERE send_key=?", (status, send_key))
    return {"status": status, "duplicate": False}