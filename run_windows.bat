@echo off
REM ===========================================================================
REM  MintDo - run from source on Windows (needs Python, no build step).
REM  For a standalone .exe instead, use build_windows.bat.
REM
REM  Double-click this file. It installs PySide6 on first run if missing,
REM  then starts MintDo.
REM ===========================================================================
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python was not found. Please install Python 3.10+ from python.org
        echo and tick "Add python.exe to PATH" during setup.
        pause
        exit /b 1
    )
    set "PY=python"
) else (
    set "PY=py"
)

%PY% -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo Installing PySide6 ^(one time^)...
    %PY% -m pip install --user -r requirements.txt
)

%PY% -m mintdo.qt_app %*
if errorlevel 1 pause
endlocal


