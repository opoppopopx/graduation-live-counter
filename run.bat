@echo off
chcp 65001 > nul
title Graduation Live Ceremony AI Counter
color 0B
cd /d "%~dp0"

set "PY_CMD=python"
if exist "C:\Program Files\Python314\python.exe" (
    set "PY_CMD=C:\Program Files\Python314\python.exe"
)

echo ========================================================
echo   Graduation Live Ceremony AI Counter is Starting...
echo   Open in Browser: http://localhost:8088/admin
echo ========================================================
"%PY_CMD%" -m uvicorn main:app --host 0.0.0.0 --port 8088
pause
