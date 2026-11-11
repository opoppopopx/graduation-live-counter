@echo off
chcp 65001 > nul
title Graduation Live Ceremony AI Counter
color 0B
cd /d "%~dp0"

set "PY_CMD=python"
if exist "C:\Program Files\Python314\python.exe" (
    set "PY_CMD=C:\Program Files\Python314\python.exe"
)

echo กำลังเริ่มระบบ... กรุณารอสักครู่ (ระบบจะเปิดหน้าต่างเบราว์เซอร์ให้เองโดยอัตโนมัติ)
"%PY_CMD%" -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
