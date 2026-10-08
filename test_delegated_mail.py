import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from flask import Flask, session
import msal
import requests
from contextlib import ExitStack

import delegated_mail as mail


class DelegatedMailTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY="test-secret", MAIL_CACHE_PATH=str(Path(self.temp.name) / "mail.sqlite3"),
                               AZURE_CLIENT_ID="test-client", AZURE_CLIENT_SECRET="test-secret", AZURE_AUTHORITY="test-authority")
        self.ctx = self.app.test_request_context("/")
        self.ctx.push()
        self.env = patch.dict(os.environ, {"DEV_BYPASS": "false"})
        self.env.start()
        session["user"] = {"oid": "user-oid", "email": "user@example.com"}
        mail.store_mail_cache(msal.SerializableTokenCache(), "user-oid")

    def tearDown(self):
        self.env.stop()
        self.ctx.pop()
        self.temp.cleanup()

    def test_cache_encrypted_and_cookie_only_contains_handle(self):
        with mail._db() as conn:
            payload = conn.execute("SELECT payload FROM caches").fetchone()[0]
        self.assertNotIn(b"AccessToken", payload)
        self.assertEqual(mail._cipher().decrypt(payload).decode(), msal.SerializableTokenCache().serialize())
        self.assertEqual(set(session), {"user", "mail_cache_handle"})

    def test_blocks_impersonation_view_as_and_bypass(self):
        for key in ("is_impersonating", "sc_view_as_email", "sc_view_as_pm_property_key"):
            session[key] = True
            with self.assertRaises(mail.MailUnavailable):
                mail._mail_token()
            session.pop(key)
        with patch.dict(os.environ, {"DEV_BYPASS": "true"}):
            with self.assertRaises(mail.MailUnavailable):
                mail._mail_token()
        self.app.config["LOCAL_AUTH_BYPASS"] = True
        with self.assertRaises(mail.MailUnavailable):
            mail._mail_token()

    def test_silent_token_uses_signed_in_oid_and_mail_scope(self):
        client = Mock()
        client.get_accounts.return_value = [{"local_account_id": "other"}, {"local_account_id": "user-oid"}]
        client.acquire_token_silent.return_value = {"access_token": "token"}
        with patch.object(mail.msal, "ConfidentialClientApplication", return_value=client):
            self.assertEqual(mail._mail_token(), "token")
        client.acquire_token_silent.assert_called_once_with(mail.MAIL_SCOPES, account={"local_account_id": "user-oid"})

    def test_accepted_message_is_idempotent(self):
        with patch.object(mail, "_mail_token", return_value="token"), patch.object(mail.requests, "post", return_value=Mock(status_code=202)) as post:
            self.assertEqual(mail.send_mail(["rm@example.com"], "Reminder", "<p>Body</p>", "request-1")["status"], "accepted")
            self.assertTrue(mail.send_mail(["rm@example.com"], "Reminder", "<p>Body</p>", "request-1")["duplicate"])
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.args[0], "https://graph.microsoft.com/v1.0/me/sendMail")
        self.assertNotIn("from", post.call_args.kwargs["json"]["message"])

    def test_timeout_is_unknown_and_not_retried(self):
        with patch.object(mail, "_mail_token", return_value="token"), patch.object(mail.requests, "post", side_effect=requests.Timeout) as post:
            self.assertEqual(mail.send_mail(["rm@example.com"], "Subject", "Body", "request-2")["status"], "unknown")
            self.assertTrue(mail.send_mail(["rm@example.com"], "Subject", "Body", "request-2")["duplicate"])
        self.assertEqual(post.call_count, 1)

    def test_logout_discards_cache(self):
        mail.discard_mail_cache()
        self.assertNotIn("mail_cache_handle", session)
        with mail._db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM caches").fetchone()[0], 0)

    def test_authorization_callback_rejects_missing_state(self):
        import auth
        with self.app.test_request_context("/auth/callback?code=untrusted"):
            with patch.object(auth, "_build_msal_app") as build:
                response, status = auth._callback_inner()
            self.assertEqual(status, 400)
            build.assert_not_called()

    def test_authorization_callback_stores_cache_off_cookie(self):
        import auth
        result = {"id_token_claims": {"oid": "user-oid", "name": "User", "preferred_username": "user@example.com"}}
        self.app.config.update(AZURE_SCOPE=["User.Read", "Mail.Send"], AZURE_REDIRECT_URI="")
        self.app.add_url_rule("/", endpoint="main.index", view_func=lambda: "home")
        client = Mock()
        client.acquire_token_by_authorization_code.return_value = result
        with self.app.test_request_context("/auth/callback?code=test&state=state-value"):
            session["auth_state"] = "state-value"
            with patch.object(auth, "_build_msal_app", return_value=client) as build, \
                 patch("security.get_employee_info", return_value={"title_group": "TECHNOLOGY ASSOCIATE"}), \
                 patch("security.resolve_access", return_value={"modules": [], "is_developer": False}):
                response = auth._callback_inner()
            self.assertEqual(response.status_code, 302)
            self.assertIn("mail_cache_handle", session)
            self.assertNotIn("access_token", session)
            self.assertIn("cache", build.call_args.kwargs)


