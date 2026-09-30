"""
여러 부서의 보고서에서 공통 문제를 찾아 해결 방안 제안서를 만드는 스크립트.

흐름: data/weekly_report_sample/ 의 부서별 보고서 읽기 -> Claude API 호출로 공통 문제
     분석 + 해결 방안 제안 -> output/ 에 제안서 저장 + 콘솔에 요약 출력

기획서: 공통문제_해결제안_자동화_기획서.md
"""
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic, AnthropicError

CONFIG = {
    "INPUT_DIR": "data/weekly_report_sample",
    "OUTPUT_DIR": "output",
    "MODEL": "claude-sonnet-5-5",
    "MAX_TOKENS": 16000,
}

SECTION_TITLES = [
    "## 1. 현재 상황",
    "## 2. 확인된 문제",
    "## 3. 해결 방안 제안",
    "## 4. 기대 효과",
    "## 5. 필요한 것과 일정",
]

SYSTEM_PROMPT = """\
당신은 여러 부서가 작성한 보고서를 읽고, 부서 간 공통 문제를 찾아 경영진에게 해결
방안을 제안하는 제안서 초안을 작성하는 역할을 맡았습니다.

아래 원문은 부서별 보고서이며, 각 문서 앞에 "### 출처 파일: 파일명"이 표시되어
있습니다. 원문을 근거로 다음 규칙을 반드시 지켜 작성하세요.

[반드시 지킬 규칙]
1. 문제의 근거가 되는 보고서 이름(출처 파일명과 부서명)과 그 보고서의 해당 내용을
   문제마다 함께 적는다. 근거 없이 문제를 단정하지 않는다.
2. 원문에 없는 해결 방안은 "[제안]"이라고 분명히 표시한다. 원문에 적힌 대응은 시점에
   맞게 구분해 표시한다.
   - "[원문 계획]": 원문의 "다음 주 계획" 등 앞으로 할 일로 적힌 것
   - "[원문 진행/완료]": 원문에서 이미 했거나 진행 중인 것으로 적힌 것(예: "요청",
     "확정", "협의 중", "체결"). 이런 내용을 앞으로 할 계획처럼 쓰지 않는다.
   구분이 애매하면 원문 표현("요청", "협의 중" 등)을 그대로 쓴다.
3. 원문에 없는 효과 수치, 예산, 담당자, 확정 일정은 절대 만들지 않는다.
   기대 효과는 방향(정성적 서술)으로만 쓰고, 이것도 "[제안에 따른 예상]"으로 표시한다.
4. 근거가 부족하거나 원문만으로 판단할 수 없는 내용은 "확인 필요"라고 표시한다.
   담당자·예산·일정이 원문에 없으면 임의로 채우지 말고 "확인 필요"라고 쓴다.
5. 한 부서에만 나오는 사안은 공통 문제로 다루지 않는다(필요하면 "단일 부서 사안"으로
   짧게 언급). 두 개 이상 부서 보고서에서 확인되는 것만 공통 문제로 삼는다.

[출력 형식]
아래 5개 항목을 반드시 이 순서, 이 제목 그대로 마크다운 제목(##)으로 구성한다.
항목을 추가하거나 생략하지 않는다.

## 1. 현재 상황
(각 부서 보고서에서 확인되는 현재 상황을 부서별로 간단히 정리. 부서명·출처 파일 표기)

## 2. 확인된 문제
(문제별로: 문제 설명 / 관련 부서 / 근거 보고서 이름과 해당 원문 내용 / 확인 필요 사항)

## 3. 해결 방안 제안
(문제별로 해결 방안을 [제안] 또는 [원문 계획]으로 표시하여 작성)

## 4. 기대 효과
(수치 없이 정성적으로만. 각 항목에 [제안에 따른 예상] 표시)

## 5. 필요한 것과 일정
(필요한 자원·협조 부서·결정 사항과 일정. 원문에 없는 담당자·예산·확정 일정은
"확인 필요"로 쓴다. 원문에 날짜가 있는 일정만 근거와 함께 적는다)
"""


def load_api_key() -> str:
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key or "여기에" in api_key:
        sys.exit("[오류] .env 파일에 ANTHROPIC_API_KEY가 설정되어 있지 않습니다.")
    return api_key


