# -*- coding: utf-8 -*-
"""
charts.py - 화면과 Word 리포트가 함께 쓰는 차트 모듈 (5단계)

 - build_price_chart : 캔들 + 이동평균(기본 20/60일, 리포트는 60/120일) + 거래량 (plotly)
                       markers를 주면 사건 위치에 번호(①②③)를 표시한다(리포트 구성 지침 4장 3.2)
 - build_fin_chart   : 매출·영업이익 막대 + 영업이익률 선(보조축) (plotly)
 - save_price_png / save_fin_png :
     plotly + kaleido로 PNG 저장을 먼저 시도하고, 실패하면 matplotlib로 같은 차트를 그린다.
     (한국식 색상 유지: 상승 빨강 / 하락 파랑, 한글 폰트는 맑은 고딕)

리포트 구성 지침 v1.6 12.3 (Word 리포트 그림 규격, report=True 일 때만 - 앱 화면 그림은 그대로)
 - 172mm 삽입 기준으로 그린다: plotly 는 650px(172mm, 96dpi) 폭에 글자 13.3px(=10pt)·범례 12px(=9pt)를 쓰고
   scale 3으로 저장, matplotlib 는 6.77인치 폭 고정 크기(bbox tight 없음)에 10pt·9pt를 쓴다.
 - 서체 Noto Sans KR, 제목은 이미지 안에 그리지 않는다(report.py 가 그림 위 문단으로 넣는다).
 - 세로/가로 비율: 52주 범위 0.30, 가격 차트 0.65, 수익률 0.42, 재무 0.43 (REPORT_RATIO)
 - 저장 뒤 외곽 실선 테두리(#B7BFC9, 172mm 기준 1.1pt)를 그린다(_outline).

앱 경로 한글 폰트(2026-09-29, 클라우드 준비): fonts 폴더의 NotoSansKR(Regular·Bold)을 matplotlib 에 등록하고,
 맑은 고딕이 설치돼 있으면(Windows PC) 그대로 쓰고, 없으면(리눅스 클라우드) Noto Sans KR 을 쓴다(_app_font_family).
 report=True 경로의 서체 지정은 그대로다.
"""

import glob
import logging
import os

import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 상승 빨강 / 하락 파랑 (국내 증시 표기 관례)
COLOR_UP = "#E53935"
COLOR_DOWN = "#1E88E5"
COLOR_MA20 = "#FB8C00"
COLOR_MA60 = "#7E57C2"
COLOR_MA120 = "#26A69A"
MA_COLORS = {"MA20": COLOR_MA20, "MA60": COLOR_MA60, "MA120": COLOR_MA120}
COLOR_MARKER = "#1F3A5F"

COLOR_SALES = "#90A4AE"
COLOR_OP = "#1565C0"
COLOR_MARGIN = "#E53935"

FONT_FAMILY = "Malgun Gothic"

# Word 리포트 그림 규격(지침 v1.6 12.3). report=True 경로에서만 쓴다.
REPORT_FONT = "Noto Sans KR"
REPORT_WIDTH_MM = 172
REPORT_WIDTH_PX = 650           # 172mm를 96dpi 픽셀로(plotly 레이아웃 단위)
REPORT_WIDTH_IN = REPORT_WIDTH_MM / 25.4
REPORT_SCALE = 3                # plotly 저장 배율(650px x 3 = 1950px)
REPORT_DPI = 300                # matplotlib 저장 해상도
REPORT_PT = 10                  # 축·데이터 레이블
REPORT_LEGEND_PT = 9            # 범례
REPORT_RATIO = {"range": 0.30, "price": 0.65, "returns": 0.42, "fin": 0.43}
OUTLINE_COLOR = "#B7BFC9"
OUTLINE_PT = 1.1


def _px(pt):
    """172mm(650px) 삽입 기준 pt -> plotly px."""
    return pt * 96 / 72

# 영업이익률 보조축 눈금 후보(%). 범위를 6칸 이하로 나누는 가장 작은 값을 쓴다.
MARGIN_STEPS = (0.5, 1, 2, 5, 10, 20, 50)


def margin_step(values, max_ticks=6):
    """영업이익률 보조축 눈금 간격(0.5%·1%·2%·5% ...). 1.75%·3.47% 같은 어중간한 눈금을 막는다."""
    vals = [float(v) for v in values if v == v and v is not None]       # NaN 제외
    if not vals:
        return 1
    span = max(max(vals) - min(vals), 0.1)
    for step in MARGIN_STEPS:
        if span / step <= max_ticks:
            return step
    return MARGIN_STEPS[-1]


# ===========================================================================
# plotly (화면 + kaleido 이미지)
# ===========================================================================

