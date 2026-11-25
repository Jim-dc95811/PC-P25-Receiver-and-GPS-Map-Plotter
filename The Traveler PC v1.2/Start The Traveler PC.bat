@echo off
cd /d "%~dp0"
set "PYEXE=py -3"
where py >nul 2>nul || set "PYEXE=python"
rem First run only: install the three helpers (this is the one time a window shows).
%PYEXE% -c "import numpy, scipy, sounddevice" 2>nul || (echo Setting up The Traveler PC ^(one-time install^) ... && %PYEXE% -m pip install numpy scipy sounddevice)
if not exist "%~dp0Maps" mkdir "%~dp0Maps"
rem Launch the control window with pythonw so NO black command windows appear.
set "PYWEXE=pythonw"
where pythonw >nul 2>nul || set "PYWEXE=%PYEXE%"
start "" %PYWEXE% "System Files\traveler_launch.pyw"
exit /b
