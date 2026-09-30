#!/bin/bash
# macOS: 이 파일을 더블클릭하면 제안서를 만듭니다.
cd "$(dirname "$0")" || exit 1

pause_exit() { echo; read -n 1 -s -r -p "아무 키나 누르면 창이 닫힙니다..."; exit "${1:-0}"; }

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 가 설치되어 있지 않습니다. https://www.python.org 에서 설치한 뒤 다시 실행하세요."
  pause_exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo ".env 파일을 만들었습니다. 열어서 ANTHROPIC_API_KEY 를 입력하고 저장한 뒤 다시 실행하세요."
  open -e .env 2>/dev/null
  pause_exit 1
fi

if [ ! -d .venv ]; then
  echo "처음 실행: 필요한 패키지를 설치합니다 (1~2분)..."
  python3 -m venv .venv || pause_exit 1
  .venv/bin/pip install -q -r requirements.txt || { echo "패키지 설치에 실패했습니다."; pause_exit 1; }
fi

mkdir -p reports
if ! ls reports/*.pptx >/dev/null 2>&1; then
  echo "reports 폴더에 부서 보고서(.pptx)를 넣은 뒤 다시 실행하세요."
  open reports 2>/dev/null
  pause_exit 1
fi

OUT="제안서_$(date +%Y%m%d_%H%M).pptx"
.venv/bin/python main.py --input reports --output "$OUT"
STATUS=$?
if [ $STATUS -eq 0 ]; then open . 2>/dev/null; fi
pause_exit $STATUS