def _marker_points(df, markers):
    """사건 번호 표시 위치: 사건 기간(시작~종료) 안 최고가 위. 차트 기간 밖 사건은 뺀다.

    markers: [{"번호", "시작일", "종료일"}] -> [(위치 번호 i, 날짜, 고가, 번호)]
    """
    import pandas as pd
    out = []
    for m in markers or []:
        start, end = pd.Timestamp(m["시작일"]), pd.Timestamp(m["종료일"])
        part = df[(df.index >= start) & (df.index <= end)]
        if part.empty:
            continue
        day = part["고가"].idxmax()
        out.append((df.index.get_loc(day), day, float(part["고가"].max()), m["번호"]))
    return out


def build_price_chart(df, title, height=720, ma_cols=("MA20", "MA60"), markers=None):
    """캔들차트 + 이동평균선 + 거래량 막대를 한 장의 plotly 그림으로 만든다. title이 비면 위 칸 제목을 그리지 않는다."""
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.72, 0.28], vertical_spacing=0.03,
        subplot_titles=(title or "", "거래량"),
    )

    # (1) 일봉 캔들
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["시가"], high=df["고가"], low=df["저가"], close=df["종가"],
            name="일봉",
            increasing_line_color=COLOR_UP, increasing_fillcolor=COLOR_UP,
            decreasing_line_color=COLOR_DOWN, decreasing_fillcolor=COLOR_DOWN,
        ),
        row=1, col=1,
    )

    # (2) 이동평균선
    for col in ma_cols:
        if col in df.columns and df[col].notna().any():
            fig.add_trace(
                go.Scatter(x=df.index, y=df[col], mode="lines", name=f"{col[2:]}일 이동평균",
                           line=dict(color=MA_COLORS.get(col, COLOR_MA60), width=1.3)),
                row=1, col=1,
            )
    # (2-1) 사건 번호
    for _, day, high, label in _marker_points(df, markers):
        fig.add_annotation(x=day, y=high, text=label, showarrow=True, arrowhead=0, arrowcolor=COLOR_MARKER,
                           ax=0, ay=-22, font=dict(size=15, color=COLOR_MARKER), row=1, col=1)

    # (3) 거래량 막대: 전일 대비 상승일은 빨강, 하락일은 파랑
    up_mask = df["종가"] >= df["종가"].shift(1).fillna(df["종가"])
    bar_colors = [COLOR_UP if flag else COLOR_DOWN for flag in up_mask]
    fig.add_trace(
        go.Bar(x=df.index, y=df["거래량"], name="거래량", marker_color=bar_colors, showlegend=False),
        row=2, col=1,
    )

    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=50, b=10),
        xaxis_rangeslider_visible=False, hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    # 주말은 거래가 없으므로 x축에서 빼 캔들이 이어지게 만든다.
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.update_yaxes(title_text="주가(원)", row=1, col=1, tickformat=",")
    fig.update_yaxes(title_text="주(株)", row=2, col=1, tickformat=",")
    return fig


