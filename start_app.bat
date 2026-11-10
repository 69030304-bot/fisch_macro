@echo off
title Fisch Macro App
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" ".venv\Scripts\python.exe" -c "import sys" >nul 2>nul
if errorlevel 1 call setup.bat nopause
if not exist ".venv\Scripts\python.exe" call setup.bat nopause
if not exist ".venv\Scripts\python.exe" exit /b 1
echo ===================================================
echo  Starting Fisch Macro Desktop App
echo ===================================================
".venv\Scripts\python.exe" fisch_macro.py
pause
