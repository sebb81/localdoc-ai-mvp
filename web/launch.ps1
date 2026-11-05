$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (!(Test-Path -LiteralPath 'dist\index.html')) { throw 'Lancez d abord installer-webnn.bat.' }
$url = 'http://127.0.0.1:8766'
$listening = Get-NetTCPConnection -State Listen -LocalPort 8766 -ErrorAction SilentlyContinue
if (!$listening) {
    New-Item -ItemType Directory -Force '.launcher' | Out-Null
    $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (!(Test-Path -LiteralPath $python)) { throw 'Lancez installer-webnn.bat a la racine du projet.' }
    $server = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','localdoc.main:app','--host','127.0.0.1','--port','8766') -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot '.launcher\server.log') -RedirectStandardError (Join-Path $PSScriptRoot '.launcher\server-error.log') -PassThru
    $server.Id | Set-Content '.launcher\server.pid'
}
$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $response = Invoke-RestMethod "$url/api/health" -TimeoutSec 2
        if ($response.application -ne 'localdoc-rag-webnn') { throw 'Le port 8766 utilise une ancienne version ou une autre application. Fermez son serveur puis relancez.' }
        $ready = $true
        break
    } catch {
        if ($listening) { throw }
        Start-Sleep -Milliseconds 300
    }
}
if (!$ready) { throw 'Le serveur ne demarre pas. Voir web/.launcher/server-error.log.' }
$edge = @(
    (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
    (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'),
    (Join-Path $env:LOCALAPPDATA 'Microsoft\Edge\Application\msedge.exe')
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (!$edge) { throw 'Microsoft Edge est requis par ce lanceur.' }
$profile = Join-Path $PSScriptRoot '.edge-profile'
# Profil propre au projet : le navigateur habituel et ses reglages ne sont pas modifies.
Start-Process -FilePath $edge -ArgumentList @("--user-data-dir=`"$profile`"", '--enable-features=WebMachineLearningNeuralNetwork', '--no-first-run', $url)
Write-Host 'LocalDoc RAG WebNN ouvert dans Edge : http://127.0.0.1:8766'
