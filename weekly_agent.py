"""
여러 팀의 주간보고(.md)를 읽어 Claude API로 하나의 주간 경영 보고서 초안을
만드는 스크립트.

흐름: data/weekly_report_sample/ 의 팀별 주간보고 읽기 -> Claude API 호출로 종합
     -> output/ 에 결과 저장 + 콘솔에 요약 출력

기획서: 주간경영보고_취합_자동화_기획서.md
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
    "MAX_TOKENS": 8000,
}

SYSTEM_PROMPT = """\
당신은 제조회사의 여러 팀이 작성한 주간보고를 모아 대표(경영진) 보고용 주간 경영
보고서 초안을 정리하는 역할을 맡았습니다.

아래 원문은 팀별 주간보고이며, 각 문서 앞에 "### 출처 파일: 파일명"이 표시되어
있습니다. 이 원문만 근거로 삼아 다음 규칙을 반드시 지켜 정리하세요.

[반드시 지킬 규칙]
1. 원문에 없는 사실이나 수치를 만들어내지 않는다. 원문에 있는 내용만 사용한다.
2. 담당자나 기한이 원문에 분명하게 나와 있지 않으면 "확인 필요"라고 표시한다.
3. 같은 사안(이슈)이 여러 팀 보고서에 나오면 하나로 합쳐서 정리하고, 관련 팀 이름과
   출처 파일명을 함께 적는다.
4. 모든 팀의 주요 내용이 결과에서 빠지지 않도록 각 팀의 핵심 실적을 최소 한 줄 이상
   반영한다.

[출력 형식]
아래 5개 항목을 반드시 이 순서, 이 제목 그대로 마크다운 제목(##)으로 구성해서
작성한다. 항목을 추가하거나 생략하지 않는다.

## 1. 핵심 요약
(3줄로, 전체 상황을 요약)

## 2. 팀별 주요 실적
(팀마다 항목을 나누어 이번 주 한 일 중 핵심만 정리)

## 3. 여러 부서가 함께 확인할 이슈
(부서 간 공통 이슈별로 관련 팀, 출처 파일, 담당, 기한을 적는다. 담당/기한이 불분명하면
"확인 필요"라고 쓴다)

## 4. 대표가 결정해야 할 사항
(원문에서 확인되는, 경영진 판단이 필요해 보이는 사항만 나열. 없으면 "해당 없음"이라고
쓴다)

## 5. 다음 주 주요 일정
(각 팀의 다음 주 계획 중 날짜가 있는 일정 위주로 정리)
"""


def load_api_key() -> str:
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key or "여기에" in api_key:
        sys.exit("[오류] .env 파일에 ANTHROPIC_API_KEY가 설정되어 있지 않습니다.")
    return api_key


def extract_team_label(text: str, filename: str):
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = match.group(1).strip() if match else filename

    short_match = re.search(r"([가-힣]{2,10}팀)", title)
    short_label = short_match.group(1) if short_match else title
    return title, short_label


def load_weekly_reports(input_dir: Path):
    if not input_dir.is_dir():
        sys.exit(f"[오류] 입력 폴더를 찾을 수 없습니다: {input_dir}")

    files = sorted(input_dir.glob("*.md"))
    if not files:
        sys.exit(f"[오류] {input_dir} 폴더에 읽을 .md 주간보고 파일이 없습니다.")

    reports = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            sys.exit(f"[오류] 파일을 읽는 중 문제가 발생했습니다: {path.name} ({e})")
        if not text.strip():
            sys.exit(f"[오류] 파일 내용이 비어 있습니다: {path.name}")
        title, short_label = extract_team_label(text, path.name)
        reports.append({
            "filename": path.name,
            "team_label": title,
            "short_label": short_label,
            "text": text,
        })
    return reports


def build_user_prompt(reports) -> str:
    blocks = []
    for r in reports:
        blocks.append(f"### 출처 파일: {r['filename']}\n\n{r['text']}")
    return "\n\n---\n\n".join(blocks)


def call_claude(api_key: str, user_prompt: str) -> str:
    client = Anthropic(api_key=api_key, timeout=120.0)
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
            "(네트워크 상태나 API 키를 확인해 주세요): "
            f"{e}"
        )
    print("[진행] 응답을 받았습니다. 결과를 정리합니다...")
    sys.stdout.flush()

    if response.stop_reason == "max_tokens":
        sys.exit(
            "[오류] Claude 응답이 출력 길이 한도(max_tokens)에 걸려 중간에 잘렸습니다. "
            "CONFIG의 MAX_TOKENS 값을 늘리고 다시 실행해 주세요."
        )

    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        sys.exit("[오류] Claude 응답에서 텍스트 내용을 찾을 수 없습니다.")
    return "\n".join(text_blocks)


def check_missing_teams(reports, result_text: str):
    missing = [r["team_label"] for r in reports if r["short_label"] not in result_text]
    return missing


def save_result(output_dir: Path, result_text: str, reports) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"주간경영보고초안_{timestamp}.md"

    source_list = "\n".join(f"- {r['team_label']} ({r['filename']})" for r in reports)
    header = (
        f"<!-- 이 보고서 초안은 Claude API로 자동 생성되었습니다. "
        f"생성 시각: {timestamp} -->\n\n"
        f"**취합 대상 주간보고 ({len(reports)}건)**\n{source_list}\n\n---\n\n"
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

    reports = load_weekly_reports(input_dir)
    print(f"[진행] 주간보고 {len(reports)}건을 읽었습니다. Claude에 보낼 내용을 준비합니다...")
    sys.stdout.flush()
    user_prompt = build_user_prompt(reports)
    result_text = call_claude(api_key, user_prompt)

    missing_teams = check_missing_teams(reports, result_text)
    out_path = save_result(output_dir, result_text, reports)

    print(f"[완료] 읽은 주간보고 파일 수: {len(reports)}건")
    for r in reports:
        print(f"  - {r['team_label']} ({r['filename']})")
    print(f"[완료] 결과 저장 위치: {out_path}")
    if missing_teams:
        print(
            "[확인 필요] 다음 팀 이름이 결과 본문에서 그대로 발견되지 않았습니다. "
            "결과에 해당 팀 내용이 실제로 빠지지 않았는지 사람이 확인해 주세요: "
            + ", ".join(missing_teams)
        )


if __name__ == "__main__":
    main()
