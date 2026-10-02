$ErrorActionPreference = "Continue"

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

$RepositoryRoot = $ProjectRoot
$ExpectedBranch = "feature/v6-ultimate-3d-printing-studio"

$VenvPython     = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PythonRunner   = Join-Path $ProjectRoot "run_python_tests.py"
$PythonResult   = Join-Path $ProjectRoot ".test-results\python-test-status.json"

$NodePath       = "C:\Program Files\nodejs\node.exe"
$FrontendRunner = Join-Path $ProjectRoot "run_frontend_tests.mjs"
$FrontendResult = Join-Path $ProjectRoot ".test-results\frontend-test-status.json"
$BuildManifest  = Join-Path $ProjectRoot "dist\frontend\frontend-build-manifest.json"

$CanRun          = $true
$PythonSuccess   = $false
$FrontendSuccess = $false

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "Ultimate 3D Printing Studio V6 - API und Frontend Build Gate" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Repository: $RepositoryRoot"
Write-Host "V6-Pfad:    $ProjectRoot"
Write-Host "Branch:     $ExpectedBranch"
Write-Host ""

if (-not (Test-Path -LiteralPath $RepositoryRoot -PathType Container)) {
    Write-Host "FEHLER: Das Repository wurde nicht gefunden." -ForegroundColor Red
    $CanRun = $false
}

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    Write-Host "FEHLER: Der V6-Arbeitsbereich wurde nicht gefunden." -ForegroundColor Red
    $CanRun = $false
}

if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    Write-Host "FEHLER: Das V6-Python wurde nicht gefunden:" -ForegroundColor Red
    Write-Host $VenvPython -ForegroundColor Red
    $CanRun = $false
}

if (-not (Test-Path -LiteralPath $PythonRunner -PathType Leaf)) {
    Write-Host "FEHLER: Der Python-Testrunner wurde nicht gefunden." -ForegroundColor Red
    $CanRun = $false
}

if (-not (Test-Path -LiteralPath $NodePath -PathType Leaf)) {
    Write-Host "FEHLER: Node.js wurde nicht gefunden:" -ForegroundColor Red
    Write-Host $NodePath -ForegroundColor Red
    $CanRun = $false
}

if (-not (Test-Path -LiteralPath $FrontendRunner -PathType Leaf)) {
    Write-Host "FEHLER: Der Frontend-Testrunner wurde nicht gefunden." -ForegroundColor Red
    $CanRun = $false
}

if ($CanRun) {
    Set-Location -LiteralPath $RepositoryRoot
    $CurrentBranch = [string](git branch --show-current)

    Write-Host "Aktiver Branch: $CurrentBranch"

    if ($CurrentBranch.Trim() -ne $ExpectedBranch) {
        Write-Host "FEHLER: Der aktive Branch ist nicht der V6-Branch." -ForegroundColor Red
        Write-Host "Es werden keine Tests und keine Installationen ausgefuehrt." -ForegroundColor Red
        $CanRun = $false
    }
    else {
        Write-Host "V6-Branch ist korrekt aktiv." -ForegroundColor Green
    }
}

if ($CanRun) {
    Write-Host ""
    Write-Host "Installiere beziehungsweise aktualisiere die V6-Python-Abhaengigkeiten ..." -ForegroundColor Yellow

    & $VenvPython -m pip install -e "${ProjectRoot}[test]"
    $PipCode = $LASTEXITCODE

    if ($PipCode -ne 0) {
        Write-Host "FEHLER: Die Python-Abhaengigkeiten konnten nicht installiert werden." -ForegroundColor Red
        $CanRun = $false
    }
    else {
        Write-Host "Python-Abhaengigkeiten sind bereit." -ForegroundColor Green
    }
}

if ($CanRun) {
    if (Test-Path -LiteralPath $PythonResult -PathType Leaf) {
        Remove-Item -LiteralPath $PythonResult -Force -ErrorAction SilentlyContinue
    }

    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host "Python-Gate inklusive HTTP-Integrationstests" -ForegroundColor Cyan
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host ""

    Set-Location -LiteralPath $ProjectRoot
    & $VenvPython $PythonRunner
    $PythonProcessCode = $LASTEXITCODE

    if (Test-Path -LiteralPath $PythonResult -PathType Leaf) {
        try {
            $PythonStatus = Get-Content -LiteralPath $PythonResult -Raw | ConvertFrom-Json

            Write-Host "Python-Syntax:  $($PythonStatus.syntax_ok)"
            Write-Host "Python-Imports: $($PythonStatus.imports_ok)"
            Write-Host "Pytest-Code:    $($PythonStatus.pytest_code)"
            Write-Host "Prozesscode:    $PythonProcessCode"

            if (
                $PythonStatus.success -eq $true -and
                $PythonStatus.syntax_ok -eq $true -and
                $PythonStatus.imports_ok -eq $true -and
                $PythonStatus.pytest_code -eq 0 -and
                $PythonProcessCode -eq 0
            ) {
                $PythonSuccess = $true
                Write-Host "Python- und HTTP-Gate erfolgreich." -ForegroundColor Green
            }
            else {
                Write-Host "Python- oder HTTP-Gate fehlgeschlagen." -ForegroundColor Red
            }
        }
        catch {
            Write-Host "FEHLER: Python-Ergebnisdatei konnte nicht ausgewertet werden." -ForegroundColor Red
            Write-Host $_.Exception.Message -ForegroundColor Red
        }
    }
    else {
        Write-Host "FEHLER: Keine Python-Ergebnisdatei erzeugt." -ForegroundColor Red
    }
}