def build_fin_chart(frame, sales_name, height=380):
    """매출·영업이익 막대 + 영업이익률 선(보조축) 차트.

    값이 전부 비어 있는 계열(금융업의 매출액·영업이익률 등)은 그리지 않고,
    영업이익률이 없으면 보조축도 만들지 않는다(빈 범례·의미 없는 눈금 방지).
    """
    has_margin = frame["영업이익률"].notna().any()
    fig = make_subplots(specs=[[{"secondary_y": has_margin}]])
    if frame["매출액"].notna().any():
        fig.add_trace(go.Bar(x=frame["구분"], y=frame["매출액"], name=f"{sales_name}(억 원)",
                             marker_color=COLOR_SALES), secondary_y=False)
    if frame["영업이익"].notna().any():
        fig.add_trace(go.Bar(x=frame["구분"], y=frame["영업이익"], name="영업이익(억 원)",
                             marker_color=COLOR_OP), secondary_y=False)
    if has_margin:
        fig.add_trace(go.Scatter(x=frame["구분"], y=frame["영업이익률"], name="영업이익률(%)",
                                 mode="lines+markers+text", text=frame["영업이익률"],
                                 texttemplate="%{text:.1f}%", textposition="top center",
                                 line=dict(color=COLOR_MARGIN, width=2)), secondary_y=True)
    fig.update_layout(height=height, barmode="group", margin=dict(l=10, r=10, t=30, b=10),
                      hovermode="x unified", showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_xaxes(type="category")
    fig.update_yaxes(title_text="억 원", tickformat=",", secondary_y=False)
    if has_margin:
        step = margin_step(frame["영업이익률"])
        fig.update_yaxes(title_text="영업이익률(%)", ticksuffix="%", showgrid=False, secondary_y=True,
                         tickmode="linear", tick0=0, dtick=step, tickformat=".1f" if step < 1 else ".0f")
    return fig


def fin_chart_label(frame, sales_name):
    """차트 설명 문구: 실제로 그린 계열만 적는다."""
    bars = [name for name, col in ((sales_name, "매출액"), ("영업이익", "영업이익")) if frame[col].notna().any()]
    text = f"{'·'.join(bars)}(막대, 억 원)" if bars else ""
    if frame["영업이익률"].notna().any():
        text += "과 영업이익률(선, %)"
    return text


def _write_plotly(fig, path, width, height, report=False):
    """kaleido로 PNG를 저장한다. 흰 배경. report=True면 지침 v1.6 12.3 규격(Noto Sans KR 10pt·범례 9pt, 테두리)."""
    if report:
        fig.update_layout(font=dict(family=REPORT_FONT, size=_px(REPORT_PT)), template="plotly_white",
                          paper_bgcolor="white", plot_bgcolor="white",
                          legend=dict(font=dict(size=_px(REPORT_LEGEND_PT))),
                          margin=dict(l=12, r=12, t=34, b=12))
        fig.update_annotations(font_size=_px(REPORT_PT))     # '거래량' 칸 제목·사건 번호
        fig.write_image(path, width=width, height=height, scale=REPORT_SCALE)
        _outline(path)
        return
    fig.update_layout(font_family=FONT_FAMILY, template="plotly_white",
                      paper_bgcolor="white", plot_bgcolor="white")
    fig.write_image(path, width=width, height=height, scale=2)


def _outline(path):
    """저장된 PNG 가장자리에 외곽 실선 테두리를 그린다(172mm 삽입 기준 OUTLINE_PT 굵기)."""
    from PIL import Image, ImageDraw
    with Image.open(path) as im:
        im = im.convert("RGB")
        w, h = im.size
        line = max(1, round(w * (OUTLINE_PT * 25.4 / 72) / REPORT_WIDTH_MM))
        ImageDraw.Draw(im).rectangle([0, 0, w - 1, h - 1], outline=OUTLINE_COLOR, width=line)
        im.save(path)


def _report_size(kind):
    """리포트 그림의 plotly 픽셀 크기 (폭 650px, 세로 = 폭 x 비율)."""
    return REPORT_WIDTH_PX, round(REPORT_WIDTH_PX * REPORT_RATIO[kind])


def _report_figsize(kind):
    """리포트 그림의 matplotlib 인치 크기 (폭 172mm, 세로 = 폭 x 비율)."""
    return REPORT_WIDTH_IN, REPORT_WIDTH_IN * REPORT_RATIO[kind]


# ===========================================================================
# matplotlib 대체 차트 (kaleido가 실패할 때)
# ===========================================================================

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
APP_FALLBACK_FONT = "Noto Sans KR"      # 앱 그림 서체(2026-09-29: PC에서도 맑은 고딕 대신 이 글꼴, 화면 글꼴과 통일)
_app_font = None                        # 한 번만 고른다


def _app_font_family():
    """앱 경로 matplotlib 서체: fonts\\ 의 글꼴 파일(Noto Sans KR Regular·Bold)을 등록하고 Noto Sans KR 을 쓴다.
    PC·클라우드 모두 같은 글꼴(앱 화면 글꼴과 같음). report=True 경로는 이 함수를 쓰지 않는다."""
    global _app_font
    if _app_font is None:
        from matplotlib import font_manager
        registered = []
        for path in sorted(glob.glob(os.path.join(FONTS_DIR, "*.ttf")) + glob.glob(os.path.join(FONTS_DIR, "*.otf"))):
            try:
                font_manager.fontManager.addfont(path)
                registered.append(f"{os.path.basename(path)} ({font_manager.FontProperties(fname=path).get_name()})")
            except Exception as exc:
                logging.getLogger(__name__).warning("글꼴 등록 실패: %s (%s)", os.path.basename(path), exc)
        _app_font = APP_FALLBACK_FONT
        logging.getLogger(__name__).info("fonts 등록: %s / 앱 서체: %s", ", ".join(registered) or "없음", _app_font)
    return _app_font


def _mpl(report=False):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = REPORT_FONT if report else _app_font_family()
    plt.rcParams["axes.unicode_minus"] = False      # 한글 폰트에서 마이너스 기호 깨짐 방지
    return plt


def _mpl_report_save(fig, path):
    """리포트 그림: 크기를 바꾸지 않고(bbox tight 없음) 여백만 맞춰 저장하고 테두리를 그린다."""
    fig.tight_layout(pad=0.6)
    fig.savefig(path, dpi=REPORT_DPI, facecolor="white")
    _outline(path)


def _mpl_price_report(df, path, ma_cols=("MA60", "MA120"), markers=None):
    """리포트용 matplotlib 가격 차트(kaleido 실패 시). 제목 없음, 지침 v1.6 12.3 규격."""
    import numpy as np
    plt = _mpl(report=True)
    from matplotlib.ticker import FuncFormatter

    x = np.arange(len(df))
    up = (df["종가"] >= df["시가"]).values
    colors = [COLOR_UP if u else COLOR_DOWN for u in up]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=_report_figsize("price"), sharex=True,
                                   gridspec_kw={"height_ratios": [0.72, 0.28], "hspace": 0.05})
    ax1.vlines(x, df["저가"], df["고가"], color=colors, linewidth=0.6)
    body_low = np.minimum(df["시가"], df["종가"])
    body_h = (df["종가"] - df["시가"]).abs().replace(0, 1e-9)
    ax1.bar(x, body_h, bottom=body_low, color=colors, width=0.7)
    for col in ma_cols:
        if col in df.columns and df[col].notna().any():
            ax1.plot(x, df[col], color=MA_COLORS.get(col, COLOR_MA60), linewidth=1.0, label=f"{col[2:]}일 이동평균")
    for i, _, high, label in _marker_points(df, markers):
        ax1.annotate(label, (i, high), xytext=(0, 12), textcoords="offset points", ha="center",
                     fontsize=REPORT_PT, color=COLOR_MARKER, arrowprops=dict(arrowstyle="-", color=COLOR_MARKER))
    ax1.set_ylabel("주가(원)", fontsize=REPORT_PT)
    ax1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax1.tick_params(labelsize=REPORT_PT)
    ax1.legend(loc="upper left", fontsize=REPORT_LEGEND_PT)
    ax1.grid(alpha=0.3)
    prev_close = df["종가"].shift(1).fillna(df["종가"])
    ax2.bar(x, df["거래량"], color=[COLOR_UP if c >= p else COLOR_DOWN for c, p in zip(df["종가"], prev_close)],
            width=0.7)
    ax2.set_ylabel("주(株)", fontsize=REPORT_PT)
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax2.tick_params(labelsize=REPORT_PT)
    ax2.grid(alpha=0.3)
    step = max(1, len(df) // 6)
    ax2.set_xticks(x[::step])
    ax2.set_xticklabels([d.strftime("%Y-%m-%d") for d in df.index[::step]], fontsize=REPORT_PT)
    _mpl_report_save(fig, path)
    plt.close(fig)


def _mpl_fin_report(frame, sales_name, path):
    """리포트용 matplotlib 재무 차트(kaleido 실패 시). 지침 v1.6 12.3 규격."""
    import numpy as np
    plt = _mpl(report=True)
    from matplotlib.ticker import FuncFormatter, MultipleLocator

    x = np.arange(len(frame))
    fig, ax = plt.subplots(figsize=_report_figsize("fin"))
    sales = frame["매출액"].astype(float)
    ops = frame["영업이익"].astype(float)
    both = sales.notna().any() and ops.notna().any()
    if sales.notna().any():
        ax.bar(x - 0.2 if both else x, sales.fillna(0), width=0.4 if both else 0.6,
               color=COLOR_SALES, label=f"{sales_name}(억 원)")
    if ops.notna().any():
        ax.bar(x + 0.2 if both else x, ops.fillna(0), width=0.4 if both else 0.6,
               color=COLOR_OP, label="영업이익(억 원)")
    ax.set_xticks(x)
    ax.set_xticklabels(frame["구분"], fontsize=REPORT_PT)
    ax.set_ylabel("억 원", fontsize=REPORT_PT)
    ax.tick_params(labelsize=REPORT_PT)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(axis="y", alpha=0.3)
    margins = frame["영업이익률"].astype(float)
    handles, labels = ax.get_legend_handles_labels()
    if margins.notna().any():
        ax2 = ax.twinx()
        ax2.plot(x, margins, color=COLOR_MARGIN, marker="o", linewidth=1.6, label="영업이익률(%)")
        for xi, m in zip(x, margins):
            if m == m:          # NaN 제외
                ax2.annotate(f"{m:.1f}%", (xi, m), textcoords="offset points", xytext=(0, 6),
                             ha="center", fontsize=REPORT_PT, color=COLOR_MARGIN)
        ax2.set_ylabel("영업이익률(%)", fontsize=REPORT_PT)
        ax2.tick_params(labelsize=REPORT_PT)
        ax2.yaxis.set_major_locator(MultipleLocator(margin_step(margins)))
        ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}%"))
        h2, l2 = ax2.get_legend_handles_labels()
        handles, labels = handles + h2, labels + l2
    ax.legend(handles, labels, loc="upper left", fontsize=REPORT_LEGEND_PT)
    _mpl_report_save(fig, path)
    plt.close(fig)


