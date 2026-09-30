"""
코스피 일/주/년 등락률 조회 스크립트 (일반 버전 - Claude API 미사용).

흐름: data/kospi_history.txt 읽기 -> 네이버 금융 실시간 지수 API에서 오늘
     코스피 지수를 자동으로 가져옴(장 마감 여부도 함께 확인) -> 사람이
     확인(맞음/직접 입력) -> 최근 20거래일 전일대비 + 1~4주 전 + 1~4년 전
     기준일(휴장이면 직전 거래일)의 종가와 비교해 등락률 계산 -> 화면에 출력
     -> (선택) 확인된 오늘 지수를 data/kospi_history.txt에도 반영

기획서: 코스피_등락률_조회_자동화_기획서.md
주의: 처음에는 Claude API 웹 검색으로, 그다음에는 사람이 매번 직접 입력하는
     방식으로 오늘 지수를 구했다. "인터넷에서 그냥 긁어오면 안 되냐"는 요청으로
     Claude API 없이, 파이썬 표준 라이브러리(urllib)만으로 네이버 금융의
     공개 실시간 지수 API를 호출해 자동으로 가져오도록 다시 바꿨다. 이 API는
     marketStatus 값으로 장 마감 여부를 알려주므로, AI 없이도 "장중(미확정)"
     인지 "확정 종가"인지 판단할 수 있다.
"""
import bisect
import csv
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

CONFIG = {
    "HISTORY_FILE": "data/kospi_history.txt",
    "YEARS_BACK": [1, 2, 3, 4],
    "WEEKS_BACK": [1, 2, 3, 4],
    "DAILY_DAYS": 20,
    "UPDATE_HISTORY_FILE": True,
    "FETCH_TIMEOUT_SECONDS": 10,
}

# 네이버 금융 공개 실시간 지수 API. 로그인/API 키 불필요.
NAVER_KOSPI_URL = "https://polling.finance.naver.com/api/realtime/domestic/index/KOSPI"

# 조회 시점이 장중이면(marketStatus != "CLOSE") 확정 종가와 구분하기 위해
# 히스토리 파일에 이 표시를 남긴다. 실제 확정 종가를 알게 되면(장 마감 후
# 다시 실행하면 자동으로, 또는 사람이 직접) 이 표시를 고쳐야 한다.
UNCONFIRMED_NOTE = "장중(미확정)"
CONFIRMED_AUTO_NOTE = "확정(자동조회)"
CONFIRMED_MANUAL_NOTE = "확정(직접입력)"


def load_history(path: Path) -> list[tuple[date, float]]:
    if not path.exists():
        sys.exit(f"[오류] 코스피 데이터 파일을 찾을 수 없습니다: {path}")

    rows = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            sys.exit(f"[오류] 데이터 파일이 비어 있습니다: {path}")
        for line_no, row in enumerate(reader, start=2):
            if len(row) < 2:
                continue
            date_raw, close_raw = row[0], row[1]
            date_str = re.sub(r"\s+", "", date_raw)
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                sys.exit(f"[오류] 날짜 형식을 읽을 수 없습니다 ({line_no}행): {date_raw}")
            close_str = close_raw.replace(",", "").strip()
            try:
                close = float(close_str)
            except ValueError:
                sys.exit(f"[오류] 종가를 숫자로 읽을 수 없습니다 ({line_no}행): {close_raw}")
            rows.append((d, close))

    if not rows:
        sys.exit(f"[오류] 읽은 데이터가 없습니다: {path}")
    rows.sort(key=lambda x: x[0])
    return rows


