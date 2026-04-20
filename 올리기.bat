@echo off
setlocal
set /p MSG=?? ??? ??(??? ??): 

if "%MSG%"=="" (
  powershell -ExecutionPolicy Bypass -File "C:\Users\user\Desktop\2026 ??\budget_tool\sync-push.ps1"
) else (
  powershell -ExecutionPolicy Bypass -File "C:\Users\user\Desktop\2026 ??\budget_tool\sync-push.ps1" -msg "%MSG%"
)

echo.
echo ??. ?? ?? ??? ?????.
pause > nul
