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
    if ($clamped -le $script:setupFloor) { return }
    $script:setupFloor = $clamped
    [System.IO.File]::WriteAllText($ProgressFile, "$clamped", [System.Text.UTF8Encoding]::new($false))
}
$script:setupFloor = 0
if (Test-Path -LiteralPath $ProgressFile) {
    $prior = 0
    if ([int]::TryParse((Get-Content -LiteralPath $ProgressFile -Raw).Trim(), [ref]$prior)) {
        $script:setupFloor = [Math]::Max(0, [Math]::Min(96, $prior))
    }
}
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
    # نسخ المتغيّر فقط: مقارنة الحجم ووقت التعديل تختصر إقلاع كل مرة
    # من نسخ آلاف الملفات (وبطء Defender معها) إلى ثوانٍ.
    $unchanged = $false
    if (Test-Path -LiteralPath $dest) {
        $dstInfo = Get-Item -LiteralPath $dest
        if ($dstInfo.Length -eq $file.Length -and
            $dstInfo.LastWriteTimeUtc -ge $file.LastWriteTimeUtc) {
            $unchanged = $true
        }
    }
    if (-not $unchanged) {
        Copy-Item -LiteralPath $file.FullName -Destination $dest -Force
    }
    $copied++
    if ($files.Count -gt 0 -and ($copied % 20 -eq 0 -or $copied -eq $files.Count)) {
        Set-SetupProgress (2 + [int](16.0 * $copied / $files.Count))
    }
}
Set-SetupProgress 18

# نسخة خام: لا بذور بيانات. أول تشغيل يطلب مجلد الحفظ الآمن ثم يبدأ فارغًا.

