"""Microsoft Graph access: app-only token and directory/mailbox reads.

Graph has no property for Outlook signatures, so this client only reads user
data and manages automatic replies. Signatures are written by
:mod:`src.exchange_client`.
"""

import logging
import re
import threading
from urllib.parse import quote

import msal
import requests

from src.config.config import Config
from src.errors import AuthenticationError, GraphError

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
USER_FIELDS = (
    "displayName",
    "userPrincipalName",
    "mail",
    "jobTitle",
    "department",
    "officeLocation",
    "businessPhones",
    "mobilePhone",
)

_CERT_RE = re.compile(
    r"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", re.DOTALL
)
_KEY_RE = re.compile(
    r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----.+?"
    r"-----END (?:RSA |EC )?PRIVATE KEY-----",
    re.DOTALL,
)


def load_certificate_credential(path: str) -> dict:
    """Build an MSAL client credential from a PEM holding cert and key.

    MSAL needs the certificate (or its thumbprint) as well as the key; with
    ``public_certificate`` set it computes the SHA-256 thumbprint itself.
    """
    with open(path, encoding="utf-8") as fh:
        pem = fh.read()
    key = _KEY_RE.search(pem)
    cert = _CERT_RE.search(pem)
    if not key or not cert:
        raise AuthenticationError(
            f"{path} must contain an unencrypted PEM private key and a PEM certificate"
        )
    return {"private_key": key.group(0), "public_certificate": cert.group(0)}


def user_path(user_principal_name: str) -> str:
    return f"{GRAPH_BASE}/users/{quote(user_principal_name, safe='@')}"


class GraphClient:
    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()
        self._app: msal.ConfidentialClientApplication | None = None
        self._lock = threading.Lock()

    def _msal_app(self) -> msal.ConfidentialClientApplication:
        # Built once so MSAL's in-memory token cache is reused across calls.
        with self._lock:
            if self._app is None:
                self._app = msal.ConfidentialClientApplication(
                    Config.CLIENT_ID,
                    authority=f"https://login.microsoftonline.com/{Config.TENANT_ID}",
                    client_credential=load_certificate_credential(Config.CERTIFICATE_PATH),
                )
            return self._app

    def get_access_token(self) -> str:
        result = self._msal_app().acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            raise AuthenticationError(
                f"Token acquisition failed: {result.get('error')}: "
                f"{result.get('error_description')}"
            )
        return result["access_token"]

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        headers = {"Authorization": f"Bearer {self.get_access_token()}"}
        try:
            response = self._session.request(
                method, url, headers=headers, timeout=Config.HTTP_TIMEOUT, **kwargs
            )
        except requests.RequestException as e:
            raise GraphError(f"{method} {url} failed: {e}") from e
        if not response.ok:
            raise GraphError(
                f"{method} {url} returned {response.status_code}: {response.text[:500]}",
                status_code=response.status_code,
            )
        return response

    def get_all_users(self) -> list[dict]:
        url = f"{GRAPH_BASE}/users?$select={','.join(USER_FIELDS)}&$top=999"
        users: list[dict] = []
        while url:
            data = self._request("GET", url).json()
            users.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
        return users

    def get_user(self, user_principal_name: str) -> dict:
        url = f"{user_path(user_principal_name)}?$select={','.join(USER_FIELDS)}"
        return self._request("GET", url).json()

    def set_automatic_reply(
        self,
        user_principal_name: str,
        message: str,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> None:
        """Turn on an out-of-office reply. Times are ISO 8601 in UTC."""
        setting = {
            "status": "scheduled" if start_time and end_time else "alwaysEnabled",
            "externalAudience": "all",
            "internalReplyMessage": message,
            "externalReplyMessage": message,
        }
        if start_time and end_time:
            setting["scheduledStartDateTime"] = {"dateTime": start_time, "timeZone": "UTC"}
            setting["scheduledEndDateTime"] = {"dateTime": end_time, "timeZone": "UTC"}
        self._request(
            "PATCH",
            f"{user_path(user_principal_name)}/mailboxSettings",
            json={"automaticRepliesSetting": setting},
        )
