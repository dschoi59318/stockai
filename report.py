# -*- coding: utf-8 -*-
"""
report.py - 종목 분석 Word 리포트 (python-docx)

구성은 docs/리포트_구성지침.md(버전 direction.REPORT_GUIDE_VERSION) 3장 표를 그대로 따른다.
 표지   : 종목명(코드), 시장·업종, 기준일, 작성일, 'AI인사이트랩 StockAI', 한 줄 요약(쉽게 읽기 7장), 종목 소개(0장)
 1      : Executive Summary - 방향 지시계 박스, 결론 문단(AI), 왜 그런가 3줄(AI), 이게 바뀌면 판단도 바뀝니다(반전 조건 표)
 2      : 왜 이런 결과가 나왔나 - 실적이 말하는 것(쉽게 읽기 3장 + 4장 빚 급변 문장), 실적 해설(AI),
          주가를 움직인 사건(표 + AI 해설), 시장 전체 움직임
 3      : 가격 차트와 해설 - 52주 범위 막대 + 쉽게 읽기 1장, 가격 차트(1년 캔들 + 60·120일 평균 + 거래량 + 사건 번호),
          이 차트가 말하는 것(추세·움직임·거래), 수익률 막대, 가격 지표 표(뜻 열 포함)
 4      : 앞으로의 방향 - 시나리오 표, 시나리오 해설(AI), 다음 확인 시점, 지켜볼 숫자 3가지(쉽게 읽기 6장)
 5      : 재무 상세 - 핵심 지표 표(첫머리), 쉽게 읽기 4장·5장, 연간·분기 표, 매출·영업이익 차트
 부록 A : 용어 풀이 - 쉽게 읽기 지침 6절 용어표 + 10절 숫자 풀이 표
 부록 B : 출처·면책 - 두 지침 버전 표시
 ("쉽게 읽기 N장" = 쉽게 읽기 결과물의 장(0~7장), "쉽게 읽기 지침 N절" = 지침 문서의 절 번호)

지침 v1.1 반영
 - 가격 차트 1년(2장 사건 표와 기간을 맞춘다). 기간 시작 = 기준일 - 365일(events.py 사건 기간과 같다)
 - 핵심 지표 표(현재가, 1개월·1년 수익률, PER, PBR, ROE, 부채비율, 영업이익률)를 5장 첫머리로 옮김
 - 용어 풀이(지침 6.4): 리포트 조립이 끝난 뒤 최종 순서(표지 → 1장 → … → 부록)로 본문 문단 전체를 앞에서부터 훑어
   easy_read.apply_gloss로 풀이를 다시 붙인다(apply_report_gloss). 대상은 표 밖의 '본문(Normal)' 문단이며,
   표(방향 지시계·반전 조건 등)·AI 자리 회색 박스·제목·설명 캡션(NOTE_STYLE)·출처 목록은 건너뛴다.
 - 체크리스트 10번: check_report_gloss(path) - 같은 범위에서 용어 첫 등장에만 풀이가 한 번 붙었는지 검사

지침 v1.4 반영
 - 5.0 기준일: 일봉은 data.session_cutoff() 뒤를 잘라 쓴다(15:40 이전 작성 = 직전 거래일). 표지·출처에
   "기준일 {날짜} 정규장 종가 (작성 {날짜 시각})"(data.base_date_note). 작성 시각은 한국시간

지침 v1.2 반영 + AI 해설(지침 8장, narrator.py)
 - AI 호출 3개: 결론 문단 + 왜 그런가 3줄(Sonnet) / 실적 해설 + 사건 해설(Haiku) / 시나리오 해설(Haiku)
 - AI 문장은 본문(Normal) 문단으로 넣으므로 용어 풀이(apply_report_gloss) 대상이 된다(지침 6.4).
 - 검증을 끝까지 통과하지 못한 해설은 본문 위에 회색 박스로 미통과 항목을 적는다.
   API 키가 없거나 호출이 실패하면 그 자리에 회색 박스 "[AI 해설 없음: 호출명 - 사유]".
 - 기존 AI 분석(7개 소제목)·Executive Summary 코드는 삭제했다(analyst.py 폐지).

지침 v1.6 반영 (12장 서식 규격 = ControlTower PREMIUM_STANDARD v3 2절)
 - Noto Sans KR, 절 제목 15 / 소제목 12 / 본문 11 / 캡션·표 안·안내 박스 10 / 출처 줄·머리글·바닥글 8pt
 - 줄간격 1.0(전 문단, 표 안 포함 - 조립이 끝난 뒤 _finalize_v3가 문단·run마다 서체와 줄간격을 명시)
 - A4, 좌우 여백 18mm(본문 폭 174mm), 위아래 20mm
 - 표 174mm·고정 레이아웃·셀 여백 1mm, 헤더 남색 + 흰 굵은 글자 + 헤더 칸 사이 흰 테두리
   정렬은 가운데(30자 넘는 셀만 왼쪽). 5장 재무 표(핵심 지표·연간·분기)만 숫자 열 오른쪽(right_cols)
 - 그림 172mm: 그림 위 제목 문단(11pt 굵게 가운데) -> 그림(테두리 포함 PNG) -> 출처 줄(8pt) -> 설명 캡션(10pt)
   그림 PNG는 charts.save_*_png(report=True)가 172mm 기준으로 그린다(앱 화면 그림은 그대로)
 - 표지 다음 쪽 목차(섹션 제목 7개, 쪽번호 없음). 목차·그림 제목·출처 줄은 용어 풀이 대상이 아니다(Normal 아님)
 - 부록 B 출처는 공식 명칭, 면책에 독립 분석·무단 복제·배포 금지
 - 저장 직후 v3 관문(ControlTower _engine/v3_gate.py) verify 전용 - 결과는 output/_gate_report.txt

서식 (그 밖)
 - 제목 3단(H1 절 / H2 소절 / H3 소제목), 절(H1)마다 새 쪽
 - 머리글(종목명·기준일, 표지 제외), 바닥글(쪽 번호 / 전체 쪽수)
차트 이미지: charts.save_*_png (kaleido 우선, 실패하면 matplotlib)
저장: output/{종목명}_{코드}_{작성일 YYYYMMDD}.docx, 같은 이름이 있으면 _2, _3 ...
"""

import os
import re
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

import charts
import data as dl
import direction
import easy_read
import events as ev_mod
import financials
import guides
import indicators
import keys
import narrator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# 지침 v1.6 12장 서식 규격 (PREMIUM_STANDARD v3 2절)
FONT = "Noto Sans KR"
H1_PT, H2_PT, H3_PT = 15, 12, 11
BODY_PT = 11
NOTE_PT = 10                    # 캡션·표 안 글자·안내 박스
TABLE_PT = NOTE_PT
SOURCE_PT = 8                   # 그림 출처 줄·머리글·바닥글
LINE_SPACING = 1.0
MARGIN_SIDE_MM = 18             # 좌우 여백
MARGIN_TB_MM = 20               # 위아래 여백
CONTENT_WIDTH_MM = 174          # A4 210mm - 좌우 여백 18mm x 2
TABLE_MM = 174                  # 전 표 폭
CHART_MM = 172                  # 전 그림 폭
CELL_MARGIN_MM = 1.0
LONG_CELL_CHARS = 30            # 이보다 긴 셀만 왼쪽 정렬(그 외 가운데)

NAVY = RGBColor(0x1F, 0x3A, 0x5F)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GRAY = RGBColor(0x66, 0x66, 0x66)
NAVY_HEX = "1F3A5F"
WHITE_HEX = "FFFFFF"
HEADER_FILL = NAVY_HEX          # 표 헤더: 남색 + 흰 글자 + 흰 안쪽 테두리
BOX_FILL = "EDEDED"             # 회색 박스(AI 자리·안내)
SIGNAL_FILL = "F3F6FA"          # 방향 지시계 판정 칸

BRAND = "AI인사이트랩 StockAI"

