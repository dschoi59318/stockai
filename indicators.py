# -*- coding: utf-8 -*-
"""
indicators.py - 개별 종목의 가격 지표 계산

[3단계] Claude에게 넘길 '숫자 근거'와 '사실 문장'을 여기서 전부 만든다.
가격은 모두 pykrx 일봉(정규장 종가) 기준이며, 시간외 거래는 반영하지 않는다.

값 규칙
 - 가격은 원 단위 정수로 반올림한다(모델이 소수점을 만들어 내지 않도록).
 - 비율·수익률은 소수 2자리로 반올림한다.
 - 대소 관계(위/아래, 높다/낮다, 증감 방향)는 파이썬이 판정해 '사실' 리스트에
   한국어 문장으로 넣는다. 모델은 이 문장만 인용하고 숫자를 직접 비교하지 않는다.

계산 항목
 1) 기간 수익률 (1주/1개월/3개월/6개월/1년)
 2) 이동평균(20/60/120일) 값·이격도·배열 상태와 배열 문자열
 3) 52주 최고·최저 대비 거리와 고저 폭
 4) 거래량 (최근 5일 평균 / 60일 평균 / 비율)
 5) 변동성 (최근 20일 일간수익률 표준편차의 연율화)
 6) 업종 대비 1개월 수익률 (같은 업종그룹 종목들의 평균과 비교)
 7) 위 항목들의 대소 관계를 문장으로 정리한 '사실' 리스트
 8) [4-2단계] 재무 블록(financials.ai_block): 최근 4분기 합산 손익, 비율, 연간·분기 매출·영업이익,
    재무 사실 문장(증감·흑자/적자·추세). 데이터가 없으면 사유만 담는다.
"""

import os
import time                                                                      # [계측]
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st

import data as dl

# 기간 라벨 -> 달력 일수
RETURN_PERIODS = {
    "1주": 7,
    "1개월": 30,
    "3개월": 91,
    "6개월": 182,
    "1년": 365,
}

TRADING_DAYS = 252          # 연율화에 쓰는 연간 거래일 수
FETCH_DAYS = 560            # 1년 + MA120 계산 여유분
MIN_PEERS = 3               # 업종 평균을 내기 위한 최소 비교 종목 수

# 이동평균 배열 판정 기준 (분석문에도 그대로 전달한다)
ARRANGEMENT_RULE = ("정배열: 현재가 > MA20 > MA60 > MA120 / "
                    "역배열: 현재가 < MA20 < MA60 < MA120 / 혼조: 그 외")

MA_WINDOWS = (20, 60, 120)


def _won(value):
    """가격을 원 단위 정수로 반올림한다."""
    return None if value is None else int(round(float(value)))


def _pct(value):
    """비율을 소수 2자리로 반올림한다."""
    return None if value is None else round(float(value), 2)


def _fetch(code):
    """지표 계산용 일봉을 가져온다(1년 + 이동평균 여유분)."""
    end = datetime.today()
    return dl.fetch_ohlcv_raw(code, end - timedelta(days=FETCH_DAYS), end)


