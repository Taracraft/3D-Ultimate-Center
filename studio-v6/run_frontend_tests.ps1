$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "Ultimate 3D Printing Studio V6 - Frontend Test und Build" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan

$FallbackProjectRoot = "F:\OneDrive - Bad-Timing\Dokumente\GitHub\3D-Ultimate Studio"

if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot)) {
    $ProjectRoot = $PSScriptRoot
}
elseif (Test-Path -LiteralPath $FallbackProjectRoot -PathType Container) {
    $ProjectRoot = $FallbackProjectRoot
}
else {
    $ProjectRoot = (Get-Location).Path
}

$NodePath = $null
$NodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
$DriverPath = Join-Path $ProjectRoot "run_frontend_tests.mjs"
$ResultPath = Join-Path $ProjectRoot ".test-results\frontend-test-status.json"

if ($null -ne $NodeCommand) {
    $NodePath = $NodeCommand.Source
}
elseif (Test-Path -LiteralPath "C:\Program Files\nodejs\node.exe") {
    $NodePath = "C:\Program Files\nodejs\node.exe"
}
elseif (Test-Path -LiteralPath "$env:LOCALAPPDATA\Programs\nodejs\node.exe") {
    $NodePath = "$env:LOCALAPPDATA\Programs\nodejs\node.exe"
}

Write-Host "Projektpfad: $ProjectRoot"

if ([string]::IsNullOrWhiteSpace($NodePath)) {
    Write-Host "FEHLER: Node.js wurde nicht gefunden." -ForegroundColor Red
}
elseif (-not (Test-Path -LiteralPath $DriverPath -PathType Leaf)) {
    Write-Host "FEHLER: run_frontend_tests.mjs wurde nicht gefunden." -ForegroundColor Red
}
else {
    $NodeVersion = & $NodePath --version 2>&1
    Write-Host "Node.js: $NodeVersion"
    Write-Host "Pfad: $NodePath"

    if (Test-Path -LiteralPath $ResultPath -PathType Leaf) {
        Remove-Item -LiteralPath $ResultPath -Force -ErrorAction SilentlyContinue
    }

    Write-Host ""
    & $NodePath $DriverPath
    $FrontendProcessCode = $LASTEXITCODE

    Write-Host ""

    if (-not (Test-Path -LiteralPath $ResultPath -PathType Leaf)) {
        Write-Host "FEHLER: Der Frontend-Runner hat keine Ergebnisdatei erzeugt." -ForegroundColor Red
    }
    else {
        try {
            $Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json

            Write-Host "npm-Code:          $($Result.install_code)"
            Write-Host "TypeScript-Code:   $($Result.typescript_code)"
            Write-Host "Logiktest-Code:    $($Result.logic_test_code)"
            Write-Host "Build-Code:        $($Result.build_code)"
            Write-Host "Manifest gueltig:  $($Result.manifest_valid)"
            Write-Host "Browser-Simulation: $($Result.synthetic_dom_used)"
            Write-Host "Prozesscode:       $FrontendProcessCode"

            if (
                $Result.success -eq $true -and
                $Result.install_code -eq 0 -and
                $Result.typescript_code -eq 0 -and
                $Result.logic_test_code -eq 0 -and
                $Result.build_code -eq 0 -and
                $Result.manifest_valid -eq $true -and
                $Result.synthetic_dom_used -eq $false -and
                $FrontendProcessCode -eq 0
            ) {
                Write-Host "Frontend-Typecheck, reine Logiktests und Production-Build waren erfolgreich." -ForegroundColor Green
            }
            else {
                Write-Host "Frontend-Gate ist fehlgeschlagen." -ForegroundColor Red
                Write-Host "Ergebnisdatei: $ResultPath" -ForegroundColor Yellow
            }
        }
        catch {
            Write-Host "FEHLER: Die Frontend-Ergebnisdatei konnte nicht ausgewertet werden." -ForegroundColor Red
            Write-Host $_.Exception.Message -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "Es wurde keine synthetische Browser-Umgebung verwendet." -ForegroundColor Cyan
Write-Host "Es wurde nichts committed." -ForegroundColor Cyan
Write-Host "Es wurde nichts gepusht." -ForegroundColor Cyan
Write-Host "Es wurde nichts nach Home Assistant deployt." -ForegroundColor Cyan
Write-Host "V5 beta38 wurde nicht veraendert." -ForegroundColor Cyan
Write-Host "Terminal bleibt offen." -ForegroundColor Cyan
