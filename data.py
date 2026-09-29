# -*- coding: utf-8 -*-
"""
data.py - 종목 목록 / 시세 / 히트맵용 데이터 수집 담당

수집 원칙
 - 가격(현재가·등락률)은 pykrx 일봉만 쓴다. 네이버 금융과 같은 정규장 종가 기준.
 - FinanceDataReader는 종목 풀과 시가총액 용도로만 쓴다(스냅샷 가격은 시간외가 섞여 다름).
 - 네트워크 호출은 streamlit 캐시 또는 pkl 파일 캐시로 감싸서 같은 날 재실행 시 재사용한다

[1단계] 개별 종목 검색 / 일봉 조회
[2단계] 종목 풀·시가총액(FDR), 200종목 일괄 일봉 수집(pykrx), 보유종목 CSV
[보유종목 입력 개편] 종목 마스터 파일(data/stock_master.csv), 보유종목 추가·수정·삭제 함수

[리포트 구성 지침 v1.4 5.0 기준일]
 - 기준일 = 정규장이 끝난 가장 최근 거래일. 한국시간 15시 40분 이전 실행이면 당일은 기준일이 될 수 없다.
 - session_cutoff(): 일봉을 쓸 수 있는 마지막 날짜(15:40 이전 = 어제, 이후 = 오늘). 휴장일은 일봉이 없으므로
   자르고 남은 마지막 행이 곧 직전 거래일이다.
 - fetch_ohlcv_raw가 cutoff 뒤의 일봉(당일 장중 일봉)을 모두 잘라 내므로, 이 함수를 거치는 가격·지표·사건·
   히트맵·가격 차트·앱 화면 계산에서 장중 일봉이 빠진다. 일괄 일봉 pkl 캐시 이름도 cutoff 날짜를 쓴다.
"""

import os
import time
import pickle
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone, time as dtime

import pandas as pd
import requests
import streamlit as st


# ---------------------------------------------------------------------------
# 네트워크 안전장치
# pykrx / FinanceDataReader 는 내부 요청에 timeout을 주지 않아서, 거래소가 응답을
# 끊으면 프로그램이 영원히 멈춘다. 모든 requests 호출에 기본 timeout을 심어 둔다.
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT = 10        # 요청 하나가 기다릴 최대 초
REQUEST_DELAY = 0.2         # 작업 스레드가 요청 사이에 쉬는 시간(초당 약 20건 제한)

_original_session_request = requests.Session.request


def _session_request_with_timeout(self, *args, **kwargs):
    """requests 세션 요청에 기본 timeout을 끼워 넣는다."""
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return _original_session_request(self, *args, **kwargs)


if getattr(requests.Session.request, "__name__", "") != "_session_request_with_timeout":
    requests.Session.request = _session_request_with_timeout

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
HOLDINGS_CSV = os.path.join(DATA_DIR, "holdings.csv")
HOLDINGS_SAMPLE_CSV = os.path.join(DATA_DIR, "holdings_sample.csv")

HOLDINGS_COLUMNS = ["종목코드", "종목명", "수량", "평균매수가"]

# 기간 선택 라벨 -> 조회 일수(달력 기준)  [1단계 개별 종목 차트용]
PERIOD_OPTIONS = {
    "1개월": 30,
    "3개월": 90,
    "6개월": 180,
    "1년": 365,
}

# 히트맵 기간 라벨 -> (기준 일수, 색상 클리핑 %)  [2단계 시장 히트맵용]
HEATMAP_PERIODS = {
    "1일": (1, 3.0),
    "1주": (7, 3.0),
    "1개월": (30, 10.0),
    "3개월": (91, 30.0),
    "6개월": (182, 30.0),
    "1년": (365, 30.0),
}

# 이동평균 계산에 필요한 과거 데이터 여유분(60일선이 화면 첫날부터 그려지도록)
MA_BUFFER_DAYS = 130

# 히트맵에 쓸 종목 수 / 일괄 수집 동시 요청 수
TOP_N = 200
MAX_WORKERS = 4


def _ensure_dirs():
    """data/ 와 data/cache/ 폴더를 만들어 둔다."""
    os.makedirs(CACHE_DIR, exist_ok=True)


class _NoCache(Exception):
    """st.cache_data 함수가 실패 결과를 캐시하지 않게 올리는 예외(2026-09-29 실패 캐시 방지).

    value = 공개 함수가 호출한 쪽에 돌려줄 기존 실패 값(빈 DataFrame 등). 화면 문구는 그대로 나온다.
    """
    def __init__(self, value):
        super().__init__("실패 결과는 캐시하지 않음")
        self.value = value


# ===========================================================================
# 1단계 - 종목 목록
# ===========================================================================

