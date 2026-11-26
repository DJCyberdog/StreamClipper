$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$env:PATH="$env:SystemRoot\System32;$env:SystemRoot"
$env:PYTHONHOME='Z:\nonexistent-python'
$env:PYTHONPATH='Z:\nonexistent-packages'
$env:VIRTUAL_ENV='Z:\nonexistent-venv'
& (Join-Path $PSScriptRoot 'bootstrap_portable.ps1') -Minimal
$target=Join-Path ([IO.Path]::GetTempPath()) ('StreamClipper moved '+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $target | Out-Null
foreach ($name in @('runtime','bin','src','portable_env.bat','run_windows.bat')) {
    Move-Item -LiteralPath (Join-Path $root $name) -Destination $target
}
try {
    $env:STREAMCLIPPER_HOME=$target
    $env:STREAMCLIPPER_FFMPEG_DIR=Join-Path $target 'bin'
    $env:QT_QPA_PLATFORM='offscreen'
    & (Join-Path $target 'runtime\python.exe') -I -c "import sys,pathlib,streamclipper; from PySide6.QtWidgets import QApplication; from streamclipper.media import tool_path; import subprocess; root=pathlib.Path(sys.prefix).resolve().parent; expected=pathlib.Path(__import__('os').environ['STREAMCLIPPER_HOME']).resolve(); assert root==expected, (root,expected); source=pathlib.Path(streamclipper.__file__).resolve(); print('source:',source); assert source.is_relative_to(root/'src'), (source,root); app=QApplication([]); ffmpeg=pathlib.Path(tool_path('ffmpeg')).resolve(); print('ffmpeg:',ffmpeg); assert ffmpeg.is_relative_to(root/'bin'), (ffmpeg,root); subprocess.run([tool_path('ffprobe'),'-version'],check=True)"
    if ($LASTEXITCODE -ne 0) { throw 'Relocation smoke failed' }
} finally {
    foreach ($name in @('runtime','bin','src','portable_env.bat','run_windows.bat')) {
        Move-Item -LiteralPath (Join-Path $target $name) -Destination $root
    }
    Remove-Item -LiteralPath $target -Recurse -Force
}