def _mpl_price(df, title, path, width, height, ma_cols=("MA20", "MA60"), markers=None):
    """matplotlib 캔들 + 이동평균 + 거래량(+ 사건 번호). 거래일을 0,1,2... 로 놓아 주말 공백을 없앤다."""
    import numpy as np
    plt = _mpl()
    from matplotlib.ticker import FuncFormatter

    x = np.arange(len(df))
    up = (df["종가"] >= df["시가"]).values
    colors = [COLOR_UP if u else COLOR_DOWN for u in up]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(width / 100, height / 100), dpi=200, sharex=True,
                                   gridspec_kw={"height_ratios": [0.72, 0.28], "hspace": 0.05})
    ax1.vlines(x, df["저가"], df["고가"], color=colors, linewidth=0.8)
    body_low = np.minimum(df["시가"], df["종가"])
    body_h = (df["종가"] - df["시가"]).abs().replace(0, 1e-9)
    ax1.bar(x, body_h, bottom=body_low, color=colors, width=0.7)
    for col in ma_cols:
        if col in df.columns and df[col].notna().any():
            ax1.plot(x, df[col], color=MA_COLORS.get(col, COLOR_MA60), linewidth=1.2, label=f"{col[2:]}일 이동평균")
    for i, _, high, label in _marker_points(df, markers):
        ax1.annotate(label, (i, high), xytext=(0, 14), textcoords="offset points", ha="center",
                     fontsize=12, color=COLOR_MARKER, arrowprops=dict(arrowstyle="-", color=COLOR_MARKER))
    ax1.set_title(title, fontsize=11)
    ax1.set_ylabel("주가(원)")
    ax1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(alpha=0.3)

    prev_close = df["종가"].shift(1).fillna(df["종가"])
    vol_colors = [COLOR_UP if c >= p else COLOR_DOWN for c, p in zip(df["종가"], prev_close)]
    ax2.bar(x, df["거래량"], color=vol_colors, width=0.7)
    ax2.set_ylabel("주(株)")
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax2.grid(alpha=0.3)

    step = max(1, len(df) // 8)
    ax2.set_xticks(x[::step])
    ax2.set_xticklabels([d.strftime("%Y-%m-%d") for d in df.index[::step]], fontsize=8)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _mpl_fin(frame, sales_name, path, width, height):
    """matplotlib 매출·영업이익 막대 + 영업이익률 선(보조축)."""
    import numpy as np
    plt = _mpl()
    from matplotlib.ticker import FuncFormatter

    x = np.arange(len(frame))
    fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=200)
    sales = frame["매출액"].astype(float)
    ops = frame["영업이익"].astype(float)
    both = sales.notna().any() and ops.notna().any()
    if sales.notna().any():
        ax.bar(x - 0.2 if both else x, sales.fillna(0), width=0.4 if both else 0.6,
               color=COLOR_SALES, label=f"{sales_name}(억 원)")
    if ops.notna().any():
        ax.bar(x + 0.2 if both else x, ops.fillna(0), width=0.4 if both else 0.6,
               color=COLOR_OP, label="영업이익(억 원)")
    ax.set_xticks(x)
    ax.set_xticklabels(frame["구분"])
    ax.set_ylabel("억 원")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(axis="y", alpha=0.3)

    margins = frame["영업이익률"].astype(float)
    if margins.notna().any():
        ax2 = ax.twinx()
        ax2.plot(x, margins, color=COLOR_MARGIN, marker="o", linewidth=2, label="영업이익률(%)")
        for xi, m in zip(x, margins):
            if m == m:          # NaN 제외
                ax2.annotate(f"{m:.1f}%", (xi, m), textcoords="offset points", xytext=(0, 6),
                             ha="center", fontsize=8, color=COLOR_MARGIN)
        ax2.set_ylabel("영업이익률(%)")
        from matplotlib.ticker import MultipleLocator
        ax2.yaxis.set_major_locator(MultipleLocator(margin_step(margins)))
        ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}%"))
        lines = ax.get_legend_handles_labels()
        lines2 = ax2.get_legend_handles_labels()
        ax.legend(lines[0] + lines2[0], lines[1] + lines2[1], loc="upper left", fontsize=8)
    else:
        ax.legend(loc="upper left", fontsize=8)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ===========================================================================