def _ticker_list_fdr():
    """FinanceDataReader로 코스피·코스닥 종목 목록을 가져온다(우선주 포함, 코넥스 제외). 실패하면 None."""
    import FinanceDataReader as fdr

    df = fdr.StockListing("KRX")
    if df is None or df.empty:
        return None

    df = df[["Code", "Name", "Market"]].copy()
    df.columns = ["종목코드", "종목명", "시장"]
    df["종목코드"] = df["종목코드"].astype(str).str.zfill(6)
    # 'KOSDAQ GLOBAL' 처럼 뒤에 구분이 붙는 경우가 있어 앞 단어만 남긴다.
    df["시장"] = df["시장"].astype(str).str.split().str[0]
    df = df[df["시장"].isin(["KOSPI", "KOSDAQ"])]           # KONEX 제외
    return df.reset_index(drop=True) if not df.empty else None


# ---------------------------------------------------------------------------
# 종목 마스터 파일 data/stock_master.csv (종목명, 종목코드, 시장)
#  - 앱 시작 시 파일 날짜(수정일)가 오늘이 아니면 FDR로 갱신을 시도하고, 실패하면 기존 파일을 쓴다.
#  - 종목 분석 검색, 보유종목 드롭다운, 보유종목 코드 검증이 모두 이 파일을 쓴다.
# ---------------------------------------------------------------------------
STOCK_MASTER_CSV = os.path.join(DATA_DIR, "stock_master.csv")
MASTER_COLUMNS = ["종목명", "종목코드", "시장"]


def _fetch_master():
    """마스터 원본 수집(FDR). 테스트에서 이 함수를 바꿔 '인터넷 차단'을 흉내 낼 수 있다."""
    return _ticker_list_fdr()


def master_updated_date():
    """마스터 파일의 마지막 갱신일(date). 파일이 없으면 None."""
    if not os.path.exists(STOCK_MASTER_CSV):
        return None
    return datetime.fromtimestamp(os.path.getmtime(STOCK_MASTER_CSV)).date()


def refresh_stock_master():
    """FDR로 종목 마스터를 새로 받아 저장한다. 반환 (성공 여부, 안내 문구).

    실패하면 기존 파일을 건드리지 않는다(임시 파일에 쓴 뒤 교체).
    """
    _ensure_dirs()
    try:
        df = _fetch_master()
    except Exception as exc:
        return False, f"종목 목록 갱신 실패({type(exc).__name__}) - 기존 목록을 사용합니다."
    if df is None or df.empty:
        return False, "종목 목록 갱신 실패(빈 응답) - 기존 목록을 사용합니다."

    df = df.drop_duplicates(subset="종목코드").sort_values("종목명")[MASTER_COLUMNS]
    tmp = STOCK_MASTER_CSV + ".tmp"
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    os.replace(tmp, STOCK_MASTER_CSV)
    load_ticker_list.clear()
    return True, f"종목 목록을 갱신했습니다({len(df):,}종목)."


def ensure_stock_master():
    """파일 날짜가 오늘이 아니면(또는 파일이 없으면) 갱신을 시도한다.

    반환: {"시도": bool, "성공": bool, "문구": str, "날짜": date|None}
    """
    if master_updated_date() == datetime.today().date():
        return {"시도": False, "성공": True, "문구": "", "날짜": master_updated_date()}
    ok, message = refresh_stock_master()
    return {"시도": True, "성공": ok, "문구": message, "날짜": master_updated_date()}


@st.cache_data(show_spinner=False)
def _read_master(mtime):
    """마스터 CSV를 읽는다. 파일 수정 시각(mtime)을 키로 캐시해 갱신되면 다시 읽는다."""
    df = pd.read_csv(STOCK_MASTER_CSV, dtype={"종목코드": str}, encoding="utf-8-sig")
    df["종목코드"] = df["종목코드"].astype(str).str.zfill(6)
    return df[["종목코드", "종목명", "시장"]].reset_index(drop=True)


def load_ticker_list():
    """코스피 + 코스닥 전체 종목 목록(data/stock_master.csv)을 DataFrame으로 반환한다.

    반환 컬럼: 종목코드 / 종목명 / 시장. 파일이 없으면 한 번 받아 보고, 그래도 없으면 빈 표.
    """
    if not os.path.exists(STOCK_MASTER_CSV):
        refresh_stock_master()
    if not os.path.exists(STOCK_MASTER_CSV):
        return pd.DataFrame(columns=["종목코드", "종목명", "시장"])
    try:
        return _read_master(os.path.getmtime(STOCK_MASTER_CSV))
    except Exception:
        return pd.DataFrame(columns=["종목코드", "종목명", "시장"])


load_ticker_list.clear = _read_master.clear      # 갱신 후 캐시 비우기용


def search_stocks(ticker_df, keyword):
    """종목명 부분일치 검색. 공백을 지우고 대소문자를 무시해서 비교한다."""
    if ticker_df is None or ticker_df.empty:
        return ticker_df
    key = str(keyword).replace(" ", "").upper()
    if not key:
        return ticker_df.head(0)

    normalized = ticker_df["종목명"].astype(str).str.replace(" ", "", regex=False).str.upper()
    matched = ticker_df[normalized.str.contains(key, regex=False) | ticker_df["종목코드"].str.contains(key)]
    # 이름이 짧은 순(= 정확히 일치에 가까운 순)으로 정렬해 원하는 종목이 위에 오게 한다.
    return matched.assign(_len=matched["종목명"].str.len()).sort_values(["_len", "종목명"]).drop(columns="_len")


