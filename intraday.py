"""
장중 참고용 현재가 한 줄 (앱 화면 전용, 2026-10-06)

판정과 분석은 그대로 확정 종가(리포트 구성 지침 5.0) 기준이다. 이 모듈은 그 값을 건드리지 않고,
장중(거래일 09:00 ~ 15:40, 한국시간)에만 네이버 금융 지연 시세를 한 번 불러 참고 문구를 만든다.

 - 시간 판단: data.now_kst() (고정 +09:00 오프셋)라 서버 시간대(TZ=UTC 클라우드 포함)와 무관하다.
 - 거래일 판단: 휴장일 달력을 따로 두지 않는다. 평일이면서 네이버 시세 시각(localTradedAt)의 날짜가
   오늘일 때만 거래일로 본다. 휴장일에는 시세 시각이 직전 거래일에 머물러 있어 자연히 걸러진다.
 - 실패(네트워크·형식 오류·timeout 3초)는 조용히 None -> 화면에 줄을 그리지 않는다.
 - report.py · 판정/계산 로직에서는 쓰지 않는다.
"""

from datetime import datetime, time as dtime

import requests
import streamlit as st

import data as dl

QUOTE_URL = "https://m.stock.naver.com/api/stock/{code}/basic"
QUOTE_TIMEOUT = 3                    # 초
QUOTE_TTL = 60                       # st.cache_data 유지 시간(초)
OPEN_TIME = dtime(9, 0)
SHOW_UNTIL = dl.CLOSE_CUTOFF         # 15:40 - 이후에는 기준일이 오늘 종가가 되므로 줄을 숨긴다
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_UP_CODES = {"1", "2"}               # 상한·상승
_DOWN_CODES = {"4", "5"}             # 하한·하락


def in_window(now=None):
    """한국시간 평일 09:00 ~ 15:40(미만) 사이인가(휴장일 여부는 시세 시각으로 따로 본다)."""
    now = now or dl.now_kst()
    return now.weekday() < 5 and OPEN_TIME <= now.time() < SHOW_UNTIL


def _num(text):
    return float(str(text).replace(",", "").replace("+", "").replace("-", ""))


@st.cache_data(ttl=QUOTE_TTL, show_spinner=False)
def fetch_quote(code):
    """네이버 지연 시세 1회 요청 -> {현재가, 전일대비, 등락률, 시각(datetime, KST)} 또는 None."""
    try:
        resp = requests.get(QUOTE_URL.format(code=code), headers=_HEADERS, timeout=QUOTE_TIMEOUT)
        resp.raise_for_status()
        js = resp.json()
        direction = str((js.get("compareToPreviousPrice") or {}).get("code", "3"))
        sign = 1 if direction in _UP_CODES else -1 if direction in _DOWN_CODES else 0
        traded = datetime.fromisoformat(js["localTradedAt"])
        return {
            "현재가": _num(js["closePrice"]),
            "전일대비": sign * _num(js["compareToPreviousClosePrice"]),
            "등락률": sign * _num(js["fluctuationsRatio"]),
            "시각": traded.astimezone(dl.KST).replace(tzinfo=None),
        }
    except Exception:
        return None


def quote_line(code, base_date, now=None, fetch=None):
    """표시할 장중 한 줄의 재료(dict) 또는 None(표시 안 함).

    base_date: 판정·분석 기준일(확정 종가 날짜, 'YYYY-MM-DD').
    now / fetch: 검증용 주입(기본은 한국시간 현재 / fetch_quote).
    """
    now = now or dl.now_kst()
    if not in_window(now):
        return None
    quote = (fetch or fetch_quote)(str(code))
    if not quote or quote["시각"].date() != now.date():     # 휴장일: 시세 시각이 오늘이 아니다
        return None
    return {**quote, "기준일": str(base_date)}


def format_line(q):
    """'장중 현재가 276,500원 (+1,500원, +0.55%) · 15:17 기준 지연 시세 | 판정과 분석은 2026-10-02 종가 기준'."""
    price = f"{q['현재가']:,.0f}원 ({q['전일대비']:+,.0f}원, {q['등락률']:+.2f}%)"
    tail = f" · {q['시각']:%H:%M} 기준 지연 시세 | 판정과 분석은 {q['기준일']} 종가 기준"
    return "장중 현재가 ", price, tail
