import json
import subprocess

import pytest

from src import exchange_client
from src.errors import ExchangeError
from src.exchange_client import ExchangeClient


class FakeRunner:
    def __init__(self, stdout_for=None, returncode=0, stderr="", exc=None):
        self.stdout_for = stdout_for
        self.returncode = returncode
        self.stderr = stderr
        self.exc = exc
        self.requests = []

    def __call__(self, command, input, env, **kwargs):
        if self.exc:
            raise self.exc
        request = json.loads(input)
        self.requests.append((command, request, env))
        stdout = self.stdout_for(request) if self.stdout_for else ""
        return subprocess.CompletedProcess(command, self.returncode, stdout, self.stderr)


def ok_results(request):
    results = [{"upn": item["upn"], "ok": True} for item in request["items"]]
    return "WARNING: noise\n__RESULT__" + json.dumps(results) + "\n"


def test_set_signatures_passes_html_and_settings():
    runner = FakeRunner(ok_results)
    results = ExchangeClient(runner).set_signatures({"a@x.com": "<p>A</p>"})
    assert results == [{"upn": "a@x.com", "ok": True}]
    command, request, env = runner.requests[0]
    assert command[-1].endswith("mailbox_signatures.ps1")
    assert request == {"action": "set", "items": [{"upn": "a@x.com", "html": "<p>A</p>"}]}
    assert env["SM_ORGANIZATION"] == "contoso.onmicrosoft.com"


def test_set_signatures_batches(monkeypatch):
    monkeypatch.setattr(exchange_client, "BATCH_SIZE", 2)
    runner = FakeRunner(ok_results)
    results = ExchangeClient(runner).set_signatures({f"u{i}@x.com": "s" for i in range(5)})
    assert len(results) == 5
    assert [len(r[1]["items"]) for r in runner.requests] == [2, 2, 1]


def test_set_signature_raises_on_failed_item():
    runner = FakeRunner(lambda r: '__RESULT__[{"upn": "a@x.com", "ok": false, "error": "No mailbox"}]')
    with pytest.raises(ExchangeError, match="No mailbox"):
        ExchangeClient(runner).set_signature("a@x.com", "<p>A</p>")


def test_missing_result_raises_with_stderr():
    runner = FakeRunner(returncode=1, stderr="Connect-ExchangeOnline: unauthorized")
    with pytest.raises(ExchangeError, match="unauthorized"):
        ExchangeClient(runner).get_signature("a@x.com")


def test_missing_pwsh():
    runner = FakeRunner(exc=FileNotFoundError())
    with pytest.raises(ExchangeError, match="PowerShell not found"):
        ExchangeClient(runner).get_signature("a@x.com")


def test_get_signature():
    runner = FakeRunner(lambda r: '__RESULT__[{"upn": "a@x.com", "ok": true, "html": "<p>hi</p>"}]')
    assert ExchangeClient(runner).get_signature("a@x.com") == "<p>hi</p>"
