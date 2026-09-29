# -*- coding: utf-8 -*-
"""
app.py - 주식 분석 도구 (Streamlit 메인 화면)

탭 구성
 1) 종목 분석      : [리포트 구성 지침] 맨 위 방향 지시계 박스(신호 3개 + 종합 상태, direction.py)
                     [1단계] 종목 검색 + 지표 카드 + 캔들차트
                     [4단계] DART 재무 표·차트·비율 카드
                     [3단계] 가격 지표 표 (기존 AI 분석 7개 소제목 호출은 폐지 - 지침 8장)
                     화면에서는 사실 문장 행(1~N번)을 보이지 않는다
화면 전용 표기(2026-09-28): 쉽게 읽기 장 제목·표 제목·열 이름은 APP_LABELS 로 화면에 그릴 때만 바꾼다.
  리포트(report.py)·지침·easy_read.py 원문은 그대로다. 화면 차트는 화면 표와 같은 테두리(테마 테두리색·1px 실선)의
  상자(_chart_box)에 담는다.
화면 차트 확대 왜곡 수정(2026-09-29): 종목 분석 탭 차트는 가로 1100px(APP_CHART_WIDTH)로 통일한다. matplotlib 그림은
  charts.app_fig 로 1100px 캔버스에 그려 st.image(width=1100)으로 원본 크기 표시(확대 없음, 좁은 화면에서만 축소).
  st.pyplot·width="stretch" 이미지는 쓰지 않는다. 가격·실적 plotly 차트도 width=1100, 히트맵은 stretch·높이 600.
                     [5단계] Word 리포트 생성·다운로드 (AI 해설 3개: narrator.py, 결론 Sonnet / 실적·사건·시나리오 Haiku)
 2) 시장 히트맵    : [2단계] 코스피/코스닥 시총 상위 200종목 트리맵
 3) 보유종목 히트맵 : [2단계] 내 보유종목 평가금액 트리맵
                     [보유종목 입력 개편] 드롭다운 추가 폼 + 수량·단가 수정 / 선택 삭제 표
사이드바: 종목 목록(data/stock_master.csv) 갱신 버튼·마지막 갱신일
"""

import hmac
import io
import os

import pandas as pd
import streamlit as st

import charts
import data as dl
import direction
import easy_read
import financials
import heatmap as hm
import indicators
import industry
import keys
import narrator
import report

MARKET_LABELS = {"코스피": "KOSPI", "코스닥": "KOSDAQ"}

# 모든 탭의 가격 표시 근처에 같은 문구를 쓴다(가격 소스 오해 방지).
PRICE_CAPTION = ("가격·등락률은 정규장 종가 기준 (시간외 거래 미반영) · "
                 "15:40 이전에는 당일 장중 시세를 쓰지 않고 직전 거래일 종가를 기준일로 씀")

# 면책 문구는 화면과 Word 리포트가 같은 문구를 쓴다(리포트 구성 지침 4장 부록 B).
DISCLAIMER = report.REPORT_DISCLAIMER

# 화면 전용 표기: 원문(쉽게 읽기 지침·리포트 문구) -> 화면 라벨. 화면에 출력할 때만 치환한다.
APP_LABELS = {
    "최근 주가는 어떻게 움직였나요?": "최근 주가 동향",
    "회사는 돈을 벌고 있나요?": "실적 분석",
    "회사의 빚은 어느 정도인가요?": "부채 분석",
    "주가와 회사 이익을 함께 보면?": "이익률 분석",
    "앞으로 지켜볼 숫자 3가지": "주요 관측 데이터",
    "한 줄 정리": "핵심 정리",
    "숫자 풀이": "데이터 분석",
    "이 종목 값": "지표값",
    "뜻": "지표 분석",
    "가격 지표": "데이터별 지표 동향",
}


def _label(text):
    """화면 표시용 라벨(APP_LABELS에 없으면 원문 그대로)."""
    return APP_LABELS.get(text, text)


def _chart_box():
    """화면 차트 상자: 화면 표(st.dataframe)와 같은 테마 테두리색·1px 실선. 모든 차트를 같은 폭으로 담는다."""
    return st.container(border=True)


# 종목 분석 탭 차트 가로 폭(px). matplotlib 그림은 이 크기로 그려 원본 크기로 표시(확대 없음, 좁은 화면에서만 축소).
# plotly 차트도 같은 폭으로 그린다. 높이: 가격 640(가격 420 + 거래량 220), 실적 320, 히트맵 600.
APP_CHART_WIDTH = charts.APP_WIDTH_PX
APP_PRICE_HEIGHT = 640
APP_FIN_HEIGHT = 320
APP_HEATMAP_HEIGHT = 600


# ===========================================================================
# [4단계] 재무 영역
# ===========================================================================

# 비율 카드 사유 표기 (지배주주 기준이면 표기 없음)
BASIS_NOTE = {
    "당기순이익": " (당기순이익 기준)",
    "자본총계": " (자본총계 기준)",
    "데이터부족": " (데이터 부족)",
}


