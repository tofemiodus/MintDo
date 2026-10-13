@echo off
REM ===========================================================================
REM  MintDo - one-click Windows build.  Produces  dist\MintDo.exe  (one file).
REM
REM  Double-click this file. It will:
REM    1. check Python is installed
REM    2. install the app dependency (PySide6) + PyInstaller
REM    3. build the single-file exe at  dist\MintDo.exe
REM
REM  You only need Python 3.10+ installed and ticked "Add to PATH".
REM ===========================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo === MintDo Windows build ===
echo.

where py >nul 2>nul
if errorlevel 1 (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Python was not found.
        echo         Install Python 3.10+ from https://www.python.org/downloads/
        echo         and tick "Add python.exe to PATH" during setup, then retry.
        echo.
        pause
        exit /b 1
    )
    set "PY=python"
) else (
    set "PY=py"
)

echo [1/3] Installing build dependencies ^(first run downloads PySide6^)...
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo [ERROR] Could not install dependencies. Check your internet connection.
    pause
    exit /b 1
)

echo.
echo [2/3] Building the single-file exe ^(this can take a minute^)...
%PY% -m PyInstaller --noconfirm --clean mintdo.spec
if errorlevel 1 (
    echo [ERROR] Build failed. Scroll up to see why.
    pause
    exit /b 1
)

echo.
echo [3/3] Done!
if exist "dist\MintDo.exe" (
    echo.
    echo  Your app is here:  %CD%\dist\MintDo.exe
    echo  Copy that ONE file anywhere and double-click it - no Python needed.
    echo.
    explorer /select,"%CD%\dist\MintDo.exe"
) else (
    echo [ERROR] Build finished but dist\MintDo.exe was not found.
)
echo.
pause
endlocal
