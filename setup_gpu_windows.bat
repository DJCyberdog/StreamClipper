@echo off
setlocal
cd /d "%~dp0"
call "%~dp0portable_env.bat"
if not exist ".venv\Scripts\python.exe" (
  echo StreamClipper-Umgebung fehlt. Bitte zuerst setup_windows.bat ausfuehren.
  pause
  exit /b 1
)
where nvidia-smi >nul 2>&1
if errorlevel 1 (
  echo HINWEIS: nvidia-smi nicht gefunden. Bitte NVIDIA-Treiber pruefen.
)
echo.
echo Installiere NVIDIA CUDA-12/cuBLAS und cuDNN-9-Bibliotheken lokal in .venv.
echo Groesse: mehr als 1 GB. Keine Installation in Systemordner.
echo.
.venv\Scripts\python.exe -m pip install -r requirements-gpu-windows.txt
if errorlevel 1 goto :failure
.venv\Scripts\python.exe scripts\check_gpu_runtime.py
if errorlevel 1 goto :failure
echo.
echo NVIDIA-Whisper-Laufzeittest abgeschlossen. Start mit run_windows.bat.
pause
exit /b 0
:failure
echo.
echo GPU-Einrichtung nicht erfolgreich. Fehler oben lesen.
echo CPU-Fallback bleibt moeglich. Installation blieb in diesem Ordner.
pause
exit /b 1