def _ma_block(df):
    """이동평균 20/60/120일 값, 이격도, 배열 상태와 배열 문자열을 만든다.

    - 이격도(%) : 현재가가 이동평균보다 얼마나 위/아래에 있는지 = (현재가/MA - 1) x 100
    - 배열 상태 : ARRANGEMENT_RULE 기준으로 정배열 / 역배열 / 혼조
    """
    close = df["종가"]
    last = _won(close.iloc[-1])
    out = {"배열판정기준": ARRANGEMENT_RULE}
    mas = {}

    for window in MA_WINDOWS:
        if len(close) >= window:
            ma = _won(close.rolling(window).mean().iloc[-1])
            mas[window] = ma
            out[f"MA{window}"] = ma
            out[f"MA{window}_이격도"] = _pct((last / ma - 1) * 100)
        else:
            mas[window] = None
            out[f"MA{window}"] = None
            out[f"MA{window}_이격도"] = None

    if all(mas.get(w) for w in MA_WINDOWS):
        if last > mas[20] > mas[60] > mas[120]:
            state = "정배열"
        elif last < mas[20] < mas[60] < mas[120]:
            state = "역배열"
        else:
            state = "혼조"

        # 실제 값으로 대소 관계 문장을 만들어 둔다(모델이 부등호를 틀리지 않도록).
        items = [("현재가", last)] + [(f"MA{w}", mas[w]) for w in MA_WINDOWS]
        text = f"{items[0][0]} {items[0][1]:,}"
        for (_, prev_value), (name, value) in zip(items, items[1:]):
            op = ">" if prev_value > value else ("<" if prev_value < value else "=")
            text += f" {op} {name} {value:,}"
        out["배열상태"] = state
        out["배열문자열"] = f"{text} ({state})"
    else:
        out["배열상태"] = "데이터 부족"
        out["배열문자열"] = "이동평균을 계산할 데이터가 부족합니다"
    return out


def _period_returns(df):
    """기간별 수익률(%)을 계산한다. 데이터가 짧은 기간은 None."""
    out = {}
    span_days = (df.index[-1] - df.index[0]).days
    for label, days in RETURN_PERIODS.items():
        rate = dl.period_change_rate(df, days)
        # 요청 기간만큼 데이터가 없으면(상장 직후 등) 값을 비워 둔다.
        out[label] = _pct(rate) if (rate is not None and span_days >= days * 0.8) else None
    return out


def _volume_block(df):
    """최근 5일 평균 거래량, 60일 평균 거래량, 그 비율을 계산한다."""
    vol = df["거래량"]
    v5 = int(round(vol.tail(5).mean())) if len(vol) >= 5 else None
    v60 = int(round(vol.tail(60).mean())) if len(vol) >= 60 else None
    ratio = round(v5 / v60, 2) if (v5 and v60) else None
    return {
        "최근5일_평균거래량": v5,
        "최근60일_평균거래량": v60,
        "거래량비율_5일대60일": ratio,          # 예: 0.72 (배)
    }


def _volatility(df):
    """최근 20일 일간수익률 표준편차를 연율화한 변동성(%)."""
    ret = df["종가"].pct_change().dropna()
    if len(ret) < 20:
        return None
    return _pct(ret.tail(20).std() * np.sqrt(TRADING_DAYS) * 100)


def _week52_block(df):
    """52주(1년) 최고·최저, 현재가와의 거리, 고저 폭을 계산한다."""
    year = df[df.index >= df.index[-1] - pd.Timedelta(days=365)]
    if year.empty:
        year = df
    last = _won(df["종가"].iloc[-1])
    high = _won(year["고가"].max())
    low = _won(year["저가"].min())
    return {
        "52주_최고": high,
        "52주_최저": low,
        "52주최고_대비": _pct((last / high - 1) * 100) if high else None,
        "52주최저_대비": _pct((last / low - 1) * 100) if low else None,
        "52주_고저폭": _pct((high / low - 1) * 100) if low else None,   # 최고가가 최저가보다 몇 % 높은지
    }


def _industry_snapshot(base_date):
    """기준일 시점의 업종 매핑 스냅샷을 돌려준다.

    data/cache/industry_snapshot_{기준일}.csv 가 있으면 그것을 쓰고, 없으면 현재 industry_map을
    그 이름으로 저장해 둔다. 같은 기준일에는 매핑이 나중에 갱신돼도 같은 표본을 쓴다.
    """
    import industry

    path = os.path.join(dl.CACHE_DIR, f"industry_snapshot_{base_date.strftime('%Y%m%d')}.csv")
    if os.path.exists(path):
        _ts = time.perf_counter()                                                # [계측]
        try:
            return pd.read_csv(path, dtype={"종목코드": str}, encoding="utf-8-sig")
        except Exception:
            pass
        finally:                                                                 # [계측]
            print(f"[SUB] 캐시읽기 industry_snapshot {time.perf_counter() - _ts:.2f}s {dl.sub_tag()}", flush=True)
    imap = industry.load_industry_map()
    if not imap.empty:
        _ts = time.perf_counter()                                                # [계측]
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            imap.to_csv(path, index=False, encoding="utf-8-sig")
        except Exception:
            pass
        print(f"[SUB] 캐시쓰기 industry_snapshot {time.perf_counter() - _ts:.2f}s {dl.sub_tag()}", flush=True)  # [계측]
    return imap


