# مجلد عمل العملية عند تشغيل التطبيق هو مجلد التثبيت، وهو مليء بملفات
# System.*.dll الخاصة بـ.NET، فيلتقطها مترجم Add-Type بدل مكتبات النظام
# ويفشل التجميع ويموت محرك التشغيل قبل تثبيت بايثون. النقل إلى TEMP يمنع ذلك.
try { [System.IO.Directory]::SetCurrentDirectory([System.IO.Path]::GetTempPath()) } catch { }
if (-not ('AlmoghniQuiet.Runner' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
namespace AlmoghniQuiet {
    public static class Runner {
        public static Process Start(string file, string args, string work, string stdout, string stderr) {
            var psi = new ProcessStartInfo(file, args);
            psi.UseShellExecute = false;
            psi.CreateNoWindow = false;
            psi.WindowStyle = ProcessWindowStyle.Hidden;
            if (!string.IsNullOrEmpty(work)) psi.WorkingDirectory = work;
            StreamWriter output = null;
            StreamWriter error = null;
            if (!string.IsNullOrEmpty(stdout)) {
                psi.RedirectStandardOutput = true;
                psi.RedirectStandardError = true;
                psi.StandardOutputEncoding = new UTF8Encoding(false);
                psi.StandardErrorEncoding = new UTF8Encoding(false);
                output = Writer(stdout);
                error = Writer(string.IsNullOrEmpty(stderr) ? stdout : stderr);
            }
            var process = new Process();
            process.StartInfo = psi;
            process.EnableRaisingEvents = true;
            if (output != null) {
                process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs ev) {
                    if (ev.Data != null) output.WriteLine(ev.Data);
                };
                process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs ev) {
                    if (ev.Data != null) error.WriteLine(ev.Data);
                };
                process.Exited += delegate { try { output.Dispose(); error.Dispose(); } catch {} };
            }
            process.Start();
            if (output != null) {
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
            }
            return process;
        }
        static StreamWriter Writer(string path) {
            var stream = new FileStream(path, FileMode.Append, FileAccess.Write, FileShare.ReadWrite);
            var writer = new StreamWriter(stream, new UTF8Encoding(false));
            writer.AutoFlush = true;
            return writer;
        }
    }
}
'@
}

function Start-QuietProcess([string]$File, [string[]]$ArgumentList, [string]$WorkingDirectory, [string]$StdOut, [string]$StdErr) {
    $parts = foreach ($arg in $ArgumentList) {
        if ($null -eq $arg) { continue }
        if ($arg -match '[\s"]') { '"' + ($arg -replace '"', '\"') + '"' } else { $arg }
    }
    return [AlmoghniQuiet.Runner]::Start($File, ($parts -join ' '), $WorkingDirectory, $StdOut, $StdErr)
}

