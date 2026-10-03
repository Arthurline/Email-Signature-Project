"""Outlook signature reads and writes through Exchange Online PowerShell.

Microsoft Graph's mailboxSettings resource has no signature property, so
signatures are set with Set-MailboxMessageConfiguration instead. Each call
starts one PowerShell process and one Exchange Online session for a whole
batch of mailboxes.
"""

import json
import logging
import os
import subprocess
from pathlib import Path

from src.config.config import Config
from src.errors import ExchangeError

logger = logging.getLogger(__name__)

SCRIPT_PATH = Path(__file__).parent / "powershell" / "mailbox_signatures.ps1"
RESULT_MARKER = "__RESULT__"
BATCH_SIZE = 200


class ExchangeClient:
    def __init__(self, runner=subprocess.run):
        self._run = runner

    def set_signatures(self, signatures: dict[str, str]) -> list[dict]:
        """Write signatures, keyed by user principal name.

        Returns one ``{"upn", "ok", "error"?}`` dict per mailbox.
        """
        items = [{"upn": upn, "html": html} for upn, html in signatures.items()]
        results: list[dict] = []
        for start in range(0, len(items), BATCH_SIZE):
            results.extend(self._invoke("set", items[start:start + BATCH_SIZE]))
        return results

    def set_signature(self, user_principal_name: str, signature_html: str) -> None:
        result = self.set_signatures({user_principal_name: signature_html})[0]
        if not result.get("ok"):
            raise ExchangeError(
                f"Setting signature for {user_principal_name} failed: {result.get('error')}"
            )

    def get_signature(self, user_principal_name: str) -> str:
        result = self._invoke("get", [{"upn": user_principal_name}])[0]
        if not result.get("ok"):
            raise ExchangeError(
                f"Reading signature for {user_principal_name} failed: {result.get('error')}"
            )
        return result.get("html") or ""

    def _invoke(self, action: str, items: list[dict]) -> list[dict]:
        env = {
            **os.environ,
            "SM_CLIENT_ID": Config.CLIENT_ID,
            "SM_ORGANIZATION": Config.EXCHANGE_ORGANIZATION,
            "SM_CERT_PATH": os.path.abspath(Config.CERTIFICATE_PATH),
        }
        command = [
            Config.PWSH_PATH, "-NoLogo", "-NoProfile", "-NonInteractive",
            "-File", str(SCRIPT_PATH),
        ]
        try:
            proc = self._run(
                command,
                input=json.dumps({"action": action, "items": items}),
                capture_output=True,
                text=True,
                env=env,
                timeout=Config.EXCHANGE_TIMEOUT,
            )
        except FileNotFoundError as e:
            raise ExchangeError(
                f"PowerShell not found at '{Config.PWSH_PATH}'. Install PowerShell 7 "
                "and the ExchangeOnlineManagement module, or set PWSH_PATH."
            ) from e
        except subprocess.TimeoutExpired as e:
            raise ExchangeError(
                f"Exchange Online PowerShell timed out after {Config.EXCHANGE_TIMEOUT}s"
            ) from e

        for line in reversed(proc.stdout.splitlines()):
            if line.startswith(RESULT_MARKER):
                return json.loads(line[len(RESULT_MARKER):])

        logger.error("PowerShell exited %s: %s", proc.returncode, proc.stderr.strip())
        raise ExchangeError(
            f"Exchange Online PowerShell failed (exit {proc.returncode}): "
            f"{proc.stderr.strip()[:500]}"
        )
