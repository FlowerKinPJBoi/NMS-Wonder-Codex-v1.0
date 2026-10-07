@echo off
setlocal
cd /d "%~dp0"
echo Wonder Codex Editor 0.4.0 - Standalone Windows Setup
echo Extract the complete ZIP before running this file.
echo First setup downloads and verifies the matching editor engine.
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Wonder-Codex.ps1"
if errorlevel 1 (
 echo.
 echo Keep this message when reporting a setup problem.
 pause
 exit /b 1
)
echo.
echo Setup finished. Use the Wonder Codex Editor 0.4.0 Desktop shortcut next time.
pause
endlocal
