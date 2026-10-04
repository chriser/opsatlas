"""Sign-in for tests of the secured mode (IAM E1): a bootstrapped administrator and a bearer session."""
from fastapi.testclient import TestClient

from assistant.api.auth import AuthService
from assistant.iam.service import IamError

EMAIL, NAME, PASSWORD = "operator@example.test", "Test Operator", "the operator's own long password"


def bootstrap(app, email: str = EMAIL, password: str = PASSWORD) -> None:
    """The first platform administrator of an app's identity store (a second call is a no-op)."""
    try:
        app.state.auth.iam.bootstrap_admin(email, NAME, password=password, enforce_policy=False)
    except IamError as exc:
        if exc.code != "ALREADY_INITIALISED":
            raise


def sign_in(client: TestClient, app, email: str = EMAIL, password: str = PASSWORD) -> str:
    """A bearer session secret for ``email``; the client keeps no cookie, so requests without the header are
    anonymous, as the tests expect."""
    bootstrap(app, email, password)
    response = client.post("/api/auth/login", json={"login": email, "password": password})
    assert response.status_code == 200, response.text
    client.cookies.clear()
    return response.json()["token"]


def signed_client(app, password: str = "operator-pw") -> TestClient:
    """A bare router app (no create_app): give it the legacy operator sign-in and a client that carries it."""
    if not hasattr(app.state, "auth"):
        app.state.auth = AuthService(password)
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {app.state.auth.login(password)}"})
    return client
