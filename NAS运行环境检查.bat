@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist logs mkdir logs
"inference\python\python.exe" -u "inference\check_runtime.py" > "logs\nas-self-check.log" 2>&1
set "NAS_CHECK_CODE=%ERRORLEVEL%"
type "logs\nas-self-check.log"
echo.
echo Logs: logs\nas-self-check.log and logs\nas-self-check.json
pause
exit /b %NAS_CHECK_CODE%
