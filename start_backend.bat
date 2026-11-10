@echo off
title Fisch Macro Backend
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" ".venv\Scripts\python.exe" -c "import sys" >nul 2>nul
if errorlevel 1 call setup.bat nopause
if not exist ".venv\Scripts\python.exe" call setup.bat nopause
if not exist ".venv\Scripts\python.exe" exit /b 1
echo ===================================================
echo  Starting Fisch Macro Backend - API docs: http://127.0.0.1:8000/docs
echo ===================================================
".venv\Scripts\python.exe" main.py
pause
