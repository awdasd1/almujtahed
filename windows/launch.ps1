$ErrorActionPreference = 'Stop'
$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $AppRoot 'source'
$Support = Join-Path $env:LOCALAPPDATA 'Almoghni'
$OldSupport = Join-Path $env:LOCALAPPDATA 'Al-Mujtahed'
if (Test-Path -LiteralPath $OldSupport) {
    if (-not (Test-Path -LiteralPath $Support)) {
        Move-Item -LiteralPath $OldSupport -Destination $Support
    } elseif (-not (Test-Path -LiteralPath (Join-Path $Support 'runtime\.venv'))) {
        $imported = Join-Path $Support 'runtime\shamela_imported'
        $oldImported = Join-Path $OldSupport 'runtime\shamela_imported'
        if ((Test-Path -LiteralPath $imported) -and -not (Test-Path -LiteralPath $oldImported)) {
            New-Item -ItemType Directory -Force -Path (Join-Path $OldSupport 'runtime') | Out-Null
            Move-Item -LiteralPath $imported -Destination $oldImported
        }
        Remove-Item -LiteralPath $Support -Recurse -Force
        Move-Item -LiteralPath $OldSupport -Destination $Support
    }
}
$Runtime = Join-Path $Support 'runtime'
$Status = Join-Path $Support 'status.txt'
$LogDir = Join-Path $Support 'logs'
$LogFile = Join-Path $LogDir 'launch.log'

New-Item -ItemType Directory -Force -Path $Support, $LogDir, $Runtime | Out-Null

function Set-Status([string]$Message) {
    [System.IO.File]::WriteAllText($Status, $Message, [System.Text.UTF8Encoding]::new($false))
}

Set-Status 'جاري تهيئة التطبيق'
$ProgressFile = Join-Path $Support 'setup-progress.txt'
$env:ALMOGHNI_PROGRESS_FILE = $ProgressFile
function Set-SetupProgress([int]$Value) {
    $clamped = [Math]::Max(0, [Math]::Min(96, $Value))
    [System.IO.File]::WriteAllText($ProgressFile, "$clamped", [System.Text.UTF8Encoding]::new($false))
}
Set-SetupProgress 1
$env:ALMOGHNI_STATUS_FILE = $Status
$env:ALMOGHNI_INIT_PID_FILE = Join-Path $Support 'init.pid'
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
    'web_ui\uploads\',
    '__pycache__\'
)
$skipFile = @(
    '.env',
    'web_ui\app_memory.db',
    'web_ui\bootstrap_status.json',
    'web_ui\init.log'
)

$files = @(Get-ChildItem -LiteralPath $Source -Recurse -File)
$copied = 0
foreach ($file in $files) {
    $rel = $file.FullName.Substring($Source.Length).TrimStart('\', '/')
    $skip = $false
    foreach ($prefix in $skipPrefix) {
        if ($rel.StartsWith($prefix)) { $skip = $true; break }
    }
    if ($skip) { continue }
    if ($skipFile -contains $rel) { continue }
    if ($rel -like '*\__pycache__\*' -or $rel.EndsWith('.pyc')) { continue }
    $dest = Join-Path $Runtime $rel
    $destDir = Split-Path -Parent $dest
    if (-not (Test-Path -LiteralPath $destDir)) {
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
    }
    Copy-Item -LiteralPath $file.FullName -Destination $dest -Force
    $copied++
    if ($files.Count -gt 0 -and ($copied % 20 -eq 0 -or $copied -eq $files.Count)) {
        Set-SetupProgress (2 + [int](16.0 * $copied / $files.Count))
    }
}

$venvPython = Join-Path $Runtime '.venv\Scripts\python.exe'
. (Join-Path $AppRoot 'python_setup.ps1')
$python = Find-RealPython
if (-not $python) {
    Set-Status 'جاري تثبيت الملفات'
    Set-SetupProgress 20
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
    Set-SetupProgress 28
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
Set-SetupProgress 91
Set-Status 'جاري تثبيت الملفات'
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $venvPython -c "import fastapi, uvicorn, huggingface_hub, dotenv, llama_cpp" | Out-Null
$importExit = $LASTEXITCODE
$ErrorActionPreference = $previous
if ($importExit -ne 0) {
    Set-Status 'جاري تثبيت الملفات'
    Set-SetupProgress 32
    $req = Join-Path $Runtime 'requirements-desktop.txt'
    if (-not (Test-Path -LiteralPath $req)) { $req = Join-Path $Runtime 'requirements.txt' }
    $packageTotal = @(Get-Content -LiteralPath $req | Where-Object { $_ -match '^[A-Za-z0-9]' }).Count
    if ($packageTotal -lt 1) { $packageTotal = 1 }
    $packagesSeen = 0
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $venvPython -m pip install --upgrade pip *>> $LogFile
    if ($LASTEXITCODE -ne 0) {
        $ErrorActionPreference = $previous
        Set-Status 'تعذر تشغيل التطبيق'
        exit $LASTEXITCODE
    }
    Set-SetupProgress 36
    & $venvPython -m pip install --extra-index-url "https://abetlen.github.io/llama-cpp-python/whl/cpu" --only-binary=llama-cpp-python -r $req 2>&1 | ForEach-Object {
        $line = "$_"
        Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
        if ($line -match '^Collecting ') {
            $packagesSeen++
            $span = [Math]::Min($packagesSeen, $packageTotal)
            Set-SetupProgress (36 + [int](50.0 * $span / $packageTotal))
        } elseif ($line -match 'Installing collected packages') {
            Set-SetupProgress 88
        }
    }
    $pipExit = $LASTEXITCODE
    $ErrorActionPreference = $previous
    if ($pipExit -ne 0) {
        Set-Status 'تعذر تشغيل التطبيق'
        exit $pipExit
    }
    Set-SetupProgress 90
}

$script = Join-Path $Runtime 'start_local.py'
$runner = Join-Path $Runtime '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $runner)) { $runner = $venvPython }
$env:ALMOGHNI_LOG_FILE = $LogFile
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
