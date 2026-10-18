@echo off
cd /d "%~dp0"
node.exe "scripts\stop-local.cjs"
if errorlevel 1 pause
