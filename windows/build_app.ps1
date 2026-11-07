# يبني ملف تثبيت المجتهد لويندوز ويضعه في مجلد التنزيلات.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Exe = if ($args.Count -gt 0) { $args[0] } else { Join-Path $env:USERPROFILE 'Downloads\المجتهد.exe' }
$Stage = Join-Path ([System.IO.Path]::GetTempPath()) ("almujtahed-win-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $Stage | Out-Null
try {
    $Bundle = Join-Path $Stage 'app'
    dotnet publish (Join-Path $PSScriptRoot 'AlMujtahed.csproj') -c Release -r win-x64 --self-contained true -p:DebugType=None -o $Bundle
    $Source = Join-Path $Stage 'source'
    New-Item -ItemType Directory -Force -Path $Source, (Join-Path $Bundle 'fonts'), (Join-Path $Bundle 'source') | Out-Null
    git -C $Root archive --format=tar -o (Join-Path $Stage 'source.tar') HEAD
    tar -xf (Join-Path $Stage 'source.tar') -C $Source
    foreach ($name in @('.gitignore', 'README.md', 'changes.md', 'dev.md', 'init_coolify_data.py', 'start_local.py', 'start_local.sh', 'start_local.bat', 'requirements-desktop.txt')) {
        Copy-Item -LiteralPath (Join-Path $Root $name) -Destination (Join-Path $Source $name) -Force
    }
    Copy-Item -LiteralPath (Join-Path $Root 'web_ui\server.py') -Destination (Join-Path $Source 'web_ui\server.py') -Force
    Copy-Item -LiteralPath (Join-Path $Root 'web_ui\templates\auth.html') -Destination (Join-Path $Source 'web_ui\templates\auth.html') -Force
    Copy-Item -LiteralPath (Join-Path $Root 'web_ui\templates\index.html') -Destination (Join-Path $Source 'web_ui\templates\index.html') -Force
    $fontDest = Join-Path $Source 'web_ui\static\fonts'
    New-Item -ItemType Directory -Force -Path $fontDest | Out-Null
    Copy-Item (Join-Path $Root 'web_ui\static\fonts\Almarai-*.ttf') -Destination $fontDest -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'launch.ps1') -Destination (Join-Path $Bundle 'launch.ps1') -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'python_setup.ps1') -Destination (Join-Path $Bundle 'python_setup.ps1') -Force
    Copy-Item (Join-Path $Root 'web_ui\static\fonts\Almarai-*.ttf') -Destination (Join-Path $Bundle 'fonts') -Force
    Copy-Item -Path (Join-Path $Source '*') -Destination (Join-Path $Bundle 'source') -Recurse -Force
    $Zip = Join-Path $Stage 'payload.zip'
    Compress-Archive -Path (Join-Path $Bundle '*') -DestinationPath $Zip
    dotnet publish (Join-Path $PSScriptRoot 'AlMujtahedSetup.csproj') -c Release -r win-x64 --self-contained true -p:DebugType=None "-p:PayloadZip=$Zip" -o (Join-Path $Stage 'setup')
    Copy-Item -LiteralPath (Join-Path $Stage 'setup\AlMujtahedSetup.exe') -Destination $Exe -Force
    Write-Output $Exe
}
finally {
    Remove-Item -LiteralPath $Stage -Recurse -Force -ErrorAction SilentlyContinue
}
