param([switch]$Minimal)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$runtime = Join-Path $root 'runtime'
$bin = Join-Path $root 'bin'
$downloads = Join-Path $root 'data\cache\bootstrap'
New-Item -ItemType Directory -Force $downloads | Out-Null
# Use the full standalone CPython distribution, not a venv or embeddable Python.
# uv's managed Python distribution is relocatable; uv itself is only a setup tool.
$uv = Join-Path $downloads 'uv.exe'
if (!(Test-Path -LiteralPath $uv)) {
    $archive = Join-Path $downloads 'uv.zip'
    Invoke-WebRequest -Uri 'https://github.com/astral-sh/uv/releases/download/0.9.18/uv-x86_64-pc-windows-msvc.zip' -OutFile $archive
    Expand-Archive -LiteralPath $archive -DestinationPath $downloads -Force
    if (!(Test-Path -LiteralPath $uv)) {
        $found = @(Get-ChildItem -LiteralPath $downloads -Filter uv.exe -Recurse)
        if ($found.Count -ne 1) { throw 'uv executable missing or ambiguous' }
        Copy-Item -LiteralPath $found[0].FullName -Destination $uv
    }
}
$env:UV_PYTHON_INSTALL_DIR = Join-Path $downloads 'python'
$env:UV_CACHE_DIR = Join-Path $root 'data\cache\uv'
$env:UV_PYTHON_PREFERENCE = 'only-managed'
$env:UV_NO_MODIFY_PATH = '1'
$env:UV_NO_CONFIG = '1'
$env:UV_LINK_MODE = 'copy'
$env:PYTHONNOUSERSITE = '1'
Remove-Item Env:PYTHONHOME,Env:PYTHONPATH,Env:VIRTUAL_ENV -ErrorAction SilentlyContinue
$python = Join-Path $runtime 'python.exe'
if (!(Test-Path -LiteralPath $python)) {
    if (Test-Path -LiteralPath $runtime) { throw 'Incomplete runtime folder; rename it before retrying.' }
    & $uv python install 3.12.12 --no-bin
    if ($LASTEXITCODE -ne 0) { throw 'Local Python download failed' }
    $managed = & $uv python find 3.12.12 --managed-python
    if ($LASTEXITCODE -ne 0 -or !$managed) { throw 'Managed Python missing' }
    $managed = [IO.Path]::GetFullPath([string]$managed)
    if (!$managed.StartsWith($env:UV_PYTHON_INSTALL_DIR + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'External Python rejected' }
    $stage = Join-Path $root ('runtime-stage-' + [Guid]::NewGuid().ToString('N'))
    Copy-Item -LiteralPath (Split-Path -Parent $managed) -Destination $stage -Recurse
    Move-Item -LiteralPath $stage -Destination $runtime
}
& $python -I -c "import sys; assert sys.version_info[:2]==(3,12); assert sys.prefix==sys.base_prefix"
if ($LASTEXITCODE -ne 0) { throw 'Standalone runtime check failed' }
# Non-editable wheels for dependencies; current source is loaded via relative .pth.
$extras = if ($Minimal) { 'gui' } else { 'gui,speech,vision,models,twitch' }
& $uv pip install --python $python --no-config --link-mode copy --system ".[${extras}]"
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $python -I -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw 'Local pip bootstrap failed' }
& $python -I -c "import sysconfig,pathlib; p=pathlib.Path(sysconfig.get_path('purelib')); (p/'00_streamclipper_source.pth').write_text('import sys, os; sys.path.insert(0, os.path.join(sys.prefix, os.pardir, chr(115)+chr(114)+chr(99)))\n',encoding='ascii')"
if ($LASTEXITCODE -ne 0) { throw 'Relative source registration failed' }
if (!(Test-Path (Join-Path $bin 'ffmpeg.exe')) -or !(Test-Path (Join-Path $bin 'ffprobe.exe'))) {
    $archive = Join-Path $downloads 'ffmpeg.zip'
    Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile $archive
    $stage = Join-Path $downloads ('ffmpeg-' + [Guid]::NewGuid().ToString('N'))
    Expand-Archive -LiteralPath $archive -DestinationPath $stage
    $exe = @(Get-ChildItem -LiteralPath $stage -Filter ffmpeg.exe -Recurse)
    if ($exe.Count -ne 1) { throw 'FFmpeg archive invalid' }
    New-Item -ItemType Directory -Force $bin | Out-Null
    foreach ($name in @('ffmpeg.exe','ffprobe.exe')) { Copy-Item -LiteralPath (Join-Path $exe[0].DirectoryName $name) -Destination $bin -Force }
    $license = Join-Path $exe[0].Directory.Parent.FullName 'LICENSE'
    if (Test-Path $license) { Copy-Item -LiteralPath $license -Destination (Join-Path $bin 'FFmpeg-LICENSE.txt') -Force }
}
foreach ($name in @('ffmpeg.exe','ffprobe.exe')) {
    & (Join-Path $bin $name) -version | Select-Object -First 1
    if ($LASTEXITCODE -ne 0) { throw "$name failed" }
}
& $python -I -c "import streamclipper, PySide6; print(streamclipper.__file__)"
if ($LASTEXITCODE -ne 0) { throw 'Local import failed' }
Write-Host 'Portable runtime ready. Existing .venv and data are retained.'
