@echo off
title SQLite Database Viewer
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" ".venv\Scripts\python.exe" -c "import sys" >nul 2>nul
if errorlevel 1 call setup.bat nopause
if not exist ".venv\Scripts\python.exe" call setup.bat nopause
if not exist ".venv\Scripts\python.exe" exit /b 1
echo ===================================================
echo  Starting SQLite Database Viewer (app.db)
echo ===================================================
".venv\Scripts\python.exe" view_database.py
pause
