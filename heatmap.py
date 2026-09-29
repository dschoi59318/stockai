# -*- coding: utf-8 -*-
"""
heatmap.py - 트리맵(히트맵) 그리기 전담

공통 규칙 (한국식)
 - 상승 빨강 / 하락 파랑 / 0% 짙은 회색(#3a3f4b) 연속 컬러스케일
 - 다크 배경, 흰 글씨, 박스 크기에 비례해 글자 크기 자동 조절
 - 박스 라벨은 "종목명<br>+1.23%" (업종별 보기는 "업종명<br>+1.23%")
 - 하단에 색상 범례와 "박스 크기는 ○○이며, %는 변동률입니다" 안내 문구

보기 2가지
 - build_treemap        : 종목별(업종 > 종목 2단). 시장 히트맵·보유종목 히트맵 공용
 - build_sector_treemap : 업종별(업종 1단). 박스 크기 = 업종 시가총액 합계, 색 = 시가총액 가중 평균 등락률.
                          hover = 업종명, 종목 수, 가중 평균 등락률, 상승·하락 종목 수, 시가총액 상위 3종목과 등락률
 - sector_summary       : 업종별 집계 표(두 그림과 업종별 표가 같은 숫자를 쓰도록 한 곳에서 계산)
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

# 배경/글자 색
BG_COLOR = "#14161c"
TEXT_COLOR = "#ffffff"
ZERO_COLOR = "#3a3f4b"          # 0% 짙은 회색

# 하락(파랑) -> 0%(회색) -> 상승(빨강) 연속 컬러스케일
KR_COLORSCALE = [
    [0.00, "#0d47a1"],          # 큰 하락: 진한 파랑
    [0.22, "#1565c0"],
    [0.42, "#2b4a7a"],
    [0.47, ZERO_COLOR],         # 0% 부근은 회색 띠
    [0.53, ZERO_COLOR],
    [0.58, "#7a3036"],
    [0.78, "#c62828"],
    [1.00, "#b71c1c"],          # 큰 상승: 진한 빨강
]

# 앱 화면 글꼴(2026-09-29): 화면 글자와 같은 Noto Sans KR. 고정 글자(컬러바 눈금·안내 문구·기준일·hover·경로 막대)는
# 11pt(14.67px), 컬러바 제목은 12pt(16px). 박스 라벨은 면적 비례 크기(아래 FONT_MIN~MAX)를 그대로 둔다.
APP_FONT = "Noto Sans KR"
APP_TEXT_PX = 14.6667
APP_TITLE_PX = 16

# 글자 크기 상·하한 (박스 면적 비율에 따라 자동 계산)
FONT_MIN = 8
FONT_MAX = 26
FONT_PARENT_MIN = 9
FONT_PARENT_MAX = 15
SECTOR_TOP = 3                  # 업종 hover에 보여 줄 시가총액 상위 종목 수


def _font_size(value, total, is_parent=False):
    """박스 크기(값 비중)에 따라 글자 크기(px)를 정한다.

    면적이 넓을수록 큰 글씨. 업종(부모) 박스는 얇은 머리띠라 상한을 낮게 둔다.
    """
    share = np.sqrt(max(value, 0.0) / total) if total > 0 else 0.0
    if is_parent:
        return int(round(min(max(FONT_PARENT_MIN + 22 * share, FONT_PARENT_MIN), FONT_PARENT_MAX)))
    return int(round(min(max(FONT_MIN + 34 * share, FONT_MIN), FONT_MAX)))


def _sized_label(name, rate, size):
    """박스 라벨을 만든다. '종목명<br>+1.23%' 에 글자 크기를 직접 지정한다.

    plotly 트리맵은 textfont.size 를 배열로 받으면 레이아웃이 깨지기 때문에,
    라벨 안에 <span style="font-size:..."> 로 크기를 넣어 박스별 글자 크기를 준다.
    """
    sub = max(int(round(size * 0.8)), 7)
    return (f"<span style='font-size:{size}px'>{name}</span><br>"
            f"<span style='font-size:{sub}px'>{rate:+.2f}%</span>")


def _weighted_rate(values, rates):
    """업종 박스에 표시할 가중평균 등락률(크기 가중)."""
    values = np.asarray(values, dtype="float64")
    rates = np.asarray(rates, dtype="float64")
    if values.sum() <= 0:
        return float(np.nanmean(rates)) if len(rates) else 0.0
    return float(np.nansum(values * rates) / values.sum())


def _figure(ids, labels, parents, values, colors, hovers, clip, size_label, color_label, base_date, height,
            pathbar=True):
    """트리맵 Figure 공통 서식(컬러스케일·컬러바·안내 문구·기준일)."""
    fig = go.Figure(go.Treemap(
        ids=ids,
        labels=labels,
        parents=parents,
        values=values,
        branchvalues="total",
        textinfo="label",
        textposition="middle center",
        textfont=dict(color=TEXT_COLOR, size=12, family=APP_FONT),   # 실제 크기는 라벨 안 span 으로 지정
        marker=dict(
            colors=colors,
            colorscale=KR_COLORSCALE,
            cmin=-clip, cmid=0, cmax=clip,
            line=dict(color=BG_COLOR, width=1.4),
            colorbar=dict(
                title=dict(text=color_label, font=dict(color=TEXT_COLOR, size=APP_TITLE_PX, family=APP_FONT)),
                orientation="h", y=-0.04, yanchor="top", x=0.5, xanchor="center",
                len=0.5, thickness=12,
                tickfont=dict(color=TEXT_COLOR, size=APP_TEXT_PX, family=APP_FONT),
                ticksuffix="%", outlinewidth=0,
            ),
        ),
        customdata=hovers,
        hovertemplate="%{customdata[0]}<extra></extra>",
        pathbar=dict(visible=pathbar, thickness=18, textfont=dict(size=APP_TEXT_PX, family=APP_FONT)),
        tiling=dict(pad=2),
    ))

    # 하단 안내 문구 / 우측 상단 기준일
    annotations = [dict(
        text=f"박스 크기는 {size_label}이며, %는 변동률입니다. 색상은 ±{clip:g}% 기준으로 clipping 됩니다.",
        xref="paper", yref="paper", x=0.5, y=-0.13, xanchor="center", yanchor="top",
        showarrow=False, font=dict(color="#9aa0aa", size=APP_TEXT_PX, family=APP_FONT),
    )]
    if base_date:
        annotations.append(dict(
            text=f"기준일 {base_date} 장마감",
            xref="paper", yref="paper", x=1.0, y=1.04, xanchor="right", yanchor="bottom",
            showarrow=False, font=dict(color="#c8ccd4", size=APP_TEXT_PX, family=APP_FONT),
        ))

    fig.update_layout(
        height=height,
        margin=dict(l=6, r=6, t=34, b=96),
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=BG_COLOR,
        font=dict(color=TEXT_COLOR, family=APP_FONT, size=APP_TEXT_PX),
        hoverlabel=dict(font=dict(family=APP_FONT, size=APP_TEXT_PX)),
        annotations=annotations,
    )
    return fig


def build_treemap(df, value_col, color_col, clip, size_label, color_label,
                  base_date="", hover_rows=None, height=760):
    """업종 > 종목 2단 트리맵을 만든다(종목별 보기).

    df         : 종목명 / 업종그룹 / 값 / 색상값 컬럼을 가진 DataFrame
    value_col  : 박스 크기로 쓸 컬럼 (시가총액 또는 평가금액)
    color_col  : 색상으로 쓸 컬럼 (등락률 또는 수익률)
    clip       : 색상 스케일 상·하한(%) — 이 값을 넘으면 같은 색으로 처리
    size_label : 범례 문구에 넣을 크기 기준 이름 (예: '시가총액')
    color_label: 컬러바 제목 (예: '등락률(%)')
    base_date  : 우측 상단에 표시할 기준일 문자열
    hover_rows : 종목별 hover 본문 문자열 리스트(없으면 기본 형식)
    """
    if df is None or df.empty:
        return None

    work = df.copy()
    work["업종그룹"] = work["업종그룹"].fillna("기타")
    work = work[work[value_col] > 0]
    if work.empty:
        return None

    ids, labels, parents, values, colors, hovers = [], [], [], [], [], []
    grand_total = float(work[value_col].sum())

    # 1) 업종(부모) 노드 — 값은 자식 합계, 색은 크기 가중평균 등락률
    for sector, part in work.groupby("업종그룹"):
        total = float(part[value_col].sum())
        rate = _weighted_rate(part[value_col], part[color_col])
        ids.append(sector)
        labels.append(_sized_label(sector, rate, _font_size(total, grand_total, is_parent=True)))
        parents.append("")
        values.append(total)
        colors.append(rate)
        hovers.append([f"<b>{sector}</b><br>종목 수: {len(part)}개<br>평균 {rate:+.2f}%"])

    # 2) 종목(자식) 노드
    hover_map = {}
    if hover_rows is not None:
        hover_map = dict(zip(work["종목코드"], hover_rows))

    for _, row in work.iterrows():
        code = str(row["종목코드"])
        rate = float(row[color_col])
        value = float(row[value_col])
        ids.append(code)
        labels.append(_sized_label(row["종목명"], rate, _font_size(value, grand_total)))
        parents.append(row["업종그룹"])
        values.append(value)
        colors.append(rate)
        hovers.append([hover_map.get(code, f"<b>{row['종목명']}</b> ({code})<br>{rate:+.2f}%")])

    return _figure(ids, labels, parents, values, colors, hovers, clip, size_label, color_label, base_date, height)


# ---------------------------------------------------------------------------
# 업종별 보기
# ---------------------------------------------------------------------------

def sector_summary(df, value_col="시가총액", color_col="등락률"):
    """업종그룹별 집계. 반환 컬럼: 업종 / 종목 수 / 등락률(시가총액 가중 평균) / 상승 / 하락 / 시가총액 / 상위종목

    상위종목: 시가총액 상위 3종목 [(종목명, 등락률), ...]
    """
    columns = ["업종", "종목 수", "등락률", "상승", "하락", "시가총액", "상위종목"]
    if df is None or df.empty:
        return pd.DataFrame(columns=columns)
    work = df.copy()
    work["업종그룹"] = work["업종그룹"].fillna("기타")
    work = work[work[value_col] > 0]
    rows = []
    for sector, part in work.groupby("업종그룹"):
        top = part.nlargest(SECTOR_TOP, value_col)
        rows.append({
            "업종": sector,
            "종목 수": len(part),
            "등락률": _weighted_rate(part[value_col], part[color_col]),
            "상승": int((part[color_col] > 0).sum()),
            "하락": int((part[color_col] < 0).sum()),
            "시가총액": float(part[value_col].sum()),
            "상위종목": list(zip(top["종목명"], top[color_col].astype(float))),
        })
    return pd.DataFrame(rows, columns=columns).sort_values("시가총액", ascending=False).reset_index(drop=True)


def sector_hover(row):
    """업종 hover 문구: 업종명, 종목 수, 가중 평균 등락률, 상승·하락 종목 수, 시가총액 상위 3종목과 등락률."""
    tops = "<br>".join(f"  {i}. {name} {rate:+.2f}%" for i, (name, rate) in enumerate(row["상위종목"], 1))
    return (f"<b>{row['업종']}</b><br>"
            f"종목 수: {row['종목 수']}개<br>"
            f"가중 평균 등락률: {row['등락률']:+.2f}%<br>"
            f"상승 {row['상승']} / 하락 {row['하락']}<br>"
            f"시가총액: {row['시가총액'] / 1e12:,.2f}조원<br>"
            f"시가총액 상위 {len(row['상위종목'])}종목<br>{tops}")


def build_sector_treemap(df, clip, color_label, base_date="", height=760, value_col="시가총액", color_col="등락률"):
    """업종별 1단 트리맵. 박스 = 업종그룹, 크기 = 업종 시가총액 합계, 색 = 시가총액 가중 평균 등락률.

    라벨 "업종명<br>+1.23%". 기간·색 스케일(clip)은 종목별 보기와 같은 값을 받는다.
    """
    summary = sector_summary(df, value_col, color_col)
    if summary.empty:
        return None
    grand_total = float(summary["시가총액"].sum())
    ids, labels, parents, values, colors, hovers = [], [], [], [], [], []
    for _, row in summary.iterrows():
        ids.append(row["업종"])
        labels.append(_sized_label(row["업종"], row["등락률"], _font_size(row["시가총액"], grand_total)))
        parents.append("")
        values.append(row["시가총액"])
        colors.append(row["등락률"])
        hovers.append([sector_hover(row)])
    return _figure(ids, labels, parents, values, colors, hovers, clip, "업종 시가총액 합계", color_label,
                   base_date, height, pathbar=False)


def market_hover_rows(df):
    """시장 히트맵 hover 문구: 종목명, 코드, 현재가, 등락률, 시가총액(조)."""
    rows = []
    for _, r in df.iterrows():
        rows.append(
            f"<b>{r['종목명']}</b> ({r['종목코드']})<br>"
            f"현재가: {r['현재가']:,.0f}원<br>"
            f"등락률: {r['등락률']:+.2f}%<br>"
            f"시가총액: {r['시가총액'] / 1e12:,.2f}조원"
        )
    return rows


def holdings_hover_rows(df):
    """보유종목 히트맵 hover 문구: 수량, 평균매수가, 현재가, 평가금액, 평가손익, 수익률."""
    rows = []
    for _, r in df.iterrows():
        rows.append(
            f"<b>{r['종목명']}</b> ({r['종목코드']})<br>"
            f"수량: {r['수량']:,.0f}주<br>"
            f"평균매수가: {r['평균매수가']:,.0f}원<br>"
            f"현재가: {r['현재가']:,.0f}원<br>"
            f"평가금액: {r['평가금액']:,.0f}원<br>"
            f"평가손익: {r['평가손익']:+,.0f}원<br>"
            f"수익률: {r['수익률']:+.2f}%<br>"
            f"당일 등락률: {r['등락률']:+.2f}%"
        )
    return rows
