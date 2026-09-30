"""기존 트렌드 분석 PPT를 흉내 낸 샘플 PPT 생성기 (1회성 스크립트)

bus_foreign_trend_plan_1.md 7번 항목의 가상 샘플 표를 그대로 옮겨
1장(요약)·2장(세부) 구성의 .pptx를 만든다.
이후 수치 자동 교체 스크립트가 이 파일의 표 셀을 찾아 값만 바꾸는
대상(= "기존 PPT")으로 쓴다.

표의 각 셀에는 나중에 자동 교체 스크립트가 찾을 수 있도록
구분/노선 라벨(예: "올해 누계", "노선A")을 고정 키로 둔다.
"""

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

BASE_DIR = Path(__file__).resolve().parent.parent
PPT_DIR = BASE_DIR / "ppt"
OUTPUT_PATH = PPT_DIR / "고속시외버스_외국인이용객_트렌드.pptx"

NAVY = RGBColor(0x1F, 0x3B, 0x57)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF2, 0xF2, 0xF2)

SUMMARY_HEADERS = ["구분", "기준", "비교 시점", "증감률"]
SUMMARY_ROWS = [
    ["올해 누계", "118", "전년 동기 100", "+18.0%"],
    ["최근 1년", "125", "그 전 1년 112", "+11.6%"],
    ["최근 3년", "125", "3년 전 100", "+25.0%"],
]

DETAIL_HEADERS = ["노선", "올해 누계(지수)", "전년 동기(지수)", "증감률"]
DETAIL_ROWS = [
    ["노선A", "60", "48", "+25.0%"],
    ["노선B", "38", "35", "+8.6%"],
    ["노선C", "20", "22", "-9.1%"],
]


def add_title(slide, text: str, subtitle: str | None = None):
    box = slide.shapes.add_textbox(Inches(0.5), Inches(0.35), Inches(9), Inches(1.0))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = text
    run.font.size = Pt(28)
    run.font.bold = True
    run.font.color.rgb = NAVY

    if subtitle:
        p2 = tf.add_paragraph()
        run2 = p2.add_run()
        run2.text = subtitle
        run2.font.size = Pt(13)
        run2.font.color.rgb = RGBColor(0x80, 0x80, 0x80)


def add_table(slide, headers: list[str], rows: list[list[str]], top: float):
    n_rows = len(rows) + 1
    n_cols = len(headers)
    left = Inches(0.6)
    width = Inches(8.8)
    height = Inches(0.5 * n_rows)

    table_shape = slide.shapes.add_table(n_rows, n_cols, left, Inches(top), width, height)
    table = table_shape.table

    for col, title in enumerate(headers):
        cell = table.cell(0, col)
        cell.text = title
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        for p in cell.text_frame.paragraphs:
            p.alignment = PP_ALIGN.CENTER
            for run in p.runs:
                run.font.bold = True
                run.font.color.rgb = WHITE
                run.font.size = Pt(14)

    for r, row in enumerate(rows, start=1):
        for c, value in enumerate(row):
            cell = table.cell(r, c)
            cell.text = value
            cell.fill.solid()
            cell.fill.fore_color.rgb = LIGHT_GRAY if r % 2 == 0 else WHITE
            for p in cell.text_frame.paragraphs:
                p.alignment = PP_ALIGN.CENTER if c > 0 else PP_ALIGN.LEFT
                for run in p.runs:
                    run.font.size = Pt(13)
                    run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

    return table


def add_footer(slide, text: str):
    box = slide.shapes.add_textbox(Inches(0.5), Inches(6.9), Inches(9), Inches(0.4))
    tf = box.text_frame
    run = tf.paragraphs[0].add_run()
    run.text = text
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)


def build_presentation() -> Presentation:
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # 1장: 요약
    slide1 = prs.slides.add_slide(blank_layout)
    add_title(
        slide1,
        "고속·시외버스 외국인 이용객 증가 현황 - 요약",
        "기간별(올해 누계 / 최근 1년 / 최근 3년) 이용객 증감 요약",
    )
    add_table(slide1, SUMMARY_HEADERS, SUMMARY_ROWS, top=1.6)
    add_footer(slide1, "[가상 샘플] 실제 수치 아님 · 자동 갱신 대상 표")

    # 2장: 세부
    slide2 = prs.slides.add_slide(blank_layout)
    add_title(
        slide2,
        "고속·시외버스 외국인 이용객 증가 현황 - 세부",
        "노선별 올해 누계 대비 전년 동기 추이",
    )
    add_table(slide2, DETAIL_HEADERS, DETAIL_ROWS, top=1.6)
    add_footer(slide2, "[가상 샘플] 실제 수치 아님 · 자동 갱신 대상 표")

    return prs


def main():
    PPT_DIR.mkdir(exist_ok=True)
    prs = build_presentation()
    prs.save(OUTPUT_PATH)
    print(f"생성 완료 -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
