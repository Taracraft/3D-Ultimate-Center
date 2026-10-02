$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "Ultimate 3D Printing Studio V6 - Standalone API Server" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan

$FallbackProjectRoot = "F:\OneDrive - Bad-Timing\Dokumente\GitHub\3D-Ultimate Studio"

if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot)) {
    $ProjectRoot = $PSScriptRoot
}
elseif (-not [string]::IsNullOrWhiteSpace($MyInvocation.MyCommand.Path)) {
    $ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
elseif (Test-Path -LiteralPath $FallbackProjectRoot -PathType Container) {
    $ProjectRoot = $FallbackProjectRoot
}
else {
    $ProjectRoot = (Get-Location).Path
}

$VenvPython  = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RuntimeRoot = Join-Path $ProjectRoot ".runtime\3D-Studio"
$HostAddress = "127.0.0.1"
$Port         = 8768
$CanStart     = $true

Write-Host "Projektpfad: $ProjectRoot"
Write-Host "Python:      $VenvPython"
Write-Host "Runtime:     $RuntimeRoot"
Write-Host "HTTP:        http://${HostAddress}:$Port"
Write-Host ""

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    Write-Host "FEHLER: Der V6-Projektpfad wurde nicht gefunden." -ForegroundColor Red
    $CanStart = $false
}

if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    Write-Host "FEHLER: Die lokale V6-Python-Umgebung wurde nicht gefunden." -ForegroundColor Red
    Write-Host "Fuehre zuerst setup_and_run_python_tests.ps1 aus." -ForegroundColor Yellow
    $CanStart = $false
}

if ($CanStart) {
    Write-Host "Pruefe aiohttp und den API-Server-Import ..." -ForegroundColor Yellow
    & $VenvPython -c "import aiohttp; import api.http_server; import api.server; print('API imports: OK')"

    if ($LASTEXITCODE -ne 0) {
        Write-Host "FEHLER: Die API-Laufzeitabhaengigkeiten oder Importe sind nicht bereit." -ForegroundColor Red
        Write-Host "Fuehre zuerst setup_and_run_python_tests.ps1 aus." -ForegroundColor Yellow
        $CanStart = $false
    }
}

if ($CanStart) {
    New-Item -Path $RuntimeRoot -ItemType Directory -Force | Out-Null

    Write-Host ""
    Write-Host "Health-Route:" -ForegroundColor Cyan
    Write-Host "http://${HostAddress}:$Port/api/printer_control_center/v1/system/health"
    Write-Host ""
    Write-Host "Version-Route:" -ForegroundColor Cyan
    Write-Host "http://${HostAddress}:$Port/api/printer_control_center/v1/system/version"
    Write-Host ""
    Write-Host "Der Server laeuft im Vordergrund." -ForegroundColor Yellow
    Write-Host "Zum kontrollierten Beenden Strg+C verwenden." -ForegroundColor Yellow
    Write-Host ""

    Set-Location -LiteralPath $ProjectRoot
    & $VenvPython -m api.server `
        --host $HostAddress `
        --port $Port `
        --root $RuntimeRoot `
        --log-level INFO

    Write-Host ""
    Write-Host "API-Server-Prozess wurde beendet." -ForegroundColor Cyan
}

Write-Host ""
Write-Host "Es wurde nichts nach Home Assistant deployt." -ForegroundColor Cyan
Write-Host "V5 beta38 wurde nicht veraendert." -ForegroundColor Cyan
Write-Host "Terminal bleibt offen." -ForegroundColor Cyan