# PNG 저장 (kaleido 우선, 실패하면 matplotlib)
# ===========================================================================

def save_price_png(df, title, path, width=1000, height=640, ma_cols=("MA20", "MA60"), markers=None, report=False):
    """가격 차트 PNG를 저장하고 사용한 엔진 이름('kaleido'/'matplotlib')을 돌려준다.

    report=True: Word 리포트 규격(지침 v1.6 12.3) - 제목 없음, 650 x (650 x 0.65)px, Noto Sans KR, 테두리.
    width·height·title 인자는 무시한다.
    """
    if report:
        width, height = _report_size("price")
        try:
            _write_plotly(build_price_chart(df, "", height=height, ma_cols=ma_cols, markers=markers),
                          path, width, height, report=True)
            return "kaleido"
        except Exception:
            _mpl_price_report(df, path, ma_cols=ma_cols, markers=markers)
            return "matplotlib"
    try:
        _write_plotly(build_price_chart(df, title, height=height, ma_cols=ma_cols, markers=markers), path, width, height)
        return "kaleido"
    except Exception:
        _mpl_price(df, title, path, width, height, ma_cols=ma_cols, markers=markers)
        return "matplotlib"


def save_fin_png(frame, sales_name, path, width=1000, height=400, report=False):
    """재무 차트 PNG를 저장하고 사용한 엔진 이름을 돌려준다. report=True면 리포트 규격(지침 v1.6 12.3)."""
    if report:
        width, height = _report_size("fin")
        try:
            fig = build_fin_chart(frame, sales_name, height=height)
            margins = frame["영업이익률"].dropna().astype(float)
            if not margins.empty:
                # 172mm 폭에서는 선 위 값 표시(예: 9.2%)가 그림 위 끝에 걸려 잘린다. 보조축 위아래에 여유를 둔다.
                lo, hi = margins.min(), margins.max()
                span = max(hi - lo, 0.5)
                fig.update_yaxes(range=[lo - span * 0.35, hi + span * 0.45], secondary_y=True)
            _write_plotly(fig, path, width, height, report=True)
            return "kaleido"
        except Exception:
            _mpl_fin_report(frame, sales_name, path)
            return "matplotlib"
    try:
        _write_plotly(build_fin_chart(frame, sales_name, height=height), path, width, height)
        return "kaleido"
    except Exception:
        _mpl_fin(frame, sales_name, path, width, height)
        return "matplotlib"