# 지침 3장 섹션 제목(순서 고정)
SECTION_TITLES = [
    "1. Executive Summary",
    "2. 왜 이런 결과가 나왔나",
    "3. 가격 차트와 해설",
    "4. 앞으로의 방향",
    "5. 재무 상세",
    "부록 A. 용어 풀이",
    "부록 B. 출처·면책",
]

# 1장 '왜 그런가' 줄 끝 섹션 안내(파이썬 틀)
WHY_LINES = (("실적", "(2장 참고)"), ("주가 움직임", "(2·3장 참고)"), ("거래", "(3장 참고)"))

# 지침 4장 부록 B 면책 문구 (v1.6: 독립 분석·무단 복제·배포 금지 추가)
REPORT_DISCLAIMER = ("본 리포트는 공개된 가격·재무·공시·뉴스 데이터를 규칙에 따라 정리한 참고 자료이며 투자 권유가 아닙니다. "
                     "시나리오는 조건에 따른 가능성을 정리한 것으로 미래 주가를 예측하거나 보장하지 않습니다. "
                     "투자 판단과 책임은 이용자 본인에게 있습니다. "
                     "본 리포트는 분석 대상 회사의 공식 입장과 무관한 독립 분석이며, 무단 복제·배포를 금합니다.")

# 지침 v1.6 12.3 그림 출처 줄
SOURCE_PRICE = "출처: 한국거래소 정규장 종가"
SOURCE_FIN = "출처: 금융감독원 전자공시시스템 정기보고서"

CHART_DAYS = 365                # 가격 차트 1년(기준일 - 365일부터, events.py 사건 기간과 같다)
CHART_BUFFER_DAYS = 200         # MA120을 차트 첫날부터 그리기 위한 앞쪽 여유(달력일)
NOTE_STYLE = "StockAI 설명"      # 캡션 문단 스타일(용어 풀이 대상에서 빠진다)
FIG_TITLE_STYLE = "StockAI 그림 제목"   # 그림 위 제목(v1.6 12.3, 용어 풀이 대상 아님)
SOURCE_STYLE = "StockAI 출처"          # 그림 아래 출처 줄(v1.6 12.3, 용어 풀이 대상 아님)
TOC_STYLE = "StockAI 목차"             # 목차(v1.6 12.4, 용어 풀이 대상 아님)
HEADING_STYLES = {1: "StockAI 제목 1", 2: "StockAI 제목 2", 3: "StockAI 제목 3"}   # 개요 수준 없는 제목(삼각형 제거)


# ===========================================================================
# 서식 도우미
# ===========================================================================

def _set_font(element_style, size=None, bold=None, color=None):
    """스타일(또는 run)의 글꼴을 맑은 고딕으로 고정한다. 한글(eastAsia)까지 지정하고 테마 글꼴은 지운다."""
    font = element_style.font
    font.name = FONT
    if size is not None:
        font.size = Pt(size)
    if bold is not None:
        font.bold = bold
    if color is not None:
        font.color.rgb = color
    rpr = element_style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), FONT)
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rfonts.get(qn(attr)) is not None:
            del rfonts.attrib[qn(attr)]


def _run_font(run, size=None, bold=None, color=None):
    """run 하나의 글꼴 지정(한글 글꼴 포함)."""
    run.font.name = FONT
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), FONT)


def _setup_document(title_left):
    """A4·여백·기본 글꼴·제목 3단·머리글/바닥글을 설정한 빈 문서를 만든다."""
    doc = Document()

    _set_doc_defaults_font(doc)
    normal = doc.styles["Normal"]
    _set_font(normal, size=BODY_PT)
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = LINE_SPACING
    # Word의 '한글과 영어/숫자 사이 간격 자동 조정'을 끈다("20 일", "AI 인사이트랩"처럼 벌어지지 않도록).
    # (OOXML 순서 규칙상 w:spacing·w:ind 등보다 앞에 넣어야 한다)
    ppr = normal.element.get_or_add_pPr()
    later = {qn(t) for t in ("w:bidi", "w:adjustRightInd", "w:snapToGrid", "w:spacing", "w:ind",
                             "w:contextualSpacing", "w:mirrorIndents", "w:suppressOverlap", "w:jc",
                             "w:textDirection", "w:textAlignment", "w:textboxTightWrap",
                             "w:outlineLvl", "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr", "w:pPrChange")}
    anchor = next((child for child in ppr if child.tag in later), None)
    for tag in ("w:autoSpaceDE", "w:autoSpaceDN"):
        el = OxmlElement(tag)
        el.set(qn("w:val"), "0")
        if anchor is not None:
            anchor.addprevious(el)
        else:
            ppr.append(el)

    for level, size in ((1, H1_PT), (2, H2_PT), (3, H3_PT)):
        style = doc.styles[f"Heading {level}"]
        _set_font(style, size=size, bold=True, color=NAVY)
        style.paragraph_format.space_before = Pt(14 if level == 1 else 10)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.line_spacing = LINE_SPACING
        style.paragraph_format.keep_with_next = True
    doc.styles["Heading 1"].paragraph_format.page_break_before = True      # 절마다 새 쪽
    _add_flat_heading_styles(doc)

    def _add_paragraph_style(name, size, color=None, bold=None, align=None, before=0, after=4):
        style = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        style.base_style = normal
        _set_font(style, size=size, color=color, bold=bold)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.line_spacing = LINE_SPACING
        if align is not None:
            style.paragraph_format.alignment = align
        return style

    _add_paragraph_style(NOTE_STYLE, NOTE_PT, color=GRAY, after=6)
    _add_paragraph_style(FIG_TITLE_STYLE, H3_PT, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, before=6, after=3)
    doc.styles[FIG_TITLE_STYLE].paragraph_format.keep_with_next = True
    _add_paragraph_style(SOURCE_STYLE, SOURCE_PT, color=GRAY, after=2)
    _add_paragraph_style(TOC_STYLE, BODY_PT, after=8)
    for name in ("List Bullet", "List Number", "Caption"):
        if name in [s.name for s in doc.styles]:
            _set_font(doc.styles[name], size=BODY_PT)
            doc.styles[name].paragraph_format.line_spacing = LINE_SPACING

    section = doc.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    for side in ("left_margin", "right_margin"):
        setattr(section, side, Mm(MARGIN_SIDE_MM))
    for side in ("top_margin", "bottom_margin"):
        setattr(section, side, Mm(MARGIN_TB_MM))
    section.header_distance = Mm(10)
    section.footer_distance = Mm(10)
    section.different_first_page_header_footer = True      # 표지에는 머리글·쪽 번호를 넣지 않는다

    head = section.header.paragraphs[0]
    head.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _run_font(head.add_run(title_left), size=SOURCE_PT, color=GRAY)

    foot = section.footer.paragraphs[0]
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_field(foot, "PAGE")
    _run_font(foot.add_run(" / "), size=SOURCE_PT, color=GRAY)
    _add_field(foot, "NUMPAGES")
    return doc


def _add_flat_heading_styles(doc):
    """제목 앞 접기·펼치기 삼각형을 없애기 위한 제목 스타일(지침 v1.6 12.1, 2026-09-28 추가).

    삼각형은 문단의 개요 수준(outline level)에서 나온다. FoodSafety(Monitoring\\_python\\report_final.py
    strip_keep_next, 2026-09-14)는 문단에 박힌 w:outlineLvl 을 지워 없앴지만, StockAI 는 Word 기본 제목 스타일
    (Heading 1~3)을 쓰고 Word 는 기본 제목 스타일의 개요 수준을 스타일 정의와 상관없이 1~3으로 고정한다
    (스타일에서 지우거나 본문 수준 9를 넣어도, 문단에 9를 넣어도 Word 가 1·2로 읽음 - 2026-09-28 실측).
    그래서 기본 제목 스타일의 서식(pPr·rPr)을 그대로 복사하고 개요 수준만 뺀 스타일을 따로 만들고,
    조립이 끝난 뒤 _flatten_headings 가 제목 문단을 이 스타일로 바꾼다. 보이는 서식은 같다.
    """
    import copy
    for level in (1, 2, 3):
        src = doc.styles[f"Heading {level}"]
        style = doc.styles.add_style(HEADING_STYLES[level], WD_STYLE_TYPE.PARAGRAPH)
        style.base_style = doc.styles["Normal"]
        for tag in ("w:pPr", "w:rPr"):
            el = src.element.find(qn(tag))
            if el is None:
                continue
            clone = copy.deepcopy(el)
            for outline in clone.findall(qn("w:outlineLvl")):
                clone.remove(outline)
            old = style.element.find(qn(tag))
            if old is not None:
                style.element.remove(old)
            style.element.append(clone)


