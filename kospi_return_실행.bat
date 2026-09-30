@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

set PY_EXE=C:\Users\KSA\AppData\Local\Programs\Python\Python312\python.exe

echo ============================================
echo  kospi_return.py starting
echo  folder: %CD%
echo ============================================
echo.

if not exist "%PY_EXE%" (
    echo [ERROR] python.exe not found at:
    echo   %PY_EXE%
    echo Please check the path and edit this .bat file.
    echo.
    pause
    exit /b 1
)

if not exist "kospi_return.py" (
    echo [ERROR] kospi_return.py not found in this folder:
    echo   %CD%
    echo.
    pause
    exit /b 1
)

"%PY_EXE%" kospi_return.py
set EXITCODE=%ERRORLEVEL%

echo.
echo ============================================
echo  finished. exit code: %EXITCODE%
echo ============================================
echo.
pause
endlocal
