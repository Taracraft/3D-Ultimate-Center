$ErrorActionPreference = "Continue"

$ProjectRoot = $PSScriptRoot
$PythonPath  = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$TestRunner  = Join-Path $ProjectRoot "run_python_tests.py"
$CommandTest = Join-Path $ProjectRoot "tests\test_v6_ha_commands.py"
$Component   = Join-Path $ProjectRoot "deploy\homeassistant\custom_components\ultimate_3d_studio_v6"
$StageRoot   = Join-Path $ProjectRoot ".runtime\v6-command-gate"
$StagePath   = Join-Path $StageRoot "ultimate_3d_studio_v6"
$ArchivePath = Join-Path $ProjectRoot "dist\ultimate_3d_studio_v6-command-api.zip"

$FilesToCheck = @(
    (Join-Path $Component "commands.py"),
    (Join-Path $Component "models.py"),
    (Join-Path $Component "mqtt_transport.py"),
    (Join-Path $Component "provider_bambu_lan.py"),
    (Join-Path $Component "runtime.py"),
    (Join-Path $Component "api.py"),
    (Join-Path $Component "__init__.py"),
    (Join-Path $Component "config_flow.py"),
    (Join-Path $Component "const.py"),
    (Join-Path $Component "discovery.py"),
    (Join-Path $Component "sensor.py"),
    (Join-Path $Component "telemetry.py")
)

$AllPassed = $true

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "V6 Command API - sicherer Gate-Lauf" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "Projekt: $ProjectRoot"
Write-Host ""

if (-not (Test-Path -LiteralPath $PythonPath)) {
    Write-Host "[FAIL] Python der virtuellen Umgebung fehlt:" -ForegroundColor Red
    Write-Host $PythonPath -ForegroundColor Red
    $AllPassed = $false
}
else {
    Write-Host "[OK] Python gefunden: $PythonPath" -ForegroundColor Green
}

foreach ($File in $FilesToCheck) {
    if (-not (Test-Path -LiteralPath $File)) {
        Write-Host "[FAIL] Pflichtdatei fehlt: $File" -ForegroundColor Red
        $AllPassed = $false
    }
}

if ($AllPassed) {
    Write-Host ""
    Write-Host "------------------------------------------------------------------------" -ForegroundColor DarkCyan
    Write-Host "1. Python-Syntaxprüfung" -ForegroundColor Cyan
    Write-Host "------------------------------------------------------------------------" -ForegroundColor DarkCyan

    & $PythonPath -m py_compile $FilesToCheck
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[PASS] Alle V6-HA-Pythondateien sind syntaktisch gültig." -ForegroundColor Green
    }
    else {
        Write-Host "[FAIL] Python-Syntaxprüfung fehlgeschlagen." -ForegroundColor Red
        $AllPassed = $false
    }
}

if ($AllPassed) {
    Write-Host ""
    Write-Host "------------------------------------------------------------------------" -ForegroundColor DarkCyan
    Write-Host "2. Fail-Closed Command-Unit-Tests" -ForegroundColor Cyan
    Write-Host "------------------------------------------------------------------------" -ForegroundColor DarkCyan

    & $PythonPath -m pytest $CommandTest -q
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[PASS] Command-Validierung, Bestätigungspflicht und Payload-Test grün." -ForegroundColor Green
    }
    else {
        Write-Host "[FAIL] Command-Unit-Tests fehlgeschlagen." -ForegroundColor Red
        $AllPassed = $false
    }
}

if ($AllPassed) {
    Write-Host ""
    Write-Host "------------------------------------------------------------------------" -ForegroundColor DarkCyan
    Write-Host "3. Vollständiger bestehender V6-Python-Testlauf" -ForegroundColor Cyan
    Write-Host "------------------------------------------------------------------------" -ForegroundColor DarkCyan

    & $PythonPath $TestRunner
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[PASS] Vollständiger V6-Python-Testlauf grün." -ForegroundColor Green
    }
    else {
        Write-Host "[FAIL] Vollständiger V6-Python-Testlauf fehlgeschlagen." -ForegroundColor Red
        $AllPassed = $false
    }
}

if ($AllPassed) {
    Write-Host ""
    Write-Host "------------------------------------------------------------------------" -ForegroundColor DarkCyan
    Write-Host "4. Sauberes Deploy-Artefakt erzeugen" -ForegroundColor Cyan
    Write-Host "------------------------------------------------------------------------" -ForegroundColor DarkCyan

    if (Test-Path -LiteralPath $StageRoot) {
        Remove-Item -LiteralPath $StageRoot -Recurse -Force -ErrorAction Continue
    }

    New-Item -Path $StagePath -ItemType Directory -Force | Out-Null

    Get-ChildItem -LiteralPath $Component -File | Where-Object {
        $_.Name -ne "api_v6_commands.py" -and
        $_.Extension -ne ".pyc"
    } | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $StagePath -Force
    }

    $TranslationsSource = Join-Path $Component "translations"
    $TranslationsTarget = Join-Path $StagePath "translations"
    if (Test-Path -LiteralPath $TranslationsSource) {
        Copy-Item -LiteralPath $TranslationsSource -Destination $TranslationsTarget -Recurse -Force
    }

    if (Test-Path -LiteralPath $ArchivePath) {
        Remove-Item -LiteralPath $ArchivePath -Force -ErrorAction Continue
    }

    Compress-Archive -Path $StagePath -DestinationPath $ArchivePath -CompressionLevel Optimal -Force

    if (Test-Path -LiteralPath $ArchivePath) {
        $Archive = Get-Item -LiteralPath $ArchivePath
        Write-Host "[PASS] Deploy-Artefakt erstellt:" -ForegroundColor Green
        Write-Host $Archive.FullName -ForegroundColor Green
        Write-Host ("Größe: {0:N0} Bytes" -f $Archive.Length) -ForegroundColor Green
    }
    else {
        Write-Host "[FAIL] Deploy-Artefakt wurde nicht erstellt." -ForegroundColor Red
        $AllPassed = $false
    }
}

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
if ($AllPassed) {
    Write-Host "GESAMTERGEBNIS: PASS" -ForegroundColor Green
    Write-Host "Noch kein MQTT-Steuerbefehl wurde gesendet." -ForegroundColor Green
    Write-Host "Der Stand ist bereit für den kontrollierten Home-Assistant-Deploy." -ForegroundColor Green
}
else {
    Write-Host "GESAMTERGEBNIS: FAIL" -ForegroundColor Red
    Write-Host "Kein Deploy durchführen. Die bestehende V6-Laufzeit bleibt unverändert." -ForegroundColor Yellow
}
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Terminal bleibt offen." -ForegroundColor Cyan
