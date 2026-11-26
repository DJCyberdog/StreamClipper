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
    # Do not use uv python find: its discovery may depend on project settings.
    $managedRoot = $env:UV_PYTHON_INSTALL_DIR
    $candidates = @(Get-ChildItem -LiteralPath $managedRoot -Directory -Filter 'cpython-3.12.12-windows-*' | ForEach-Object {
        $candidate = Join-Path $_.FullName 'python.exe'
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { $candidate }
    })
    if ($candidates.Count -ne 1) {
        Get-ChildItem -LiteralPath $managedRoot -Force | Select-Object Name | Out-Host
        throw "Expected one local CPython 3.12.12 runtime under $managedRoot; found $($candidates.Count)"
    }
    $managed = $candidates[0]
    & $managed -I -c "import sys,struct; assert sys.version_info[:3]==(3,12,12); assert struct.calcsize('P')==8; assert sys.prefix==sys.base_prefix"
    if ($LASTEXITCODE -ne 0) { throw 'Downloaded standalone Python validation failed' }
    $stage = Join-Path $root ('runtime-stage-' + [Guid]::NewGuid().ToString('N'))
    Copy-Item -LiteralPath (Split-Path -Parent $managed) -Destination $stage -Recurse
    Move-Item -LiteralPath $stage -Destination $runtime
}
& $python -I -c "import sys; assert sys.version_info[:2]==(3,12); assert sys.prefix==sys.base_prefix"
if ($LASTEXITCODE -ne 0) { throw 'Standalone runtime check failed' }
# The runtime is our private copy, not uv's managed installation.
# Explicitly allow package installation only after checking its actual prefix.
$actualPrefix = & $python -I -c "import sys; print(sys.prefix)"
if ($LASTEXITCODE -ne 0 -or !$actualPrefix -or [IO.Path]::GetFullPath([string]$actualPrefix) -ne [IO.Path]::GetFullPath($runtime)) { throw 'External runtime prefix rejected' }
# Remove the copied PEP 668 marker only inside our verified private runtime,
# so later local pip commands (GPU and optional extras) work as well.
$stdlib = & $python -I -c "import sysconfig; print(sysconfig.get_path('stdlib'))"
if ($LASTEXITCODE -ne 0 -or !$stdlib -or !([IO.Path]::GetFullPath([string]$stdlib).StartsWith($runtime + '\', [StringComparison]::OrdinalIgnoreCase))) { throw 'External stdlib rejected' }
$marker = Join-Path $stdlib 'EXTERNALLY-MANAGED'
if (Test-Path -LiteralPath $marker -PathType Leaf) { Remove-Item -LiteralPath $marker -Force }
# Non-editable wheels for dependencies; current source is loaded via relative .pth.
$extras = if ($Minimal) { 'gui' } else { 'gui,speech,vision,models,twitch' }
# Preserve installed CUDA wheels on repair/update.
$gpuPair = @(& $python -I -c "import importlib.metadata as m; exec('try:\n a=m.version(\x27torch\x27); b=m.version(\x27torchvision\x27); print(a); print(b)\nexcept m.PackageNotFoundError: pass')")
if ($LASTEXITCODE -ne 0) { throw 'Installed GPU package inventory failed' }
$constraints = Join-Path $downloads 'preserve-gpu.txt'
$gpuArgs = @()
if ($gpuPair.Count -eq 2 -and $gpuPair[0] -match '\+cu[0-9]+$' -and $gpuPair[1] -match '\+cu[0-9]+$') {
    @("torch==$($gpuPair[0])","torchvision==$($gpuPair[1])") | Set-Content -LiteralPath $constraints -Encoding ASCII
    $gpuArgs = @('--constraint', $constraints)
    if ($gpuPair[0] -match '\+(cu[0-9]+)$') {
        $gpuArgs += @('--index', ('https://download.pytorch.org/whl/' + $Matches[1]))
    }
    Write-Host 'Preserving installed CUDA PyTorch/TorchVision.'
}
& $uv pip install --python $python --no-config --link-mode copy --system --break-system-packages @gpuArgs ('.[' + $extras + ']')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
if ($gpuArgs.Count -gt 0) {
    $currentPair = @(& $python -I -c "import importlib.metadata as m; print(m.version('torch')); print(m.version('torchvision'))")
    if ($LASTEXITCODE -ne 0 -or ($currentPair -join '|') -ne ($gpuPair -join '|')) { throw 'GPU wheel preservation check failed; rerun GPU setup' }
}
& $python -I -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw 'Local pip bootstrap failed' }
& $python -I -c "import sysconfig,pathlib; p=pathlib.Path(sysconfig.get_path('purelib')); (p/'00_streamclipper_source.pth').write_text('import sys, os; sys.path.insert(0, os.path.join(sys.prefix, os.pardir, chr(115)+chr(114)+chr(99)))\n',encoding='ascii')"
if ($LASTEXITCODE -ne 0) { throw 'Relative source registration failed' }
if (!(Test-Path (Join-Path $bin 'ffmpeg.exe')) -or !(Test-Path (Join-Path $bin 'ffprobe.exe'))) {
    $archive = Join-Path $downloads 'ffmpeg.zip'
    $urls = @(
        'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
        'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
    )
    $downloaded = $false
    foreach ($url in $urls) {
        $partial = "$archive.partial"
        try {
            Write-Host "Downloading FFmpeg from $url"
            Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $partial -ErrorAction Stop
            # Reject incomplete/non-ZIP responses before promoting the download.
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $zip = [IO.Compression.ZipFile]::OpenRead($partial)
            try {
                foreach ($name in @('ffmpeg.exe','ffprobe.exe')) {
                    if (@($zip.Entries | Where-Object { $_.Name -eq $name }).Count -ne 1) { throw "Archive missing unique $name" }
                }
            } finally { $zip.Dispose() }
            Move-Item -LiteralPath $partial -Destination $archive -Force
            $downloaded = $true
            break
        } catch {
            Write-Warning "FFmpeg download failed: $($_.Exception.Message)"
            Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue
        }
    }
    if (!$downloaded) { throw 'All FFmpeg downloads failed. Place ffmpeg.exe and ffprobe.exe in the local bin folder and rerun setup.' }
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
    # Drain the complete native output before displaying its first line.
    $versionOutput = @(& (Join-Path $bin $name) -version)
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0 -or $versionOutput.Count -eq 0) { throw "$name version check failed (exit $exitCode)" }
    Write-Host $versionOutput[0]
}
$smoke = Join-Path $downloads ('smoke-' + [Guid]::NewGuid().ToString('N') + '.wav')
try {
    & (Join-Path $bin 'ffmpeg.exe') -hide_banner -nostdin -loglevel error -f lavfi -i 'anullsrc=r=16000:cl=mono' -t 0.25 -c:a pcm_s16le $smoke
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { throw "FFmpeg audio generation failed (exit $exitCode)" }
    $probeOutput = @(& (Join-Path $bin 'ffprobe.exe') -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels -of json $smoke)
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { throw "FFprobe media check failed (exit $exitCode)" }
    $probe = ($probeOutput -join "`n") | ConvertFrom-Json
    if (@($probe.streams).Count -ne 1 -or $probe.streams[0].codec_name -ne 'pcm_s16le' -or $probe.streams[0].sample_rate -ne '16000' -or $probe.streams[0].channels -ne 1) {
        throw 'FFprobe returned unexpected audio properties'
    }
    Write-Host 'FFmpeg / FFprobe media self-test passed.'
} finally {
    Remove-Item -LiteralPath $smoke -Force -ErrorAction SilentlyContinue
}
& $python -I -c "import streamclipper, PySide6; print(streamclipper.__file__)"
if ($LASTEXITCODE -ne 0) { throw 'Local import failed' }
Write-Host 'Portable runtime ready. Existing .venv and data are retained.'
 -and $gpuPair[1] -match '\+cu[0-9]+
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $python -I -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw 'Local pip bootstrap failed' }
& $python -I -c "import sysconfig,pathlib; p=pathlib.Path(sysconfig.get_path('purelib')); (p/'00_streamclipper_source.pth').write_text('import sys, os; sys.path.insert(0, os.path.join(sys.prefix, os.pardir, chr(115)+chr(114)+chr(99)))\n',encoding='ascii')"
if ($LASTEXITCODE -ne 0) { throw 'Relative source registration failed' }
if (!(Test-Path (Join-Path $bin 'ffmpeg.exe')) -or !(Test-Path (Join-Path $bin 'ffprobe.exe'))) {
    $archive = Join-Path $downloads 'ffmpeg.zip'
    $urls = @(
        'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
        'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
    )
    $downloaded = $false
    foreach ($url in $urls) {
        $partial = "$archive.partial"
        try {
            Write-Host "Downloading FFmpeg from $url"
            Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $partial -ErrorAction Stop
            # Reject incomplete/non-ZIP responses before promoting the download.
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $zip = [IO.Compression.ZipFile]::OpenRead($partial)
            try {
                foreach ($name in @('ffmpeg.exe','ffprobe.exe')) {
                    if (@($zip.Entries | Where-Object { $_.Name -eq $name }).Count -ne 1) { throw "Archive missing unique $name" }
                }
            } finally { $zip.Dispose() }
            Move-Item -LiteralPath $partial -Destination $archive -Force
            $downloaded = $true
            break
        } catch {
            Write-Warning "FFmpeg download failed: $($_.Exception.Message)"
            Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue
        }
    }
    if (!$downloaded) { throw 'All FFmpeg downloads failed. Place ffmpeg.exe and ffprobe.exe in the local bin folder and rerun setup.' }
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
    # Drain the complete native output before displaying its first line.
    $versionOutput = @(& (Join-Path $bin $name) -version)
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0 -or $versionOutput.Count -eq 0) { throw "$name version check failed (exit $exitCode)" }
    Write-Host $versionOutput[0]
}
$smoke = Join-Path $downloads ('smoke-' + [Guid]::NewGuid().ToString('N') + '.wav')
try {
    & (Join-Path $bin 'ffmpeg.exe') -hide_banner -nostdin -loglevel error -f lavfi -i 'anullsrc=r=16000:cl=mono' -t 0.25 -c:a pcm_s16le $smoke
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { throw "FFmpeg audio generation failed (exit $exitCode)" }
    $probeOutput = @(& (Join-Path $bin 'ffprobe.exe') -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels -of json $smoke)
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { throw "FFprobe media check failed (exit $exitCode)" }
    $probe = ($probeOutput -join "`n") | ConvertFrom-Json
    if (@($probe.streams).Count -ne 1 -or $probe.streams[0].codec_name -ne 'pcm_s16le' -or $probe.streams[0].sample_rate -ne '16000' -or $probe.streams[0].channels -ne 1) {
        throw 'FFprobe returned unexpected audio properties'
    }
    Write-Host 'FFmpeg / FFprobe media self-test passed.'
} finally {
    Remove-Item -LiteralPath $smoke -Force -ErrorAction SilentlyContinue
}
& $python -I -c "import streamclipper, PySide6; print(streamclipper.__file__)"
if ($LASTEXITCODE -ne 0) { throw 'Local import failed' }
Write-Host 'Portable runtime ready. Existing .venv and data are retained.'
) {
    @("torch==$($gpuPair[0])","torchvision==$($gpuPair[1])") | Set-Content -LiteralPath $constraints -Encoding ASCII
    $gpuArgs = @('--constraint', $constraints)
    Write-Host 'Preserving installed CUDA PyTorch/TorchVision.'
}
& $uv pip install --python $python --no-config --link-mode copy --system --break-system-packages @gpuArgs ".[${extras}]"
if ($LASTEXITCODE -eq 0 -and $gpuArgs.Count -gt 0) {
    $currentPair = @(& $python -I -c "import importlib.metadata as m; print(m.version('torch')); print(m.version('torchvision'))")
    if ($LASTEXITCODE -ne 0 -or ($currentPair -join '|') -ne ($gpuPair -join '|')) { throw 'GPU wheel preservation check failed; rerun GPU setup' }
}
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $python -I -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw 'Local pip bootstrap failed' }
& $python -I -c "import sysconfig,pathlib; p=pathlib.Path(sysconfig.get_path('purelib')); (p/'00_streamclipper_source.pth').write_text('import sys, os; sys.path.insert(0, os.path.join(sys.prefix, os.pardir, chr(115)+chr(114)+chr(99)))\n',encoding='ascii')"
if ($LASTEXITCODE -ne 0) { throw 'Relative source registration failed' }
if (!(Test-Path (Join-Path $bin 'ffmpeg.exe')) -or !(Test-Path (Join-Path $bin 'ffprobe.exe'))) {
    $archive = Join-Path $downloads 'ffmpeg.zip'
    $urls = @(
        'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
        'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
    )
    $downloaded = $false
    foreach ($url in $urls) {
        $partial = "$archive.partial"
        try {
            Write-Host "Downloading FFmpeg from $url"
            Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $partial -ErrorAction Stop
            # Reject incomplete/non-ZIP responses before promoting the download.
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $zip = [IO.Compression.ZipFile]::OpenRead($partial)
            try {
                foreach ($name in @('ffmpeg.exe','ffprobe.exe')) {
                    if (@($zip.Entries | Where-Object { $_.Name -eq $name }).Count -ne 1) { throw "Archive missing unique $name" }
                }
            } finally { $zip.Dispose() }
            Move-Item -LiteralPath $partial -Destination $archive -Force
            $downloaded = $true
            break
        } catch {
            Write-Warning "FFmpeg download failed: $($_.Exception.Message)"
            Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue
        }
    }
    if (!$downloaded) { throw 'All FFmpeg downloads failed. Place ffmpeg.exe and ffprobe.exe in the local bin folder and rerun setup.' }
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
    # Drain the complete native output before displaying its first line.
    $versionOutput = @(& (Join-Path $bin $name) -version)
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0 -or $versionOutput.Count -eq 0) { throw "$name version check failed (exit $exitCode)" }
    Write-Host $versionOutput[0]
}
$smoke = Join-Path $downloads ('smoke-' + [Guid]::NewGuid().ToString('N') + '.wav')
try {
    & (Join-Path $bin 'ffmpeg.exe') -hide_banner -nostdin -loglevel error -f lavfi -i 'anullsrc=r=16000:cl=mono' -t 0.25 -c:a pcm_s16le $smoke
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { throw "FFmpeg audio generation failed (exit $exitCode)" }
    $probeOutput = @(& (Join-Path $bin 'ffprobe.exe') -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels -of json $smoke)
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { throw "FFprobe media check failed (exit $exitCode)" }
    $probe = ($probeOutput -join "`n") | ConvertFrom-Json
    if (@($probe.streams).Count -ne 1 -or $probe.streams[0].codec_name -ne 'pcm_s16le' -or $probe.streams[0].sample_rate -ne '16000' -or $probe.streams[0].channels -ne 1) {
        throw 'FFprobe returned unexpected audio properties'
    }
    Write-Host 'FFmpeg / FFprobe media self-test passed.'
} finally {
    Remove-Item -LiteralPath $smoke -Force -ErrorAction SilentlyContinue
}
& $python -I -c "import streamclipper, PySide6; print(streamclipper.__file__)"
if ($LASTEXITCODE -ne 0) { throw 'Local import failed' }
Write-Host 'Portable runtime ready. Existing .venv and data are retained.'