def _flatten_headings(doc):
    """제목 문단(Heading 1~3)을 개요 수준 없는 같은 서식의 스타일로 바꾼다(삼각형 제거). 바꾼 문단 수를 돌려준다."""
    names = {f"Heading {level}": doc.styles[name] for level, name in HEADING_STYLES.items()}
    n = 0
    for p in doc.paragraphs:
        target = names.get(p.style.name)
        if target is not None:
            p.style = target
            n += 1
    return n


def _set_doc_defaults_font(doc):
    """문서 기본값(docDefaults)의 글꼴을 Noto Sans KR로 둔다. 스타일이 없는 글자도 규격 서체가 되게 한다."""
    defaults = doc.styles.element.find(qn("w:docDefaults"))
    if defaults is None:
        return
    rpr_default = defaults.find(qn("w:rPrDefault"))
    rpr = rpr_default.find(qn("w:rPr")) if rpr_default is not None else None
    if rpr is None:
        return
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rfonts.get(qn(attr)) is not None:
            del rfonts.attrib[qn(attr)]
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), FONT)


def _drop_spacers_before_breaks(doc):
    """쪽 나눔으로 시작하는 문단(절 제목 등) 바로 앞의 빈 문단을 지운다(v3 "빈 페이지 0개").

    표 뒤 여백 문단은 표가 쪽 끝까지 차면 다음 쪽으로 밀려나고, 이어지는 절 제목이 새 쪽에서 시작하므로
    여백 문단 하나만 있는 빈 쪽이 생긴다(KH바텍 v1.6 첫 빌드 16쪽). 표와 표 사이 여백은 건드리지 않는다.
    """
    from docx.text.paragraph import Paragraph
    body = doc.element.body
    for p_el in list(body.iterchildren(qn("w:p"))):
        nxt = p_el.getnext()
        if nxt is None or nxt.tag != qn("w:p"):
            continue
        para = Paragraph(p_el, doc)
        if para.text.strip() or p_el.xpath(".//w:drawing"):
            continue
        following = Paragraph(nxt, doc)
        breaks = following.paragraph_format.page_break_before or following.style.paragraph_format.page_break_before
        if breaks:
            body.remove(p_el)


def _finalize_v3(doc):
    """조립이 끝난 문서의 모든 문단(표 안·머리글·바닥글 포함)에 줄간격 1.0을, 모든 글자(run)에 규격 서체를 명시한다.

    스타일 기본값에만 기대지 않는다(v3 2절 "문단마다 실제 적용 확인", 지침 v1.6 12.1). 글자 내용은 바꾸지 않는다.
    """
    from docx.text.paragraph import Paragraph
    _drop_spacers_before_breaks(doc)
    _flatten_headings(doc)                               # 제목 앞 접기 삼각형 제거(개요 수준 없는 제목 스타일)
    parts = [doc.element.body]
    for section in doc.sections:                        # 표지(첫 쪽) 머리글은 만들지 않았으므로 건드리지 않는다
        parts += [section.header._element, section.footer._element]
    for part in parts:
        for p_el in part.iter(qn("w:p")):
            Paragraph(p_el, doc).paragraph_format.line_spacing = LINE_SPACING
        for r_el in part.iter(qn("w:r")):
            rfonts = r_el.get_or_add_rPr().get_or_add_rFonts()
            for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
                if rfonts.get(qn(attr)) is not None:
                    del rfonts.attrib[qn(attr)]
            for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
                rfonts.set(qn(attr), FONT)


def _add_field(paragraph, instr):
    """쪽 번호 같은 필드 코드(PAGE, NUMPAGES)를 넣는다."""
    def fld(kind):
        el = OxmlElement("w:fldChar")
        el.set(qn("w:fldCharType"), kind)
        return el

    run = paragraph.add_run()
    _run_font(run, size=SOURCE_PT, color=GRAY)
    run._r.append(fld("begin"))
    run = paragraph.add_run()
    _run_font(run, size=SOURCE_PT, color=GRAY)
    text = OxmlElement("w:instrText")
    text.set(qn("xml:space"), "preserve")
    text.text = instr
    run._r.append(text)
    run = paragraph.add_run()
    run._r.append(fld("separate"))
    run = paragraph.add_run("1")
    _run_font(run, size=SOURCE_PT, color=GRAY)
    run = paragraph.add_run()
    run._r.append(fld("end"))


def _shade(cell, fill):
    """표 셀 배경 음영."""
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcpr.append(shd)


def _cell_text(cell, text, bold=False, align=None, size=TABLE_PT, color=None):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = LINE_SPACING
    if align is not None:
        p.alignment = align
    _run_font(p.add_run(str(text)), size=size, bold=bold, color=color)


def _v3_align(text, right=False):
    """v1.6 12.2 표 정렬: 숫자 열(5장 재무 표만) 오른쪽, 30자 넘는 셀 왼쪽, 그 외 가운데."""
    if right:
        return WD_ALIGN_PARAGRAPH.RIGHT
    return WD_ALIGN_PARAGRAPH.LEFT if len(str(text).strip()) > LONG_CELL_CHARS else WD_ALIGN_PARAGRAPH.CENTER


def _cell_border(cell, side, color=WHITE_HEX, sz=6):
    """셀 한쪽 테두리(헤더 칸 사이 흰 선). tcPr 순서 규칙상 w:shd 앞에 둔다."""
    tcpr = cell._tc.get_or_add_tcPr()
    borders = tcpr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tcpr.insert_element_before(borders, "w:shd", "w:noWrap", "w:tcMar", "w:textDirection",
                                   "w:tcFitText", "w:vAlign", "w:hideMark")
    el = borders.find(qn(f"w:{side}"))
    if el is None:
        el = OxmlElement(f"w:{side}")
        borders.append(el)
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(sz))
    el.set(qn("w:space"), "0")
    el.set(qn("w:color"), color)


def _navy_header(cells):
    """헤더 칸들: 남색 배경 + 흰 굵은 글자(글자는 _cell_text에서) + 서로 맞닿는 쪽 흰 테두리."""
    for i, cell in enumerate(cells):
        _shade(cell, HEADER_FILL)
        if i > 0:
            _cell_border(cell, "left")
        if i < len(cells) - 1:
            _cell_border(cell, "right")


def _table_geometry(table, widths_mm):
    """v1.6 12.2: 표 폭 174mm 고정(열 폭은 비율 유지로 맞춤), 가운데, 고정 레이아웃, 셀 여백 1mm."""
    n = len(table.columns)
    widths = list(widths_mm) if widths_mm else [TABLE_MM / n] * n
    k = TABLE_MM / sum(widths)
    widths = [round(w * k, 2) for w in widths]
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False                                # tblLayout fixed
    for row in table.rows:
        for i, width in enumerate(widths):
            row.cells[i].width = Mm(width)
    twips = lambda mm: str(int(round(mm * 1440 / 25.4)))
    grid = table._tbl.find(qn("w:tblGrid"))
    if grid is not None:
        for i, col in enumerate(grid.findall(qn("w:gridCol"))):
            if i < len(widths):
                col.set(qn("w:w"), twips(widths[i]))
    tblpr = table._tbl.tblPr
    tblw = tblpr.find(qn("w:tblW"))
    if tblw is None:
        tblw = OxmlElement("w:tblW")
        tblpr.insert_element_before(tblw, "w:jc", "w:tblCellSpacing", "w:tblInd", "w:tblBorders", "w:shd",
                                    "w:tblLayout", "w:tblCellMar", "w:tblLook", "w:tblCaption", "w:tblDescription")
    tblw.set(qn("w:w"), twips(TABLE_MM))
    tblw.set(qn("w:type"), "dxa")
    mar = tblpr.find(qn("w:tblCellMar"))
    if mar is None:
        mar = OxmlElement("w:tblCellMar")
        tblpr.insert_element_before(mar, "w:tblLook", "w:tblCaption", "w:tblDescription")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), twips(CELL_MARGIN_MM))
        el.set(qn("w:type"), "dxa")
        mar.append(el)


