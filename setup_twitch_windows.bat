@echo off
setlocal
cd /d "%~dp0"
call "%~dp0portable_env.bat"
if not exist "%~dp0runtime\python.exe" (
  echo StreamClipper-Umgebung fehlt. Bitte zuerst setup_windows.bat ausfuehren.
  pause
  exit /b 1
)
echo Installiere lokalen Twitch-VOD-Import in die vorhandene runtime ...
"%~dp0runtime\python.exe" -m pip install ".[twitch]"
if errorlevel 1 (
  echo Twitch-Import konnte nicht eingerichtet werden.
  pause
  exit /b 1
)
echo.
echo Twitch-Import bereit. StreamClipper mit run_windows.bat starten.
pause
exit /b 0
