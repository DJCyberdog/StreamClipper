@echo off
setlocal
cd /d "%~dp0"
call "%~dp0portable_env.bat"
if not exist "%~dp0runtime\python.exe" (
  echo Lokale Runtime fehlt. Bitte setup_windows.bat ausfuehren.
  exit /b 1
)
"%~dp0runtime\python.exe" -I -m streamclipper
exit /b %errorlevel%