# ===========================================================================
# 쉽게 읽기 그림 (matplotlib, 리포트와 화면 공통)
# ===========================================================================

# 쉽게 읽기 지침 1장: 회색 막대 + 진한 남색 점. 빨강·파랑은 쓰지 않는다(상승·하락 색과 혼동 방지).
COLOR_RANGE = "#BDBDBD"
COLOR_POINT = "#1F3A5F"


# ---------------------------------------------------------------------------
# 앱 화면 그림 규격(app=True 경로). 캔버스 = 화면 표시 크기 1:1(1100px, dpi 100)로 그려서
# st.image(width=1100)이 늘리지 않게 한다. 리포트(report=True) 규격과 무관하다.
# ---------------------------------------------------------------------------
APP_WIDTH_PX = 1100
APP_DPI = 100
APP_HEIGHT_IN = {"range": 3.2, "returns": 3.2, "bar": 3.2, "price": 4.2, "volume": 2.2, "fin": 3.2}
# 글자 크기(2026-09-29): 화면 글자와 같게 제목 12pt(16px), 축·눈금·범례·값 라벨 11pt(14.67px).
# 그림은 dpi 100 캔버스를 1:1 로 보이므로 matplotlib 포인트 = 화면 px x 72 / 100 으로 바꿔 넣는다.
APP_TITLE_PX = 16.0
APP_TEXT_PX = 14.6667
APP_TITLE_PT = APP_TITLE_PX * 72 / APP_DPI      # 11.52
APP_LABEL_PT = APP_TEXT_PX * 72 / APP_DPI       # 10.56
APP_TICK_PT = APP_LABEL_PT
APP_VALUE_PT = APP_LABEL_PT     # 막대 값 라벨(bold)
APP_BAR_WIDTH = 0.35
APP_LINE_WIDTH = 1.2
# 앱 화면 색(2026-09-29, 네이비 + 대비 보강): 바탕 #162033(카드와 같은 색), 축·눈금·글자 #C9D1E0, 격자선 #2B3A55,
# 상승 #FF5A5F / 하락 #4F9BFF. 어두운 바탕에서 안 보이던 COLOR_POINT #1F3A5F(현재가 점·글자) -> #7EA6FF.
# 리포트 경로 색은 그대로.
APP_BG = "#162033"
APP_FG = "#C9D1E0"
APP_GRID = "#2B3A55"
APP_UP = "#FF5A5F"
APP_DOWN = "#4F9BFF"
APP_COLOR_POINT = "#7EA6FF"
# 52주 범위(2026-09-30): 가로 막대 #2B3A55, 현재가 점·"현재가" 글자 #F5B544, 최저/최고 글자 #C9D1E0(APP_FG).
APP_RANGE_BAR = "#2B3A55"
APP_RANGE_POINT = "#F5B544"


def app_fig(kind):
    """앱 화면 그림을 만든다: figsize=(11.0, H), dpi=100 -> 가로 1100px. (plt, fig, ax) 를 돌려준다.
    kind='price' 는 가격(4.2) + 거래량(2.2) 두 칸, ax 는 (ax1, ax2).
    전역 rcParams 는 건드리지 않는다(같은 프로세스에서 만드는 리포트 그림에 번지지 않게) - 눈금 글자만 축에 지정."""
    plt = _mpl()
    width_in = APP_WIDTH_PX / APP_DPI
    if kind == "price":
        top, bottom = APP_HEIGHT_IN["price"], APP_HEIGHT_IN["volume"]
        fig, ax = plt.subplots(2, 1, figsize=(width_in, top + bottom), dpi=APP_DPI, sharex=True,
                               gridspec_kw={"height_ratios": [top, bottom], "hspace": 0.05})
        axes = ax
    else:
        fig, ax = plt.subplots(figsize=(width_in, APP_HEIGHT_IN[kind]), dpi=APP_DPI)
        axes = [ax]
    fig.patch.set_facecolor(APP_BG)
    for a in axes:
        a.set_facecolor(APP_BG)
        a.tick_params(labelsize=APP_TICK_PT, colors=APP_FG)          # 눈금·눈금 글자
        for spine in a.spines.values():
            spine.set_color(APP_FG)                                  # 축선
        a.xaxis.label.set_color(APP_FG)
        a.yaxis.label.set_color(APP_FG)
        a.title.set_color(APP_FG)
    return plt, fig, ax