class ScorecardMailTests(unittest.TestCase):
    def setUp(self):
        import scorecard
        self.sc = scorecard
        self.app = Flask(__name__)
        self.app.secret_key = "test-secret"
        self.app.config["AZURE_REDIRECT_URI"] = "https://app.example.com/auth/callback"
        self.app.register_blueprint(scorecard.scorecard_bp)
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["user"] = {"email": "author@example.com", "name": "Author", "oid": "author-oid"}
            sess["user_modules"] = [{"id": 36, "access": "user"}]
            sess["mail_cache_handle"] = "test-handle"
        self.stack = ExitStack()
        self.stack.enter_context(patch.dict(os.environ, {"DEV_BYPASS": "false"}))
        self.stack.enter_context(patch.object(scorecard, "_get_env", return_value={}))
        self.stack.enter_context(patch.object(scorecard, "_is_admin", return_value=False))
        self.conn = Mock()
        self.stack.enter_context(patch.object(scorecard, "SafeConnection", return_value=self.conn))
        self.row = (123, "A & B Property", "rm@example.com", "RM Name", None, 0, None)
        self.scoped = self.stack.enter_context(patch.object(scorecard, "_scoped_property_row", return_value=self.row))
        self.send = self.stack.enter_context(patch.object(scorecard, "send_mail", return_value={"status": "accepted", "duplicate": False}))

    def tearDown(self):
        self.stack.close()

    def reminder(self, headers=True):
        return self.client.post("/scorecard/api/mail/reminder", json={
            "request_id": "46f2cdb1-867e-4a86-96eb-1ff3f4f60cf0", "ay": 2026,
            "quarter": "Q3", "property_keys": [123], "rm_email": "rm@example.com", "recipient": "attacker@example.com"
        }, headers={"X-AppHub-Mail": "1"} if headers else {})

    def test_reminder_uses_authorized_rm_and_escaped_content(self):
        response = self.reminder()
        self.assertEqual(response.status_code, 200)
        args = self.send.call_args.args
        self.assertEqual(args[0], ["rm@example.com"])
        self.assertIn("A &amp; B Property", args[2])
        self.assertIn("Controllable NOI", args[2])
        self.assertNotIn("Surveys &amp; Reviews", args[2])
        self.assertIn("https://app.example.com/scorecard/", args[2])

    def test_reminder_rejects_out_of_scope(self):
        self.scoped.return_value = None
        self.assertEqual(self.reminder().status_code, 403)
        self.send.assert_not_called()

    def test_reminder_requires_custom_header(self):
        self.assertEqual(self.reminder(headers=False).status_code, 403)
        self.send.assert_not_called()

    def test_reminder_blocks_impersonation(self):
        with self.client.session_transaction() as sess:
            sess["is_impersonating"] = True
        self.assertEqual(self.reminder().status_code, 403)
        self.send.assert_not_called()

    def test_completed_properties_are_not_emailed(self):
        self.scoped.return_value = (123, "Property", "rm@example.com", "RM", 0, 0, 0)
        self.assertEqual(self.reminder().status_code, 409)
        self.send.assert_not_called()

    def test_changed_rm_assignment_is_not_emailed(self):
        self.scoped.return_value = (123, "Property", "new-rm@example.com", "New RM", None, None, None)
        self.assertEqual(self.reminder().status_code, 409)
        self.send.assert_not_called()

    def test_saved_note_survives_mail_failure_and_only_emails_candidates(self):
        self.scoped.return_value = (123, "Property")
        self.conn.scalar.return_value = 17
        with patch.object(self.sc, "_latest_period", return_value=(2026, "Q3")), \
             patch.object(self.sc, "_mention_candidates", return_value=[{"email": "rm@example.com", "name": "RM"}]), \
             patch.object(self.sc, "_note_author_role", return_value="RM"), \
             patch.object(self.sc, "_audit_scorecard_change"):
            def failed_send(*args):
                self.conn.commit.assert_called_once()
                self.assertEqual(args[0], ["rm@example.com"])
                raise mail.MailUnavailable("Sign in again")
            self.send.side_effect = failed_send
            response = self.client.post("/scorecard/api/notes/123", json={
                "text": "A note", "measure_key": "NOI", "email_mentions": True,
                "mentions": ["rm@example.com", "attacker@example.com", "rm@example.com"]
            }, headers={"X-AppHub-Mail": "1"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["note"]["mentions"]), 1)
        self.assertEqual(data["email_notification"]["status"], "skipped")
        self.send.assert_called_once()

    def test_saved_note_reports_graph_acceptance_after_commit(self):
        self.scoped.return_value = (123, "Property")
        self.conn.scalar.return_value = 18
        with patch.object(self.sc, "_latest_period", return_value=(2026, "Q3")), \
             patch.object(self.sc, "_mention_candidates", return_value=[{"email": "rm@example.com", "name": "RM"}]), \
             patch.object(self.sc, "_note_author_role", return_value="RM"), \
             patch.object(self.sc, "_audit_scorecard_change"):
            def accepted_send(*args):
                self.conn.commit.assert_called_once()
                return {"status": "accepted", "duplicate": False}
            self.send.side_effect = accepted_send
            response = self.client.post("/scorecard/api/notes/123", json={
                "text": "A note", "measure_key": "NOI", "email_mentions": True,
                "mentions": ["rm@example.com"]
            }, headers={"Content-Type": "application/json", "X-AppHub-Mail": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["email_notification"]["status"], "accepted")


if __name__ == "__main__":
    unittest.main()