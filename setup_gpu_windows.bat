@echo off
setlocal
cd /d "%~dp0"
call "%~dp0portable_env.bat"
if not exist "%~dp0runtime\python.exe" (
  echo StreamClipper-Umgebung fehlt. Bitte zuerst setup_windows.bat ausfuehren.
  pause
  exit /b 1
)
"%~dp0runtime\python.exe" "%~dp0scripts\setup_gpu_runtime.py" %*
set "SC_GPU_STATUS=%ERRORLEVEL%"
if "%SC_GPU_STATUS%"=="3" goto :pending
if not "%SC_GPU_STATUS%"=="0" goto :failure
echo GPU-Einrichtung fuer beide Backends abgeschlossen.
goto :finish
:pending
echo Whisper-Test ausstehend. Modell herunterladen und GPU-Setup erneut starten.
goto :finish
:failure
echo GPU-Einrichtung nicht vollstaendig verifiziert. Ausgabe oben pruefen.
:finish
pause
exit /b %SC_GPU_STATUS%