function Test-RealPython([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    if ($Path -like '*\WindowsApps\*') { return $false }
    return ((Get-Item -LiteralPath $Path).Length -gt 30000)
}

function Wait-QuietProcess($Process, [int]$Seconds) {
    if (-not $Process) { return -1 }
    if (-not $Process.WaitForExit($Seconds * 1000)) {
        & taskkill.exe /T /F /PID $Process.Id 2>$null | Out-Null
        try { [void]$Process.WaitForExit(5000) } catch { }
        return -1
    }
    try { return [int]$Process.ExitCode } catch { return -1 }
}

function Get-PythonVersionText([string]$Path) {
    if (-not (Test-RealPython $Path)) { return '' }
    $out = Join-Path $env:TEMP 'almoghni-py-run.txt'
    $err = Join-Path $env:TEMP 'almoghni-py-run.err'
    Remove-Item -LiteralPath $out, $err -Force -ErrorAction SilentlyContinue
    $proc = Start-QuietProcess $Path @('-c', 'import sys; print("%d.%d.%d" % sys.version_info[:3])') '' $out $err
    $code = Wait-QuietProcess $proc 20
    if ($code -ne 0 -or -not (Test-Path -LiteralPath $out)) { return '' }
    return ((Get-Content -LiteralPath $out -Raw -ErrorAction SilentlyContinue) -as [string]).Trim()
}

function Test-SupportedPython([string]$Path) {
    $text = Get-PythonVersionText $Path
    return $text -match '^3\.(1[2-9]|[2-9]\d)\.\d+'
}

function Find-RealPython {
    foreach ($ver in @('3.12', '3.13', '3.11', '3.10')) {
        foreach ($root in @('HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore')) {
            $key = Join-Path $root $ver
            $install = Join-Path $key 'InstallPath'
            $dir = $null
            try { $dir = (Get-ItemProperty -LiteralPath $install -ErrorAction Stop).'(default)' } catch { }
            if ([string]::IsNullOrWhiteSpace($dir)) { continue }
            $exe = Join-Path $dir 'python.exe'
            if (Test-SupportedPython $exe) { return $exe }
        }
    }
    $localRoot = Join-Path $env:LOCALAPPDATA 'Programs\Python'
    $fixed = @(
        (Join-Path $localRoot 'Python312\python.exe'),
        (Join-Path $localRoot 'Python313\python.exe'),
        (Join-Path $localRoot 'Python311\python.exe'),
        (Join-Path $localRoot 'Python310\python.exe'),
        'C:\Program Files\Python312\python.exe',
        'C:\Program Files\Python313\python.exe',
        'C:\Program Files\Python311\python.exe',
        'C:\Program Files\Python310\python.exe'
    )
    foreach ($exe in $fixed) {
        if (Test-SupportedPython $exe) { return $exe }
    }
    if (Test-Path -LiteralPath $localRoot) {
        $candidates = @(Get-ChildItem -LiteralPath $localRoot -Filter python.exe -Recurse -Depth 2 -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending)
        foreach ($candidate in $candidates) {
            if (Test-SupportedPython $candidate.FullName) { return $candidate.FullName }
        }
    }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py -and $py.Source -notlike '*\WindowsApps\*') {
        $pyOut = Join-Path $env:TEMP 'almoghni-py-which.txt'
        $pyErr = Join-Path $env:TEMP 'almoghni-py-which.err'
        Remove-Item -LiteralPath $pyOut, $pyErr -Force -ErrorAction SilentlyContinue
        $which = Start-QuietProcess $py.Source @('-3', '-c', 'import sys; print(sys.executable)') '' $pyOut $pyErr
        Wait-QuietProcess $which 12 | Out-Null
        $exe = ''
        if (Test-Path -LiteralPath $pyOut) { $exe = (Get-Content -LiteralPath $pyOut -Raw -ErrorAction SilentlyContinue).Trim() }
        if (Test-SupportedPython $exe) { return $exe }
    }
    return $null
}

