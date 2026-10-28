@echo off
setlocal
cd /d "%~dp0"
if exist ".venv-drl\Scripts\python.exe" (
  ".venv-drl\Scripts\python.exe" scripts\open_uav_dashboard.py
) else (
  python scripts\open_uav_dashboard.py
)
if errorlevel 1 pause
