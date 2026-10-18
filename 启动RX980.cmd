@echo off
cd /d "%~dp0"
node.exe "scripts\start-local.cjs"
if errorlevel 1 pause