def _fmt_ratio(value, suffix=""):
    if value is None:
        return "-"
    if isinstance(value, str):             # PER '적자'
        return value
    return f"{value:,.1f}{suffix}"


def _industry_group(code):
    """업종 매핑에서 종목의 업종그룹을 찾는다(없으면 None)."""
    imap = industry.load_industry_map()
    if imap.empty:
        return None
    hit = imap[imap["종목코드"].astype(str).str.zfill(6) == str(code).zfill(6)]
    return hit.iloc[0]["업종그룹"] if not hit.empty else None


def render_financial_section(picked):
    """DART 재무 표(연간/분기) + 차트 + 비율 카드를 그린다."""
    st.divider()
    st.subheader("📊 재무")

    if not keys.has_dart_key():
        st.info("DART API 키가 없어 재무 정보를 표시할 수 없습니다. api_secrets.py의 DART_API_KEY를 채워 주세요.")
        return

    code = str(picked["종목코드"])
    with st.spinner("DART 재무 데이터를 불러오는 중입니다..."):
        fin = financials.load_financials(code, picked["종목명"])

    if not fin["연간"] and not fin["분기"]:
        st.warning("DART에서 재무 데이터를 찾지 못했습니다. (신규 상장, 리츠·스팩 등은 주요계정이 없을 수 있습니다)")
        return

    sales_name = fin.get("매출계정명") or "매출액"
    ratios = fin["비율"]

    # 지배주주 기준으로 계산하지 못했으면 카드 이름에 사유를 붙인다.
    per_label = "PER" + BASIS_NOTE.get(ratios.get("PER기준"), "")
    pbr_label = "PBR" + BASIS_NOTE.get(ratios.get("PBR기준"), "")
    roe_label = "ROE" + BASIS_NOTE.get(ratios.get("ROE기준"), "")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(per_label, _fmt_ratio(ratios.get("PER"), "배"))
    c2.metric(pbr_label, _fmt_ratio(ratios.get("PBR"), "배"))
    c3.metric(roe_label, _fmt_ratio(ratios.get("ROE"), "%"))
    c4.metric("부채비율", _fmt_ratio(ratios.get("부채비율"), "%"))
    if _industry_group(code) == "금융":
        c4.caption("금융업은 예금·보험부채 구조상 부채비율이 높게 나타나며 일반 기업과 직접 비교하지 않습니다")
    c5.metric("영업이익률", _fmt_ratio(ratios.get("영업이익률"), "%"))
    if ratios.get("기간"):
        st.caption(f"최근 4분기({ratios['기간']}) 합산 기준, 재무상태는 {ratios['기준분기']} 말")
    prefs = ", ".join(name for name, _ in ratios.get("우선주") or [])
    st.caption("PER·PBR은 우선주 포함 시가총액, ROE는 평균 자기자본 기준"
               + (f" (합산 우선주: {prefs})" if prefs else ""))

    t_year, t_quarter = st.tabs(["연간", "분기"])
    with t_year:
        st.dataframe(financials.to_table(fin["연간"], sales_name), width="stretch", hide_index=True)
    with t_quarter:
        st.dataframe(financials.to_table(fin["분기"], sales_name), width="stretch", hide_index=True)
        st.caption("분기 손익은 해당 분기 3개월 값 · 4분기 = 연간 − (1~3분기 합)")

    basis = st.radio("차트 기간", ["연간", "분기"], horizontal=True, key=f"fin_basis_{code}")
    frame = financials.to_chart_frame(fin[basis])
    if frame["매출액"].isna().all() and frame["영업이익"].isna().all():
        st.info("차트로 표시할 매출·영업이익 계정이 없습니다.")
    else:
        with _chart_box():
            st.plotly_chart(charts.build_fin_chart(frame, sales_name, height=APP_FIN_HEIGHT), width=APP_CHART_WIDTH)

    st.caption(f"출처: 금융감독원 DART, {fin['연결구분'] or '연결'}재무제표 기준 · 단위 억 원 · "
               f"수집 {fin['수집시각']}")


# ===========================================================================
# [쉽게 읽기] 초보자용 블록 (AI 분석 위)
# ===========================================================================

def _png_bytes(draw):
    """matplotlib 그림을 메모리 PNG로 만든다(st.image용). draw(buffer)로 그린다."""
    buffer = io.BytesIO()
    draw(buffer)
    return buffer.getvalue()


