@echo off
setlocal
cd /d "%~dp0"
call "%~dp0portable_env.bat"
where py >nul 2>&1
if errorlevel 1 (
  echo Python Launcher nicht gefunden. Python 3.12 installieren.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 (
    echo Python-Umgebung konnte nicht eingerichtet werden.
    pause
    exit /b 1
  )
)
echo Installiere StreamClipper und KI-Abhaengigkeiten nach %STREAMCLIPPER_HOME% ...
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m pip install -e ".[gui,speech,vision,models,twitch]"
if errorlevel 1 goto :error
echo.
echo Lade lokale Sprach- und Bildmodelle ins Projektverzeichnis ...
.venv\Scripts\python.exe scripts\setup_local_models.py --which both
if errorlevel 1 goto :error
echo.
echo Einrichtung abgeschlossen. Ab jetzt run_windows.bat verwenden.
pause
exit /b 0
:error
echo.
echo Einrichtung fehlgeschlagen. Ausgabe oben pruefen.
pause
exit /b 1