def get_stock_name(code, ticker_df=None):
    """종목코드로 종목명을 찾는다. 못 찾으면 빈 문자열."""
    df = ticker_df if ticker_df is not None else load_ticker_list()
    if df is None or df.empty:
        return ""
    hit = df[df["종목코드"] == str(code).zfill(6)]
    return str(hit.iloc[0]["종목명"]) if not hit.empty else ""


# ===========================================================================
# 1단계 - 개별 종목 일봉(OHLCV)
# ===========================================================================

def _ohlcv_pykrx(code, start_date, end_date):
    """pykrx로 일봉을 가져와 한글 컬럼 DataFrame으로 반환. 실패하면 None."""
    from pykrx import stock

    df = stock.get_market_ohlcv(
        start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d"), code
    )
    if df is None or df.empty:
        return None

    keep = [c for c in ["시가", "고가", "저가", "종가", "거래량"] if c in df.columns]
    if len(keep) < 5:
        return None
    return df[keep]


def _ohlcv_fdr(code, start_date, end_date):
    """FinanceDataReader로 일봉을 가져온다(대체 경로). 실패하면 None."""
    import FinanceDataReader as fdr

    df = fdr.DataReader(code, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    if df is None or df.empty:
        return None

    rename = {"Open": "시가", "High": "고가", "Low": "저가", "Close": "종가", "Volume": "거래량"}
    df = df.rename(columns=rename)
    keep = [c for c in ["시가", "고가", "저가", "종가", "거래량"] if c in df.columns]
    if len(keep) < 5:
        return None
    return df[keep]


# ---------------------------------------------------------------------------
# 기준일 규칙 (리포트 구성 지침 v1.4 5.0)
# ---------------------------------------------------------------------------
KST = timezone(timedelta(hours=9))
CLOSE_CUTOFF = dtime(15, 40)        # 이 시각 전에는 당일 일봉을 쓰지 않는다(정규장 종가 확정 전)


def now_kst():
    """한국시간 현재 시각(시간대 정보 없는 datetime)."""
    return datetime.now(KST).replace(tzinfo=None)


def session_cutoff(now=None):
    """일봉을 쓸 수 있는 마지막 날짜(date). 15:40 이전이면 어제, 이후면 오늘."""
    now = now or now_kst()
    return now.date() if now.time() >= CLOSE_CUTOFF else now.date() - timedelta(days=1)


def is_closed_session(day, now=None):
    """그 날짜의 정규장 종가가 확정됐는가(day <= session_cutoff)."""
    return pd.Timestamp(day).date() <= session_cutoff(now)


def closed_after(path, day):
    """파일이 그 날짜 15:40(종가 확정) 이후에 저장됐는가. 장중에 만든 캐시를 걸러 내는 데 쓴다."""
    try:
        saved = datetime.fromtimestamp(os.path.getmtime(path), KST).replace(tzinfo=None)
    except OSError:
        return False
    return saved >= datetime.combine(pd.Timestamp(day).date(), CLOSE_CUTOFF)


def trim_to_session(df, now=None):
    """cutoff 뒤의 행(당일 장중 일봉)을 잘라 낸다. 인덱스는 날짜."""
    if df is None or df.empty:
        return df
    return df[df.index <= pd.Timestamp(session_cutoff(now))]


def base_date_note(base_date, written=None):
    """표지·출처 표기: '기준일 2026년 9월 25일 정규장 종가 (작성 2026년 9월 28일 10:12)'."""
    written = written or now_kst()
    day = pd.Timestamp(base_date)
    return (f"기준일 {day.year}년 {day.month}월 {day.day}일 정규장 종가 "
            f"(작성 {written.year}년 {written.month}월 {written.day}일 {written:%H:%M})")


def fetch_ohlcv_raw(code, start_date, end_date):
    """pykrx -> FinanceDataReader 순으로 일봉을 시도해 정리된 DataFrame을 반환한다.

    지침 v1.4 5.0: session_cutoff() 뒤의 일봉(15:40 이전 실행 시 당일 장중 일봉)은 잘라 낸다.
    """
    for loader in (_ohlcv_pykrx, _ohlcv_fdr):
        try:
            raw = loader(code, start_date, end_date)
        except Exception:
            raw = None
        if raw is not None and not raw.empty:
            df = raw.copy()
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            df = df.apply(pd.to_numeric, errors="coerce").dropna(subset=["종가"])
            # 휴장일·거래정지로 0이 들어오는 행은 차트를 망치므로 제거한다.
            df = df[df["종가"] > 0]
            df = trim_to_session(df)
            if not df.empty:
                return df
    return pd.DataFrame()


def load_ohlcv(code, period_label):
    """선택 종목의 일봉 시세를 가져와 이동평균까지 붙여 반환한다(30분 캐시).

    반환 컬럼: 시가 / 고가 / 저가 / 종가 / 거래량 / MA20 / MA60
    데이터를 못 받으면 빈 DataFrame을 반환한다.
    캐시 키에 기준일 cutoff 날짜를 넣어, 15:40을 넘기면 장 마감 일봉으로 다시 받는다(지침 v1.4 5.0).
    받지 못한 결과(빈 DataFrame)는 캐시하지 않는다 - 다음 화면 갱신 때 다시 받는다.
    """
    try:
        return _load_ohlcv_cached(code, period_label, session_cutoff().isoformat())
    except _NoCache as miss:
        return miss.value


@st.cache_data(ttl=60 * 30, show_spinner="시세를 불러오는 중입니다...")
def _load_ohlcv_cached(code, period_label, cutoff):
    days = PERIOD_OPTIONS.get(period_label, 180)
    end_date = datetime.strptime(cutoff, "%Y-%m-%d") + timedelta(days=1)
    view_start = end_date - timedelta(days=days)
    # 이동평균선이 화면 첫날부터 그려지도록 과거 데이터를 넉넉히 더 받아온다.
    fetch_start = view_start - timedelta(days=MA_BUFFER_DAYS)

    df = fetch_ohlcv_raw(code, fetch_start, end_date)
    if df.empty:
        raise _NoCache(pd.DataFrame())          # 실패는 캐시하지 않는다(load_ohlcv 가 빈 표로 돌려준다)

    # 이동평균선(20일/60일)은 잘라내기 전 전체 구간으로 계산해야 값이 정확하다.
    df["MA20"] = df["종가"].rolling(window=20).mean()
    df["MA60"] = df["종가"].rolling(window=60).mean()

    view = df[df.index >= pd.Timestamp(view_start.date())]
    return view if not view.empty else df


def summarize(df):
    """상단 지표 카드에 쓸 값들을 계산한다.

    현재가(최근 종가) / 전일대비 등락률 / 기간 최고·최저 / 평균 거래량
    """
    if df is None or df.empty:
        return None

    close = df["종가"]
    last_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2]) if len(close) >= 2 else last_close
    diff = last_close - prev_close
    rate = (diff / prev_close * 100) if prev_close else 0.0

    return {
        "현재가": last_close,
        "전일대비": diff,
        "등락률": rate,
        "기간최고": float(df["고가"].max()),
        "기간최저": float(df["저가"].min()),
        "평균거래량": float(df["거래량"].mean()),
        "최근일자": df.index[-1].strftime("%Y-%m-%d"),
    }


