@echo off
setlocal

echo.
echo ==================================================
echo Starting Project Setup and Synchronization
echo ==================================================
echo.

:: --- Change to the script's directory ---
echo Changing directory to: %~dp0
cd /d %~dp0
if errorlevel 1 (
    echo ERROR: Failed to change directory.
    goto :error
)

:: --- Check if Python is available ---
echo Checking if Python is available...
where python > nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in the PATH.
    goto :error
)

:: --- Dependency Installation ---
echo.
echo Installing dependencies using setup.py...
python setup.py
if errorlevel 1 (
    echo ERROR: Failed to install dependencies. Check setup.py.
    goto :error
)

:: --- GitHub Sync ---
echo.
echo Starting GitHub Sync script...
python github_sync.py
if errorlevel 1 (
    echo ERROR: GitHub Sync script failed. Check github_sync.py.
    goto :error
)

echo.
echo ==================================================
echo Project Setup and Synchronization Complete
echo ==================================================
echo.
pause
goto :eof

:error
echo.
echo ==================================================
echo ERROR: An error occurred during the process.
echo ==================================================
echo.
pause
exit /b 1