def render_easy_section(picked):
    """쉽게 읽기: docs/쉽게읽기_작성지침.md(현재 버전 easy_read.EASY_READ_GUIDE_VERSION)의 8개 장 + 숫자 풀이 표. 리포트와 같은 내용(AI 미사용).
    장 제목·표 제목·열 이름은 화면에 그릴 때만 APP_LABELS 로 바꾼다."""
    st.divider()
    st.subheader("🔰 주식평가")                     # 앱 화면 제목만 변경(리포트 문서는 그대로)
    code = str(picked["종목코드"])
    ind = indicators.compute(code, picked["종목명"], picked["시장"])
    if ind is None:
        st.info("지표를 계산할 데이터가 부족합니다.")
        return
    fin = None
    if keys.has_dart_key():
        try:
            fin = financials.load_financials(code, picked["종목명"])
        except Exception:
            fin = None

    result = easy_read.build(ind, fin)
    st.caption("주식을 처음 보는 분을 위해 정해진 순서와 문장 틀로 숫자의 뜻을 풀었습니다. "
               f"(쉽게 읽기 지침 {easy_read.EASY_READ_GUIDE_VERSION}, AI 미사용)")
    for chapter in result["장"]:
        st.markdown(f"**{_label(chapter['제목'])}**")
        figure = chapter.get("그림")
        if figure and figure["종류"] == "범위":
            with _chart_box():
                st.image(_png_bytes(lambda buf: charts.save_range_png(figure["최저"], figure["최고"], figure["현재가"],
                                                                       buf, title=figure["제목"], app=True)),
                         width=APP_CHART_WIDTH)
        elif figure and figure["종류"] == "수익률" and figure["항목"]:
            with _chart_box():
                st.image(_png_bytes(lambda buf: charts.save_returns_png(figure["항목"], buf, app=True)),
                         width=APP_CHART_WIDTH)
        st.write("\n\n".join(chapter["문장"]))
    st.markdown(f"**{_label(easy_read.TABLE_TITLE)}**")
    st.dataframe(pd.DataFrame(result["풀이표"], columns=[_label(c) for c in ("지표", "이 종목 값", "뜻")]),
                 hide_index=True, width="stretch")


# ===========================================================================
# [리포트 구성 지침] 방향 지시계
# ===========================================================================

def render_direction_box(picked):
    """종목 분석 탭 맨 위: 신호 3개(가격 추세 / 실적 흐름 / 거래 관심도) + 종합 상태(지침 5.1~5.4)."""
    code = str(picked["종목코드"])
    ind = indicators.compute(code, picked["종목명"], picked["시장"])
    if ind is None:
        return
    fin = None
    if keys.has_dart_key():
        try:
            fin = financials.load_financials(code, picked["종목명"])
        except Exception:
            fin = None
    box = direction.indicator(ind, fin)
    with st.container(border=True):
        st.markdown(f"**방향 지시계** · 기준일 {ind['기준일']}")
        cols = st.columns(3)
        for col, key in zip(cols, ("가격 추세", "실적 흐름", "거래 관심도")):
            sig = box[key] or {"판정": "판정 불가", "근거": "이동평균을 계산할 데이터가 부족합니다"}
            col.caption(key)
            col.markdown(f"### {sig['판정']}")
            col.caption(sig["근거"])
        st.markdown(f"**종합 상태: {box['종합 상태']}**")
        st.caption(f"리포트 구성 지침 {direction.REPORT_GUIDE_VERSION} 규칙으로 파이썬이 판정(AI 미사용)")


FACT_GROUP = "사실 문장"          # indicators.to_table 의 AI 입력 근거 행(구분 열 값) - 화면에서 뺀다


def render_indicator_section(picked):
    """가격 지표 표(화면 라벨 '데이터별 지표 동향'). 사실 문장 행(1~N번)은 화면에 보이지 않는다."""
    st.divider()
    st.subheader(f"📐 {_label('가격 지표')}")
    ind = indicators.compute(str(picked["종목코드"]), picked["종목명"], picked["시장"])
    if ind is None:
        st.warning("지표를 계산할 만큼 일봉 데이터가 충분하지 않습니다.")
        return
    st.caption(f"기준일 {ind['기준일']} · 거래일 {ind['거래일수']}일 · {PRICE_CAPTION}")
    table = indicators.to_table(ind)
    st.dataframe(table[table["구분"] != FACT_GROUP], width="stretch", hide_index=True, height=430)


def render_stock_tab(picked, period_label):
    """[1단계 + 3단계] 종목 분석 탭 본문을 그린다."""
    if picked is None:
        st.info("왼쪽 사이드바에서 종목을 검색해 주세요. 예) 삼성전자, OCI, 카카오")
        return

    df = dl.load_ohlcv(picked["종목코드"], period_label)
    if df.empty:
        st.error(
            f"{picked['종목명']}({picked['종목코드']})의 시세를 가져오지 못했습니다.\n\n"
            "신규 상장·거래정지 종목이거나 일시적인 데이터 수집 오류일 수 있습니다. "
            "기간을 바꾸거나 잠시 후 다시 시도해 주세요."
        )
        return

    info = dl.summarize(df)
    if info is None:
        st.warning("해당 기간에 거래된 날이 없습니다. 휴장 기간일 수 있으니 기간을 넓혀 보세요.")
        return

    st.subheader(f"{picked['종목명']} ({picked['종목코드']}, {picked['시장']})")
    render_direction_box(picked)
    st.caption(f"기준일 {info['최근일자']} · 조회기간 {period_label} · 거래일 {len(df)}일")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("현재가(최근 종가)", f"{info['현재가']:,.0f}원",
              f"{info['전일대비']:+,.0f}원 ({info['등락률']:+.2f}%)")
    c2.metric(f"{period_label} 최고", f"{info['기간최고']:,.0f}원")
    c3.metric(f"{period_label} 최저", f"{info['기간최저']:,.0f}원")
    c4.metric("평균 거래량", f"{info['평균거래량']:,.0f}주")
    st.caption(PRICE_CAPTION)

    with _chart_box():
        st.plotly_chart(charts.build_price_chart(df, f"{picked['종목명']} 일봉 ({period_label})",
                                                 height=APP_PRICE_HEIGHT), width=APP_CHART_WIDTH)

    with st.expander("원본 데이터 보기 (최근 10일)"):
        st.dataframe(df.tail(10).iloc[::-1].style.format("{:,.0f}"), width="stretch")

    render_financial_section(picked)
    render_easy_section(picked)
    render_indicator_section(picked)
    render_report_section(picked)
    st.caption(DISCLAIMER)