def _industry_block(code, name="", base_date=None):
    """같은 업종그룹 종목들의 1개월 평균 수익률과 비교한다.

    [표본 고정] 기준일 시점 업종 매핑 스냅샷의 같은 업종 종목 '전부'를 표본으로 쓴다.
     - 예전에는 그날 일봉 캐시에 이미 있는 종목만 써서, 히트맵을 어느 시장까지 열었느냐에 따라
       같은 기준일에도 표본(예: 52 -> 14종목)과 평균이 달라졌다.
     - 캐시에 없는 종목은 load_ohlcv_bulk로 채우고(같은 날 재사용), 기준일 이후 데이터는 잘라 낸다.
    비교 종목이 MIN_PEERS 미만이면 '업종 비교 표본 부족(n=O)'으로 표기한다.
    """
    import industry

    # 매핑에 없는 종목이면 DART를 1회 호출해 업종을 채우고 CSV에 저장한다.
    _ts = time.perf_counter()                                                    # [계측]
    group = industry.ensure_industry(code, name)
    print(f"[SUB] ensure_industry {code} {time.perf_counter() - _ts:.2f}s {dl.sub_tag()}", flush=True)  # [계측]
    if group == industry.ETC:
        return {"가능": False, "사유": "업종 비교 불가 (업종 정보를 확인할 수 없음)", "업종그룹": group}

    base_date = pd.Timestamp(base_date or datetime.today()).normalize()
    imap = _industry_snapshot(base_date)
    if imap.empty:
        return {"가능": False, "사유": "업종 비교 불가 (업종 매핑 파일 없음)", "업종그룹": group}

    imap["종목코드"] = imap["종목코드"].astype(str).str.zfill(6)
    peer_codes = imap[(imap["업종그룹"] == group) & (imap["종목코드"] != str(code).zfill(6))]["종목코드"].tolist()
    _ts = time.perf_counter()                                                    # [계측]
    store = dl.load_ohlcv_bulk(peer_codes) if peer_codes else {}
    print(f"[SUB] load_ohlcv_bulk(업종 {group} 비교 {len(peer_codes)}종목) {time.perf_counter() - _ts:.2f}s "
          f"{dl.sub_tag()}", flush=True)                                         # [계측]

    rates = []
    for peer_code in peer_codes:
        peer_df = store.get(peer_code)
        if peer_df is None or peer_df.empty:
            continue
        peer_df = peer_df[peer_df.index <= base_date]          # 기준일 시점으로 맞춘다
        if peer_df.empty:
            continue
        rate = dl.period_change_rate(peer_df, 30)
        if rate is not None:
            rates.append(rate)

    if len(rates) < MIN_PEERS:
        return {"가능": False, "사유": f"업종 비교 표본 부족(n={len(rates)})",
                "업종그룹": group, "비교종목수": len(rates)}

    # 평균과 함께 중앙값을 낸다. 대형주 급등 한두 종목에 평균이 끌려가는 영향을 줄이려고
    # AI 입력의 초과수익률은 중앙값 기준으로 넘긴다(대상 종목 자신은 표본에서 이미 뺐다).
    return {
        "가능": True,
        "업종그룹": group,
        "비교종목수": len(rates),
        "표본설명": f"본 종목 제외 {len(rates)}종목",
        "표본기준": f"{base_date.strftime('%Y-%m-%d')} 업종 매핑 스냅샷",
        "업종평균_1개월수익률": _pct(np.mean(rates)),
        "업종중앙값_1개월수익률": _pct(np.median(rates)),
    }


