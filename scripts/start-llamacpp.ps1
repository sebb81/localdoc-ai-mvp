$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$logs = Join-Path $root 'web\.launcher'
New-Item -ItemType Directory -Force $logs | Out-Null
$url = if ($env:LOCALDOC_LLAMA_URL) { $env:LOCALDOC_LLAMA_URL.TrimEnd('/') } else { 'http://127.0.0.1:8081' }
function Test-Llama {
    try {
        $health = Invoke-RestMethod "$url/health" -TimeoutSec 2
        $models = Invoke-RestMethod "$url/v1/models" -TimeoutSec 2
        return ($health.status -eq 'ok' -and @($models.data.id) -contains 'phi4')
    } catch { return $false }
}
if (Test-Llama) { return }
if ($url -ne 'http://127.0.0.1:8081') { throw "Le serveur configure doit etre lance avec --alias phi4 : $url" }
if (Get-NetTCPConnection -State Listen -LocalPort 8081 -ErrorAction SilentlyContinue) { throw 'Port 8081 occupe ou modele en cours de chargement. Voir web/.launcher/llama-error.log, puis reessayer.' }
$exe = Get-ChildItem -LiteralPath (Join-Path $root 'runtime\llamacpp') -Filter llama-server.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
$model = if ($env:LOCALDOC_MODEL_PATH) { $env:LOCALDOC_MODEL_PATH } else { Join-Path $root 'models\phi4.gguf' }
if (!$exe -or !(Test-Path -LiteralPath $model)) { throw 'Lancez installer-webnn.bat : moteur ou modele absent.' }
$gpuLayers = if ($env:LOCALDOC_GPU_LAYERS) { $env:LOCALDOC_GPU_LAYERS } else { '99' }
$process = Start-Process -FilePath $exe.FullName -WorkingDirectory $exe.DirectoryName -WindowStyle Hidden -ArgumentList @('--model',"`"$model`"",'--alias','phi4','--host','127.0.0.1','--port','8081','--ctx-size','4096','--parallel','1','--n-gpu-layers',$gpuLayers) -RedirectStandardOutput (Join-Path $logs 'llama.log') -RedirectStandardError (Join-Path $logs 'llama-error.log') -PassThru
$process.Id | Set-Content (Join-Path $logs 'llama.pid')
for ($attempt = 0; $attempt -lt 240; $attempt++) {
    $process.Refresh()
    if ($process.HasExited) { throw 'llama.cpp a quitte. Voir web/.launcher/llama-error.log.' }
    if (Test-Llama) { Write-Host 'Phi-4 charge dans llama.cpp.'; return }
    Start-Sleep -Milliseconds 1000
}
throw 'Chargement trop long. Voir web/.launcher/llama-error.log.'
