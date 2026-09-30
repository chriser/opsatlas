"""Sign-in and the account lifecycle over HTTP in the secured mode (IAM F3): no shared password, cookie sessions with
CSRF, throttling, idle and absolute expiry, sign-out, password change, recovery, suspension, fresh authentication."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.iam.service import Identity
from assistant.iam.store import IamStore
from assistant.sources.register import SourceRegister

EMAIL, PASSWORD = "kris@example.test", "the quiet river runs east"
BROWSER = {"origin": "http://testserver"}


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta) -> None:
        self.now += timedelta(**delta)


@pytest.fixture
def secured(tmp_path):
    clock = Clock()
    iam = Identity(IamStore(tmp_path / "iam.db", clock=clock), origin="http://testserver", guide_space="default")
    iam.register_space("default", "Knowledge base", "product")
    app = create_app(SourceRegister(tmp_path / "data"), AuthService(iam=iam), space_id="default")
    _, token = iam.bootstrap_admin(EMAIL, "Kris")
    return TestClient(app), iam, clock, token


def browser_login(client, login=EMAIL, password=PASSWORD):
    csrf = client.get("/api/auth/csrf").json()["csrf"]
    return client.post("/api/auth/login", json={"login": login, "password": password}, headers={**BROWSER, "x-csrf-token": csrf})


def api_login(client, login=EMAIL, password=PASSWORD) -> dict:
    """An API client: no Origin header, the session secret in the body, no cookie kept."""
    response = client.post("/api/auth/login", json={"login": login, "password": password})
    client.cookies.clear()
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_set_up_by_invitation_then_a_personal_sign_in_with_a_cookie(secured):
    client, iam, _, token = secured
    preview = client.post("/api/auth/invitations/preview", json={"token": token}).json()
    assert preview["email"] == EMAIL and preview["bootstrap"] is True
    weak = client.post("/api/auth/invitations/accept", json={"token": token, "password": "short"})
    assert weak.status_code == 422 and weak.json()["code"] == "WEAK_PASSWORD"
    assert client.post("/api/auth/invitations/accept", json={"token": token, "password": PASSWORD}).json()["login"] == EMAIL
    replay = client.post("/api/auth/invitations/accept", json={"token": token, "password": PASSWORD})
    assert replay.status_code == 410
    # No shared password: a login without an address is refused, and so is a browser without its CSRF token.
    assert client.post("/api/auth/login", json={"password": PASSWORD}).status_code == 401
    assert client.post("/api/auth/login", json={"login": EMAIL, "password": PASSWORD}, headers=BROWSER).status_code == 403
    signed = browser_login(client)
    assert signed.status_code == 200 and "token" not in signed.json()
    cookie = signed.headers["set-cookie"]
    assert cookie.startswith("opsatlas_session=") and "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
    assert "Secure" not in cookie  # loopback HTTP: the development cookie
    me = client.get("/api/auth/me").json()
    assert me["user"]["login"] == EMAIL and me["user"]["role_label"] == "Platform administrator"
    assert me["session"]["csrf"] and me["session"]["privileged"] is True and me["legacy"] is False
    assert "spaces.create" in me["platform_permissions"]
    assert [s["id"] for s in me["spaces"]] == ["default"] and "documents.approve" in me["spaces"][0]["permissions"]
    assert client.get("/api/sources").status_code == 200  # the cookie carries the session


def test_a_cookie_change_needs_the_csrf_token_and_an_api_client_does_not(secured):
    client, iam, _, token = secured
    iam.accept_invitation(token, PASSWORD)
    me = browser_login(client).json()
    refused = client.post("/api/query", json={"q": "anything"}, headers=BROWSER)
    assert refused.status_code == 403 and refused.json()["code"] == "CSRF_REQUIRED"
    assert client.post("/api/query", json={"q": "anything"}, headers={**BROWSER, "x-csrf-token": me["session"]["csrf"]}).status_code == 200
    api = TestClient(client.app)
    headers = api_login(api)
    assert api.post("/api/query", json={"q": "anything"}, headers=headers).status_code == 200


def test_wrong_passwords_are_throttled_and_an_unknown_account_answers_the_same(secured):
    client, iam, clock, token = secured
    iam.accept_invitation(token, PASSWORD)
    wrong = client.post("/api/auth/login", json={"login": EMAIL, "password": "not the password at all"})
    unknown = client.post("/api/auth/login", json={"login": "nobody@example.test", "password": "not the password at all"})
    assert wrong.status_code == unknown.status_code == 401 and wrong.json()["detail"] == unknown.json()["detail"]
    for _ in range(4):
        client.post("/api/auth/login", json={"login": EMAIL, "password": "not the password at all"})
    blocked = client.post("/api/auth/login", json={"login": EMAIL, "password": PASSWORD})
    assert blocked.status_code == 429 and blocked.json()["code"] == "RATE_LIMITED" and int(blocked.headers["retry-after"]) <= 31
    clock.advance(seconds=31)
    assert client.post("/api/auth/login", json={"login": EMAIL, "password": PASSWORD}).status_code == 200


def test_sessions_expire_when_idle_or_old_and_polling_does_not_keep_them_alive(secured):
    client, iam, clock, token = secured
    iam.accept_invitation(token, PASSWORD)
    headers = api_login(client)  # a platform administrator: 15 minutes idle, 8 hours in all
    deliberate = {**headers, "x-opsatlas-interaction": "1"}
    for _ in range(3):
        clock.advance(minutes=14)
        assert client.get("/api/sources", headers=deliberate).status_code == 200
    clock.advance(minutes=14)
    assert client.get("/api/sources", headers=headers).status_code == 200  # a poll, 14 minutes after the last action
    clock.advance(minutes=2)
    assert client.get("/api/sources", headers=headers).status_code == 401  # 16 minutes idle: gone, poll or not
    headers = api_login(client)
    clock.advance(hours=8, seconds=1)
    assert client.get("/api/sources", headers=deliberate).status_code == 401  # the absolute life is over
    iam.store.set_setting("session.privileged_idle_minutes", 60)  # an administrator may lengthen the window
    headers = api_login(client)
    clock.advance(minutes=45)
    assert client.get("/api/sources", headers=headers).status_code == 200


def test_sign_out_password_change_and_recovery_end_the_other_sessions(secured):
    client, iam, clock, token = secured
    iam.accept_invitation(token, PASSWORD)
    first, second = api_login(client), api_login(client)
    assert client.post("/api/auth/logout", headers=first).status_code == 200
    assert client.get("/api/sources", headers=first).status_code == 401
    assert client.get("/api/sources", headers=second).status_code == 200
    changed = client.post(
        "/api/auth/password/change", headers=second, json={"current": "wrong current password", "new": "another long and quiet password"}
    )
    assert changed.status_code == 403
    changed = client.post("/api/auth/password/change", headers=second, json={"current": PASSWORD, "new": "another long and quiet password"})
    assert changed.status_code == 200
    third = {"Authorization": f"Bearer {changed.json()['token']}"}
    assert client.get("/api/sources", headers=second).status_code == 401  # the old session died with the old password
    assert client.get("/api/sources", headers=third).status_code == 200
    # Recovery: an administrator issues a one-use reset link (shown once); using it ends every session.
    admin_id = iam.user_by_login(EMAIL)["id"]
    link = client.post(f"/api/iam/users/{admin_id}/recovery", json={"reason": "lost the password"}, headers=third).json()["link"]
    reset_token = link.split("#reset:", 1)[1]
    assert client.post("/api/auth/password/reset/preview", json={"token": reset_token}).json()["email"] == EMAIL
    assert (
        client.post("/api/auth/password/reset", json={"token": reset_token, "password": "a third long and quiet password"}).status_code
        == 200
    )
    assert client.get("/api/sources", headers=third).status_code == 401
    assert (
        client.post("/api/auth/password/reset", json={"token": reset_token, "password": "a fourth long and quiet password"}).status_code
        == 410
    )
    assert client.post("/api/auth/login", json={"login": EMAIL, "password": "another long and quiet password"}).status_code == 401
    assert client.post("/api/auth/login", json={"login": EMAIL, "password": "a third long and quiet password"}).status_code == 200
    actions = [e["action"] for e in iam.audit.events(limit=50)]
    assert {"sign_out", "password.change", "recovery.initiated", "password.reset"} <= set(actions)


def test_an_invited_reader_suspension_reactivation_and_the_last_administrator(secured):
    client, iam, clock, token = secured
    iam.accept_invitation(token, PASSWORD)
    admin = api_login(client)
    invited = client.post(
        "/api/iam/users/invite",
        headers=admin,
        json={"email": "rita@example.test", "display_name": "Rita", "role_id": "space_reader", "space_id": "default"},
    ).json()
    reader_token = invited["link"].split("#invitation:", 1)[1]
    assert client.post("/api/auth/invitations/preview", json={"token": reader_token}).json()["role"]["name"] == "Space reader"
    client.post("/api/auth/invitations/accept", json={"token": reader_token, "password": "reads a great many documents daily"})
    reader = api_login(client, "rita@example.test", "reads a great many documents daily")
    assert client.get("/api/sources", headers=reader).status_code == 200
    assert client.get("/api/iam/users", headers=reader).status_code == 403
    uploaded = client.post("/api/sources/upload", files={"file": ("a.md", b"# A", "text/markdown")}, data={"title": "A"}, headers=reader)
    assert uploaded.status_code == 403
    rita = iam.user_by_login("rita@example.test")["id"]
    assert client.post(f"/api/iam/users/{rita}/suspend", json={"reason": "leave"}, headers=admin).status_code == 200
    assert client.get("/api/sources", headers=reader).status_code == 401  # the next request, not the next sign-in
    assert (
        client.post("/api/auth/login", json={"login": "rita@example.test", "password": "reads a great many documents daily"}).status_code
        == 401
    )
    assert client.post(f"/api/iam/users/{rita}/reactivate", json={"reason": "back"}, headers=admin).status_code == 200
    assert api_login(client, "rita@example.test", "reads a great many documents daily")
    me = iam.user_by_login(EMAIL)["id"]
    last = client.post(f"/api/iam/users/{me}/suspend", json={"reason": "oops"}, headers=admin)
    assert last.status_code == 409 and last.json()["code"] == "LAST_ADMINISTRATOR"
    people = {u["login"]: u for u in client.get("/api/iam/users", headers=admin).json()["users"]}
    assert people["rita@example.test"]["roles"][0]["role_name"] == "Space reader" and people[EMAIL]["sessions"] >= 1


def test_protected_changes_need_a_fresh_password(secured):
    client, iam, clock, token = secured
    iam.accept_invitation(token, PASSWORD)
    admin = api_login(client)
    invited = client.post("/api/iam/users/invite", json={"email": "tom@example.test", "display_name": "Tom"}, headers=admin).json()
    tom = invited["user"]["id"]
    clock.advance(minutes=6)  # past the five-minute window
    stale = client.post(f"/api/iam/users/{tom}/deactivate", json={"reason": "left"}, headers=admin)
    assert stale.status_code == 403 and stale.json()["code"] == "REAUTH_REQUIRED"
    assert client.post("/api/auth/reauthenticate", json={"password": "not it"}, headers=admin).status_code == 403
    assert client.post("/api/auth/reauthenticate", json={"password": PASSWORD}, headers=admin).status_code == 200
    assert client.post(f"/api/iam/users/{tom}/deactivate", json={"reason": "left"}, headers=admin).json()["state"] == "deactivated"
    # Giving a protected role also needs it: the platform administrator role is never handed out casually.
    invited = client.post("/api/iam/users/invite", json={"email": "ann@example.test", "display_name": "Ann"}, headers=admin).json()
    clock.advance(minutes=6)
    grant = client.post(
        "/api/iam/bindings",
        json={"subject_id": invited["user"]["id"], "role_id": "identity_administrator", "scope_type": "platform"},
        headers=admin,
    )
    assert grant.status_code == 403 and grant.json()["code"] == "REAUTH_REQUIRED"
    client.post("/api/auth/reauthenticate", json={"password": PASSWORD}, headers=admin)
    assert (
        client.post(
            "/api/iam/bindings",
            json={"subject_id": invited["user"]["id"], "role_id": "identity_administrator", "scope_type": "platform"},
            headers=admin,
        ).status_code
        == 200
    )
    audit = client.get("/api/iam/audit", params={"action": "role.granted"}, headers=admin).json()["events"]
    assert audit and audit[0]["after"]["role_id"] == "identity_administrator" and audit[0]["actor_name"] == "Kris"
    assert client.get("/api/iam/audit/verify", headers=admin).json()["intact"] is True


def test_the_https_profile_uses_the_host_cookie(tmp_path):
    iam = Identity(IamStore(tmp_path / "iam.db"), origin="https://opsatlas.example", guide_space="default")
    iam.register_space("default", "Knowledge base", "product")
    iam.bootstrap_admin(EMAIL, "Kris", password=PASSWORD)
    client = TestClient(create_app(SourceRegister(tmp_path / "data"), AuthService(iam=iam, secure_cookie=True), space_id="default"))
    cookie = client.post("/api/auth/login", json={"login": EMAIL, "password": PASSWORD}).headers["set-cookie"]
    assert cookie.startswith("__Host-opsatlas_session=") and "Secure" in cookie and "HttpOnly" in cookie


def test_legacy_mode_keeps_the_single_operator_for_tests_and_the_development_core(tmp_path):
    client = TestClient(create_app(SourceRegister(tmp_path), AuthService("operator-pw")))
    body = client.post("/api/auth/login", json={"password": "operator-pw"}).json()
    assert body["legacy"] is True and body["token"] and body["user"]["role_label"] == "Platform administrator"
    assert client.get("/api/sources", headers={"Authorization": f"Bearer {body['token']}"}).status_code == 200
    assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401