def _build_facts(last, ma, returns, day_rate, volume, week52, industry_block):
    """대소 관계를 파이썬이 판정해 한국어 사실 문장 리스트로 만든다.

    모델은 이 문장들만 근거로 '높다/낮다/위/아래/증가/감소'를 서술한다.
    """
    facts = [ma.get("배열문자열", "")]

    values = {w: ma.get(f"MA{w}") for w in MA_WINDOWS}
    if all(values.get(w) for w in MA_WINDOWS):
        names = [f"MA{w}" for w in MA_WINDOWS]
        higher = [n for n, w in zip(names, MA_WINDOWS) if last > values[w]]
        lower = [n for n, w in zip(names, MA_WINDOWS) if last < values[w]]
        if not lower:
            facts.append("현재가는 " + ", ".join(names) + " 모두보다 높다")
        elif not higher:
            facts.append("현재가는 " + ", ".join(names) + " 모두보다 낮다")
        else:
            facts.append("현재가는 " + ", ".join(higher) + "보다 높고 " +
                         ", ".join(lower) + "보다 낮다")

        # 이동평균 하나하나에 대해서도 방향을 따로 못 박는다(뭉뚱그린 문장과 혼동하지 않도록).
        for n, w in zip(names, MA_WINDOWS):
            word = "높다" if last > values[w] else ("낮다" if last < values[w] else "같다")
            facts.append(f"현재가는 {n}보다 {word}")

        # 이동평균끼리의 쌍 비교
        for i, first in enumerate(MA_WINDOWS):
            for second in MA_WINDOWS[i + 1:]:
                a, b = values[first], values[second]
                word = "높다" if a > b else ("낮다" if a < b else "같다")
                facts.append(f"MA{first}은 MA{second}보다 {word}")

        facts.append(f"이동평균 배열 상태는 {ma.get('배열상태')}이다")

    # 수익률 부호 요약
    positive = [k for k, v in returns.items() if v is not None and v > 0]
    negative = [k for k, v in returns.items() if v is not None and v < 0]
    parts = []
    if positive:
        parts.append("·".join(positive) + " 수익률은 양수")
    if negative:
        parts.append("·".join(negative) + " 수익률은 음수")
    if parts:
        facts.append(", ".join(parts) + "이다")

    if day_rate is not None:
        word = "양수" if day_rate > 0 else ("음수" if day_rate < 0 else "보합")
        facts.append(f"전일 대비 등락률은 {word}이다")

    ratio = volume.get("거래량비율_5일대60일")
    if ratio is not None:
        word = "적다" if ratio < 1 else ("많다" if ratio > 1 else "같다")
        facts.append(f"최근 5일 평균 거래량은 60일 평균보다 {word}")

    if week52.get("52주_최고") and week52.get("52주_최저"):
        facts.append("현재가는 52주 최고가보다 낮고 52주 최저가보다 높다")

    if industry_block.get("가능"):
        mine = returns.get("1개월")
        peer = industry_block.get("업종중앙값_1개월수익률")          # 중앙값 기준
        if mine is not None and peer is not None:
            word = "낮다" if mine < peer else ("높다" if mine > peer else "같다")
            facts.append(f"1개월 수익률이 업종 중앙값보다 {word}")

    return [f for f in facts if f]