def app_save(plt, fig, path_or_buffer, tight=True):
    """앱 화면 그림 저장: 크기를 바꾸지 않는다(bbox_inches=None, dpi 100 -> 1100px 그대로). 바탕은 카드색 APP_BG."""
    if tight:
        fig.tight_layout(pad=0.8)
    fig.savefig(path_or_buffer, dpi=APP_DPI, bbox_inches=None, facecolor=APP_BG, format="png")
    plt.close(fig)


def _range_app(low, high, cur, path_or_buffer, title=None):
    """앱 화면용 52주 범위 막대(1100px 폭, 1:1 표시)."""
    plt, fig, ax = app_fig("range")
    fig.subplots_adjust(left=0.04, right=0.96, top=0.86 if title else 0.96, bottom=0.04)
    if title:
        ax.set_title(title, fontsize=APP_TITLE_PT, color=APP_FG, pad=10)
    ax.plot([low, high], [0, 0], color=APP_RANGE_BAR, linewidth=12, solid_capstyle="round", zorder=1)
    ax.scatter([cur], [0], s=170, color=APP_RANGE_POINT, zorder=3)
    ax.annotate(f"현재가 {cur:,}원", (cur, 0), xytext=(0, 13), textcoords="offset points",
                ha="center", va="bottom", fontsize=APP_VALUE_PT, fontweight="bold", color=APP_RANGE_POINT)
    for value, label in ((low, "52주 최저"), (high, "52주 최고")):
        ax.annotate(f"{label}\n{value:,}원", (value, 0), xytext=(0, -14), textcoords="offset points",
                    ha="center", va="top", fontsize=APP_LABEL_PT, linespacing=1.3, color=APP_FG)
    pad = (high - low) * 0.08
    ax.set_xlim(low - pad, high + pad)
    ax.set_ylim(-1.45, 1.15)
    ax.axis("off")
    app_save(plt, fig, path_or_buffer, tight=False)


def _returns_app(items, path_or_buffer):
    """앱 화면용 기간 수익률 막대(1100px 폭, 1:1 표시). 값 라벨은 막대 끝 바깥에 둔다."""
    plt, fig, ax = app_fig("returns")
    labels = [label for label, _ in items]
    values = [value for _, value in items]
    colors = [APP_UP if v >= 0 else APP_DOWN for v in values]
    bars = ax.bar(labels, values, color=colors, width=APP_BAR_WIDTH)
    ax.axhline(0, color="#90A4AE", linewidth=APP_LINE_WIDTH)
    for bar, value in zip(bars, values):
        ax.annotate(f"{value:+.2f}%", (bar.get_x() + bar.get_width() / 2, value),
                    xytext=(0, 4 if value >= 0 else -4), textcoords="offset points",
                    ha="center", va="bottom" if value >= 0 else "top",
                    fontsize=APP_VALUE_PT, fontweight="bold", color=APP_UP if value >= 0 else APP_DOWN)
    span = max(abs(v) for v in values) or 1
    ax.set_ylim(min(0, min(values)) - span * 0.25, max(0, max(values)) + span * 0.25)
    ax.set_ylabel("수익률(%)", fontsize=APP_LABEL_PT, color=APP_FG)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=APP_GRID)
    ax.set_axisbelow(True)                                            # 격자선은 막대 뒤로
    app_save(plt, fig, path_or_buffer)


def save_range_png(low, high, cur, path_or_buffer, width=900, height=190, title=None, report=False, app=False):
    """52주 최저~최고 가로 막대 위에 현재가 위치를 점으로 표시한다(쉽게 읽기 1장).

    report=True: Word 리포트 규격(지침 v1.6 12.3) - 172mm x 0.30 고정 크기, 제목 없음, 10pt, 테두리.
    path_or_buffer는 파일 경로여야 한다(테두리를 다시 그리므로).
    app=True: 앱 화면 규격(app_fig, 1100px 1:1). width·height 인자는 무시한다.
    """
    if report:
        _range_report(low, high, cur, path_or_buffer)
        return
    if app:
        _range_app(low, high, cur, path_or_buffer, title=title)
        return
    plt = _mpl()
    fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=200)
    if title:
        ax.set_title(title, fontsize=11, color=COLOR_POINT, pad=18)
    ax.plot([low, high], [0, 0], color=COLOR_RANGE, linewidth=14, solid_capstyle="round", zorder=1)
    ax.scatter([cur], [0], s=220, color=COLOR_POINT, zorder=3)
    ax.annotate(f"현재가 {cur:,}원", (cur, 0), xytext=(0, 16), textcoords="offset points",
                ha="center", fontsize=10, fontweight="bold", color=COLOR_POINT)
    ax.annotate(f"52주 최저\n{low:,}원", (low, 0), xytext=(0, -30), textcoords="offset points",
                ha="center", va="top", fontsize=9)
    ax.annotate(f"52주 최고\n{high:,}원", (high, 0), xytext=(0, -30), textcoords="offset points",
                ha="center", va="top", fontsize=9)
    pad = (high - low) * 0.08
    ax.set_xlim(low - pad, high + pad)
    ax.set_ylim(-1, 1)
    ax.axis("off")
    fig.savefig(path_or_buffer, bbox_inches="tight", facecolor="white", format="png")
    plt.close(fig)


