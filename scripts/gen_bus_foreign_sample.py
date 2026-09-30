"""외국인 이용객 트렌드 실습용 가상 샘플 데이터 생성기 (1회성 스크립트)

data/bus_foreign_sample.md  : 당사 버스 이용객 가상 샘플(월별, 노선/터미널별, 해외카드+해외OTA)
data/kosis_foreign_sample.md: 통계청(KOSIS) 외국인 통계 가상 샘플(월별, 전국 단위)

실제 수치가 아닌 실습용 더미 데이터이며, 결과 파일 상단에 그 사실을 명시한다.
기준 시점(최신월)은 2026-09로 두고 최근 36개월(2023-10~2026-09)을 생성한다.
"""

import random
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

random.seed(42)

LATEST_YEAR, LATEST_MONTH = 2026, 9
MONTHS = 36  # 최근 3년

ROUTES = [
    # (노선, 터미널, 연간증감률, 기준 월 합계(카드+OTA))
    ("노선A", "터미널가", 0.25, 120),
    ("노선B", "터미널나", 0.086, 85),
    ("노선C", "터미널다", -0.091, 42),
]


def month_range(latest_year: int, latest_month: int, count: int):
    """(연, 월) 튜플을 과거->최신 순으로 count개 반환."""
    months = []
    y, m = latest_year, latest_month
    for _ in range(count):
        months.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(months))


def seasonal_factor(month: int) -> float:
    # 7~8월(여름 성수기), 1~2월(설 연휴)에 소폭 증가하는 간단한 계절 패턴
    if month in (7, 8):
        return 1.15
    if month in (1, 2):
        return 1.08
    return 1.0


def gen_bus_rows():
    months = month_range(LATEST_YEAR, LATEST_MONTH, MONTHS)
    rows = []
    for route, terminal, annual_growth, base_total in ROUTES:
        for idx, (y, m) in enumerate(months):
            years_elapsed = idx / 12
            trend = (1 + annual_growth) ** years_elapsed
            noise = random.uniform(0.95, 1.05)
            total = base_total * trend * seasonal_factor(m) * noise
            card = round(total * 0.6)
            ota = round(total * 0.4)
            rows.append((f"{y:04d}-{m:02d}", route, terminal, card, ota))
    return rows


def gen_kosis_rows():
    months = month_range(LATEST_YEAR, LATEST_MONTH, MONTHS)
    rows = []
    base_entrants = 380000
    base_residents = 1_950_000
    for idx, (y, m) in enumerate(months):
        years_elapsed = idx / 12
        entrants = base_entrants * (1.12 ** years_elapsed) * seasonal_factor(m) * random.uniform(0.97, 1.03)
        residents = base_residents * (1.05 ** years_elapsed) * random.uniform(0.99, 1.01)
        rows.append((f"{y:04d}-{m:02d}", round(entrants), round(residents)))
    return rows


def write_bus_sample(rows):
    path = DATA_DIR / "bus_foreign_sample.md"
    lines = [
        "# 고속·시외버스 외국인 이용객 - 당사 시스템 가상 샘플",
        "",
        "> **가상 샘플(실제 수치 아님)**. 실습용으로 생성한 더미 데이터이며 보고·발표에 사용하지 마세요.",
        "> 국적 구분 없음. 외국인 이용객 = 해외 이용 카드 집계 인원 + 해외 OTA 유입 인원(중복 여부 미확인, 단순 합산).",
        "> 기준: 월별 합계(실제 원본은 일 단위이나, 실습 편의상 월 단위로 집계한 가상 데이터).",
        "> 기간: 2023-10 ~ 2026-09 (최근 36개월)",
        "",
        "| 연월 | 노선 | 터미널 | 해외카드 인원 | 해외OTA 인원 |",
        "|---|---|---|---|---|",
    ]
    for ym, route, terminal, card, ota in rows:
        lines.append(f"| {ym} | {route} | {terminal} | {card} | {ota} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_kosis_sample(rows):
    path = DATA_DIR / "kosis_foreign_sample.md"
    lines = [
        "# 통계청(KOSIS) 외국인 통계 가상 샘플",
        "",
        "> **가상 샘플(실제 수치 아님)**. 실습용으로 생성한 더미 데이터이며 보고·발표에 사용하지 마세요.",
        "> 실제 KOSIS 원본 파일 형식(.xlsx/.csv, 열 구성 등)은 확인 필요 — 확정 시 이 파일 대신 실제 자료를 사용.",
        "> 외국인 입국자: 「국제인구이동통계」 국적/체류자격별 입국자(전국 합계로 단순화).",
        "> 체류 외국인: 법무부 「출입국자및체류외국인통계」(전국 합계로 단순화).",
        "> 기간: 2023-10 ~ 2026-09 (최근 36개월)",
        "",
        "| 연월 | 외국인입국자수 | 체류외국인수 |",
        "|---|---|---|",
    ]
    for ym, entrants, residents in rows:
        lines.append(f"| {ym} | {entrants} | {residents} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main():
    DATA_DIR.mkdir(exist_ok=True)
    bus_path = write_bus_sample(gen_bus_rows())
    kosis_path = write_kosis_sample(gen_kosis_rows())
    print(f"생성 완료 -> {bus_path}")
    print(f"생성 완료 -> {kosis_path}")


if __name__ == "__main__":
    main()