@st.cache_data(ttl=60 * 30, show_spinner=False)
def compute(code, name="", market=""):
    """종목 하나의 지표를 모두 계산해 dict로 반환한다(30분 캐시). 실패하면 None."""
    _t = time.perf_counter()                                                     # [계측] st 캐시가 없을 때만 찍힌다
    code = str(code).zfill(6)
    print(f"[SUB] indicators.compute 시작(st 캐시 없음) {code} {dl.sub_tag()}", flush=True)  # [계측]
    df = _fetch(code)
    print(f"[SUB] _fetch(시세 1년) {code} {time.perf_counter() - _t:.2f}s {dl.sub_tag()}", flush=True)  # [계측]
    if df is None or df.empty or len(df) < 25:
        print(f"[STEP] indicators.compute(없음) {code} {time.perf_counter() - _t:.2f}s", flush=True)  # [계측]
        return None

    last = _won(df["종가"].iloc[-1])
    day_rate = _pct(dl.period_change_rate(df, 1) or 0.0)
    ma = _ma_block(df)
    returns = _period_returns(df)
    volume = _volume_block(df)
    week52 = _week52_block(df)
    _ts = time.perf_counter()                                                    # [계측]
    industry_block = _industry_block(code, name, df.index[-1])
    print(f"[SUB] _industry_block {code} {time.perf_counter() - _ts:.2f}s {dl.sub_tag()}", flush=True)  # [계측]

    result = {
        "종목명": name,
        "종목코드": code,
        "시장": market,
        "기준일": df.index[-1].strftime("%Y-%m-%d"),
        "가격기준": "정규장 종가 (시간외 거래 미반영)",
        "거래일수": len(df),
        "현재가": last,
        "전일대비_등락률": day_rate,
        "기간수익률": returns,
        "이동평균": ma,
        "52주": week52,
        "거래량": volume,
        "변동성_20일연율화": _volatility(df),
        "업종대비": industry_block,
    }

    # 업종 비교가 가능하면 초과수익률을 미리 계산한다.
    #  초과수익률 = 내 1개월 - 업종 중앙값 1개월 (AI 입력 기준), 초과수익률_평균기준은 표 참고용
    one_month = returns.get("1개월")
    if industry_block.get("가능") and one_month is not None:
        industry_block["종목_1개월수익률"] = one_month
        industry_block["초과수익률"] = _pct(one_month - industry_block["업종중앙값_1개월수익률"])
        industry_block["초과수익률_평균기준"] = _pct(one_month - industry_block["업종평균_1개월수익률"])

    # 대소 관계는 모두 여기서 문장으로 확정한다.
    result["사실"] = _build_facts(last, ma, returns, day_rate, volume, week52, industry_block)

    # [4-2단계] 재무 블록 (DART). 재무 사실 문장은 블록 안의 '사실'에 따로 둔다.
    import financials
    _ts = time.perf_counter()                                                    # [계측]
    result["재무"] = financials.ai_block(code, name, industry_block.get("업종그룹"))
    print(f"[SUB] financials.ai_block {code} {time.perf_counter() - _ts:.2f}s {dl.sub_tag()}", flush=True)  # [계측]

    # 관찰 지표 후보: 표현을 고정한 완성 문자열. AI는 이 중에서만 고른다(PER·PBR은 후보에서 뺀다).
    result["관찰지표후보"] = _watch_candidates(result)
    print(f"[STEP] indicators.compute {code} {time.perf_counter() - _t:.2f}s", flush=True)  # [계측]
    return result


def _watch_candidates(ind):
    """관찰 지표 후보 문자열 목록(가격·거래량·변동성 + 영업이익률). PER·PBR은 넣지 않는다."""
    out = []
    ratio = (ind.get("거래량") or {}).get("거래량비율_5일대60일")
    if ratio is not None:
        out.append(f"60일 평균 대비 최근 5일 평균 거래량 {ratio:.2f}배")
    ma = ind.get("이동평균") or {}
    for w in (20, 60):
        gap = ma.get(f"MA{w}_이격도")
        if gap is not None:
            out.append(f"{w}일 이동평균 대비 현재가 이격도 {gap:+.2f}%")
    if ma.get("배열상태") in ("정배열", "역배열", "혼조"):
        out.append(f"이동평균 배열 상태({ma['배열상태']})")
    vol = ind.get("변동성_20일연율화")
    if vol is not None:
        out.append(f"최근 20일 일간수익률 기준 연율화 변동성 {vol:.2f}%")
    w52 = ind.get("52주") or {}
    if w52.get("52주최고_대비") is not None:
        out.append(f"52주 최고가 대비 현재가 {w52['52주최고_대비']:+.2f}%")
    fin = ind.get("재무") or {}
    margin = (fin.get("손익비율") or {}).get("영업이익률")
    if fin.get("가능") and margin and "해당 없음" not in margin:
        out.append(f"최근 4분기 합산 {margin}")
    return out


