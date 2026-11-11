@echo off
chcp 65001 > nul
title ระบบนับจำนวนบัณฑิตพิธีรับปริญญาบัตร (Graduation Live Counter)
color 0B
cd /d "%~dp0"

echo ===================================================================
echo     🎓 ระบบนับจำนวนบัณฑิตพิธีรับปริญญาบัตรอัตโนมัติ (Live AI Counter)
echo ===================================================================
echo.
echo [*] กำลังเริ่มเปิดเซิร์ฟเวอร์... กรุณารอสักครู่ (ระบบจะเปิดหน้าเว็บให้อัตโนมัติ)
echo [*] กรุณาอย่าปิดหน้าต่างสีดำนี้ระหว่างใช้งาน
echo.

set "PY_CMD=python"
if exist "C:\Program Files\Python314\python.exe" (
    set "PY_CMD=C:\Program Files\Python314\python.exe"
)

"%PY_CMD%" -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