# ===========================================================================
# 2단계 - 시장 스냅샷 (종목 풀 + 시가총액 전용)
# ===========================================================================
#
# [가격 소스 원칙]
#   현재가와 등락률은 어느 화면에서나 pykrx 일봉(= 네이버 금융과 같은 정규장 종가)만 쓴다.
#   FinanceDataReader의 StockListing 스냅샷은 시간외 체결까지 섞인 값이라
#   같은 날인데도 종가가 다르게 나온다(예: 2026-09-23 삼성전자 285,500 vs 정규장 286,500).
#   그래서 FDR은 '어떤 종목을 그릴지(종목 풀)'와 '박스 크기(시가총액)'에만 쓴다.
# ===========================================================================

#   [시가총액 = 상장주식수 x 기준일 종가] (지침 v1.4 5.0과 맞춤)
#   FDR 스냅샷의 Marcap은 조회 시점의 실시간 값이라 기준일(직전 거래일 종가)과 날짜가 어긋나고,
#   KRX가 시세를 내주지 않는 시간(예: 2026-09-28 연휴 뒤 첫 장, lateInfoMsgCd ME005)에는 Close·Marcap이
#   모두 비어 스냅샷이 통째로 빈 표가 된다(시장 히트맵 '시장 데이터를 가져오지 못했습니다'의 원인).
#   그래서 스냅샷에서는 상장주식수(Stocks)만 믿고, 시가총액은 pykrx 기준일 종가로 다시 계산한다.
#   상위 N종목을 고르는 순위만 FDR Marcap(있을 때) 또는 '상장주식수 x 저장된 최근 종가'로 정한다.
# ===========================================================================

RANK_CACHE = os.path.join(CACHE_DIR, "marcap_rank.csv")   # 순위용 최근 종가·상장주식수(성공할 때마다 갱신)


def load_market_snapshot():
    """FinanceDataReader 전종목 목록에서 종목 풀·상장주식수·(있으면) 시가총액을 가져온다(10분 캐시).

    반환 컬럼: 종목코드 / 종목명 / 시장 / 시가총액(FDR, 없으면 NaN) / 상장주식수
    (가격·등락률은 일부러 담지 않는다. 가격은 pykrx 일봉에서만 읽는다.)
    FDR 호출이 실패하면 순위 캐시(marcap_rank.csv)의 종목·상장주식수로 대신한다(이 대체 결과는 캐시하지 않는다).
    """
    try:
        return _market_snapshot_cached()
    except _NoCache as miss:
        return miss.value


