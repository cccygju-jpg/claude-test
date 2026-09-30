@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Windows: 이 파일을 더블클릭하면 제안서를 만듭니다.

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
  echo Python 3 가 설치되어 있지 않습니다. https://www.python.org 에서 설치한 뒤 다시 실행하세요.
  echo 설치할 때 "Add python.exe to PATH" 를 체크하세요.
  pause
  exit /b 1
)

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo .env 파일을 만들었습니다. 메모장에서 ANTHROPIC_API_KEY 를 입력하고 저장한 뒤 다시 실행하세요.
  start notepad ".env"
  pause
  exit /b 1
)

if not exist ".venv" (
  echo 처음 실행: 필요한 패키지를 설치합니다 ^(1~2분^)...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo 가상환경을 만들지 못했습니다.
    pause
    exit /b 1
  )
  ".venv\Scripts\pip.exe" install -q -r requirements.txt
  if errorlevel 1 (
    echo 패키지 설치에 실패했습니다.
    pause
    exit /b 1
  )
)

if not exist "reports" mkdir reports
dir /b "reports\*.pptx" >nul 2>nul
if errorlevel 1 (
  echo reports 폴더에 부서 보고서^(.pptx^)를 넣은 뒤 다시 실행하세요.
  start "" "reports"
  pause
  exit /b 1
)

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"') do set "TS=%%i"
".venv\Scripts\python.exe" main.py --input reports --output "제안서_%TS%.pptx"
set "STATUS=%errorlevel%"
if "%STATUS%"=="0" start "" "%cd%"
pause
exit /b %STATUS%
