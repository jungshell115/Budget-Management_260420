@echo off
setlocal
set /p MSG=Commit message (Enter for auto): 
if "%MSG%"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-push.ps1"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-push.ps1" -msg "%MSG%"
)
echo.
pause
