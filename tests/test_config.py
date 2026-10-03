import pytest

from src.config.config import Config, ConfigError


def test_valid_config_passes():
    Config.validate_config()


def test_missing_settings_are_listed(monkeypatch):
    monkeypatch.setattr(Config, "API_KEY", "")
    monkeypatch.setattr(Config, "TENANT_ID", "")
    with pytest.raises(ConfigError, match="TENANT_ID, API_KEY"):
        Config.validate_config()


def test_debug_on_public_host_is_rejected(monkeypatch):
    monkeypatch.setattr(Config, "DEBUG", True)
    monkeypatch.setattr(Config, "HOST", "0.0.0.0")
    with pytest.raises(ConfigError, match="DEBUG"):
        Config.validate_config()


def test_missing_certificate_file(monkeypatch):
    monkeypatch.setattr(Config, "CERTIFICATE_PATH", "/nonexistent.pem")
    with pytest.raises(ConfigError, match="Certificate"):
        Config.validate_config()
