$ErrorActionPreference = "Continue"

$ProjectRoot = $PSScriptRoot
$FrontendRunner = Join-Path $ProjectRoot "run_frontend_tests.mjs"
$CoreBuilder = Join-Path $ProjectRoot "build_v6_core.mjs"
$PythonRunner = Join-Path $ProjectRoot "run_python_tests.py"
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$DeployIntegration = Join-Path $ProjectRoot "deploy\homeassistant\custom_components\ultimate_3d_studio_v6"
$DeployFrontend = Join-Path $ProjectRoot "deploy\homeassistant\www\3d-studio-v6"
$FrontendSource = Join-Path $ProjectRoot "frontend"
$MarkerFile = Join-Path $FrontendSource "studio-transform-tools.ts.before-direct-mount-20260704"
$ResultDirectory = Join-Path $ProjectRoot ".test-results"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TranscriptPath = Join-Path $ResultDirectory "v6-full-gate-$Timestamp.log"
$ResultPath = Join-Path $ResultDirectory "v6-full-gate-$Timestamp.json"
$ServiceName = "JARVISPCConnector"
$ConnectorHost = "192.168.100.10"
$ConnectorPort = 8767

New-Item `
    -Path $ResultDirectory `
    -ItemType Directory `
    -Force |
    Out-Null

Start-Transcript `
    -LiteralPath $TranscriptPath `
    -Force |
    Out-Null

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "V6 vollständiger Qualitäts-, Build- und Deploybaum-Gate" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Projekt: $ProjectRoot" -ForegroundColor White
Write-Host "Protokoll: $TranscriptPath" -ForegroundColor White
Write-Host ""

$Results = [ordered]@{
    StartedAt = (Get-Date).ToString("o")
    ProjectRoot = $ProjectRoot
    NodeFound = $false
    PythonFound = $false
    FrontendGate = $null
    CoreBuild = $null
    PythonTests = $null
    CompileAll = $null
    SourcePolicy = $null
    NavigationAuthority = $null
    DeployFrontend = $null
    ConnectorRestart = $null
    OverallSuccess = $false
}

$CanRun = $true

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    Write-Host "FEHLER: Projektverzeichnis wurde nicht gefunden." -ForegroundColor Red
    $CanRun = $false
}

$NodeCommand = Get-Command "node.exe" -ErrorAction SilentlyContinue

if ($null -eq $NodeCommand) {
    Write-Host "FEHLER: node.exe wurde nicht gefunden." -ForegroundColor Red
    $CanRun = $false
}
else {
    $NodeExe = $NodeCommand.Source
    $Results.NodeFound = $true
    Write-Host "Node.js: $NodeExe" -ForegroundColor Green
}

if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    Write-Host "FEHLER: Projekt-Python wurde nicht gefunden:" -ForegroundColor Red
    Write-Host $PythonExe -ForegroundColor Red
    $CanRun = $false
}
else {
    $Results.PythonFound = $true
    Write-Host "Python: $PythonExe" -ForegroundColor Green
}

if ($CanRun) {
    if (Test-Path -LiteralPath $MarkerFile -PathType Leaf) {
        Remove-Item `
            -LiteralPath $MarkerFile `
            -Force `
            -ErrorAction Continue

        if (Test-Path -LiteralPath $MarkerFile -PathType Leaf) {
            Write-Host "WARNUNG: Temporäre Markerdatei konnte nicht entfernt werden:" -ForegroundColor Yellow
            Write-Host $MarkerFile -ForegroundColor Yellow
        }
        else {
            Write-Host "Temporäre Markerdatei wurde entfernt." -ForegroundColor Green
        }
    }

    Push-Location $ProjectRoot

    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host "1. Frontend: npm, TypeScript strict, Logiktests und Produktionsbuild" -ForegroundColor Cyan
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host ""

    & $NodeExe $FrontendRunner
    $Results.FrontendGate = $LASTEXITCODE

    if ($Results.FrontendGate -eq 0) {
        Write-Host "Frontend-Gate: ERFOLGREICH" -ForegroundColor Green
    }
    else {
        Write-Host "Frontend-Gate: FEHLGESCHLAGEN ($($Results.FrontendGate))" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host "2. Kanonischer Home-Assistant-Core-Build" -ForegroundColor Cyan
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host ""

    if ($Results.FrontendGate -eq 0) {
        & $NodeExe $CoreBuilder
        $Results.CoreBuild = $LASTEXITCODE
    }
    else {
        $Results.CoreBuild = -1
        Write-Host "Übersprungen, weil das Frontend-Gate fehlgeschlagen ist." -ForegroundColor Yellow
    }

    if ($Results.CoreBuild -eq 0) {
        Write-Host "HA-Core-Build: ERFOLGREICH" -ForegroundColor Green
    }
    elseif ($Results.CoreBuild -ne -1) {
        Write-Host "HA-Core-Build: FEHLGESCHLAGEN ($($Results.CoreBuild))" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host "3. Python-Tests" -ForegroundColor Cyan
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host ""

    & $PythonExe $PythonRunner
    $Results.PythonTests = $LASTEXITCODE

    if ($Results.PythonTests -eq 0) {
        Write-Host "Python-Tests: ERFOLGREICH" -ForegroundColor Green
    }
    else {
        Write-Host "Python-Tests: FEHLGESCHLAGEN ($($Results.PythonTests))" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host "4. Home-Assistant-Integration kompilieren" -ForegroundColor Cyan
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host ""

    & $PythonExe `
        -m compileall `
        -q `
        $DeployIntegration

    $Results.CompileAll = $LASTEXITCODE

    if ($Results.CompileAll -eq 0) {
        Write-Host "Compileall: ERFOLGREICH" -ForegroundColor Green
    }
    else {
        Write-Host "Compileall: FEHLGESCHLAGEN ($($Results.CompileAll))" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "Bereinige erzeugte Python-Bytecode-Dateien aus dem Deploybaum ..." -ForegroundColor Cyan

    Get-ChildItem `
        -LiteralPath $DeployIntegration `
        -Directory `
        -Recurse `
        -Force `
        -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -eq "__pycache__"
        } |
        Sort-Object FullName -Descending |
        Remove-Item `
            -Recurse `
            -Force `
            -ErrorAction Continue

    Get-ChildItem `
        -LiteralPath $DeployIntegration `
        -File `
        -Recurse `
        -Force `
        -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Extension -in @(".pyc", ".pyo")
        } |
        Remove-Item `
            -Force `
            -ErrorAction Continue

    Write-Host "Deploybaum enthält keine absichtlich ausgelieferten Bytecode-Dateien." -ForegroundColor Green

    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host "5. Quellrichtlinie: keine Runtime-/DOM-/Prototype-Patches" -ForegroundColor Cyan
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host ""

    $ForbiddenPatterns = @(
        "prototype.connectedCallback =",
        "prototype.disconnectedCallback =",
        "prototype._render =",
        "__transformToolsPatched",
        "__transformMountPatched",
        "new MutationObserver",
        "ultimate-3d-studio-status-patch",
        "ultimate-3d-controls-confirmation-patch"
    )

    $SourceFiles = @(
        Get-ChildItem `
            -LiteralPath $FrontendSource `
            -File `
            -Filter "*.ts" `
            -ErrorAction SilentlyContinue
    )

    $PolicyViolations = [System.Collections.Generic.List[object]]::new()

    foreach ($SourceFile in $SourceFiles) {
        foreach ($Pattern in $ForbiddenPatterns) {
            $Matches = @(
                Select-String `
                    -LiteralPath $SourceFile.FullName `
                    -SimpleMatch `
                    -Pattern $Pattern `
                    -ErrorAction SilentlyContinue
            )

            foreach ($Match in $Matches) {
                $PolicyViolations.Add(
                    [PSCustomObject]@{
                        File = $SourceFile.FullName
                        Line = $Match.LineNumber
                        Pattern = $Pattern
                    }
                )
            }
        }
    }

    $NavigationMatches = @(
        $SourceFiles |
            Select-String `
                -SimpleMatch `
                -Pattern "const NAVIGATION:" `
                -ErrorAction SilentlyContinue
    )

    $Results.SourcePolicy = $PolicyViolations.Count
    $Results.NavigationAuthority = $NavigationMatches.Count

    if ($PolicyViolations.Count -eq 0) {
        Write-Host "Patch-Policy: ERFOLGREICH" -ForegroundColor Green
    }
    else {
        Write-Host "Patch-Policy: FEHLGESCHLAGEN" -ForegroundColor Red

        foreach ($Violation in $PolicyViolations) {
            Write-Host (
                "{0}:{1} -> {2}" -f
                $Violation.File,
                $Violation.Line,
                $Violation.Pattern
            ) -ForegroundColor Red
        }
    }

    if ($NavigationMatches.Count -eq 1) {
        Write-Host "Navigationsautorität: genau eine bestätigt." -ForegroundColor Green
        Write-Host $NavigationMatches[0].Path -ForegroundColor Gray
    }
    else {
        Write-Host "Navigationsautorität: FEHLER, gefunden: $($NavigationMatches.Count)" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host "6. Kanonischen HA-Frontend-Deploybaum prüfen" -ForegroundColor Cyan
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host ""

    $ExpectedJavaScript = "ultimate-3d-studio.js"
    $JavaScriptFiles = @(
        Get-ChildItem `
            -LiteralPath $DeployFrontend `
            -File `
            -Filter "*.js" `
            -ErrorAction SilentlyContinue |
            Sort-Object Name
    )

    $CanonicalFiles = @(
        Join-Path $DeployFrontend "ultimate-3d-studio.js"
        Join-Path $DeployFrontend "ultimate-3d-studio.css"
        Join-Path $DeployFrontend "ultimate-3d-studio-build.json"
    )

    $MissingCanonicalFiles = @(
        $CanonicalFiles |
            Where-Object {
                -not (Test-Path -LiteralPath $_ -PathType Leaf)
            }
    )

    $UnexpectedJavaScript = @(
        $JavaScriptFiles |
            Where-Object {
                $_.Name -ne $ExpectedJavaScript
            }
    )

    $DeployFrontendSuccess = (
        $MissingCanonicalFiles.Count -eq 0 -and
        $UnexpectedJavaScript.Count -eq 0 -and
        $JavaScriptFiles.Count -eq 1
    )

    $Results.DeployFrontend = [ordered]@{
        Success = $DeployFrontendSuccess
        JavaScriptFiles = @($JavaScriptFiles.Name)
        MissingCanonicalFiles = @($MissingCanonicalFiles)
        UnexpectedJavaScriptFiles = @($UnexpectedJavaScript.Name)
        Artifacts = @()
    }

    foreach ($CanonicalFile in $CanonicalFiles) {
        if (Test-Path -LiteralPath $CanonicalFile -PathType Leaf) {
            $FileHash = Get-FileHash `
                -LiteralPath $CanonicalFile `
                -Algorithm SHA256

            $FileInfo = Get-Item `
                -LiteralPath $CanonicalFile

            $Artifact = [ordered]@{
                Name = $FileInfo.Name
                SizeBytes = $FileInfo.Length
                SHA256 = $FileHash.Hash
            }

            $Results.DeployFrontend.Artifacts += $Artifact

            Write-Host (
                "{0} | {1} Bytes | SHA256 {2}" -f
                $Artifact.Name,
                $Artifact.SizeBytes,
                $Artifact.SHA256
            ) -ForegroundColor White
        }
    }

    if ($DeployFrontendSuccess) {
        Write-Host "Deploy-Frontend: kanonisch und frei von Alt-/Patchdateien." -ForegroundColor Green
    }
    else {
        Write-Host "Deploy-Frontend: FEHLGESCHLAGEN" -ForegroundColor Red

        foreach ($MissingFile in $MissingCanonicalFiles) {
            Write-Host "Fehlt: $MissingFile" -ForegroundColor Red
        }

        foreach ($UnexpectedFile in $UnexpectedJavaScript) {
            Write-Host "Unerwartete JS-Datei: $($UnexpectedFile.FullName)" -ForegroundColor Red
        }
    }

    Pop-Location

    $GateSuccess = (
        $Results.FrontendGate -eq 0 -and
        $Results.CoreBuild -eq 0 -and
        $Results.PythonTests -eq 0 -and
        $Results.CompileAll -eq 0 -and
        $Results.SourcePolicy -eq 0 -and
        $Results.NavigationAuthority -eq 1 -and
        $DeployFrontendSuccess
    )

    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host "7. JARVIS-PC-Connector mit aktuellem SSH-/Bundle-Code neu laden" -ForegroundColor Cyan
    Write-Host "========================================================================" -ForegroundColor Cyan
    Write-Host ""

    $Service = Get-Service `
        -Name $ServiceName `
        -ErrorAction SilentlyContinue

    if ($null -eq $Service) {
        Write-Host "WARNUNG: Dienst $ServiceName wurde nicht gefunden." -ForegroundColor Yellow
        $Results.ConnectorRestart = $false
    }
    else {
        Restart-Service `
            -Name $ServiceName `
            -Force `
            -ErrorAction Continue

        $ServiceRunning = $false

        for ($Attempt = 1; $Attempt -le 30; $Attempt++) {
            Start-Sleep -Seconds 1

            $CurrentService = Get-Service `
                -Name $ServiceName `
                -ErrorAction SilentlyContinue

            if ($null -ne $CurrentService -and $CurrentService.Status -eq "Running") {
                $ServiceRunning = $true
                break
            }

            Write-Host "Dienstprüfung $Attempt/30 ..." -ForegroundColor Gray
        }

        $PortReachable = $false

        if ($ServiceRunning) {
            for ($Attempt = 1; $Attempt -le 30; $Attempt++) {
                Start-Sleep -Seconds 1
                $TcpClient = $null

                try {
                    $TcpClient = [System.Net.Sockets.TcpClient]::new()
                    $ConnectTask = $TcpClient.ConnectAsync(
                        $ConnectorHost,
                        $ConnectorPort
                    )

                    if ($ConnectTask.Wait(1000) -and $TcpClient.Connected) {
                        $PortReachable = $true
                        break
                    }
                }
                catch {
                }
                finally {
                    if ($null -ne $TcpClient) {
                        $TcpClient.Dispose()
                    }
                }

                Write-Host "Portprüfung $Attempt/30 ..." -ForegroundColor Gray
            }
        }

        $Results.ConnectorRestart = ($ServiceRunning -and $PortReachable)

        if ($Results.ConnectorRestart) {
            Write-Host "JARVIS-PC-Connector wurde erfolgreich neu geladen." -ForegroundColor Green
        }
        else {
            Write-Host "WARNUNG: Connector-Neuladung konnte nicht vollständig bestätigt werden." -ForegroundColor Yellow
        }
    }

    $Results.OverallSuccess = $GateSuccess
}

$Results.FinishedAt = (Get-Date).ToString("o")

$Results |
    ConvertTo-Json `
        -Depth 12 |
    Set-Content `
        -LiteralPath $ResultPath `
        -Encoding UTF8 `
        -Force

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "Gesamtergebnis" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

if ($Results.OverallSuccess) {
    Write-Host "V6-GESAMTGATE: ERFOLGREICH" -ForegroundColor Green
    Write-Host "Der bereinigte Build ist für Backup und HA-Deployment vorbereitet." -ForegroundColor Green
}
else {
    Write-Host "V6-GESAMTGATE: FEHLGESCHLAGEN" -ForegroundColor Red
    Write-Host "Es wird noch kein Home-Assistant-Deployment freigegeben." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Ergebnisdatei:" -ForegroundColor Cyan
Write-Host $ResultPath -ForegroundColor White
Write-Host ""
Write-Host "Protokoll:" -ForegroundColor Cyan
Write-Host $TranscriptPath -ForegroundColor White
Write-Host ""
Write-Host "Terminal bleibt offen." -ForegroundColor Yellow

Stop-Transcript |
    Out-Null
