function Test-RealPython([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    if ($Path -like '*\WindowsApps\*') { return $false }
    return ((Get-Item -LiteralPath $Path).Length -gt 30000)
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
            if (Test-RealPython $exe) { return $exe }
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
        if (Test-RealPython $exe) { return $exe }
    }
    if (Test-Path -LiteralPath $localRoot) {
        $found = Get-ChildItem -LiteralPath $localRoot -Filter python.exe -Recurse -Depth 2 -ErrorAction SilentlyContinue |
            Where-Object { Test-RealPython $_.FullName } |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py -and $py.Source -notlike '*\WindowsApps\*') {
        $exe = (& $py.Source -3 -c "import sys; print(sys.executable)" 2>$null | Out-String).Trim()
        if (Test-RealPython $exe) { return $exe }
    }
    return $null
}

function Save-WithProgress([string]$Url, [string]$Dest, [int]$FromPercent, [int]$ToPercent) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    if (Test-Path -LiteralPath $Dest) {
        $existing = (Get-Item -LiteralPath $Dest).Length
        if ($existing -gt 8000000) { return }
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

function Install-UserPython([string]$LogFile) {
    $version = '3.12.10'
    $installer = Join-Path $env:TEMP "python-$version-amd64.exe"
    $url = "https://www.python.org/ftp/python/$version/python-$version-amd64.exe"
    if (Get-Command Set-SetupProgress -ErrorAction SilentlyContinue) { Set-SetupProgress 20 }
    Save-WithProgress $url $installer 20 26
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
    if (-not (Test-RealPython $python)) {
        if (Get-Command Set-SetupProgress -ErrorAction SilentlyContinue) { Set-SetupProgress 26 }
        $repair = Start-Process -FilePath $installer -ArgumentList @('/repair', '/quiet') -Wait -PassThru
        if ($LogFile) {
            Add-Content -LiteralPath $LogFile -Value "python repair exit $($repair.ExitCode)" -Encoding UTF8
        }
    }
    if (-not (Test-RealPython $python)) {
        $remove = Start-Process -FilePath $installer -ArgumentList @('/uninstall', '/quiet') -Wait -PassThru
        if ($LogFile) {
            Add-Content -LiteralPath $LogFile -Value "python uninstall exit $($remove.ExitCode)" -Encoding UTF8
        }
        if (Get-Command Set-SetupProgress -ErrorAction SilentlyContinue) { Set-SetupProgress 27 }
        $proc = Start-Process -FilePath $installer -ArgumentList $installArgs -Wait -PassThru
        if ($LogFile) {
            Add-Content -LiteralPath $LogFile -Value "python installer exit $($proc.ExitCode)" -Encoding UTF8
        }
        if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne 3010) {
            throw "python installer exit $($proc.ExitCode)"
        }
    }
    if (-not (Test-RealPython $python)) {
        throw 'python missing after install'
    }
    return $python
}
