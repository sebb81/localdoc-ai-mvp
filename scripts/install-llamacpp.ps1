$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$runtime = Join-Path $root 'runtime\llamacpp'
$models = Join-Path $root 'models'
New-Item -ItemType Directory -Force $runtime,$models | Out-Null
# Version fixe, archives officielles et empreintes fournies par GitHub.
$release = Invoke-RestMethod 'https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b12110'
foreach ($name in @('llama-b12110-bin-win-cuda-12.4-x64.zip','cudart-llama-bin-win-cuda-12.4-x64.zip')) {
    $asset = $release.assets | Where-Object name -eq $name
    if (!$asset -or !$asset.digest.StartsWith('sha256:')) { throw "Archive ou empreinte absente : $name" }
    $archive = Join-Path $runtime $name
    if (!(Test-Path -LiteralPath $archive) -or (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLower() -ne $asset.digest.Substring(7)) {
        Write-Host "Telechargement : $name"
        & curl.exe --fail --location --retry 3 --output $archive $asset.browser_download_url
        if ($LASTEXITCODE -ne 0) { throw "Telechargement echoue : $name" }
    }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLower() -ne $asset.digest.Substring(7)) { throw "Empreinte incorrecte : $name" }
    Expand-Archive -LiteralPath $archive -DestinationPath $runtime -Force
}
$model = Join-Path $models 'phi4.gguf'
if (!(Test-Path -LiteralPath $model)) {
    $store = if ($env:OLLAMA_MODELS) { $env:OLLAMA_MODELS } else { Join-Path $env:USERPROFILE '.ollama\models' }
    $manifest = Join-Path $store 'manifests\registry.ollama.ai\library\phi4\latest'
    if (!(Test-Path -LiteralPath $manifest)) { throw 'Placez un modele Phi-4 GGUF dans models\phi4.gguf, puis relancez installer-webnn.bat.' }
    $layer = (Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json).layers | Where-Object mediaType -eq 'application/vnd.ollama.image.model' | Select-Object -First 1
    $blob = Join-Path $store ('blobs\' + $layer.digest.Replace(':','-'))
    $stream = [IO.File]::OpenRead($blob)
    try {
        $magic = New-Object byte[] 4
        if ($stream.Read($magic,0,4) -ne 4 -or [Text.Encoding]::ASCII.GetString($magic) -ne 'GGUF') { throw 'Le modele existant ne contient pas un GGUF.' }
    } finally { $stream.Dispose() }
    if ((Get-FileHash -LiteralPath $blob -Algorithm SHA256).Hash.ToLower() -ne $layer.digest.Substring(7)) { throw 'Empreinte du modele incorrecte.' }
    # Lien NTFS : pas de duplication des 9 Go ; supprimer le fichier source ne supprime pas ce lien.
    try { New-Item -ItemType HardLink -Path $model -Target $blob -ErrorAction Stop | Out-Null }
    catch { Copy-Item -LiteralPath $blob -Destination $model }
}
$exe = Get-ChildItem -LiteralPath $runtime -Filter llama-server.exe -Recurse | Select-Object -First 1
if (!$exe) { throw 'llama-server.exe absent apres extraction.' }
Write-Host "llama.cpp pret : $($exe.FullName)"