def _keep_rows_together(table):
    """표가 쪽 끝에서 머리글만 남고 갈라지지 않도록 마지막 행 전까지 '다음 행과 함께'를 건다."""
    for row in table.rows[:-1]:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.keep_with_next = True


def _table(doc, header, rows, widths_mm=None, right_cols=(), size=TABLE_PT, keep=False):
    """남색 헤더 표를 만든다(v1.6 12.2). widths_mm은 비율로 보고 합이 174mm가 되게 맞춘다.

    right_cols: 숫자를 오른쪽 정렬할 열. 5장 재무 표(핵심 지표·연간·분기)에서만 넘긴다(결정 4).
    그 밖의 칸은 가운데, 30자 넘는 칸만 왼쪽.
    """
    table = doc.add_table(rows=1, cols=len(header))
    table.style = "Table Grid"
    for i, name in enumerate(header):
        _cell_text(table.rows[0].cells[i], name, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=size, color=WHITE)
    _navy_header(table.rows[0].cells)
    # 표가 쪽을 넘어가면 헤더를 다시 보여 준다
    trpr = table.rows[0]._tr.get_or_add_trPr()
    hdr = OxmlElement("w:tblHeader")
    hdr.set(qn("w:val"), "true")
    trpr.append(hdr)

    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            text = "" if value is None else value
            _cell_text(cells[i], text, align=_v3_align(text, right=i in right_cols), size=size)

    _table_geometry(table, widths_mm)
    if keep:
        _keep_rows_together(table)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def _gray_box(doc, text):
    """회색 배경 박스(1칸 표)로 안내 문구를 넣는다. 박스 안 글자는 왼쪽 정렬(v1.6 12.2)."""
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.rows[0].cells[0]
    _shade(cell, BOX_FILL)
    _cell_text(cell, text, size=NOTE_PT, align=WD_ALIGN_PARAGRAPH.LEFT)
    cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(0x44, 0x44, 0x44)
    _table_geometry(table, [TABLE_MM])
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def _ai_result(doc, ai, call, notify=True):
    """AI 호출 결과의 파싱 본문. 없으면 회색 박스로 사유를 적고 None.

    notify=True면 검증 미통과 항목도 회색 박스로 적는다(같은 호출의 첫 자리에서만).
    """
    name = narrator.CALLS[call]["이름"]
    if ai is None:
        if notify:
            _gray_box(doc, f"[AI 해설 없음: {name} - API 키 없음]")
        return None
    if call in ai["오류"]:
        if notify:
            _gray_box(doc, f"[AI 해설 없음: {name} - 호출 실패 {ai['오류'][call][:80]}]")
        return None
    result = ai["결과"][call]
    if notify and not result["통과"]:
        _gray_box(doc, f"이 해설은 자동 검증 일부를 통과하지 못했습니다: {', '.join(narrator.failed_items(result))} "
                       f"({result['시도경로']})")
    return result["parsed"]


def _ai_missing(doc, call, what):
    _gray_box(doc, f"[AI 해설 없음: {narrator.CALLS[call]['이름']} - {what} 형식 오류]")


def _caption(doc, text):
    """표·그림 아래 설명 문단(10pt). 바로 앞 블록과 같은 쪽에 붙인다(_keep_previous_with_next)."""
    _keep_previous_with_next(doc)
    p = doc.add_paragraph(style=NOTE_STYLE)
    _run_font(p.add_run(text), size=NOTE_PT, color=GRAY)
    return p


def _keep_previous_with_next(doc):
    """지금 문서 끝에 올 문단이 앞 블록에서 떨어져 다음 쪽 첫 줄로 넘어가지 않게 '다음 문단과 함께'를 건다.

    - 바로 앞 문단(표 뒤 여백 문단, 그림 출처 줄, '종합 상태' 줄)에 keep_with_next
    - 그 앞이 표면 표 마지막 행의 모든 칸 문단에도 keep_with_next (표 끝 -> 여백 -> 설명이 한 덩어리)
    긴 표(가격 지표·재무 표)는 마지막 행만 묶이므로 표 자체는 쪽을 넘어 나뉠 수 있다.
    그림은 _picture가 이미 그림 -> 출처 줄을 묶어 두었으므로 출처 줄만 걸면 그림 -> 출처 -> 설명이 이어진다.
    """
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    body = doc.element.body
    last = body[-1]
    if last.tag == qn("w:sectPr"):
        last = last.getprevious()
    if last is None or last.tag != qn("w:p"):
        return
    Paragraph(last, doc).paragraph_format.keep_with_next = True
    before = last.getprevious()
    if before is not None and before.tag == qn("w:tbl"):
        for cell in Table(before, doc).rows[-1].cells:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.keep_with_next = True


