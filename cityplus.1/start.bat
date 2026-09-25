@echo off
cd /d "%~dp0"
echo ========================================
echo        CityPulse Jaipur v3
 echo ========================================
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Installation failed. Check that Python is installed.
  pause
  exit /b 1
)
echo.
echo Starting CityPulse...
python backend\main.py
pause
