$ErrorActionPreference = 'Stop'
$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $AppRoot 'source'
$Support = Join-Path $env:LOCALAPPDATA 'Al-Mujtahed'
$Runtime = Join-Path $Support 'runtime'
$Status = Join-Path $Support 'status.txt'
$LogDir = Join-Path $Support 'logs'
$LogFile = Join-Path $LogDir 'launch.log'

New-Item -ItemType Directory -Force -Path $Support, $LogDir, $Runtime | Out-Null

function Set-Status([string]$Message) {
    [System.IO.File]::WriteAllText($Status, $Message, [System.Text.UTF8Encoding]::new($false))
}

Set-Status 'جاري تهيئة التطبيق'
$env:ALMUJTAHED_STATUS_FILE = $Status
$env:ALMUJTAHED_QDRANT_PID_FILE = Join-Path $Support 'qdrant.pid'
$env:ALMUJTAHED_INIT_PID_FILE = Join-Path $Support 'init.pid'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

if (-not (Test-Path -LiteralPath $Source)) {
    Set-Status 'تعذر تشغيل التطبيق'
    exit 1
}

$skipPrefix = @(
    '.venv\',
    'models\',
    'shamela4_data\',
    'qdrant_service\storage\',
    'qdrant_service\snapshots\',
    'web_ui\uploads\',
    '__pycache__\'
)
$skipFile = @(
    '.env',
    'qdrant_service\qdrant.exe',
    'qdrant_service\qdrant',
    'qdrant_service\qdrant.log',
    'web_ui\app_memory.db',
    'web_ui\bootstrap_status.json',
    'web_ui\init.log'
)

Get-ChildItem -LiteralPath $Source -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($Source.Length).TrimStart('\', '/')
    foreach ($prefix in $skipPrefix) {
        if ($rel.StartsWith($prefix)) { return }
    }
    if ($skipFile -contains $rel) { return }
    if ($rel -like '*\__pycache__\*' -or $rel.EndsWith('.pyc')) { return }
    $dest = Join-Path $Runtime $rel
    $destDir = Split-Path -Parent $dest
    if (-not (Test-Path -LiteralPath $destDir)) {
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
    }
    Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
}

$venvPython = Join-Path $Runtime '.venv\Scripts\python.exe'
. (Join-Path $AppRoot 'python_setup.ps1')
$python = Find-RealPython
if (-not $python) {
    Set-Status 'جاري تثبيت الملفات'
    try {
        $python = Install-UserPython $LogFile
    } catch {
        Add-Content -LiteralPath $LogFile -Value $_ -Encoding UTF8
        Set-Status 'تعذر تشغيل التطبيق'
        exit 1
    }
}
if (-not (Test-Path -LiteralPath $venvPython)) {
    Set-Status 'جاري تثبيت الملفات'
    $venvDir = Join-Path $Runtime '.venv'
    if (Test-Path -LiteralPath $venvDir) {
        Remove-Item -LiteralPath $venvDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    & $python -m venv $venvDir *>> $LogFile
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
        Set-Status 'تعذر تشغيل التطبيق'
        exit 1
    }
}

Set-Location -LiteralPath $Runtime
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $venvPython -c "import fastapi, uvicorn, qdrant_client, huggingface_hub, dotenv, llama_cpp" | Out-Null
$importExit = $LASTEXITCODE
$ErrorActionPreference = $previous
if ($importExit -ne 0) {
    Set-Status 'جاري تثبيت الملفات'
    $req = Join-Path $Runtime 'requirements-desktop.txt'
    if (-not (Test-Path -LiteralPath $req)) { $req = Join-Path $Runtime 'requirements.txt' }
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $venvPython -m pip install --upgrade pip *>> $LogFile
    if ($LASTEXITCODE -ne 0) {
        $ErrorActionPreference = $previous
        Set-Status 'تعذر تشغيل التطبيق'
        exit $LASTEXITCODE
    }
    & $venvPython -m pip install --extra-index-url "https://abetlen.github.io/llama-cpp-python/whl/cpu" --only-binary=llama-cpp-python -r $req *>> $LogFile
    $pipExit = $LASTEXITCODE
    $ErrorActionPreference = $previous
    if ($pipExit -ne 0) {
        Set-Status 'تعذر تشغيل التطبيق'
        exit $pipExit
    }
}

$script = Join-Path $Runtime 'start_local.py'
$runner = Join-Path $Runtime '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $runner)) { $runner = $venvPython }
$env:ALMUJTAHED_LOG_FILE = $LogFile
$ErrorActionPreference = 'Continue'
$proc = New-Object System.Diagnostics.Process
$proc.StartInfo.FileName = $runner
$proc.StartInfo.Arguments = "-X utf8 -u `"$script`""
$proc.StartInfo.WorkingDirectory = $Runtime
$proc.StartInfo.UseShellExecute = $false
$proc.StartInfo.CreateNoWindow = $true
$proc.StartInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
[void]$proc.Start()
$proc.WaitForExit()
exit $proc.ExitCode
