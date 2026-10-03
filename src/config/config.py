import os

from dotenv import load_dotenv

load_dotenv()


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


class ConfigError(Exception):
    """Raised when required settings are missing or invalid."""


class Config:
    TENANT_ID = os.getenv("TENANT_ID", "")
    CLIENT_ID = os.getenv("CLIENT_ID", "")
    CERTIFICATE_PATH = os.getenv("CERTIFICATE_PATH", "")
    EXCHANGE_ORGANIZATION = os.getenv("EXCHANGE_ORGANIZATION", "")

    API_KEY = os.getenv("API_KEY", "")
    SECRET_KEY = os.getenv("SECRET_KEY", "")

    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))
    DEBUG = _bool(os.getenv("DEBUG", "false"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    PWSH_PATH = os.getenv("PWSH_PATH", "pwsh")
    EXCHANGE_TIMEOUT = int(os.getenv("EXCHANGE_TIMEOUT", "600"))
    HTTP_TIMEOUT = 30

    REQUIRED = (
        "TENANT_ID",
        "CLIENT_ID",
        "CERTIFICATE_PATH",
        "EXCHANGE_ORGANIZATION",
        "API_KEY",
        "SECRET_KEY",
    )

    @classmethod
    def validate_config(cls) -> None:
        missing = [name for name in cls.REQUIRED if not getattr(cls, name)]
        if missing:
            raise ConfigError(f"Missing required settings: {', '.join(missing)}")
        if not os.path.isfile(cls.CERTIFICATE_PATH):
            raise ConfigError(f"Certificate file not found: {cls.CERTIFICATE_PATH}")
        if len(cls.API_KEY) < 16:
            raise ConfigError("API_KEY must be at least 16 characters")
        if cls.DEBUG and cls.HOST not in {"127.0.0.1", "localhost", "::1"}:
            raise ConfigError(
                "DEBUG=true is only allowed when HOST is a loopback address; "
                "the Werkzeug debugger allows remote code execution"
            )