function Save-WithProgress([string]$Url, [string]$Dest, [int]$FromPercent, [int]$ToPercent) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    if (Test-Path -LiteralPath $Dest) {
        $existing = (Get-Item -LiteralPath $Dest).Length
        if ($existing -gt 24000000) { return }
        Remove-Item -LiteralPath $Dest -Force -ErrorAction SilentlyContinue
    }
    Add-Type -AssemblyName System.Net.Http
    $client = [System.Net.Http.HttpClient]::new()
    $client.Timeout = [TimeSpan]::FromMinutes(8)
    $client.DefaultRequestHeaders.UserAgent.ParseAdd('almoghni-local')
    $response = $client.GetAsync($Url, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
    $response.EnsureSuccessStatusCode() | Out-Null
    $total = $response.Content.Headers.ContentLength
    $stream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
    $file = [System.IO.File]::Create($Dest)
    try {
        $buffer = New-Object byte[] 65536
        $got = 0L
        while (($count = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $file.Write($buffer, 0, $count)
            $got += $count
            if ($total -gt 0 -and (Get-Command Set-SetupProgress -ErrorAction SilentlyContinue)) {
                $span = $ToPercent - $FromPercent
                Set-SetupProgress ($FromPercent + [int]($span * $got / $total))
            }
        }
    } finally {
        $file.Close()
        $stream.Close()
        $client.Dispose()
    }
}

function Write-PythonLog([string]$LogFile, [string]$Message) {
    if ($LogFile) { Add-Content -LiteralPath $LogFile -Value $Message -Encoding UTF8 }
}

function Invoke-QuietInstaller([string]$File, [string[]]$ArgumentList, [int]$Seconds, [string]$LogFile, [string]$Label) {
    if (-not (Test-Path -LiteralPath $File)) {
        Write-PythonLog $LogFile "$Label missing"
        return -1
    }
    $proc = Start-QuietProcess $File $ArgumentList '' '' ''
    $code = Wait-QuietProcess $proc $Seconds
    Write-PythonLog $LogFile "$Label exit $code"
    return $code
}

function Split-InstallerCommand([string]$Command) {
    $command = $Command.Trim()
    $file = ''
    $rest = ''
    if ($command.StartsWith('"')) {
        $end = $command.IndexOf('"', 1)
        if ($end -gt 1) {
            $file = $command.Substring(1, $end - 1)
            $rest = $command.Substring($end + 1).Trim()
        }
    } elseif ($command) {
        $parts = $command.Split(' ', 2)
        $file = $parts[0]
        if ($parts.Length -gt 1) { $rest = $parts[1] }
    }
    $argList = @()
    if ($rest) {
        $argList = @([regex]::Matches($rest, '"[^"]*"|\S+') | ForEach-Object { $_.Value.Trim('"') })
    }
    return @{ File = $file; Args = $argList }
}

function Clear-Python312Registration {
    $root = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall'
    if (Test-Path -LiteralPath $root) {
        foreach ($key in @(Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue)) {
            $prop = Get-ItemProperty -LiteralPath $key.PSPath -ErrorAction SilentlyContinue
            $name = [string]$prop.DisplayName
            if ($name -notmatch '^Python 3\.12') { continue }
            $location = [string]$prop.InstallLocation
            if ($location -and $location -notlike '*\Programs\Python\Python312*') { continue }
            Remove-Item -LiteralPath $key.PSPath -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    Remove-Item -LiteralPath 'HKCU:\Software\Python\PythonCore\3.12' -Recurse -Force -ErrorAction SilentlyContinue
}

function Remove-StalePython312([string]$Installer, [string]$LogFile) {
    $root = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall'
    if (Test-Path -LiteralPath $root) {
        foreach ($key in @(Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue)) {
            $prop = Get-ItemProperty -LiteralPath $key.PSPath -ErrorAction SilentlyContinue
            $name = [string]$prop.DisplayName
            if ($name -notmatch '^Python 3\.12') { continue }
            $location = [string]$prop.InstallLocation
            if ($location -and $location -notlike '*\Programs\Python\Python312*') { continue }
            $command = [string]$prop.QuietUninstallString
            if (-not $command) { $command = [string]$prop.UninstallString }
            if (-not $command) { continue }
            $parsed = Split-InstallerCommand $command
            if (-not $parsed.File) { continue }
            $argList = @($parsed.Args)
            if ($argList -notcontains '/quiet' -and $argList -notcontains '/silent') { $argList += '/quiet' }
            Invoke-QuietInstaller $parsed.File $argList 120 $LogFile 'python registry uninstall' | Out-Null
        }
    }
    Invoke-QuietInstaller $Installer @('/uninstall', '/quiet') 120 $LogFile 'python bundle uninstall' | Out-Null
}

function Install-UserPython([string]$LogFile) {
    $version = '3.12.10'
    $installer = Join-Path $env:TEMP "python-$version-amd64.exe"
    $url = "https://www.python.org/ftp/python/$version/python-$version-amd64.exe"
    $target = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312'
    $python = Join-Path $target 'python.exe'
    $installArgs = @(
        '/quiet',
        'InstallAllUsers=0',
        'PrependPath=0',
        'Include_test=0',
        'Include_pip=1',
        'Include_launcher=0',
        'Shortcuts=0',
        "TargetDir=$target"
    )
    if (Test-SupportedPython $python) { return $python }
    if (Get-Command Set-SetupProgress -ErrorAction SilentlyContinue) { Set-SetupProgress 20 }
    Save-WithProgress $url $installer 20 26
    # حذف مجلد بايثون يدوياً يترك تسجيل ويندوز سليماً، فيخرج التنصيب العادي بنجاح
    # دون إعادة أي ملف. الإصلاح وحده يعيد الملفات المحذوفة، لذا يأتي أولاً دائماً.
    if (Get-Command Set-Status -ErrorAction SilentlyContinue) { Set-Status 'جاري إصلاح بايثون' }
    if (Get-Command Set-SetupProgress -ErrorAction SilentlyContinue) { Set-SetupProgress 26 }
    Invoke-QuietInstaller $installer @('/repair', '/quiet') 240 $LogFile 'python repair' | Out-Null
    if (Test-SupportedPython $python) { return $python }
    if (Get-Command Set-Status -ErrorAction SilentlyContinue) { Set-Status 'جاري تثبيت بايثون' }
    if (Get-Command Set-SetupProgress -ErrorAction SilentlyContinue) { Set-SetupProgress 27 }
    Remove-StalePython312 $installer $LogFile
    if (Test-SupportedPython $python) { return $python }
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue
    }
    Clear-Python312Registration
    $code = Invoke-QuietInstaller $installer $installArgs 300 $LogFile 'python installer'
    if (-not (Test-SupportedPython $python)) {
        Invoke-QuietInstaller $installer @('/repair', '/quiet') 240 $LogFile 'python repair after install' | Out-Null
    }
    if (-not (Test-SupportedPython $python)) {
        Clear-Python312Registration
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue
        }
        $code = Invoke-QuietInstaller $installer $installArgs 300 $LogFile 'python installer retry'
        Invoke-QuietInstaller $installer @('/repair', '/quiet') 240 $LogFile 'python repair after retry' | Out-Null
    }
    if (-not (Test-SupportedPython $python)) {
        throw "python missing after install ($code)"
    }
    return $python
}