def save_today_to_history(path: Path, today: date, value: float, note: str) -> str:
    """확인된 오늘 지수를 히스토리 파일에 반영한다.

    같은 날짜 행이 이미 있으면(예: 장중에 한 번 조회하고 마감 후 다시 실행한
    경우) 종가와 표시를 교체하고, 없으면 맨 위(최신 날짜 순)에 새 행을
    추가한다. 시가/고가/저가/거래량은 알 수 없으므로 비워둔다.
    """
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        sys.exit(f"[오류] 데이터 파일이 비어 있습니다: {path}")
    header, data_rows = rows[0], rows[1:]

    today_str = today.isoformat()
    value_str = f"{value:,.2f}"

    updated = False
    for row in data_rows:
        if len(row) < 1:
            continue
        row_date = re.sub(r"\s+", "", row[0])
        if row_date == today_str:
            row[0] = today_str
            while len(row) < 7:
                row.append("")
            row[1] = value_str
            row[6] = note
            updated = True
            break

    if not updated:
        data_rows.insert(0, [today_str, value_str, "", "", "", "", note])

    try:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(header)
            writer.writerows(data_rows)
    except OSError as e:
        sys.exit(f"[오류] 히스토리 파일을 저장하는 중 문제가 발생했습니다: {e}")

    return "교체" if updated else "추가"


def build_daily_change_lines(series: list[tuple[date, float]], n_days: int) -> list[str]:
    """series(날짜 오름차순, 오늘 값 포함)의 마지막 n_days 거래일에 대해 전일대비
    등락률을 한 줄씩 만든다(최신 날짜가 위로 오도록 반환). 전일 종가를 알아야
    하므로 내부적으로 n_days + 1개를 사용한다."""
    n_days = min(n_days, len(series) - 1)
    if n_days <= 0:
        return []
    recent = series[-(n_days + 1):]

    lines = []
    for i in range(1, len(recent)):
        prev_date, prev_close = recent[i - 1]
        cur_date, cur_close = recent[i]
        pct = (cur_close - prev_close) / prev_close * 100
        direction = "상승" if pct > 0 else ("하락" if pct < 0 else "보합")
        lines.append(
            f"{cur_date.isoformat()} : {cur_close:,.2f} (전일 {prev_date.isoformat()} 대비 "
            f"{abs(pct):.2f}% {direction})"
        )
    lines.reverse()
    return lines


def shift_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:
        # 2/29 기준일이 대상 연도에 없는 경우(윤년 아님) -> 2/28로 처리
        return d.replace(month=2, day=28, year=d.year - years)


def build_comparison_line(
    label: str, dates: list[date], closes: list[float],
    today_value: float, target_date: date,
) -> str:
    """target_date(휴장이면 직전 거래일)의 종가와 오늘 지수를 비교해 한 줄로 만든다."""
    idx = bisect.bisect_right(dates, target_date)
    if idx == 0:
        sys.exit(
            f"[오류] {label} 기준일({target_date}) 이전의 데이터를 찾을 수 없습니다. "
            f"{CONFIG['HISTORY_FILE']}의 데이터 범위를 확인해 주세요."
        )
    base_date, base_close = dates[idx - 1], closes[idx - 1]
    pct = (today_value - base_close) / base_close * 100
    direction = "상승" if pct > 0 else ("하락" if pct < 0 else "보합")
    return (
        f"{label} (기준일 {base_date.isoformat()}, 종가 {base_close:,.2f}) : "
        f"{abs(pct):.2f}% {direction}"
    )


def fetch_today_index_from_web():
    """네이버 금융 실시간 지수 API에서 코스피 현재가를 가져온다.

    반환: (지수 값, 기준 시각 문자열, 장 마감 여부) — 가져오지 못하면
    (None, None, None).
    """
    req = urllib.request.Request(NAVER_KOSPI_URL, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=CONFIG["FETCH_TIMEOUT_SECONDS"]) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        item = payload["datas"][0]
        value = float(item["closePriceRaw"])
        traded_at = item["localTradedAt"]
        is_closed = item["marketStatus"] == "CLOSE"
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError, json.JSONDecodeError) as e:
        print(f"[확인 필요] 네이버 금융에서 코스피 지수를 가져오지 못했습니다: {e}")
        return None, None, None
    return value, traded_at, is_closed