# ===========================================================================
# [5단계] Word 리포트
# ===========================================================================

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _ai_caption(ai):
    """AI 해설 3개의 모델·시도 경로·비용·검증 결과를 한 줄씩 보여 준다."""
    if ai is None:
        st.info("Claude API 키가 없어 AI 해설 없이 저장했습니다(해설 자리는 회색 박스). "
                "api_secrets.py에 ANTHROPIC_API_KEY를 입력하세요.")
        return
    for call in narrator.CALL_ORDER:
        name = narrator.CALLS[call]["이름"]
        if call in ai["오류"]:
            st.error(f"{name}: 호출 실패 - {ai['오류'][call]}")
            continue
        r = ai["결과"][call]
        source = "저장본 재사용(추가 비용 없음)" if r.get("cached") else f"새로 호출 · 비용 약 {r['cost_krw']:,.2f}원"
        line = f"{name} · {r['model']} · {r['시도경로']} · {source}"
        if r["통과"]:
            st.caption(line + " · 검증 통과")
        else:
            st.warning(line + " · 검증 미통과: " + ", ".join(narrator.failed_items(r)))
    st.caption(f"이번 추가 비용 약 {ai['이번비용']:,.2f}원 (환율 {narrator.USD_KRW:,.0f}원/USD 기준)")


def _gate_caption(gate):
    """v3 관문(verify 전용) 결과: 치명·경고 건수와 로그 위치(리포트 구성 지침 v1.6 12.5)."""
    if not gate:
        return
    if "건너뜀" in gate:
        st.caption(f"v3 관문: 건너뜀 - {gate['건너뜀']}")
        return
    text = (f"v3 관문(서식·표현 검사, 문서는 고치지 않음): 치명 {gate['치명']}건 · 경고 {gate['경고']}건"
            f" · 로그 {gate['로그']}")
    if gate["치명"]:
        st.warning(text)
    else:
        st.caption(text)


def render_report_section(picked):
    """'Word 리포트 생성' 버튼: 파이썬 판정 + AI 해설 3개(입력 해시가 같은 저장본은 재사용)."""
    st.divider()
    st.subheader("📄 Word 리포트")
    code = str(picked["종목코드"])
    state_key = f"report::{code}"
    try:
        c1, c2, _ = st.columns([1, 1, 3])
        run = c1.button("Word 리포트 생성", key=f"report_btn_{code}",
                        help="파이썬 규칙으로 판정하고, AI 해설 3개를 붙여 저장합니다(저장본이 있으면 재사용)")
        again = c2.button("AI 해설 다시 쓰기", key=f"report_again_{code}", disabled=not keys.has_api_key(),
                          help="저장된 AI 해설을 무시하고 3개 호출을 다시 합니다(API 비용 발생)")
        if run or again:
            with st.spinner("Word 리포트를 작성하는 중입니다(공시·뉴스 사건 수집, AI 해설 포함)..."):
                ind = indicators.compute(code, picked["종목명"], picked["시장"])
                if ind is None:
                    st.error("지표를 계산할 데이터가 부족해 리포트를 만들 수 없습니다.")
                    return
                built = report.build_report(picked, ind=ind, force_ai=bool(again))
            st.session_state[state_key] = built["path"]
            st.success(f"리포트를 저장했습니다: {built['path']}")
            _ai_caption(built["ai"])
            _gate_caption(built.get("gate"))
            for warning in built.get("지침버전경고") or []:
                st.warning(warning)
    except Exception as exc:
        st.error(f"리포트 생성에 실패했습니다: {exc}")
        return

    path = st.session_state.get(state_key)
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            st.download_button("리포트 다운로드 (.docx)", data=f.read(), file_name=os.path.basename(path),
                               mime=DOCX_MIME, key=f"report_dl_{code}")

    # AI 해설 모델·단가 안내(사이드바 'AI 해설' 코너에서 옮김, 모델은 리포트 구성 지침 8장에 고정)
    models = " · ".join(
        f"{narrator.CALLS[call]['이름']}: {narrator.MODELS[narrator.CALLS[call]['모델']]['label']}"
        f" (입력 ${narrator.MODELS[narrator.CALLS[call]['모델']]['input_per_mtok']:.2f} / "
        f"출력 ${narrator.MODELS[narrator.CALLS[call]['모델']]['output_per_mtok']:.2f}, 100만 토큰당)"
        for call in narrator.CALL_ORDER)
    st.caption(f"AI 해설 모델 - {models}")


