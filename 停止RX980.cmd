@echo off
cd /d "%~dp0"
if exist "%~dp0RX980.exe" (
  "%~dp0RX980.exe" --stop
  exit /b
)
node.exe "scripts\stop-local.cjs"
if errorlevel 1 pause