$venvPython = Join-Path $Runtime '.venv\Scripts\python.exe'
Set-Location -LiteralPath $Runtime
try { [System.IO.Directory]::SetCurrentDirectory($Runtime) } catch { }
. (Join-Path $AppRoot 'python_setup.ps1')
$python = Find-RealPython
if ($python) {
    Add-Content -LiteralPath $LogFile -Value "python found $python" -Encoding UTF8
} else {
    Set-Status 'جاري تثبيت بايثون'
    Set-SetupProgress 20
    try {
        $python = Install-UserPython $LogFile
        Add-Content -LiteralPath $LogFile -Value "python installed $python" -Encoding UTF8
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
    $venvProc = Start-QuietProcess $python @('-m', 'venv', $venvDir) $Runtime $LogFile (Join-Path $LogDir 'venv-err.log')
    $venvCode = Wait-QuietProcess $venvProc 180
    if ($venvCode -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
        Set-Status 'تعذر تشغيل التطبيق'
        exit 1
    }
}

Set-Location -LiteralPath $Runtime
# ختم المكتبات: إن لم تتغير قائمة المتطلبات منذ آخر فحص ناجح، لا فحص
# ولا تثبيت — كان الفحص/التثبيت يعاد عند كل إقلاع فيطيل التحميل جدًا.
$depsReq = Join-Path $Runtime 'requirements-desktop.txt'
if (-not (Test-Path -LiteralPath $depsReq)) { $depsReq = Join-Path $Runtime 'requirements.txt' }
$depsStamp = Join-Path $Support 'deps-ok.txt'
$depsHash = ''
if (Test-Path -LiteralPath $depsReq) {
    $depsHash = (Get-FileHash -LiteralPath $depsReq -Algorithm SHA256).Hash
}
$depsOk = $false
if ($depsHash -and (Test-Path -LiteralPath $depsStamp)) {
    $depsOk = ((Get-Content -LiteralPath $depsStamp -Raw).Trim() -eq $depsHash)
}
$importOut = Join-Path $LogDir 'import-check.log'
$importErr = Join-Path $LogDir 'import-check.err'
if ($depsOk) {
    $importExit = 0
} else {
    Remove-Item -LiteralPath $importOut, $importErr -Force -ErrorAction SilentlyContinue
    $importProc = Start-QuietProcess $venvPython @('-c', 'import fastapi, uvicorn, huggingface_hub, dotenv, llama_cpp, jpype') $Runtime $importOut $importErr
    $importProc.WaitForExit()
    $importExit = $importProc.ExitCode
}
if ($importExit -ne 0) {
    Set-Status 'جاري تثبيت المكتبات'
    Set-SetupProgress 32
    $req = Join-Path $Runtime 'requirements-desktop.txt'
    if (-not (Test-Path -LiteralPath $req)) { $req = Join-Path $Runtime 'requirements.txt' }
    $packageTotal = @(Get-Content -LiteralPath $req | Where-Object { $_ -match '^[A-Za-z0-9]' }).Count
    if ($packageTotal -lt 1) { $packageTotal = 1 }
    $pipOut = Join-Path $LogDir 'pip.log'
    $pipErr = Join-Path $LogDir 'pip-err.log'
    Remove-Item -LiteralPath $pipOut, $pipErr -Force -ErrorAction SilentlyContinue
    function Read-SharedText([string]$Path) {
        if (-not (Test-Path -LiteralPath $Path)) { return '' }
        $stream = [System.IO.File]::Open($Path, 'Open', 'Read', 'ReadWrite')
        try {
            $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8, $true)
            return $reader.ReadToEnd()
        } finally {
            $stream.Close()
        }
    }
    function Update-PipProgress {
        $text = (Read-SharedText $pipOut) + (Read-SharedText $pipErr)
        $collecting = ([regex]::Matches($text, '(?m)^Collecting ')).Count
        if ($collecting -gt $script:pipPackages) { $script:pipPackages = $collecting }
        $total = [Math]::Max($packageTotal, $script:pipPackages)
        if ($total -lt 1) { $total = 1 }
        $slot = 60.0 / $total
        $tail = $text
        $mark = $text.LastIndexOf("Collecting ")
        if ($mark -ge 0) { $tail = $text.Substring($mark) }
        $intra = 0
        $percents = [regex]::Matches($tail, '(?<![0-9])(\d{1,3})%')
        if ($percents.Count -gt 0) {
            $intra = [Math]::Min(100, [int]$percents[$percents.Count - 1].Groups[1].Value)
        }
        $done = [Math]::Max(0, $script:pipPackages - 1)
        Set-SetupProgress ([int](30 + ($done * $slot) + ($intra / 100.0 * $slot)))
    }
    $script:pipPackages = 0
    $upgrade = Start-QuietProcess $venvPython @('-m', 'pip', 'install', '--disable-pip-version-check', '--progress-bar', 'off', '--upgrade', 'pip') $Runtime $pipOut $pipErr
    while (-not $upgrade.HasExited) {
        Update-PipProgress
        Start-Sleep -Milliseconds 600
    }
    $upgrade.WaitForExit()
    if ($upgrade.ExitCode -ne 0) {
        Set-Status 'تعذر تشغيل التطبيق'
        exit $upgrade.ExitCode
    }
    $install = Start-QuietProcess $venvPython @(
        '-m', 'pip', 'install', '--disable-pip-version-check', '--progress-bar', 'off',
        '--extra-index-url', 'https://abetlen.github.io/llama-cpp-python/whl/cpu',
        '--only-binary=llama-cpp-python', '-r', $req
    ) $Runtime $pipOut $pipErr
    while (-not $install.HasExited) {
        Update-PipProgress
        Start-Sleep -Milliseconds 600
    }
    $install.WaitForExit()
    if ($install.ExitCode -ne 0) {
        Set-Status 'تعذر تشغيل التطبيق'
        exit $install.ExitCode
    }
    Get-Content -LiteralPath $pipOut, $pipErr -ErrorAction SilentlyContinue | Add-Content -LiteralPath $LogFile -Encoding UTF8
    Set-SetupProgress 90
} else {
    Set-SetupProgress 90
}

if ($depsHash) {
    try { [System.IO.File]::WriteAllText($depsStamp, $depsHash) } catch { }
}
Set-SetupProgress 91
$script = Join-Path $Runtime 'start_local.py'
$runner = Join-Path $Runtime '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $runner)) { $runner = $venvPython }
$env:ALMOGHNI_LOG_FILE = $LogFile
$ErrorActionPreference = 'Continue'
# حلقة المشرف: خروج الخادم بالرمز 17 يعني «أعد تشغيلي» (بعد حفظ مجلد
# الحفظ مثلًا) فيُعاد إقلاعه من هنا عبر start_local.py كاملًا — نفس
# طبقة الإقلاع الأول بسجلّها وبيئتها. كان الخادم يولّد نسخة منفصلة
# بلا مجارٍ إخراج فتموت فورًا بصمت ولا يعيدها أحد.
$restartCode = 17
while ($true) {
    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo.FileName = $runner
    $proc.StartInfo.Arguments = "-X utf8 -u `"$script`""
    $proc.StartInfo.WorkingDirectory = $Runtime
    $proc.StartInfo.UseShellExecute = $false
    $proc.StartInfo.CreateNoWindow = $true
    $proc.StartInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    [void]$proc.Start()
    $proc.WaitForExit()
    if ($proc.ExitCode -ne $restartCode) { exit $proc.ExitCode }
    Add-Content -LiteralPath $LogFile -Value 'restart requested by server (exit 17) - relaunching' -Encoding UTF8
    Start-Sleep -Seconds 1
}