# ===========================================================================
# [2단계] 시장 히트맵 탭
# ===========================================================================

def render_sector_view(table, period, clip, base_date):
    """업종별 보기: 업종그룹마다 박스 1개(크기 = 업종 시가총액 합계, 색 = 시가총액 가중 평균 등락률) + 업종별 표."""
    fig = hm.build_sector_treemap(table, clip=clip, color_label=f"{period} 등락률(%)", base_date=base_date,
                                  height=APP_HEATMAP_HEIGHT)
    if fig is None:
        st.error("히트맵을 그릴 데이터가 없습니다.")
        return
    with _chart_box():                                   # 화면 차트 공통 상자(표와 같은 테두리)
        st.plotly_chart(fig, width="stretch")

    summary = hm.sector_summary(table)
    view = summary[["업종", "종목 수", "등락률", "상승", "하락", "시가총액"]].copy()
    view["시가총액"] = view["시가총액"] / 1e12
    st.markdown("##### 업종별 표")
    st.dataframe(                                        # 열 머리를 누르면 정렬된다
        view, width="stretch", hide_index=True,
        column_config={
            "종목 수": st.column_config.NumberColumn("종목 수", format="%d"),
            "등락률": st.column_config.NumberColumn(f"{period} 등락률(%)", format="%+.2f",
                                                  help="업종 안 종목 등락률의 시가총액 가중 평균"),
            "상승": st.column_config.NumberColumn("상승 수", format="%d"),
            "하락": st.column_config.NumberColumn("하락 수", format="%d"),
            "시가총액": st.column_config.NumberColumn("시가총액(조)", format="%.2f"),
        },
    )


def render_market_tab():
    """코스피/코스닥 시가총액 상위 200종목 히트맵을 그린다."""
    st.subheader("시장 히트맵")

    view_mode = st.radio("보기", ["종목별", "업종별"], horizontal=True, key="hm_view")
    c1, c2 = st.columns([1, 3])
    with c1:
        market_kr = st.radio("시장", list(MARKET_LABELS.keys()), horizontal=True, key="hm_market")
    with c2:
        period = st.radio("기간", list(dl.HEATMAP_PERIODS.keys()), horizontal=True,
                          index=0, key="hm_period")

    market = MARKET_LABELS[market_kr]
    _days, clip = dl.HEATMAP_PERIODS[period]

    # 종목별 일봉을 받아야 하므로 진행률을 표시한다.
    progress_box = st.empty()
    bar = None

    def _progress(ratio, text):
        nonlocal bar
        if bar is None:
            bar = progress_box.progress(0.0, text=text)
        bar.progress(min(max(ratio, 0.0), 1.0), text=text)

    with st.spinner(f"{market_kr} {period} 데이터를 준비하는 중입니다..."):
        table, base_date = dl.build_market_heatmap_data(market, period, progress_cb=_progress)
    progress_box.empty()

    if table.empty:
        st.error("시장 데이터를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.")
        return

    up = int((table["등락률"] > 0).sum())
    down = int((table["등락률"] < 0).sum())
    flat = len(table) - up - down
    st.caption(
        f"{market_kr} 시가총액 상위 {len(table)}종목 · {period} 기준 · "
        f"상승 {up} / 하락 {down} / 보합 {flat} · 업종 {table['업종그룹'].nunique()}개"
    )
    st.caption(PRICE_CAPTION + " · 시가총액 = 상장주식수 × 기준일 종가")

    if view_mode == "업종별":
        render_sector_view(table, period, clip, base_date)
        return

    fig = hm.build_treemap(
        table, value_col="시가총액", color_col="등락률", clip=clip,
        size_label="시가총액", color_label=f"{period} 등락률(%)",
        base_date=base_date, hover_rows=hm.market_hover_rows(table), height=APP_HEATMAP_HEIGHT,
    )
    if fig is None:
        st.error("히트맵을 그릴 데이터가 없습니다.")
        return
    with _chart_box():                                   # 화면 차트 공통 상자(표와 같은 테두리)
        st.plotly_chart(fig, width="stretch")

    with st.expander("원본 데이터 보기 (등락률 순)"):
        view = table[["종목명", "종목코드", "업종그룹", "현재가", "등락률", "시가총액"]].copy()
        view["시가총액(조)"] = view["시가총액"] / 1e12
        view = view.drop(columns="시가총액").sort_values("등락률", ascending=False)
        st.dataframe(view, width="stretch", hide_index=True)


# ===========================================================================
# [2단계] 보유종목 히트맵 탭
# ===========================================================================

def _flash(kind, message):
    """다음 화면 갱신(st.rerun) 뒤에 보여 줄 안내 문구를 쌓아 둔다."""
    st.session_state.setdefault("holdings_flash", []).append((kind, message))


def _refresh_holdings_view():
    """저장 후 표를 새 내용으로 다시 그리도록 편집기 키를 바꾸고 화면을 갱신한다."""
    st.session_state["holdings_ver"] = st.session_state.get("holdings_ver", 0) + 1
    st.rerun()


