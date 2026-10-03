import pytest

from src.app import create_app
from src.errors import ExchangeError, GraphError
from src.signature_manager import OutlookSignatureManager
from tests.conftest import API_KEY

HEADERS = {"X-API-Key": API_KEY}
USER = {
    "displayName": "Ada",
    "userPrincipalName": "ada@contoso.com",
    "mail": "ada@contoso.com",
    "jobTitle": None,
    "department": "R&D",
}


class FakeGraph:
    def __init__(self):
        self.users = [USER, {"userPrincipalName": "room@contoso.com", "mail": None}]

    def get_all_users(self):
        return self.users

    def get_user(self, upn):
        for user in self.users:
            if user["userPrincipalName"] == upn:
                return user
        raise GraphError("not found", status_code=404)

    def get_access_token(self):
        return "token"


class FakeExchange:
    def __init__(self, fail=False):
        self.fail = fail
        self.written = {}

    def set_signature(self, upn, html):
        if self.fail:
            raise ExchangeError("boom")
        self.written[upn] = html

    def set_signatures(self, signatures):
        self.written.update(signatures)
        return [{"upn": upn, "ok": True} for upn in signatures]

    def get_signature(self, upn):
        return self.written.get(upn, "")


@pytest.fixture
def exchange():
    return FakeExchange()


@pytest.fixture
def client(exchange):
    manager = OutlookSignatureManager(graph=FakeGraph(), exchange=exchange)
    return create_app(manager).test_client()


def test_dashboard_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Outlook Signature Manager" in response.data
    assert b'value="standard"' in response.data


def test_health_needs_no_key(client):
    assert client.get("/api/health").json == {"status": "ok"}


@pytest.mark.parametrize("path", ["/api/users", "/api/templates", "/api/health/graph"])
def test_api_requires_key(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-API-Key": "wrong"}).status_code == 401


def test_users_replace_null_fields(client):
    response = client.get("/api/users", headers=HEADERS)
    assert response.status_code == 200
    assert response.json["users"][0]["jobTitle"] == ""


def test_set_signature_sanitises(client, exchange):
    response = client.post("/api/signature", headers=HEADERS, json={
        "userPrincipalName": "ada@contoso.com",
        "signature": "<p>Hi</p><script>alert(1)</script>",
    })
    assert response.status_code == 200
    assert exchange.written["ada@contoso.com"] == "<p>Hi</p>"


def test_set_signature_from_template(client, exchange):
    response = client.post("/api/signature", headers=HEADERS, json={
        "userPrincipalName": "ada@contoso.com", "template": "standard",
    })
    assert response.status_code == 200
    assert "Ada" in exchange.written["ada@contoso.com"]
    assert "R&amp;D" in exchange.written["ada@contoso.com"]


def test_failed_write_is_not_reported_as_success():
    manager = OutlookSignatureManager(graph=FakeGraph(), exchange=FakeExchange(fail=True))
    client = create_app(manager).test_client()
    response = client.post("/api/signature", headers=HEADERS, json={
        "userPrincipalName": "ada@contoso.com", "signature": "<p>x</p>",
    })
    assert response.status_code == 502
    assert "boom" not in response.get_data(as_text=True)


@pytest.mark.parametrize("body", [
    None,
    {"signature": "<p>x</p>"},
    {"userPrincipalName": "../../users", "signature": "<p>x</p>"},
    {"userPrincipalName": "ada@contoso.com", "template": "missing"},
    {"userPrincipalName": "ada@contoso.com", "signature": ""},
])
def test_bad_requests(client, body):
    response = client.post("/api/signature", headers=HEADERS, json=body)
    assert response.status_code == 400


def test_unknown_user_preview_returns_404(client):
    response = client.post("/api/signature/preview", headers=HEADERS, json={
        "userPrincipalName": "nobody@contoso.com", "template": "standard",
    })
    assert response.status_code == 404


def test_bulk_skips_users_without_mail(client, exchange):
    response = client.post("/api/signature/bulk", headers=HEADERS, json={"template": "minimal"})
    assert response.json == {"succeeded": 1, "failed": []}
    assert list(exchange.written) == ["ada@contoso.com"]


def test_security_headers(client):
    response = client.get("/")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