def _range_report(low, high, cur, path):
    """리포트용 52주 범위 막대. 172mm 폭 기준으로 글자 10pt, 크기 고정(bbox tight 없음)."""
    plt = _mpl(report=True)
    fig, ax = plt.subplots(figsize=_report_figsize("range"))
    fig.subplots_adjust(left=0.03, right=0.97, top=0.97, bottom=0.03)
    ax.plot([low, high], [0, 0], color=COLOR_RANGE, linewidth=12, solid_capstyle="round", zorder=1)
    ax.scatter([cur], [0], s=170, color=COLOR_POINT, zorder=3)
    ax.annotate(f"현재가 {cur:,}원", (cur, 0), xytext=(0, 13), textcoords="offset points",
                ha="center", va="bottom", fontsize=REPORT_PT, fontweight="bold", color=COLOR_POINT)
    for value, label in ((low, "52주 최저"), (high, "52주 최고")):
        ax.annotate(f"{label}\n{value:,}원", (value, 0), xytext=(0, -14), textcoords="offset points",
                    ha="center", va="top", fontsize=REPORT_PT, linespacing=1.3)
    pad = (high - low) * 0.12
    ax.set_xlim(low - pad, high + pad)
    ax.set_ylim(-1.45, 1.15)                             # 위(현재가)·아래(최저·최고) 글자의 여백을 비슷하게
    ax.axis("off")
    fig.savefig(path, dpi=REPORT_DPI, facecolor="white")
    plt.close(fig)
    _outline(path)


def _returns_report(items, path):
    """리포트용 기간 수익률 막대. 172mm x 0.42 고정 크기, 축·값 10pt."""
    plt = _mpl(report=True)
    labels = [label for label, _ in items]
    values = [value for _, value in items]
    colors = [COLOR_UP if v >= 0 else COLOR_DOWN for v in values]
    fig, ax = plt.subplots(figsize=_report_figsize("returns"))
    bars = ax.bar(labels, values, color=colors, width=0.45)
    ax.axhline(0, color="#90A4AE", linewidth=1)
    for bar, value in zip(bars, values):
        ax.annotate(f"{value:+.2f}%", (bar.get_x() + bar.get_width() / 2, value),
                    xytext=(0, 4 if value >= 0 else -4), textcoords="offset points",
                    ha="center", va="bottom" if value >= 0 else "top",
                    fontsize=REPORT_PT, fontweight="bold", color=COLOR_UP if value >= 0 else COLOR_DOWN)
    span = max(abs(v) for v in values) or 1
    ax.set_ylim(min(0, min(values)) - span * 0.25, max(0, max(values)) + span * 0.25)
    ax.set_ylabel("수익률(%)", fontsize=REPORT_PT)
    ax.tick_params(labelsize=REPORT_PT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    _mpl_report_save(fig, path)
    plt.close(fig)


def save_returns_png(items, path_or_buffer, width=700, height=300, report=False, app=False):
    """기간 수익률 막대(상승 빨강, 하락 파랑, 막대 끝에 값 표시 - 쉽게 읽기 2장). items: [(라벨, 수익률%), ...]

    report=True: Word 리포트 규격(지침 v1.6 12.3). path_or_buffer는 파일 경로여야 한다.
    app=True: 앱 화면 규격(app_fig, 1100px 1:1). width·height 인자는 무시한다.
    """
    if report:
        _returns_report(items, path_or_buffer)
        return
    if app:
        _returns_app(items, path_or_buffer)
        return
    plt = _mpl()
    labels = [label for label, _ in items]
    values = [value for _, value in items]
    colors = [COLOR_UP if v >= 0 else COLOR_DOWN for v in values]
    fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=200)
    bars = ax.bar(labels, values, color=colors, width=0.5)
    ax.axhline(0, color="#90A4AE", linewidth=1)
    for bar, value in zip(bars, values):
        ax.annotate(f"{value:+.2f}%", (bar.get_x() + bar.get_width() / 2, value),
                    xytext=(0, 6 if value >= 0 else -14), textcoords="offset points",
                    ha="center", fontsize=10, fontweight="bold", color=COLOR_UP if value >= 0 else COLOR_DOWN)
    span = max(abs(v) for v in values) or 1
    ax.set_ylim(min(0, min(values)) - span * 0.25, max(0, max(values)) + span * 0.25)
    ax.set_ylabel("수익률(%)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    fig.savefig(path_or_buffer, bbox_inches="tight", facecolor="white", format="png")
    plt.close(fig)
