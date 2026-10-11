@echo off
rem Double-click to start BuildCO2 Pro
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-BuildCO2Pro.ps1"
if errorlevel 1 pause
