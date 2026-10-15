#requires -Version 7.0
<#
.SYNOPSIS
  Isolated native Slicer + real Home Assistant backend HTTPS acceptance.
.DESCRIPTION
  Generates a disposable self-signed localhost certificate in the OS temp
  directory, checks the real native server and actual HA options connection
  probe over HTTPS, and removes the key/certificate even after a failed test.

  Never modifies HA, the printer, systemd, public repos or any production key.
  The key is not checked into source control or printed in diagnostics.
#>
[CmdletBinding()]
param(
    [string]$SourceRoot = (Split-Path -Parent $PSScriptRoot)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Python = Join-Path $SourceRoot '.venv\Scripts\python.exe'
$Probe = Join-Path $PSScriptRoot 'native_slicer_https_probe.py'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Native TLS test requires the project Python virtual environment'
}
if (-not (Test-Path -LiteralPath $Probe -PathType Leaf)) {
    throw 'Native TLS test runner is missing'
}

$Scratch = Join-Path ([System.IO.Path]::GetTempPath()) (
    'studio-tls-acceptance-' + [guid]::NewGuid().ToString('N')
)
New-Item -Path $Scratch -ItemType Directory -Force | Out-Null
$CertificateFile = Join-Path $Scratch 'certificate.pem'
$PrivateKeyFile = Join-Path $Scratch 'private-key.pem'
$Rsa = $null
$Certificate = $null
try {
    $Rsa = [System.Security.Cryptography.RSA]::Create(2048)
    $Request = [System.Security.Cryptography.X509Certificates.CertificateRequest]::new(
        'CN=localhost',
        $Rsa,
        [System.Security.Cryptography.HashAlgorithmName]::SHA256,
        [System.Security.Cryptography.RSASignaturePadding]::Pkcs1
    )
    $AlternativeNames = [System.Security.Cryptography.X509Certificates.SubjectAlternativeNameBuilder]::new()
    $AlternativeNames.AddDnsName('localhost')
    $AlternativeNames.AddIpAddress([System.Net.IPAddress]::Parse('127.0.0.1'))
    $Request.CertificateExtensions.Add($AlternativeNames.Build())
    $Certificate = $Request.CreateSelfSigned(
        [DateTimeOffset]::UtcNow.AddMinutes(-5),
        [DateTimeOffset]::UtcNow.AddHours(1)
    )
    [System.IO.File]::WriteAllText(
        $CertificateFile, $Certificate.ExportCertificatePem(),
        [System.Text.Encoding]::ASCII
    )
    [System.IO.File]::WriteAllText(
        $PrivateKeyFile, $Rsa.ExportPkcs8PrivateKeyPem(),
        [System.Text.Encoding]::ASCII
    )

    & $Python $Probe --cert $CertificateFile --key $PrivateKeyFile
    if ($LASTEXITCODE -ne 0) {
        throw 'Native slicer + HA backend TLS handshake acceptance failed'
    }
    Write-Output 'REAL_NATIVE_TLS_AND_HA_CONNECTION_ACCEPTANCE=PASS'
}
finally {
    if ($null -ne $Certificate) {
        $Certificate.Dispose()
    }
    if ($null -ne $Rsa) {
        $Rsa.Dispose()
    }
    if (Test-Path -LiteralPath $Scratch) {
        Remove-Item -LiteralPath $Scratch -Recurse -Force
    }
    Write-Output 'TEMPORARY_TLS_FILES_REMOVED=true'
}
