import pytest

from src.config.config import Config

API_KEY = "test-api-key-0123456789"


@pytest.fixture(autouse=True)
def config(monkeypatch, tmp_path):
    cert = tmp_path / "cert.pem"
    cert.write_text("placeholder")
    values = {
        "TENANT_ID": "tenant",
        "CLIENT_ID": "client",
        "CERTIFICATE_PATH": str(cert),
        "EXCHANGE_ORGANIZATION": "contoso.onmicrosoft.com",
        "API_KEY": API_KEY,
        "SECRET_KEY": "secret",
        "HOST": "127.0.0.1",
        "DEBUG": False,
        "PWSH_PATH": "pwsh",
    }
    for name, value in values.items():
        monkeypatch.setattr(Config, name, value)
    return Config
