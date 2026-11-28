@echo off
cd /d "%~dp0"
echo Running the receiver self-check...
echo.
set "PYEXE=py -3"
where py >nul 2>nul || set "PYEXE=python"
%PYEXE% "System Files\self_check.py"
echo.
pause
