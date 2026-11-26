@echo off
setlocal
cd /d "%~dp0"
call "%~dp0portable_env.bat"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap_portable.ps1"
if errorlevel 1 goto :error
echo Einrichtung abgeschlossen. Modelle bei Bedarf im GUI herunterladen.
echo Start mit run_windows.bat.
pause
exit /b 0
:error
echo Einrichtung fehlgeschlagen. Ausgabe oben pruefen.
pause
exit /b 1