if ($CanRun) {
    if (Test-Path -LiteralPath $FrontendResult -PathType Leaf) {
        Remove-Item -LiteralPath $FrontendResult -Force -ErrorAction SilentlyContinue
    }

    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host "Frontend-Typecheck und Production-Build" -ForegroundColor Cyan
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host ""

    Set-Location -LiteralPath $ProjectRoot
    & $NodePath $FrontendRunner
    $FrontendProcessCode = $LASTEXITCODE

    if (Test-Path -LiteralPath $FrontendResult -PathType Leaf) {
        try {
            $FrontendStatus = Get-Content -LiteralPath $FrontendResult -Raw | ConvertFrom-Json

            Write-Host "npm-Code:         $($FrontendStatus.install_code)"
            Write-Host "TypeScript-Code:  $($FrontendStatus.typescript_code)"
            Write-Host "Build-Code:       $($FrontendStatus.build_code)"
            Write-Host "Manifest gueltig: $($FrontendStatus.manifest_valid)"
            Write-Host "Prozesscode:      $FrontendProcessCode"

            if (
                $FrontendStatus.success -eq $true -and
                $FrontendStatus.install_code -eq 0 -and
                $FrontendStatus.typescript_code -eq 0 -and
                $FrontendStatus.build_code -eq 0 -and
                $FrontendStatus.manifest_valid -eq $true -and
                $FrontendProcessCode -eq 0 -and
                (Test-Path -LiteralPath $BuildManifest -PathType Leaf)
            ) {
                $FrontendSuccess = $true
                Write-Host "Frontend-Typecheck und Production-Build erfolgreich." -ForegroundColor Green
            }
            else {
                Write-Host "Frontend-Typecheck oder Production-Build fehlgeschlagen." -ForegroundColor Red
            }
        }
        catch {
            Write-Host "FEHLER: Frontend-Ergebnisdatei konnte nicht ausgewertet werden." -ForegroundColor Red
            Write-Host $_.Exception.Message -ForegroundColor Red
        }
    }
    else {
        Write-Host "FEHLER: Keine Frontend-Ergebnisdatei erzeugt." -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "Abschlussstatus" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Python und HTTP: $PythonSuccess"
Write-Host "Frontend-Build:  $FrontendSuccess"

if ($PythonSuccess -and $FrontendSuccess) {
    Write-Host ""
    Write-Host "API- und Frontend-Build-Gate ist vollstaendig gruen." -ForegroundColor Green
    Write-Host "Erwarteter Python-Stand: 47 bestandene Tests ohne Warnungen." -ForegroundColor Green
    Write-Host "Frontend-Artefakte: dist\frontend" -ForegroundColor Green
}
else {
    Write-Host ""
    Write-Host "API- und Frontend-Build-Gate ist noch nicht freigegeben." -ForegroundColor Red
    Write-Host "Es wird nichts committed, gepusht oder deployt." -ForegroundColor Yellow
}

if (Test-Path -LiteralPath $RepositoryRoot -PathType Container) {
    Set-Location -LiteralPath $RepositoryRoot

    Write-Host ""
    Write-Host "Aktueller Branch:" -ForegroundColor Yellow
    git branch --show-current

    Write-Host ""
    Write-Host "V6-Aenderungen:" -ForegroundColor Yellow
    git status --short -- "v6"

    Write-Host ""
    Write-Host "V6-Diff-Statistik fuer bereits versionierte Dateien:" -ForegroundColor Yellow
    git diff --stat -- "v6"
}

Write-Host ""
Write-Host "Es wurde nichts committed." -ForegroundColor Cyan
Write-Host "Es wurde nichts gepusht." -ForegroundColor Cyan
Write-Host "Es wurde nichts nach Home Assistant deployt." -ForegroundColor Cyan
Write-Host "V5 beta38 wurde nicht veraendert." -ForegroundColor Cyan
Write-Host ""
Write-Host "Terminal bleibt offen." -ForegroundColor Cyan