@st.cache_data(ttl=60 * 10, show_spinner="종목 목록을 불러오는 중입니다...")
def _market_snapshot_cached():
    import FinanceDataReader as fdr

    columns = ["종목코드", "종목명", "시장", "시가총액", "상장주식수"]
    try:
        df = fdr.StockListing("KRX")
    except Exception:
        df = None
    if df is None or df.empty:
        saved = _load_rank_cache()
        raise _NoCache(saved[columns[:3] + ["상장주식수"]].assign(시가총액=float("nan"))[columns] if not saved.empty
                       else pd.DataFrame(columns=columns))

    out = pd.DataFrame({
        "종목코드": df["Code"].astype(str).str.zfill(6),
        "종목명": df["Name"].astype(str),
        "시장": df["Market"].astype(str).str.split().str[0],   # 'KOSDAQ GLOBAL' -> 'KOSDAQ'
        "시가총액": pd.to_numeric(df["Marcap"], errors="coerce"),
        "상장주식수": pd.to_numeric(df["Stocks"], errors="coerce") if "Stocks" in df else float("nan"),
    })
    out = out[out["시장"].isin(["KOSPI", "KOSDAQ"])]
    out = out[(out["상장주식수"] > 0) | (out["시가총액"] > 0)]
    return out.reset_index(drop=True)


def _load_rank_cache():
    """순위용 최근 종가 캐시. 컬럼: 종목코드 / 종목명 / 시장 / 상장주식수 / 종가 / 기준일"""
    if not os.path.exists(RANK_CACHE):
        return pd.DataFrame(columns=["종목코드", "종목명", "시장", "상장주식수", "종가", "기준일"])
    try:
        return pd.read_csv(RANK_CACHE, dtype={"종목코드": str})
    except Exception:
        return pd.DataFrame(columns=["종목코드", "종목명", "시장", "상장주식수", "종가", "기준일"])


def _save_rank_cache(rows):
    """순위용 캐시를 종목별 최신 값으로 합쳐 저장한다. rows: 같은 컬럼의 DataFrame"""
    _ensure_dirs()
    merged = pd.concat([f for f in (_load_rank_cache(), rows) if not f.empty], ignore_index=True)
    merged = merged.sort_values("기준일").drop_duplicates(subset="종목코드", keep="last")
    try:
        merged.to_csv(RANK_CACHE, index=False, encoding="utf-8-sig")
    except Exception:
        pass


def _recent_closes():
    """순위 추정용 종목별 최근 종가 {종목코드: 종가}. 순위 캐시 + 일봉 pkl 캐시(가장 최근 파일부터)."""
    closes = {}
    saved = _load_rank_cache()
    for code, close in saved[["종목코드", "종가"]].itertuples(index=False):
        if pd.notna(close):
            closes[str(code).zfill(6)] = float(close)
    pkls = sorted((f for f in os.listdir(CACHE_DIR) if f.startswith("ohlcv_") and f.endswith(".pkl")),
                  key=lambda f: os.path.getmtime(os.path.join(CACHE_DIR, f)), reverse=True) \
        if os.path.isdir(CACHE_DIR) else []
    for name in pkls:
        try:
            with open(os.path.join(CACHE_DIR, name), "rb") as f:
                store = pickle.load(f)
        except Exception:
            continue
        for code, df in store.items():
            if code not in closes and df is not None and not df.empty:
                closes[code] = float(df["종가"].iloc[-1])
    return closes


def get_top_marcap(market, top_n=TOP_N):
    """해당 시장의 시가총액 상위 N개 종목을 반환한다.

    순위 기준: FDR 시가총액이 있으면 그 값, 없으면 상장주식수 x 저장된 최근 종가(순위 캐시·일봉 캐시).
    반환 컬럼의 '시가총액'은 순위용 값이다. 히트맵 박스 크기는 build_market_heatmap_data에서
    상장주식수 x 기준일 종가로 다시 계산한다.
    """
    snapshot = load_market_snapshot()
    if snapshot.empty:
        return snapshot
    part = snapshot[snapshot["시장"] == market].copy()
    if part["시가총액"].notna().sum() < min(top_n, len(part)) // 2:        # FDR 시가총액이 비었다
        closes = _recent_closes()
        part["시가총액"] = part["상장주식수"] * part["종목코드"].map(closes)
    part = part.dropna(subset=["시가총액"])
    return part.nlargest(top_n, "시가총액").reset_index(drop=True)


# ===========================================================================
# 2단계 - 200종목 일봉 일괄 수집 (하루 1개 pkl 캐시)
# ===========================================================================