@st.cache_data(show_spinner=False)
def _stock_options(ticker_df, market):
    """한 시장(KOSPI/KOSDAQ)의 드롭다운 표시 문자열 목록과 {표시 문자열: (종목코드, 종목명)} 사전.

    표시 형식 '삼성전자 (005930)' - 시장은 드롭다운 위 코스피/코스닥 선택으로 나눈다.
    """
    labels, lookup = [], {}
    part = ticker_df[ticker_df["시장"] == market] if not ticker_df.empty else ticker_df
    for code, name, market in part[["종목코드", "종목명", "시장"]].itertuples(index=False):
        label = dl.stock_label({"종목명": name, "종목코드": code, "시장": market})
        labels.append(label)
        lookup[label] = (code, name)
    return labels, lookup


def render_holdings_editor():
    """[보유종목 입력] 추가 폼(드롭다운) + 보유종목 표(수량·단가 수정, 선택 삭제). 저장된 보유종목을 돌려준다."""
    for kind, message in st.session_state.pop("holdings_flash", []):
        getattr(st, kind)(message)

    # --- 추가 폼: 종목은 드롭다운에서만 고른다(코드 직접 입력 없음) ---
    st.markdown("#### 보유종목 추가")
    ticker_df = dl.load_ticker_list()
    if ticker_df.empty:
        st.warning("종목 목록이 없습니다. 사이드바의 '종목 목록 갱신'을 눌러 주세요.")
    # 시장 선택은 폼 밖에 둔다(폼 안 위젯은 제출 전까지 화면을 다시 그리지 않아 드롭다운이 바뀌지 않는다).
    # key로 세션 동안 마지막 선택 시장을 기억하고, 추가 후 폼이 비워져도 시장 선택은 그대로 남는다.
    market_kr = st.radio("시장", list(MARKET_LABELS.keys()), horizontal=True, index=0, key="add_market")
    labels, lookup = _stock_options(ticker_df, MARKET_LABELS[market_kr])
    with st.form("add_holding_form", clear_on_submit=True):          # 추가 후 입력칸 초기화
        c1, c2, c3, c4 = st.columns([4, 1.4, 1.8, 1], vertical_alignment="bottom")
        pick = c1.selectbox(f"종목 ({market_kr} {len(labels):,}개)", labels, index=None, placeholder="종목명 입력",
                            key=f"add_pick_{MARKET_LABELS[market_kr]}", help="종목명이나 코드 일부를 입력하면 목록이 좁혀집니다")
        qty = c2.number_input("수량(주)", min_value=1, step=1, value=None, placeholder="1 이상", key="add_qty")
        price = c3.number_input("평균매수가(원)", min_value=1, step=100, value=None, placeholder="원 단위",
                                key="add_price")
        submitted = c4.form_submit_button("추가", type="primary", width="stretch")
    if submitted:
        problems = [msg for ok, msg in ((pick, "종목을 선택해 주세요."), (qty, "수량을 1 이상으로 입력해 주세요."),
                                        (price, "평균매수가를 원 단위로 입력해 주세요.")) if not ok]
        if problems:
            st.error(" ".join(problems))
        else:
            code, name = lookup[pick]
            saved, messages = dl.add_holding(code, name, int(qty), int(price))
            for message in messages:
                _flash("success" if message.startswith(name) else "warning", message)
            _refresh_holdings_view()

    # --- 보유종목 표: 수량·평균매수가만 수정, 행 추가는 폼으로만 ---
    st.markdown("#### 보유종목 목록")
    holdings = dl.load_holdings()
    if holdings.empty:
        st.info("보유종목이 없습니다. 위 '보유종목 추가'에서 종목을 고르거나 샘플을 불러오세요.")
        if st.button("샘플 불러오기", key="load_sample"):
            dl.load_sample_holdings()
            _flash("success", "샘플 보유종목을 불러왔습니다.")
            _refresh_holdings_view()
        return holdings

    view = holdings.copy()
    view.insert(0, "삭제", False)
    edited = st.data_editor(
        view, num_rows="fixed", hide_index=True, width="stretch",
        key=f"holdings_editor_{st.session_state.get('holdings_ver', 0)}",
        disabled=["종목코드", "종목명"],
        column_config={
            "삭제": st.column_config.CheckboxColumn("삭제", help="지울 종목을 고른 뒤 '선택 삭제'"),
            "종목코드": st.column_config.TextColumn("종목코드"),
            "종목명": st.column_config.TextColumn("종목명"),
            "수량": st.column_config.NumberColumn("수량(주)", min_value=1, step=1, format="%d"),
            "평균매수가": st.column_config.NumberColumn("평균매수가(원)", min_value=1, step=1, format="%.0f"),
        },
    )
    b1, b2, b3, _ = st.columns([1, 1, 1, 3])
    if b1.button("저장", type="primary", key="save_holdings", help="표에서 고친 수량·평균매수가를 저장합니다"):
        saved, warns = dl.update_holdings(edited)
        for w in warns:
            _flash("warning", w)
        _flash("success", f"{len(saved)}개 종목을 저장했습니다.")
        _refresh_holdings_view()
    if b2.button("선택 삭제", key="delete_holdings"):
        codes = edited.loc[edited["삭제"] == True, "종목코드"].tolist()      # noqa: E712 (체크박스 열)
        if not codes:
            st.warning("삭제할 종목의 '삭제' 칸을 먼저 체크해 주세요.")
        else:
            saved, removed = dl.delete_holdings(codes)
            _flash("success", f"{', '.join(removed)} 을(를) 삭제했습니다. 남은 종목 {len(saved)}개.")
            _refresh_holdings_view()
    if b3.button("샘플 불러오기", key="load_sample", help="현재 보유종목을 교재용 샘플로 바꿉니다"):
        dl.load_sample_holdings()
        _flash("success", "샘플 보유종목을 불러왔습니다.")
        _refresh_holdings_view()
    return holdings


