# Outlook Signature Manager

A small Flask app for setting Outlook signatures across a Microsoft 365 tenant. It reads user details (name, title, department, phones) from Microsoft Graph, fills them into an HTML template, and writes the result to each mailbox.

## How signatures are written

Microsoft Graph has no API for Outlook signatures: `mailboxSettings` covers automatic replies, time zone and working hours, nothing more. This app therefore writes signatures with Exchange Online PowerShell (`Set-MailboxMessageConfiguration -SignatureHtml`), driven from Python by `src/powershell/mailbox_signatures.ps1`. A bulk update opens one Exchange session per batch of 200 mailboxes.

**Roaming signatures.** Current Outlook clients (new Outlook, Outlook on the web, recent Outlook for Windows) store signatures in the cloud and ignore the value set by `Set-MailboxMessageConfiguration` unless roaming signatures are postponed for the tenant:

```powershell
Set-OrganizationConfig -PostponeRoamingSignaturesUntilLater $true
```

Check Microsoft's current guidance before changing this. Its effect on clients has changed over time. If you want a signature on every message whatever the client, an Exchange transport rule (server-side disclaimer) is the alternative.

## Requirements

- Python 3.10+
- PowerShell 7.1+ (`pwsh`) with the `ExchangeOnlineManagement` module 3.x:
  `pwsh -c "Install-Module ExchangeOnlineManagement -Scope CurrentUser"`
- An Entra ID app registration with:
  - Microsoft Graph application permissions `User.Read.All`, plus `MailboxSettings.ReadWrite` if you use automatic replies. Admin consent is required.
  - Office 365 Exchange Online application permission `Exchange.ManageAsApp`.
  - An Exchange role for the app's service principal that can run `Set-MailboxMessageConfiguration`, e.g. the Exchange Administrator role, or a narrower custom role.
  - A certificate uploaded under *Certificates & secrets* (see `certificate/README.md`).

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # then fill it in
python run.py
```

Open http://127.0.0.1:5000 and enter the `API_KEY` from `.env`.

The server binds to `127.0.0.1` by default. `DEBUG=true` is refused unless the host is loopback, because the Werkzeug debugger allows code execution. For anything beyond local use, run it behind a production WSGI server (e.g. `gunicorn "src.app:create_app()"`) and TLS.

## API

Every `/api/*` route except `/api/health` needs the `X-API-Key` header.

| Method | Path | Body | Purpose |
|---|---|---|---|
| GET | `/api/health` | | Liveness |
| GET | `/api/health/graph` | | Checks a Graph token can be acquired |
| GET | `/api/users` | | All users |
| GET | `/api/templates` | | Built-in templates |
| GET | `/api/signature/<upn>` | | Current signature |
| POST | `/api/signature/preview` | `userPrincipalName`, `template` or `templateHtml` | Render without saving |
| POST | `/api/signature` | `userPrincipalName`, and `signature` (HTML as-is) or `template`/`templateHtml` | Set one user's signature |
| POST | `/api/signature/bulk` | `template` or `templateHtml` | Set everyone's signature (users with a mail address) |

Templates use `{{field}}` placeholders, filled from the Graph user: `displayName`, `jobTitle`, `department`, `officeLocation`, `businessPhones`, `mobilePhone`, `mail`, `userPrincipalName`. Values are HTML-escaped and the final HTML is sanitised: no scripts, event handlers or `javascript:` links.

The bulk endpoint runs synchronously and can take several minutes on a large tenant.

## Tests

```bash
pytest
```

The tests stub Graph and PowerShell, so they need no tenant.