def _cache_path_for_today():
    """기준일 cutoff 날짜 기준 일봉 캐시 파일 경로(지침 v1.4 5.0).

    이름에 'close'를 넣어, 장중 일봉이 섞였을 수 있는 예전 ohlcv_YYYYMMDD.pkl 파일은 다시 읽지 않는다.
    """
    stamp = session_cutoff().strftime("%Y%m%d")
    return os.path.join(CACHE_DIR, "ohlcv_close_" + stamp + ".pkl")


def _load_day_cache():
    """오늘 자 pkl 캐시를 읽는다. 없으면 빈 딕셔너리."""
    path = _cache_path_for_today()
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}


def _save_day_cache(store):
    """오늘 자 pkl 캐시를 저장한다."""
    _ensure_dirs()
    try:
        with open(_cache_path_for_today(), "wb") as f:
            pickle.dump(store, f)
    except Exception:
        pass


def load_ohlcv_bulk(codes, progress_cb=None):
    """여러 종목의 최근 1년 일봉을 한꺼번에 수집한다.

    - 같은 날 이미 받은 종목은 data/cache/ohlcv_YYYYMMDD.pkl 에서 재사용
    - 새로 받아야 하는 종목만 동시 4개까지 병렬 요청
    반환: {종목코드: 일봉 DataFrame}
    """
    codes = [str(c).zfill(6) for c in codes]
    store = _load_day_cache()

    todo = [c for c in codes if c not in store]
    if not todo:
        if progress_cb:
            progress_cb(1.0, "캐시 재사용 " + str(len(codes)) + "종목")
        return {c: store[c] for c in codes if c in store}

    end_date = datetime.combine(session_cutoff(), dtime(23, 59))
    start_date = end_date - timedelta(days=400)     # 1년 + 여유

    def _one(code):
        """작업 스레드 1개가 종목 하나의 일봉을 받아온다.

        너무 빠르게 연속 요청하면 거래소가 응답을 끊으므로 요청 사이에 잠깐 쉰다.
        """
        time.sleep(REQUEST_DELAY)
        try:
            return code, fetch_ohlcv_raw(code, start_date, end_date)
        except Exception:
            return code, pd.DataFrame()

    done = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for code, df in pool.map(_one, todo):
            if df is not None and not df.empty:
                store[code] = df
            done += 1
            if progress_cb and (done % 5 == 0 or done == len(todo)):
                progress_cb(done / len(todo), "일봉 수집 " + str(done) + "/" + str(len(todo)) + "종목")

    _save_day_cache(store)
    return {c: store[c] for c in codes if c in store}


def period_change_rate(df, days):
    """일봉 DataFrame에서 '기간 시작 거래일 종가 -> 최근 종가' 등락률(%)을 계산한다.

    days=1 이면 바로 앞 거래일 종가와 비교한 '전일대비 등락률'이 된다.
    """
    if df is None or df.empty or len(df) < 2:
        return None
    if days <= 1:                                   # 전일대비는 직전 행과 바로 비교
        prev_close = float(df["종가"].iloc[-2])
        return (float(df["종가"].iloc[-1]) / prev_close - 1) * 100 if prev_close else None
    last_date = df.index[-1]
    start_date = last_date - pd.Timedelta(days=days)
    past = df[df.index <= start_date]
    # 기간 시작일 이전 마지막 거래일이 기준. 데이터가 짧으면 가장 오래된 날을 쓴다.
    base_close = float(past["종가"].iloc[-1]) if not past.empty else float(df["종가"].iloc[0])
    last_close = float(df["종가"].iloc[-1])
    if not base_close:
        return None
    return (last_close / base_close - 1) * 100


def build_market_heatmap_data(market, period_label, progress_cb=None):
    """시장 히트맵에 필요한 표를 만든다.

    종목 풀과 시가총액은 FDR, 현재가와 등락률은 pykrx 일봉 캐시에서 계산한다.
    (1일 등락률도 스냅샷을 쓰지 않고 '최근 종가 대비 직전 거래일 종가'로 직접 구한다.)

    반환: (DataFrame, 기준일 문자열)
    DataFrame 컬럼: 종목코드 / 종목명 / 현재가 / 등락률 / 시가총액 / 업종그룹
    """
    import industry

    top = get_top_marcap(market)
    if top.empty:
        return pd.DataFrame(), ""

    days, _clip = HEATMAP_PERIODS.get(period_label, (1, 3.0))
    base_date = ""

    # 모든 기간을 같은 일봉 캐시에서 계산해야 탭마다 현재가가 달라지지 않는다.
    store = load_ohlcv_bulk(top["종목코드"].tolist(), progress_cb=progress_cb)

    rates, prices, days_seen = [], [], []
    for code in top["종목코드"]:
        df = store.get(code)
        rates.append(period_change_rate(df, days))
        prices.append(float(df["종가"].iloc[-1]) if df is not None and not df.empty else None)
        days_seen.append(df.index[-1].strftime("%Y-%m-%d") if df is not None and not df.empty else None)
    known = [d for d in days_seen if d]
    if known:
        base_date = max(known).replace("-", ".")

    result = top.copy()
    result["등락률"] = rates
    result["현재가"] = prices
    # 박스 크기 = 상장주식수 x 기준일 종가(FDR 실시간 Marcap 대신, 지침 v1.4 5.0 기준일과 맞춤)
    shares = pd.to_numeric(result.get("상장주식수"), errors="coerce")
    exact = shares * pd.to_numeric(result["현재가"], errors="coerce")
    result["시가총액"] = exact.where(exact > 0, result["시가총액"])

    result = result.dropna(subset=["등락률", "현재가", "시가총액"])
    if not result.empty:
        _save_rank_cache(pd.DataFrame({
            "종목코드": result["종목코드"], "종목명": result["종목명"], "시장": market,
            "상장주식수": result.get("상장주식수"), "종가": result["현재가"],
            "기준일": result["종목코드"].map(dict(zip(top["종목코드"], days_seen))),
        }))
    result = industry.attach_industry(result)       # 업종그룹 컬럼 붙이기
    return result.reset_index(drop=True), base_date


