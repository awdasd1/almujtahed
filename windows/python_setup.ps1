function Test-RealPython([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    if ($Path -like '*\WindowsApps\*') { return $false }
    return ((Get-Item -LiteralPath $Path).Length -gt 30000)
}

function Find-RealPython {
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
    foreach ($root in @($localRoot, 'C:\Program Files', 'C:\Program Files (x86)')) {
        if (-not (Test-Path -LiteralPath $root)) { continue }
        $found = Get-ChildItem -LiteralPath $root -Filter python.exe -Recurse -Depth 3 -ErrorAction SilentlyContinue |
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

function Install-UserPython([string]$LogFile) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $ProgressPreference = 'SilentlyContinue'
    $version = '3.12.10'
    $installer = Join-Path $env:TEMP "python-$version-amd64.exe"
    $url = "https://www.python.org/ftp/python/$version/python-$version-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing -Headers @{ 'User-Agent' = 'almujtahed-local' }
    $target = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312'
    $arg = "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1 Include_launcher=1 Shortcuts=0 TargetDir=`"$target`""
    $proc = Start-Process -FilePath $installer -ArgumentList $arg -Wait -PassThru
    if ($LogFile) {
        Add-Content -LiteralPath $LogFile -Value "python installer exit $($proc.ExitCode)" -Encoding UTF8
    }
    if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne 3010) {
        throw "python installer exit $($proc.ExitCode)"
    }
    $python = Join-Path $target 'python.exe'
    if (-not (Test-RealPython $python)) {
        throw 'python missing after install'
    }
    return $python
}