def confirm_today_index(fetched_value, traded_at, is_closed) -> tuple[float, str, str]:
    """자동으로 가져온 값을 사람이 확인한다. 반환: (지수 값, 표시용 출처, 히스토리 저장용 note)."""
    if fetched_value is not None:
        status_label = "확정 종가" if is_closed else "장중 값(진행 중)"
        print(
            f"[확인] 네이버 금융에서 가져온 코스피 지수: {fetched_value:,.2f} "
            f"({status_label}, 기준시각 {traded_at})"
        )
        answer = input("이 값이 맞으면 Enter, 다르면 실제 값을 입력하세요: ").strip()
        if answer == "":
            note = CONFIRMED_AUTO_NOTE if is_closed else UNCONFIRMED_NOTE
            return fetched_value, "네이버 금융(실시간)", note
    else:
        print("[확인 필요] 자동으로 가져오지 못했습니다. 오늘 코스피 지수를 직접 입력해 주세요.")
        answer = input("오늘 코스피 지수를 입력하세요: ").strip()

    manual_input = answer.replace(",", "")
    try:
        value = float(manual_input)
    except ValueError:
        sys.exit(f"[오류] 입력한 지수 값을 숫자로 읽을 수 없습니다: {manual_input}")
    return value, "직접 입력", CONFIRMED_MANUAL_NOTE


def main():
    base_dir = Path(__file__).resolve().parent
    history_path = base_dir / CONFIG["HISTORY_FILE"]
    today = date.today()

    history = load_history(history_path)
    dates = [d for d, _ in history]
    closes = [c for _, c in history]

    fetched_value, traded_at, is_closed = fetch_today_index_from_web()
    today_value, today_source, note = confirm_today_index(fetched_value, traded_at, is_closed)

    week_lines = [
        build_comparison_line(
            f"{weeks}주 전", dates, closes, today_value,
            today - timedelta(weeks=weeks),
        )
        for weeks in CONFIG["WEEKS_BACK"]
    ]
    year_lines = [
        build_comparison_line(
            f"{years}년 전", dates, closes, today_value, shift_years(today, years),
        )
        for years in CONFIG["YEARS_BACK"]
    ]

    # 오늘 값을 히스토리 뒤에 붙여서 "전일대비" 계산의 기준(가장 최신 값)으로 쓴다.
    # 히스토리에 이미 오늘 날짜 행(장중 미확정 등)이 있으면 오늘 값으로 대체한다.
    daily_series = [(d, c) for d, c in history if d != today]
    daily_series.append((today, today_value))
    daily_lines = build_daily_change_lines(daily_series, CONFIG["DAILY_DAYS"])

    print()
    print(f"오늘 코스피: {today_value:,.2f} (출처: {today_source})")
    print()
    print(f"[초단기: 최근 {CONFIG['DAILY_DAYS']}일 일별 등락률(전일대비)]")
    for line in daily_lines:
        print(line)
    print()
    print("[단기: 최근 1~4주 대비]")
    for line in week_lines:
        print(line)
    print()
    print("[중장기: 최근 1~4년 대비]")
    for line in year_lines:
        print(line)

    if CONFIG["UPDATE_HISTORY_FILE"]:
        action = save_today_to_history(history_path, today, today_value, note)
        print(
            f"\n[완료] {CONFIG['HISTORY_FILE']}에 오늘({today.isoformat()}) 지수를 "
            f"{today_value:,.2f}로 {action}했습니다({note} 표시)."
        )
        if note == UNCONFIRMED_NOTE:
            print(
                "[확인 필요] 아직 장 마감 전이라 이 값은 장중 값입니다. 장 마감 후 "
                "다시 실행하면 확정 종가로 자동 교체됩니다(직접 고치지 않아도 됩니다)."
            )


if __name__ == "__main__":
    main()