# ===========================================================================
# 2단계 - 보유종목 CSV
# ===========================================================================

def _empty_holdings():
    """보유종목 빈 표(컬럼만 있는 DataFrame)."""
    return pd.DataFrame({
        "종목코드": pd.Series(dtype="str"),
        "종목명": pd.Series(dtype="str"),
        "수량": pd.Series(dtype="float"),
        "평균매수가": pd.Series(dtype="float"),
    })


def load_holdings():
    """data/holdings.csv를 읽는다. 파일이 없으면 빈 파일을 만들고 빈 표를 반환."""
    _ensure_dirs()
    if not os.path.exists(HOLDINGS_CSV):
        _empty_holdings().to_csv(HOLDINGS_CSV, index=False, encoding="utf-8-sig")
        return _empty_holdings()
    try:
        df = pd.read_csv(HOLDINGS_CSV, dtype={"종목코드": str})
    except Exception:
        return _empty_holdings()

    for col in HOLDINGS_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df["종목코드"] = df["종목코드"].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
    df["수량"] = pd.to_numeric(df["수량"], errors="coerce")
    df["평균매수가"] = pd.to_numeric(df["평균매수가"], errors="coerce")
    return df[HOLDINGS_COLUMNS]


def save_holdings(df):
    """보유종목 표를 검증해서 저장한다. 반환: (저장된 DataFrame, 경고 메시지 리스트)"""
    _ensure_dirs()
    warnings = []
    rows = []
    ticker_df = load_ticker_list()

    for _, row in df.iterrows():
        raw_code = str(row.get("종목코드") or "").strip().replace(".0", "")
        if not raw_code or raw_code.lower() == "nan":
            continue
        # 엑셀에서 앞자리 0이 떨어진 경우를 위해 6자리로 채운 뒤 검증한다.
        # 최근 상장 종목·일부 우선주는 영문이 섞인 코드(예: 02826K, 0126Z0)라 영문·숫자 6자리를 허용한다.
        code = raw_code.upper().zfill(6)
        if not (len(code) == 6 and code.isascii() and code.isalnum()):
            warnings.append("종목코드 '" + raw_code + "' 는 6자리 종목코드가 아니라 제외했습니다.")
            continue

        name = str(row.get("종목명") or "").strip()
        listed_name = get_stock_name(code, ticker_df)
        if not listed_name:                             # 상장 종목 목록에 없는 코드
            warnings.append("종목코드 '" + raw_code + "' 는 코스피·코스닥 목록에 없어 제외했습니다.")
            continue
        if not name or name.lower() == "nan":           # 종목명은 코드로 자동 채움
            name = listed_name

        qty = pd.to_numeric(row.get("수량"), errors="coerce")
        avg = pd.to_numeric(row.get("평균매수가"), errors="coerce")
        if pd.isna(qty) or qty <= 0:
            warnings.append(name + "(" + code + ") 의 수량이 비어 있어 제외했습니다.")
            continue
        if pd.isna(avg) or avg <= 0:
            warnings.append(name + "(" + code + ") 의 평균매수가가 비어 있어 제외했습니다.")
            continue

        rows.append({"종목코드": code, "종목명": name, "수량": float(qty), "평균매수가": float(avg)})

    result = pd.DataFrame(rows, columns=HOLDINGS_COLUMNS) if rows else _empty_holdings()

    # 같은 종목이 여러 줄로 들어오면 하나로 합친다(수량 합계 + 매수단가 가중평균).
    if len(result) != result["종목코드"].nunique():
        result["_금액"] = result["수량"] * result["평균매수가"]
        merged = result.groupby("종목코드", as_index=False).agg(
            종목명=("종목명", "first"), 수량=("수량", "sum"), _금액=("_금액", "sum"))
        merged["평균매수가"] = merged["_금액"] / merged["수량"]
        warnings.append("같은 종목이 여러 줄 있어 수량을 합치고 평균매수가를 가중평균으로 계산했습니다.")
        result = merged[HOLDINGS_COLUMNS]

    result.to_csv(HOLDINGS_CSV, index=False, encoding="utf-8-sig")
    return result, warnings