def render_holdings_tab():
    """보유종목 입력(추가 폼·표) + 평가금액 기준 히트맵을 그린다."""
    st.subheader("보유종목 히트맵")

    holdings = render_holdings_editor()
    if holdings.empty:
        return
    st.divider()

    basis = st.radio("색상 기준", ["당일 등락률", "내 수익률"], horizontal=True, key="holdings_basis")
    color_col, clip, color_label = (
        ("등락률", 3.0, "당일 등락률(%)") if basis == "당일 등락률" else ("수익률", 30.0, "내 수익률(%)")
    )

    with st.spinner("보유종목 시세를 불러오는 중입니다..."):
        table, summary = dl.build_holdings_heatmap_data(holdings)

    if table.empty:
        st.error("보유종목 시세를 가져오지 못했습니다. 종목코드를 확인해 주세요.")
        return

    # 요약 카드 5종
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("총 매수금액", f"{summary['총매수금액']:,.0f}원")
    c2.metric("총 평가금액", f"{summary['총평가금액']:,.0f}원")
    c3.metric("총 평가손익", f"{summary['총평가손익']:+,.0f}원")
    c4.metric("총 수익률", f"{summary['총수익률']:+.2f}%")
    c5.metric("당일 손익", f"{summary['당일손익']:+,.0f}원")
    st.caption(f"기준일 {summary['기준일']} · 보유 {len(table)}종목 · 업종 {table['업종그룹'].nunique()}개")
    st.caption(PRICE_CAPTION)

    fig = hm.build_treemap(
        table, value_col="평가금액", color_col=color_col, clip=clip,
        size_label="평가금액", color_label=color_label,
        base_date=str(summary["기준일"]).replace("-", "."),
        hover_rows=hm.holdings_hover_rows(table), height=APP_HEATMAP_HEIGHT,
    )
    if fig is None:
        st.error("히트맵을 그릴 데이터가 없습니다.")
        return
    with _chart_box():                                   # 화면 차트 공통 상자(표와 같은 테두리)
        st.plotly_chart(fig, width="stretch")

    with st.expander("보유종목 상세"):
        view = table[["종목명", "종목코드", "업종그룹", "수량", "평균매수가", "현재가",
                      "등락률", "평가금액", "평가손익", "수익률"]]
        st.dataframe(view.sort_values("평가금액", ascending=False), width="stretch", hide_index=True)


# ===========================================================================
# 사이드바 (시장 선택 + 종목 드롭다운 + 종목 목록·업종·재무 갱신)
# ===========================================================================

