$ErrorActionPreference = "Continue"

$ProjectRoot = $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$DistRoot = Join-Path $ProjectRoot "dist\frontend"
$FrontendJs = Join-Path $DistRoot "ultimate-3d-studio.js"
$FrontendCss = Join-Path $DistRoot "ultimate-3d-studio.css"
$BuildJson = Join-Path $DistRoot "frontend-build-manifest.json"
$BackendRoot = Join-Path $ProjectRoot "deploy\homeassistant\custom_components\ultimate_3d_studio_v6"

$GateOk = $true

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Ultimate 3D Studio V6 - vollstaendiger Quality Gate" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $ProjectRoot)) {
    Write-Host "FEHLER: Projektpfad wurde nicht gefunden:" -ForegroundColor Red
    Write-Host $ProjectRoot -ForegroundColor Red
    $GateOk = $false
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "FEHLER: Projekt-Python wurde nicht gefunden:" -ForegroundColor Red
    Write-Host $VenvPython -ForegroundColor Red
    $GateOk = $false
}

if ($GateOk) {
    Set-Location -LiteralPath $ProjectRoot

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "1. Frontend-Tests"
    Write-Host "============================================================"

    & npm.cmd test

    if ($LASTEXITCODE -ne 0) {
        Write-Host "FEHLER: Frontend-Tests fehlgeschlagen." -ForegroundColor Red
        $GateOk = $false
    }
    else {
        Write-Host "Frontend-Tests erfolgreich." -ForegroundColor Green
    }
}

if ($GateOk) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "2. TypeScript-Pruefung"
    Write-Host "============================================================"

    & npm.cmd run typecheck

    if ($LASTEXITCODE -ne 0) {
        Write-Host "FEHLER: TypeScript-Pruefung fehlgeschlagen." -ForegroundColor Red
        $GateOk = $false
    }
    else {
        Write-Host "TypeScript-Pruefung erfolgreich." -ForegroundColor Green
    }
}

if ($GateOk) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "3. Frontend-Build"
    Write-Host "============================================================"

    & npm.cmd run build

    if ($LASTEXITCODE -ne 0) {
        Write-Host "FEHLER: Frontend-Build fehlgeschlagen." -ForegroundColor Red
        $GateOk = $false
    }
    else {
        Write-Host "Frontend-Build erfolgreich." -ForegroundColor Green
    }
}

if ($GateOk) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "4. Python-Tests aus Projektumgebung"
    Write-Host "============================================================"

    & $VenvPython -m pytest -q

    if ($LASTEXITCODE -ne 0) {
        Write-Host "FEHLER: Python-Tests fehlgeschlagen." -ForegroundColor Red
        $GateOk = $false
    }
    else {
        Write-Host "Python-Tests erfolgreich." -ForegroundColor Green
    }
}

if ($GateOk) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "5. Python-Compilepruefung"
    Write-Host "============================================================"

    & $VenvPython -m compileall -q $BackendRoot

    if ($LASTEXITCODE -ne 0) {
        Write-Host "FEHLER: Python-Compilepruefung fehlgeschlagen." -ForegroundColor Red
        $GateOk = $false
    }
    else {
        Write-Host "Python-Compilepruefung erfolgreich." -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host "6. Neu gebaute Artefakte und SHA-256"
Write-Host "============================================================"

$Artifacts = @(
    $FrontendJs,
    $FrontendCss,
    $BuildJson,
    (Join-Path $BackendRoot "three_mf_materials.py"),
    (Join-Path $BackendRoot "direct_print_slot_views.py")
)

foreach ($Artifact in $Artifacts) {
    if (Test-Path -LiteralPath $Artifact) {
        $Hash = Get-FileHash -LiteralPath $Artifact -Algorithm SHA256
        Write-Host ""
        Write-Host $Artifact
        Write-Host $Hash.Hash.ToLowerInvariant()
    }
    else {
        Write-Host ""
        Write-Host "FEHLER: Artefakt fehlt:" -ForegroundColor Red
        Write-Host $Artifact -ForegroundColor Red
        $GateOk = $false
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host "Abschluss"
Write-Host "============================================================"

if ($GateOk) {
    Write-Host "Der vollstaendige V6-Quality-Gate ist erfolgreich." -ForegroundColor Green
    Write-Host "Es wurde noch nichts deployed." -ForegroundColor Yellow
}
else {
    Write-Host "Der Quality-Gate ist fehlgeschlagen." -ForegroundColor Red
    Write-Host "Es wurde nichts deployed." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Terminal bleibt offen."