def load_reports(input_dir: Path):
    if not input_dir.is_dir():
        sys.exit(f"[오류] 입력 폴더를 찾을 수 없습니다: {input_dir}")

    files = sorted(input_dir.glob("*.md"))
    if len(files) < 2:
        sys.exit(f"[오류] 공통 문제를 찾으려면 보고서가 2개 이상 필요합니다: {input_dir}")

    reports = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            sys.exit(f"[오류] 파일을 읽는 중 문제가 발생했습니다: {path.name} ({e})")
        if not text.strip():
            sys.exit(f"[오류] 파일 내용이 비어 있습니다: {path.name}")
        match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = match.group(1).strip() if match else path.name
        reports.append({"filename": path.name, "title": title, "text": text})
    return reports


def build_user_prompt(reports) -> str:
    blocks = [f"### 출처 파일: {r['filename']}\n\n{r['text']}" for r in reports]
    return "\n\n---\n\n".join(blocks)


def call_claude(api_key: str, user_prompt: str) -> str:
    client = Anthropic(api_key=api_key, timeout=180.0)
    print("[진행] Claude API에 요청을 보냈습니다. 답변 생성에 수십 초 정도 걸릴 수 있습니다...")
    sys.stdout.flush()
    try:
        response = client.messages.create(
            model=CONFIG["MODEL"],
            max_tokens=CONFIG["MAX_TOKENS"],
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except AnthropicError as e:
        sys.exit(
            "[오류] Claude API 호출 중 문제가 발생했습니다 "
            f"(네트워크 상태나 API 키를 확인해 주세요): {e}"
        )

    if response.stop_reason == "max_tokens":
        sys.exit(
            "[오류] Claude 응답이 출력 길이 한도(max_tokens)에 걸려 중간에 잘렸습니다. "
            "CONFIG의 MAX_TOKENS 값을 늘리고 다시 실행해 주세요."
        )

    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        sys.exit("[오류] Claude 응답에서 텍스트 내용을 찾을 수 없습니다.")
    return "\n".join(text_blocks)


def check_structure(result_text: str):
    """5개 섹션 제목이 모두, 순서대로 있는지 확인. 문제 목록을 반환."""
    problems = []
    last_pos = -1
    for title in SECTION_TITLES:
        pos = result_text.find(title)
        if pos < 0:
            problems.append(f"섹션 누락: {title}")
        elif pos < last_pos:
            problems.append(f"섹션 순서 어긋남: {title}")
        else:
            last_pos = pos
    if "[제안]" not in result_text:
        problems.append("'[제안]' 표시가 하나도 없음")
    return problems


def save_result(output_dir: Path, result_text: str, reports) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"공통문제_해결제안서_{timestamp}.md"

    source_list = "\n".join(f"- {r['title']} ({r['filename']})" for r in reports)
    header = (
        f"<!-- 이 제안서 초안은 Claude API로 자동 생성되었습니다. "
        f"생성 시각: {timestamp} -->\n\n"
        f"**분석 대상 보고서 ({len(reports)}건)**\n{source_list}\n\n"
        "> 이 문서의 [제안] 항목은 원문에 없는 새 제안이며, 수치·예산·담당자·확정 일정은 "
        "원문에 없으면 \"확인 필요\"로 남겨 두었습니다. 사람이 검토한 뒤 사용하세요.\n\n---\n\n"
    )

    try:
        out_path.write_text(header + result_text, encoding="utf-8")
    except OSError as e:
        sys.exit(f"[오류] 결과 파일을 저장하는 중 문제가 발생했습니다: {e}")
    return out_path


def main():
    api_key = load_api_key()

    base_dir = Path(__file__).resolve().parent
    input_dir = base_dir / CONFIG["INPUT_DIR"]
    output_dir = base_dir / CONFIG["OUTPUT_DIR"]

    reports = load_reports(input_dir)
    print(f"[진행] 보고서 {len(reports)}건을 읽었습니다.")
    sys.stdout.flush()

    result_text = call_claude(api_key, build_user_prompt(reports))
    problems = check_structure(result_text)
    out_path = save_result(output_dir, result_text, reports)

    print(f"[완료] 읽은 보고서: {len(reports)}건")
    for r in reports:
        print(f"  - {r['title']} ({r['filename']})")
    print(f"[완료] 결과 저장 위치: {out_path}")
    if problems:
        print("[확인 필요] 결과 형식에 다음 문제가 있습니다. 사람이 확인해 주세요:")
        for p in problems:
            print(f"  - {p}")


if __name__ == "__main__":
    main()