def to_table(ind):
    """지표 dict를 화면에 표로 보여 주기 위한 DataFrame으로 바꾼다."""
    if not ind:
        return pd.DataFrame(columns=["구분", "항목", "값"])

    def fmt(value, suffix="", digits=2):
        if value is None:
            return "-"
        if isinstance(value, (int, float)):
            return f"{value:,.{digits}f}{suffix}"
        return str(value)

    rows = []
    for label in RETURN_PERIODS:
        rows.append(("기간 수익률", label, fmt(ind["기간수익률"].get(label), "%")))

    ma = ind["이동평균"]
    for window in MA_WINDOWS:
        rows.append(("이동평균", f"MA{window}", fmt(ma.get(f'MA{window}'), "원", 0)))
        rows.append(("이동평균", f"현재가 vs MA{window}", fmt(ma.get(f'MA{window}_이격도'), "%")))
    rows.append(("이동평균", "배열 상태", ma.get("배열문자열", ma.get("배열상태", "-"))))

    w = ind["52주"]
    rows.append(("52주", "최고", fmt(w["52주_최고"], "원", 0)))
    rows.append(("52주", "최저", fmt(w["52주_최저"], "원", 0)))
    rows.append(("52주", "최고 대비", fmt(w["52주최고_대비"], "%")))
    rows.append(("52주", "최저 대비", fmt(w["52주최저_대비"], "%")))
    rows.append(("52주", "고저 폭", fmt(w.get("52주_고저폭"), "%")))

    v = ind["거래량"]
    rows.append(("거래량", "최근 5일 평균", fmt(v["최근5일_평균거래량"], "주", 0)))
    rows.append(("거래량", "최근 60일 평균", fmt(v["최근60일_평균거래량"], "주", 0)))
    rows.append(("거래량", "5일 / 60일 비율", fmt(v["거래량비율_5일대60일"], "배")))

    rows.append(("변동성", "20일 변동성(연율화)", fmt(ind["변동성_20일연율화"], "%")))

    ic = ind["업종대비"]
    if ic.get("가능"):
        rows.append(("업종 대비", "업종그룹", ic["업종그룹"]))
        sample = ic.get("표본설명") or f"본 종목 제외 {ic['비교종목수']}종목"
        rows.append(("업종 대비", f"업종 평균 1개월 ({sample})", fmt(ic["업종평균_1개월수익률"], "%")))
        rows.append(("업종 대비", f"업종 중앙값 1개월 ({sample})", fmt(ic.get("업종중앙값_1개월수익률"), "%")))
        rows.append(("업종 대비", "초과 수익률 (중앙값 기준)", fmt(ic.get("초과수익률"), "%p")))
        rows.append(("업종 대비", "초과 수익률 (평균 기준)", fmt(ic.get("초과수익률_평균기준"), "%p")))
    else:
        if ic.get("업종그룹"):
            rows.append(("업종 대비", "업종그룹", ic["업종그룹"]))
        rows.append(("업종 대비", "상태", ic.get("사유", "업종 비교 불가")))

    for i, fact in enumerate(ind.get("사실", []), start=1):
        rows.append(("사실 문장", f"{i}", fact))

    return pd.DataFrame(rows, columns=["구분", "항목", "값"])
