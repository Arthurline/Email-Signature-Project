# Reads or writes Outlook signatures through Exchange Online PowerShell.
#
# Input (stdin, JSON):  {"action": "set" | "get", "items": [{"upn": "...", "html": "..."}]}
# Output (stdout):      one line "__RESULT__<json array>" with {upn, ok, html?, error?} per item
# Settings come from SM_CLIENT_ID, SM_ORGANIZATION and SM_CERT_PATH.
#
# Requires PowerShell 7.1+ and the ExchangeOnlineManagement module (3.x).

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$request = [Console]::In.ReadToEnd() | ConvertFrom-Json

# The PEM file holds both the certificate and its private key.
$cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::CreateFromPemFile($env:SM_CERT_PATH)

Import-Module ExchangeOnlineManagement
Connect-ExchangeOnline -AppId $env:SM_CLIENT_ID -Organization $env:SM_ORGANIZATION `
    -Certificate $cert -ShowBanner:$false | Out-Null

try {
    $results = foreach ($item in $request.items) {
        try {
            if ($request.action -eq 'set') {
                Set-MailboxMessageConfiguration -Identity $item.upn -SignatureHtml $item.html `
                    -AutoAddSignature $true -AutoAddSignatureOnReply $true | Out-Null
                [pscustomobject]@{ upn = $item.upn; ok = $true }
            }
            else {
                $config = Get-MailboxMessageConfiguration -Identity $item.upn
                [pscustomobject]@{ upn = $item.upn; ok = $true; html = $config.SignatureHtml }
            }
        }
        catch {
            [pscustomobject]@{ upn = $item.upn; ok = $false; error = $_.Exception.Message }
        }
    }
    '__RESULT__' + (ConvertTo-Json -InputObject @($results) -Depth 4 -Compress)
}
finally {
    Disconnect-ExchangeOnline -Confirm:$false | Out-Null
}
