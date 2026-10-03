# Certificate

The app authenticates to Entra ID and Exchange Online with a certificate. Nothing in this folder except this README is committed (see `.gitignore`).

Create a self-signed certificate and a single PEM holding the private key and certificate:

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -subj "/CN=Outlook Signature Manager" \
  -keyout certificate/key.pem -out certificate/cert.pem
cat certificate/key.pem certificate/cert.pem > certificate/signature-manager.pem
chmod 600 certificate/*.pem
```

1. Upload `certificate/cert.pem` (public part only) to the app registration under *Certificates & secrets → Certificates*.
2. Set `CERTIFICATE_PATH=certificate/signature-manager.pem` in `.env`.

The private key must be unencrypted (`-nodes`), so protect the file with filesystem permissions. Renew the certificate before it expires and upload the new one.