def stock_label(row):
    """드롭다운 표시 형식: '삼성전자 (005930)' (시장은 드롭다운 위 코스피/코스닥 선택으로 나눈다)"""
    return f"{row['종목명']} ({row['종목코드']})"


def add_holding(code, name, qty, avg_price):
    """보유종목 1건을 추가하고 바로 저장한다.

    이미 있는 종목이면 save_holdings의 합치기 로직(수량 합산 + 평균매수가 가중평균)을 그대로 쓴다.
    반환: (저장된 DataFrame, 안내 문구 리스트)
    """
    current = load_holdings()
    existed = str(code).zfill(6) in set(current["종목코드"])
    new_row = pd.DataFrame([{"종목코드": str(code).zfill(6), "종목명": name,
                             "수량": float(qty), "평균매수가": float(avg_price)}])
    saved, warnings = save_holdings(pd.concat([current, new_row], ignore_index=True))
    # 합치기 안내는 '추가' 상황에 맞는 문구로 바꾼다.
    warnings = [w for w in warnings if not w.startswith("같은 종목이 여러 줄")]
    hit = saved[saved["종목코드"] == str(code).zfill(6)]
    if existed and not hit.empty:
        row = hit.iloc[0]
        warnings.insert(0, f"{name}: 기존 보유분과 합쳐 수량 {row['수량']:,.0f}주, "
                           f"평균매수가 {row['평균매수가']:,.0f}원(가중평균)으로 저장했습니다.")
    elif not hit.empty:
        warnings.insert(0, f"{name} {float(qty):,.0f}주를 평균매수가 {float(avg_price):,.0f}원으로 추가했습니다.")
    return saved, warnings


def update_holdings(edited):
    """표에서 수정한 수량·평균매수가를 저장한다(종목코드·종목명은 수정 불가). '삭제' 열은 무시한다."""
    return save_holdings(edited.drop(columns=["삭제"], errors="ignore"))


def delete_holdings(codes):
    """선택한 종목코드들을 저장된 보유종목에서 지운다. 반환: (저장된 DataFrame, 지운 종목명 리스트)"""
    codes = {str(c).zfill(6) for c in codes}
    current = load_holdings()
    removed = current[current["종목코드"].isin(codes)]["종목명"].tolist()
    saved, _ = save_holdings(current[~current["종목코드"].isin(codes)])
    return saved, removed


def load_sample_holdings():
    """교재용 샘플 보유종목을 holdings.csv로 복사한다."""
    if not os.path.exists(HOLDINGS_SAMPLE_CSV):
        return _empty_holdings()
    sample = pd.read_csv(HOLDINGS_SAMPLE_CSV, dtype={"종목코드": str})
    sample["종목코드"] = sample["종목코드"].astype(str).str.zfill(6)
    sample.to_csv(HOLDINGS_CSV, index=False, encoding="utf-8-sig")
    return sample


def build_holdings_heatmap_data(holdings):
    """보유종목에 현재가·수익률·평가금액을 붙인 표를 만든다.

    현재가와 당일 등락률은 1단계 개별 일봉 함수(load_ohlcv)를 재사용한다.
    반환: (DataFrame, 요약 dict)
    """
    import industry

    if holdings is None or holdings.empty:
        return pd.DataFrame(), {}

    rows = []
    for _, row in holdings.iterrows():
        code = str(row["종목코드"]).zfill(6)
        df = load_ohlcv(code, "1개월")              # 1단계 함수 재사용
        info = summarize(df)
        if info is None:
            continue
        qty = float(row["수량"])
        avg = float(row["평균매수가"])
        price = info["현재가"]
        rows.append({
            "종목코드": code,
            "종목명": row["종목명"],
            "수량": qty,
            "평균매수가": avg,
            "현재가": price,
            "등락률": info["등락률"],                     # 당일 등락률
            "매수금액": qty * avg,
            "평가금액": qty * price,
            "평가손익": qty * (price - avg),
            "수익률": (price / avg - 1) * 100 if avg else 0.0,
            "당일손익": qty * info["전일대비"],
            "최근일자": info["최근일자"],
        })

    if not rows:
        return pd.DataFrame(), {}

    result = pd.DataFrame(rows)
    # 보유종목은 수가 적으므로, 업종 매핑에 없는 종목은 DART를 1회씩 호출해 채운다.
    result = industry.attach_industry(result, ensure=True)
    total_buy = float(result["매수금액"].sum())
    summary = {
        "총매수금액": total_buy,
        "총평가금액": float(result["평가금액"].sum()),
        "총평가손익": float(result["평가손익"].sum()),
        "총수익률": (float(result["평가금액"].sum()) / total_buy - 1) * 100 if total_buy else 0.0,
        "당일손익": float(result["당일손익"].sum()),
        "기준일": result["최근일자"].max(),
    }
    return result, summary
