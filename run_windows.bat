@echo off
setlocal
cd /d "%~dp0"
call "%~dp0portable_env.bat"
where py >nul 2>&1
if errorlevel 1 (
  echo Python Launcher "py" fehlt. Bitte Python 3.12 (64-bit) installieren.
  echo https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Erstelle lokale Python-Umgebung ...
  py -3.12 -m venv .venv
  if errorlevel 1 (
    echo Python 3.12 fehlt oder konnte keine venv erzeugen.
    pause
    exit /b 1
  )
  echo Installiere GUI-Abhaengigkeiten ...
  .venv\Scripts\python.exe -m pip install -e ".[gui]"
  if errorlevel 1 (
    echo Installation fehlgeschlagen.
    pause
    exit /b 1
  )
)
.venv\Scripts\python.exe -m streamclipper
if errorlevel 1 (
  echo StreamClipper wurde mit einem Fehler beendet.
  pause
)