def render_sidebar():
    """사이드바를 그리고 (선택 종목, 조회 기간)을 돌려준다."""
    st.sidebar.header("종목 선택")
    ticker_df = dl.load_ticker_list()

    if ticker_df.empty:
        st.sidebar.error("종목 목록을 불러오지 못했습니다.")
        return None, "6개월"

    # 시장을 먼저 고르고, 그 시장 종목만 드롭다운에 보여 준다(드롭다운에 글자를 치면 목록이 좁혀진다)
    market_kr = st.sidebar.radio("시장", list(MARKET_LABELS.keys()), horizontal=True, index=0, key="side_market")
    labels, lookup = _stock_options(ticker_df, MARKET_LABELS[market_kr])
    picked = None
    if not labels:
        st.sidebar.warning(f"{market_kr} 종목이 없습니다. '종목 목록 갱신'을 눌러 주세요.")
    else:
        default = next((i for i, label in enumerate(labels) if label.startswith("삼성전자 (")), 0)
        picked_label = st.sidebar.selectbox(f"종목 ({len(labels):,}개)", labels, index=default,
                                            key=f"side_pick_{MARKET_LABELS[market_kr]}",
                                            help="종목명이나 코드 일부를 입력하면 목록이 좁혀집니다")
        code, name = lookup[picked_label]
        picked = pd.Series({"종목코드": code, "종목명": name, "시장": MARKET_LABELS[market_kr]})

    period_label = st.sidebar.selectbox(
        "조회 기간", list(dl.PERIOD_OPTIONS.keys()),
        index=list(dl.PERIOD_OPTIONS.keys()).index("6개월"),
    )

    # --- 종목 목록(마스터 파일) ---
    st.sidebar.divider()
    st.sidebar.subheader("종목 목록")
    updated = dl.master_updated_date()
    st.sidebar.caption(f"{len(ticker_df):,}종목 (코스피·코스닥, 우선주 포함) · 마지막 갱신 {updated or '-'}")
    if st.sidebar.button("종목 목록 갱신", help="FinanceDataReader로 코스피·코스닥 전 종목을 다시 받습니다"):
        ok, message = dl.refresh_stock_master()
        st.session_state["master_status"] = {"시도": True, "성공": ok, "문구": message,
                                             "날짜": dl.master_updated_date()}
        (st.sidebar.success if ok else st.sidebar.error)(message)
    else:
        # 시작 시 자동 갱신이 실패했으면 알린다(버튼을 누른 회차에는 버튼 결과만 보여 준다)
        status = st.session_state.get("master_status") or {}
        if status.get("시도") and not status.get("성공"):
            st.sidebar.warning(status["문구"])

    # --- 업종 정보 ---
    st.sidebar.divider()
    st.sidebar.subheader("업종 정보")
    imap = industry.load_industry_map()
    st.sidebar.caption(f"매핑된 종목 {len(imap)}개 · 업종그룹 {imap['업종그룹'].nunique() if not imap.empty else 0}개")

    if st.sidebar.button("업종 정보 갱신", help="DART 기업개황 API로 업종을 다시 수집합니다(수 분 소요)"):
        if not keys.has_dart_key():
            st.sidebar.error("DART API 키가 없습니다. api_secrets.py의 DART_API_KEY를 채워 주세요.")
        else:
            targets = pd.concat([dl.get_top_marcap("KOSPI"), dl.get_top_marcap("KOSDAQ")], ignore_index=True)
            targets = targets[["종목코드", "종목명"]].drop_duplicates(subset="종목코드")
            bar = st.sidebar.progress(0.0, text="업종 수집 준비 중...")
            try:
                result = industry.build_industry_map(targets, progress_cb=lambda r, t: bar.progress(r, text=t))
                ok = int((result["업종그룹"] != "기타").sum())
                st.sidebar.success(f"{len(result)}종목 중 {ok}종목 업종 매핑 완료")
                st.cache_data.clear()
            except Exception as exc:
                st.sidebar.error(f"업종 수집 실패: {exc}")

    # --- 재무 ---
    st.sidebar.divider()
    st.sidebar.subheader("재무")
    if st.sidebar.button("재무 새로고침", disabled=picked is None,
                         help="선택 종목의 DART 재무 캐시를 지우고 다시 수집합니다"):
        removed = financials.clear_cache(picked["종목코드"])
        # load_financials 는 st 캐시 함수가 아니다(.clear() 없음). 재무 값을 들고 있는 st 캐시 함수만 비운다.
        for cached in (indicators.compute, financials.load_season_years):
            if hasattr(cached, "clear"):
                cached.clear()
        st.sidebar.success(f"재무 캐시 {removed}개를 지웠습니다. 다시 수집합니다.")

    st.sidebar.divider()
    st.sidebar.caption("Claude API 키: " + ("준비됨 ✅" if keys.has_api_key() else "미설정"))
    st.sidebar.caption("DART API 키: " + ("준비됨 ✅" if keys.has_dart_key() else "미설정"))
    return picked, period_label


def _app_password():
    """st.secrets 의 APP_PASSWORD (없거나 secrets.toml 이 없으면 None - 로컬은 게이트 없음)."""
    try:
        value = st.secrets.get("APP_PASSWORD")
        return str(value) if value else None
    except Exception:
        return None


def password_gate():
    """APP_PASSWORD 가 설정된 환경(클라우드)에서만 비밀번호를 묻는다. 통과하면 True(세션 동안 유지)."""
    expected = _app_password()
    if expected is None or st.session_state.get("auth_ok"):
        return True
    st.title("📈 주식 분석 도구")
    with st.form("password_gate"):
        entered = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("입장", type="primary")
    if submitted:
        if hmac.compare_digest(entered.encode("utf-8"), expected.encode("utf-8")):
            st.session_state["auth_ok"] = True
            st.rerun()
        st.error("비밀번호가 맞지 않습니다.")
    return False


def main():
    st.set_page_config(page_title="주식 분석 도구", page_icon="📈", layout="wide")
    if not password_gate():
        return
    st.title("📈 주식 분석 도구")
    st.caption("코스피·코스닥 종목의 일봉 시세와 시장/보유종목 히트맵, 규칙 기반 판정과 Claude 해설 리포트를 제공합니다.")

    # 종목 마스터: 세션마다 한 번, 파일 날짜가 오늘이 아니면 갱신을 시도한다(실패하면 기존 파일 사용).
    if "master_status" not in st.session_state:
        st.session_state["master_status"] = dl.ensure_stock_master()

    picked, period_label = render_sidebar()

    tab1, tab2, tab3 = st.tabs(["종목 분석", "시장 히트맵", "보유종목 히트맵"])
    with tab1:
        render_stock_tab(picked, period_label)
    with tab2:
        render_market_tab()
    with tab3:
        render_holdings_tab()


if __name__ == "__main__":
    main()