def _md_runs(paragraph, text, size=None):
    """'**굵게**'만 해석해 run으로 넣는다."""
    for part in re.split(r"(\*\*[^*]+\*\*)", text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            _run_font(paragraph.add_run(part[2:-2]), size=size, bold=True)
        else:
            _run_font(paragraph.add_run(part), size=size)


def _labeled(doc, label, text):
    """'추세: 문장'처럼 앞 라벨만 굵게."""
    p = doc.add_paragraph()
    _run_font(p.add_run(f"{label}: "), bold=True)
    _run_font(p.add_run(text))
    return p


def _picture(doc, path, width_mm=CHART_MM):
    doc.add_picture(path, width=Mm(width_mm))
    p = doc.paragraphs[-1]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True             # 그림과 출처 줄을 같은 쪽에
    return p


def _figure(doc, title, path, source):
    """v1.6 12.3 그림 한 벌: 그림 위 제목 문단(11pt 굵게 가운데) -> 172mm 그림 -> 출처 줄(8pt).

    제목·출처는 Normal이 아닌 스타일이라 용어 풀이 대상에서 빠진다. 설명 캡션(10pt)은 부르는 쪽이 이어서 넣는다.
    """
    p = doc.add_paragraph(style=FIG_TITLE_STYLE)
    _run_font(p.add_run(title), size=H3_PT, bold=True)
    _picture(doc, path)
    p = doc.add_paragraph(style=SOURCE_STYLE)
    _run_font(p.add_run(source), size=SOURCE_PT, color=GRAY)
    return p


# ===========================================================================
# 표지
# ===========================================================================

def _cover(doc, name, code, market, group, base_date, today, summary, intro):
    """표지. 크기는 v1.6 12.1 표지 예외(종목명 20pt, 나머지 12·11pt)."""
    for _ in range(5):
        doc.add_paragraph()
    p = doc.add_paragraph()
    _run_font(p.add_run("종목 분석 리포트"), size=12, color=GRAY)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    _run_font(p.add_run(name), size=20, bold=True, color=NAVY)
    p = doc.add_paragraph()
    _run_font(p.add_run(f"({code})"), size=12, color=NAVY)
    doc.add_paragraph()

    note = dl.base_date_note(base_date, today)           # 지침 v1.4 5.0: 기준일 + 작성 시각
    for label, value in (("시장 · 업종", f"{market} · {group or '미상'}"),
                         ("기준일", note[len("기준일 "):])):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(3)
        _run_font(p.add_run(f"{label}   "), size=11, bold=True)
        _run_font(p.add_run(value), size=11)

    doc.add_paragraph()
    p = doc.add_paragraph()                              # 한 줄 요약: 쉽게 읽기 7장
    _run_font(p.add_run("한 줄 요약   "), size=11, bold=True, color=NAVY)
    _run_font(p.add_run(" ".join(summary)), size=11)
    for sentence in intro:                               # 종목 소개: 쉽게 읽기 0장
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        _run_font(p.add_run(sentence), size=11, color=GRAY)

    for _ in range(6):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _run_font(p.add_run(BRAND), size=12, bold=True, color=NAVY)


def _toc(doc):
    """목차(v1.6 12.4): 표지 다음 쪽, 섹션 제목 7개, 쪽번호 없음. 용어 풀이 대상이 아닌 스타일로 넣는다."""
    p = doc.add_paragraph(style=TOC_STYLE)
    p.paragraph_format.page_break_before = True
    p.paragraph_format.space_after = Pt(14)
    _run_font(p.add_run("목차"), size=H1_PT, bold=True, color=NAVY)
    for title in SECTION_TITLES:
        p = doc.add_paragraph(style=TOC_STYLE)
        _run_font(p.add_run(title), size=BODY_PT)


# ===========================================================================
# 1. Executive Summary
# ===========================================================================

SIGNAL_KEYS = ("가격 추세", "실적 흐름", "거래 관심도")


def _direction_box(doc, box):
    """방향 지시계: 신호 3개를 가로로(판정 이름 + 근거 1줄), 아래에 종합 상태를 굵게."""
    table = doc.add_table(rows=3, cols=3)
    table.style = "Table Grid"
    for i, key in enumerate(SIGNAL_KEYS):
        sig = box[key] or {"판정": "판정 불가", "근거": "이동평균을 계산할 데이터가 부족합니다"}
        head, verdict, evidence = table.rows[0].cells[i], table.rows[1].cells[i], table.rows[2].cells[i]
        _cell_text(head, key, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, color=WHITE)
        _cell_text(verdict, sig["판정"], bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=H2_PT, color=NAVY)
        _shade(verdict, SIGNAL_FILL)
        _cell_text(evidence, sig["근거"], align=_v3_align(sig["근거"]))
    _navy_header(table.rows[0].cells)
    _table_geometry(table, [TABLE_MM / 3] * 3)
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    _run_font(p.add_run("종합 상태: "), size=11, bold=True)
    _run_font(p.add_run(box["종합 상태"]), size=11, bold=True, color=NAVY)


def _exec_section(doc, d, ai):
    doc.add_heading(SECTION_TITLES[0], level=1)
    _direction_box(doc, d)
    _caption(doc, "가격 추세: 현재가와 최근 3개월(60일)·6개월(120일) 평균 비교 · "
                  "실적 흐름: 최근 6개월(2개 분기 합)과 1년 전 같은 6개월 비교 · "
                  "거래 관심도: 최근 5일 평균 거래량 ÷ 최근 3개월(60일) 평균")

    doc.add_heading("결론", level=2)
    parsed = _ai_result(doc, ai, "conclusion")
    if parsed is not None:
        if parsed["결론"]:
            doc.add_paragraph(parsed["결론"])
        else:
            _ai_missing(doc, "conclusion", "결론 문단")

    doc.add_heading("왜 그런가", level=2)
    if parsed is not None:
        for label, where in WHY_LINES:
            line = parsed["3줄"].get(label)
            if line:
                p = _labeled(doc, label, line)
                _run_font(p.add_run(f" {where}"), color=GRAY)
            else:
                _ai_missing(doc, "conclusion", f"'{label}:' 줄")

    doc.add_heading("이게 바뀌면 판단도 바뀝니다", level=2)
    rows = [(r["신호"], r["지금 판정"], r["바뀌는 조건"], r["지금과의 거리"]) for r in d["반전조건"]]
    if rows:
        _table(doc, ["신호", "지금 판정", "바뀌는 조건", "지금과의 거리"], rows, widths_mm=[22, 22, 86, 40], keep=True)
        _caption(doc, "가격 조건은 기준일의 3개월·6개월 평균값으로 계산했습니다. 실적 조건은 최근 2개 분기 합으로 판정하므로 "
                      "한 분기 값은 판정이 바뀌는 근거가 됩니다.")
    else:
        doc.add_paragraph("반전 조건을 계산할 데이터가 부족합니다.")


# ===========================================================================
# 2. 왜 이런 결과가 나왔나
# ===========================================================================

def _why_section(doc, d, easy, events, ai):
    doc.add_heading(SECTION_TITLES[1], level=1)
    ch = easy["장"]

    doc.add_heading("실적이 말하는 것", level=2)
    for sentence in ch[3]["문장"]:
        doc.add_paragraph(sentence)
    if len(ch[4]["문장"]) >= 3:                           # 4장 3문장(빚 급변)은 해당할 때만 있다
        doc.add_paragraph(ch[4]["문장"][2])

    doc.add_heading("실적 해설", level=2)
    parsed = _ai_result(doc, ai, "story")
    if parsed is not None:
        if parsed["실적"]:
            doc.add_paragraph(parsed["실적"])
        else:
            _ai_missing(doc, "story", "실적 해설")

    doc.add_heading("주가를 움직인 사건", level=2)
    if events is None:
        doc.add_paragraph("공시·뉴스 사건 자료를 불러오지 못했습니다.")
    elif not d["사건"]:
        doc.add_paragraph("지난 1년 동안 시장 대비 누적 등락이 3% 이상인 사건이 없습니다.")
    else:
        rows = []
        for e in d["사건"]:
            period = f"{e['번호']} {e['기간']}" + (" (공시 기반)" if e["유형"] == "공시 기반 사건" else "")
            rows.append((period, e["누적등락"], e["대표공시"], e["대표기사"], e["근거강도"]))
        _table(doc, ["기간", "누적 등락(시장 대비)", "대표 공시", "대표 기사", "근거 강도"], rows,
               widths_mm=[30, 28, 44, 56, 16], keep=True)
        _caption(doc, "사건: 지난 1년 중 시장 지수 대비 초과 등락·거래량이 기준을 넘은 날(3거래일 이내는 한 사건)과 "
                      "강한 공시 전후 초과 등락이 큰 날(공시 기반) · 시장 대비 누적 등락이 3% 이상인 사건 중 큰 순서로 "
                      "최대 5개, 기간 순 표시 · 번호는 3장 가격 차트의 표시와 같습니다.")
        if parsed is not None:
            for e in d["사건"]:
                line = parsed["사건"].get(e["번호"])
                if line:
                    doc.add_paragraph(f"{e['번호']} {line}")
                else:
                    _ai_missing(doc, "story", f"사건 {e['번호']}")

    doc.add_heading("시장 전체 움직임", level=2)
    doc.add_paragraph(d["시장전체문장"] if d.get("시장전체문장") else "시장 지수 자료를 불러오지 못했습니다.")


# ===========================================================================
# 3. 가격 차트와 해설
# ===========================================================================

# 가격 지표 표의 '뜻' 열
def _indicator_meaning(group, item):
    if group == "기간 수익률":
        return f"최근 {item} 동안 주가가 오르내린 비율"
    if group == "이동평균":
        m = re.match(r"^MA(\d+)$", item)
        if m:
            span = {"20": "약 1개월", "60": "약 3개월", "120": "약 6개월"}.get(m.group(1), "")
            return f"최근 {m.group(1)}거래일({span}) 종가의 평균"
        if item.startswith("현재가 vs"):
            return "현재가가 그 평균보다 몇 % 위(+)·아래(-)에 있는지"
        if item == "배열 상태":
            return "현재가와 세 평균의 크기 순서(정배열·역배열·혼조)"
    if group == "52주":
        return {"최고": "지난 1년 동안 거래된 가장 높은 가격", "최저": "지난 1년 동안 거래된 가장 낮은 가격",
                "최고 대비": "현재가가 52주 최고보다 몇 % 낮은지", "최저 대비": "현재가가 52주 최저보다 몇 % 높은지",
                "고저 폭": "52주 최고가 최저보다 몇 % 높은지"}.get(item, "")
    if group == "거래량":
        return {"최근 5일 평균": "최근 5거래일 하루 평균 사고판 주식 수",
                "최근 60일 평균": "최근 60거래일(약 3개월) 하루 평균 사고판 주식 수",
                "5일 / 60일 비율": "최근 5일 평균이 60일 평균의 몇 배인지"}.get(item, "")
    if group == "변동성":
        return "최근 20일 하루 등락의 흔들림을 1년 기준으로 환산한 값"
    if group == "업종 대비":
        if item == "업종그룹":
            return "금융감독원 기업개황 업종코드로 묶은 업종"          # v1.6 부록 B 규칙: 도구명 대신 공식 명칭
        if item.startswith("업종 평균"):
            return "같은 업종 종목들의 1개월 수익률 평균"
        if item.startswith("업종 중앙값"):
            return "같은 업종 종목들의 1개월 수익률 가운데 값"
        if item.startswith("초과 수익률"):
            return "이 종목 1개월 수익률에서 업종 값을 뺀 차이"
        if item == "상태":
            return "업종 비교를 하지 못한 사유"
    return ""


def load_chart_frame(code, base_date):
    """가격 차트용 1년 일봉 + MA60·MA120(앞쪽 여유분으로 계산한 뒤 기준일 - 365일부터 자른다)."""
    end = datetime.today()
    view_start = datetime.strptime(str(base_date)[:10], "%Y-%m-%d") - timedelta(days=CHART_DAYS)
    df = dl.fetch_ohlcv_raw(code, view_start - timedelta(days=CHART_BUFFER_DAYS), end)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["MA60"] = df["종가"].rolling(60).mean()
    df["MA120"] = df["종가"].rolling(120).mean()
    view = df[df.index >= pd.Timestamp(view_start.date())]
    return view if not view.empty else df


def _price_section(doc, ind, d, easy, df, name, tmpdir):
    doc.add_heading(SECTION_TITLES[2], level=1)
    ch = easy["장"]

    doc.add_heading("지금 주가는 1년 중 어디쯤인가요?", level=2)
    figure = ch[1].get("그림")
    if figure and figure["종류"] == "범위":
        path = os.path.join(tmpdir, "range.png")
        charts.save_range_png(figure["최저"], figure["최고"], figure["현재가"], path, report=True)
        _figure(doc, figure["제목"], path, SOURCE_PRICE)
        _keep_previous_with_next(doc)                    # 그림 -> 출처 -> 첫 설명 문장을 같은 쪽에
    for sentence in ch[1]["문장"]:
        doc.add_paragraph(sentence)

    doc.add_heading("가격 차트", level=2)
    engine = None
    markers = [{"번호": e["번호"], "시작일": e["시작일"], "종료일": e["종료일"]} for e in d["사건"]]
    if df is not None and not df.empty:
        path = os.path.join(tmpdir, "price.png")
        engine = charts.save_price_png(df, "", path, ma_cols=("MA60", "MA120"), markers=markers, report=True)
        _figure(doc, f"{name} 일봉 1년", path, SOURCE_PRICE)
        shown = [m["번호"] for m in markers if pd.Timestamp(m["종료일"]) >= df.index[0]]
        _caption(doc, "캔들 + 최근 3개월(60일)·6개월(120일) 평균 + 거래량 · 상승 빨강 / 하락 파랑 · "
                      "정규장 종가 기준(시간외 거래 미반영) · "
                      + (f"번호 {''.join(shown)}는 2장 사건 표의 사건 위치" if shown else "2장 사건 없음"))
    else:
        doc.add_paragraph("가격 데이터를 불러오지 못해 차트를 넣지 못했습니다.")

    doc.add_heading("이 차트가 말하는 것", level=2)
    a = d["가격 추세"]
    _labeled(doc, "추세", a["문장"] if a else easy_read.NO_DATA["상장 기간 부족"])
    moves = ch[2]["문장"]
    _labeled(doc, "움직임", " ".join(moves[:2]))
    _labeled(doc, "거래", moves[2] if len(moves) >= 3 else easy_read.NO_DATA["상장 기간 부족"])

    figure = ch[2].get("그림")
    if figure and figure["종류"] == "수익률" and figure["항목"]:
        doc.add_heading("기간 수익률", level=2)
        path = os.path.join(tmpdir, "returns.png")
        charts.save_returns_png(figure["항목"], path, report=True)
        _figure(doc, "최근 1개월·6개월·1년 주가 수익률", path, SOURCE_PRICE)

    table = indicators.to_table(ind)
    table = table[table["구분"] != "사실 문장"]
    rows = [(g, item, value, _indicator_meaning(g, item)) for g, item, value in table.values.tolist()]
    doc.add_heading("가격 지표", level=2)
    _table(doc, ["구분", "항목", "값", "뜻"], rows, widths_mm=[20, 42, 48, 64])      # v1.6: 숫자 우측은 5장 재무 표만
    return engine


# ===========================================================================
# 4. 앞으로의 방향
# ===========================================================================

def _outlook_section(doc, d, easy, ai):
    doc.add_heading(SECTION_TITLES[3], level=1)
    doc.add_heading("시나리오 3개", level=2)
    rows = [(s["시나리오"], s["발동 조건"], s["지금 상태에서의 거리"]) for s in d["시나리오"]]
    if rows:
        _table(doc, ["이름", "발동 조건", "지금 상태에서의 거리"], rows, widths_mm=[16, 104, 50], keep=True)
        _caption(doc, "발동 조건은 1장 반전 조건 표와 같은 경계값입니다. 확률·목표 가격·기간은 정하지 않습니다.")
    else:
        doc.add_paragraph("시나리오를 계산할 데이터가 부족합니다.")
    parsed = _ai_result(doc, ai, "scenario") if d["시나리오"] else None
    if parsed is not None:
        for name in narrator.SCENARIO_NAMES:
            if parsed.get(name):
                _labeled(doc, name, parsed[name])
            else:
                _ai_missing(doc, "scenario", name)

    doc.add_heading("다음 확인 시점", level=2)
    doc.add_paragraph(d["확인시점"]["문장"])

    doc.add_heading("지켜볼 숫자 3가지", level=2)
    for item in easy["장"][6]["문장"]:
        doc.add_paragraph(item)


# ===========================================================================
# 5. 재무 상세
# ===========================================================================

def _ratio_value(ratios, key, unit, note_key=None):
    """카드 값 문자열. 기준 사유(당기순이익 기준 등)가 있으면 뒤에 붙인다."""
    value = ratios.get(key)
    if value is None:
        text = "-"
    elif isinstance(value, str):
        text = value                     # PER '적자'
    else:
        text = f"{value:,.1f}{unit}"
    note = financials.NOTE_TEXT.get(ratios.get(note_key)) if note_key else None
    return f"{text} ({note})" if note else text


def _key_metrics(doc, ind, fin, is_finance):
    """핵심 지표 표(항목·값 2쌍씩): 현재가, 1개월·1년 수익률, PER, PBR, ROE, 부채비율, 영업이익률(지침 v1.1 4장 5)."""
    ret = ind.get("기간수익률") or {}
    ratios = (fin or {}).get("비율") or {}
    items = [
        ("현재가", f"{ind['현재가']:,}원"),
        ("1개월 수익률", _pct(ret.get("1개월"))),
        ("1년 수익률", _pct(ret.get("1년"))),
        ("PER", _ratio_value(ratios, "PER", "배", "PER기준")),
        ("PBR", _ratio_value(ratios, "PBR", "배", "PBR기준")),
        ("ROE", _ratio_value(ratios, "ROE", "%", "ROE기준")),
        ("부채비율", _ratio_value(ratios, "부채비율", "%")),
        ("영업이익률", "해당 없음" if is_finance else _ratio_value(ratios, "영업이익률", "%")),
    ]
    rows = [(items[i][0], items[i][1], items[i + 1][0], items[i + 1][1]) for i in range(0, len(items), 2)]
    _table(doc, ["항목", "값", "항목", "값"], rows, widths_mm=[30, 55, 30, 55], right_cols=(1, 3))
    note = f"현재가·수익률: {ind['기준일']} 정규장 종가 기준"
    if ratios.get("기간"):
        note = (f"PER·ROE·영업이익률: 최근 4분기 합산({ratios['기간']}) · PBR·부채비율: {ratios['기준분기']} 말 · "
                "PER·PBR은 우선주 포함 시가총액, ROE는 평균 자기자본 기준 · " + note)
    _caption(doc, note)


def _pct(value, digits=2):
    return "-" if value is None else f"{value:+.{digits}f}%"


def _financial_section(doc, ind, fin, easy, is_finance, tmpdir):
    doc.add_heading(SECTION_TITLES[4], level=1)
    ch = easy["장"]
    doc.add_heading("핵심 지표", level=2)
    _key_metrics(doc, ind, fin, is_finance)
    doc.add_heading("회사의 빚은 어느 정도인가요?", level=2)
    for sentence in ch[4]["문장"]:
        doc.add_paragraph(sentence)
    doc.add_heading("주가와 회사 이익을 함께 보면?", level=2)
    for sentence in ch[5]["문장"]:
        doc.add_paragraph(sentence)

    if not fin or (not fin.get("연간") and not fin.get("분기")):
        doc.add_paragraph("재무 데이터를 불러오지 못했습니다.")
        return []

    sales_name = fin.get("매출계정명") or "매출액"
    engines = []
    for title, items in (("연간 재무 (최근 3개 사업연도)", fin["연간"]), ("분기 재무 (최근 4분기, 3개월 값)", fin["분기"])):
        doc.add_heading(title, level=2)
        frame = financials.to_table(items, sales_name)
        if frame.empty:
            doc.add_paragraph("데이터 없음")
            continue
        cols = list(frame.columns)
        widths = [18] + [(TABLE_MM - 18) / (len(cols) - 1)] * (len(cols) - 1)
        _table(doc, cols, frame.values.tolist(), widths_mm=widths, right_cols=range(1, len(cols)))
    _caption(doc, "단위: 억 원 · 분기 손익은 해당 분기 3개월 값(4분기 = 연간 − 1~3분기 합) · "
                  f"출처: 금융감독원 전자공시시스템, {fin.get('연결구분') or '연결'}재무제표 기준")

    doc.add_heading("매출·영업이익 추이", level=2)
    for label, items, filename in (("연간", fin["연간"], "fin_annual.png"), ("분기", fin["분기"], "fin_quarter.png")):
        frame = financials.to_chart_frame(items)
        if frame.empty or (frame["매출액"].isna().all() and frame["영업이익"].isna().all()):
            continue
        path = os.path.join(tmpdir, filename)
        engines.append(charts.save_fin_png(frame, sales_name, path, report=True))
        _figure(doc, f"{label} 실적 추이", path, SOURCE_FIN)
        _caption(doc, f"{label} {charts.fin_chart_label(frame, sales_name)}")
    return engines


# ===========================================================================
# 부록
# ===========================================================================

def _glossary_section(doc, easy):
    doc.add_heading(SECTION_TITLES[5], level=1)
    doc.add_heading("용어", level=2)
    _table(doc, ["용어", "풀이"], list(easy_read.TERM_GLOSS.items()), widths_mm=[50, 120], keep=True)
    doc.add_heading(easy_read.TABLE_TITLE, level=2)
    _table(doc, ["지표", "이 종목 값", "뜻"], easy["풀이표"], widths_mm=[42, 38, 94], keep=True)


def guide_versions_text():
    return (f"리포트 구성 지침 {direction.REPORT_GUIDE_VERSION} · "
            f"쉽게 읽기 지침 {easy_read.EASY_READ_GUIDE_VERSION}")


def _ai_source_line(ai):
    if ai is None:
        return "AI 해설: 넣지 않음(API 키 없음)"
    parts = []
    for call in narrator.CALL_ORDER:
        name = narrator.CALLS[call]["이름"]
        if call in ai["오류"]:
            parts.append(f"{name} 호출 실패")
            continue
        r = ai["결과"][call]
        parts.append(f"{name} {r['model']}({r['시도경로']}{'' if r['통과'] else ', 검증 일부 미통과'})")
    return ("AI 해설: " + " · ".join(parts)
            + f" - 파이썬이 정한 판정·근거를 리포트 구성 지침 {direction.REPORT_GUIDE_VERSION} 6장 규칙으로 풀어 씀")


def _sources(doc, ind, fin, group, events, ai, written):
    doc.add_heading(SECTION_TITLES[6], level=1)
    label = (fin or {}).get("연결구분") or "연결"
    lines = [
        f"{dl.base_date_note(ind['기준일'], written)} - 한국시간 15시 40분 이전 작성이면 당일 장중 일봉을 모든 계산에서 빼고 "
        "직전 거래일을 기준일로 씀(리포트 구성 지침 5.0)",
        # 지침 v1.6 4장 부록 B: 수집 도구 이름 대신 자료를 낸 기관의 공식 명칭
        f"가격: 한국거래소 정규장 종가(시간외 거래 미반영), 기준일 {ind['기준일']}, 가격 차트 1년",
        "시장 지수: 한국거래소 코스피·코스닥 지수(초과 등락·시장 전체 움직임 계산)",
        "시가총액: 한국거래소 시가총액(보통주 + 우선주)",
        f"재무: 금융감독원 전자공시시스템 정기보고서 재무제표, {label}재무제표 기준",
        f"업종: 금융감독원 기업개황 업종코드 기반 업종그룹({group or '미상'})",
        "공시: 금융감독원 전자공시시스템 공시목록(정기공시·주요사항·지분공시·거래소공시), 기준일 전 1년",
        "뉴스: 국내 언론 보도(사건 기간별) - 제목·날짜·링크만 사용",
        f"판정: 리포트 구성 지침 {direction.REPORT_GUIDE_VERSION}에 따라 파이썬이 계산"
        "(방향 지시계·반전 조건·사건 선정과 근거 강도·다음 확인 시점·시나리오)",
        f"쉽게 읽기 문장: 쉽게 읽기 지침 {easy_read.EASY_READ_GUIDE_VERSION}에 따라 파이썬이 문장 틀로 생성(AI 미사용), "
        "용어 풀이는 리포트 전체에서 처음 나오는 곳에 한 번 붙임",
        _ai_source_line(ai),
    ]
    if events is None:
        lines.append("공시·뉴스 사건 자료: 불러오지 못함")
    for line in lines:
        _md_runs(doc.add_paragraph(style="List Bullet"), line)
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    _run_font(p.add_run("지침 버전: "), bold=True)
    _run_font(p.add_run(guide_versions_text()))
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    _run_font(p.add_run(REPORT_DISCLAIMER), size=NOTE_PT, color=GRAY)


# ===========================================================================
# 용어 풀이 (지침 v1.1 6.4) - 최종 리포트 순서 기준
# ===========================================================================

def gloss_scope(doc):
    """용어 풀이 대상 문단: 표 밖(본문 최상위)의 'Normal' 문단. 순서 = 최종 리포트 순서.

    표(방향 지시계·반전 조건·사건·시나리오·재무 표)와 AI 자리 회색 박스(1칸 표), 제목, 캡션(NOTE_STYLE),
    출처 목록(List Bullet)은 들어가지 않는다.
    """
    return [p for p in doc.paragraphs if p.style.name == "Normal" and p.text.strip()]


def apply_report_gloss(doc):
    """조립이 끝난 리포트 전체를 앞에서부터 훑어 용어가 처음 나오는 곳에만 고정 풀이를 붙인다.

    easy_read.apply_gloss는 문장 틀에 붙어 온 풀이 괄호를 먼저 모두 떼고 다시 붙이므로,
    쉽게 읽기 섹션 순서로 붙어 있던 풀이는 리포트 순서 기준으로 옮겨진다. run 단위로 바꿔 굵게 등 서식은 유지한다.
    """
    runs = [r for p in gloss_scope(doc) for r in p.runs if r.text]
    if not runs:
        return
    glossed = easy_read.apply_gloss([[r.text for r in runs]])[0]
    for run, text in zip(runs, glossed):
        if run.text != text:
            run.text = text


def check_report_gloss(path):
    """체크리스트 10번: 용어 첫 등장 괄호 풀이가 최종 리포트 순서 기준으로 한 번씩만 붙어 있는가.

    검사 범위는 gloss_scope와 같고, 용어·풀이 목록은 생성 코드와 따로 둔 easy_read.GLOSS_TERMS를 쓴다.
    반환: 문제 목록(비어 있으면 통과)
    """
    doc = Document(path)
    texts = [p.text for p in gloss_scope(doc)]
    return easy_read.check_term_gloss([{"문장": texts}])


# ===========================================================================
# 진입점
# ===========================================================================

# ===========================================================================
# v3 관문 (ControlTower _engine\v3_gate.py, verify 전용)
# ===========================================================================

# 게이트 도메인 프로파일: 주제 어휘만 담는다(v3_gate [새 리포트에 붙이는 법] 3).
# brands·off_topic 이 비어 있으면 C(브랜드 값 충돌)·D(오염 인용)는 건너뛰고 A·B·E·F 만 돈다.
V3_DOMAIN = {"name": "StockAI", "subject": "국내 주식 종목", "brands": [],
             "off_topic": [], "off_topic_exempt": []}


def _find_engine_dir(start):
    """start에서 상위 폴더로 올라가며 engine\\ 패키지가 든 _engine 을 찾는다. 없으면 None.

    NEW_REPORT_GUIDE 2-2 자동탐색과 같지만, 교재 독자 환경(_engine 없음)에서는 예외 대신 None을 돌려
    게이트만 건너뛴다.
    """
    for d in (start, *start.parents):
        cand = d / "_engine"
        if (cand / "engine").is_dir():
            return str(cand)
    return None


ENGINE_DIR = _find_engine_dir(Path(__file__).resolve().parent)


def run_v3_gate(path):
    """저장된 docx를 v3 관문에 통과시킨다(enforce=False: 문서는 고치지 않는다).

    결과는 docx 옆 _gate_report.txt 에 이어 붙인다. 반환: {"치명", "경고", "통과", "로그", "항목"} 또는
    {"건너뜀": 사유}. 항목 = [(검사, 위치, 근거, 내용, 심각도), ...]
    """
    if ENGINE_DIR is None:
        return {"건너뜀": "_engine 을 찾지 못함(ControlTower 밖 환경)"}
    try:
        if ENGINE_DIR not in sys.path:
            sys.path.insert(0, ENGINE_DIR)
        from v3_gate import run_gate
    except Exception as exc:
        return {"건너뜀": f"v3_gate 를 불러오지 못함: {type(exc).__name__}: {exc}"}
    try:
        r = run_gate(path, domain=V3_DOMAIN, enforce=False, verbose=False, log=True)
    except Exception as exc:
        return {"건너뜀": f"게이트 실행 실패: {type(exc).__name__}: {exc}"}
    return {"치명": r["critical"], "경고": r["warning"], "통과": r["passed"], "로그": r["log"],
            "항목": r["findings"]}


def _output_path(name, code, today, out_dir, overwrite=False):
    """output/{종목명}_{코드}_{YYYYMMDD}.docx. 같은 이름이 있으면 _2, _3 ... (overwrite=True면 덮어쓴다)"""
    os.makedirs(out_dir, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|\s]+', "_", str(name)).strip("_") or "종목"
    stem = f"{safe}_{code}_{today.strftime('%Y%m%d')}"
    path = os.path.join(out_dir, stem + ".docx")
    if overwrite:
        return path
    n = 2
    while os.path.exists(path):
        path = os.path.join(out_dir, f"{stem}_{n}.docx")
        n += 1
    return path


def load_events(code, name, market):
    """events.build_events(기준일별 파일 캐시). 실패하면 None."""
    try:
        return ev_mod.build_events(code, name, market)
    except Exception:
        return None


def build_report(picked, ind=None, out_dir=OUTPUT_DIR, overwrite=False, events=None, use_ai=True, force_ai=False,
                 reuse_ai=()):
    """Word 리포트를 만들어 저장한다.

    picked: 종목코드·종목명·시장이 든 dict(또는 pandas Series)
    ind: 지표 결과 객체(없으면 새로 계산). events: events.build_events 결과(없으면 새로 불러온다).
    use_ai: AI 해설 3개 호출(narrator.narrate, 입력 해시가 같은 저장본은 재사용). force_ai=True면 저장본 무시.
    reuse_ai: 입력 해시만 같으면 프롬프트가 바뀌어도 저장본을 쓸 호출 이름들(예: ("conclusion", "scenario")).
    반환: {"path", "차트엔진": {"가격", "재무"}, "방향": direction.build 결과, "쉽게읽기": easy_read.build 결과,
           "ai": narrator.narrate 결과(없으면 None), "gate": run_v3_gate 결과,
           "지침버전경고": guides.check_versions() 결과(일치하면 빈 목록)}
    """
    code = str(picked["종목코드"]).zfill(6)
    name, market = picked["종목명"], picked["시장"]
    today = dl.now_kst()                                 # 작성 시각(한국시간)

    ind = ind or indicators.compute(code, name, market)
    if ind is None:
        raise RuntimeError("지표를 계산할 데이터가 부족합니다.")
    fin = None
    if keys.has_dart_key():
        try:
            fin = financials.load_financials(code, name)
        except Exception:
            fin = None
    if events is None:
        events = load_events(code, name, market)
    group = (ind.get("업종대비") or {}).get("업종그룹")
    finance = easy_read.is_finance(ind, fin)
    easy = easy_read.build(ind, fin)
    d = direction.build(ind, fin, events)
    ai = narrator.narrate(ind, fin, d, easy, force=force_ai, reuse_calls=reuse_ai) if use_ai else None
    df = load_chart_frame(code, ind["기준일"])

    doc = _setup_document(f"{name} ({code}) · 기준일 {ind['기준일']}")
    _cover(doc, name, code, market, group, ind["기준일"], today, easy["장"][7]["문장"], easy["장"][0]["문장"])
    _toc(doc)                                            # 지침 v1.6 12.4: 표지 다음 쪽 목차(쪽번호 없음)
    with tempfile.TemporaryDirectory() as tmpdir:       # 그림은 문서에 넣는 순간 복사되므로 바로 지워도 된다
        _exec_section(doc, d, ai)
        _why_section(doc, d, easy, events, ai)
        price_engine = _price_section(doc, ind, d, easy, df, name, tmpdir)
        _outlook_section(doc, d, easy, ai)
        fin_engines = _financial_section(doc, ind, fin, easy, finance, tmpdir)
        _glossary_section(doc, easy)
        _sources(doc, ind, fin, group, events, ai, today)
        apply_report_gloss(doc)                          # 최종 순서 기준 첫 등장 풀이(지침 6.4)
        _finalize_v3(doc)                                # 지침 v1.6 12.1: 문단마다 줄간격 1.0·run마다 규격 서체
        path = _output_path(name, code, today, out_dir, overwrite)
        doc.save(path)

    gate = run_v3_gate(path)                             # 저장 직후 v3 관문(verify 전용, 로그는 docx 옆)
    return {"path": path, "차트엔진": {"가격": price_engine, "재무": fin_engines}, "방향": d, "쉽게읽기": easy, "ai": ai,
            "gate": gate, "지침버전경고": guides.check_versions()}
