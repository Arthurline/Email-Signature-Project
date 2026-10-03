import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from src.errors import AuthenticationError, GraphError
from src.graph_client import GraphClient, load_certificate_credential


def make_pem(path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(1).not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        + cert.public_bytes(serialization.Encoding.PEM)
    )


def test_load_certificate_credential(tmp_path):
    pem = tmp_path / "combined.pem"
    make_pem(pem)
    cred = load_certificate_credential(str(pem))
    assert cred["private_key"].startswith("-----BEGIN PRIVATE KEY-----")
    assert cred["public_certificate"].startswith("-----BEGIN CERTIFICATE-----")


def test_load_certificate_credential_requires_certificate(tmp_path):
    pem = tmp_path / "key-only.pem"
    make_pem(pem)
    pem.write_text(pem.read_text().split("-----BEGIN CERTIFICATE-----")[0])
    with pytest.raises(AuthenticationError):
        load_certificate_credential(str(pem))


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


@pytest.fixture
def client_factory(monkeypatch):
    def make(responses):
        session = FakeSession(responses)
        client = GraphClient(session=session)
        monkeypatch.setattr(client, "get_access_token", lambda: "token")
        return client, session
    return make


def test_get_all_users_follows_pagination(client_factory):
    client, session = client_factory([
        FakeResponse(200, {"value": [{"userPrincipalName": "a@x.com"}], "@odata.nextLink": "next"}),
        FakeResponse(200, {"value": [{"userPrincipalName": "b@x.com"}]}),
    ])
    users = client.get_all_users()
    assert [u["userPrincipalName"] for u in users] == ["a@x.com", "b@x.com"]
    assert "businessPhones" in session.calls[0][1]
    assert "officeLocation" in session.calls[0][1]
    assert session.calls[1][1] == "next"
    assert all(call[2]["timeout"] for call in session.calls)


def test_graph_error_keeps_status(client_factory):
    client, _ = client_factory([FakeResponse(404, {"error": "nope"})])
    with pytest.raises(GraphError) as exc:
        client.get_user("missing@x.com")
    assert exc.value.status_code == 404


def test_user_principal_name_is_url_encoded(client_factory):
    client, session = client_factory([FakeResponse(200, {})])
    client.get_user("guest_x.com#EXT#@contoso.onmicrosoft.com")
    assert "guest_x.com%23EXT%23@contoso.onmicrosoft.com" in session.calls[0][1]


def test_set_automatic_reply_payload(client_factory):
    client, session = client_factory([FakeResponse(200, {})])
    client.set_automatic_reply("a@x.com", "Away", "2026-01-01T00:00:00", "2026-01-02T00:00:00")
    method, url, kwargs = session.calls[0]
    assert method == "PATCH"
    assert url.endswith("/users/a@x.com/mailboxSettings")
    setting = kwargs["json"]["automaticRepliesSetting"]
    assert setting["status"] == "scheduled"
    assert setting["scheduledEndDateTime"]["dateTime"] == "2026-01-02T00:00:00"


def test_token_failure_raises_authentication_error(monkeypatch):
    client = GraphClient(session=FakeSession([]))

    class FakeApp:
        def acquire_token_for_client(self, scopes):
            return {"error": "invalid_client", "error_description": "bad cert"}

    monkeypatch.setattr(client, "_msal_app", lambda: FakeApp())
    with pytest.raises(AuthenticationError, match="bad cert"):
        client.get_access_token()
