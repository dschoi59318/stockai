# -*- coding: utf-8 -*-
"""
financials.py - DART 재무 데이터 수집 (4단계)

사용 API: 금융감독원 DART
 - 단일회사 주요계정 (fnlttSinglAcnt.json)      : 매출액·영업이익·당기순이익·자산·부채·자본
 - 단일회사 전체 재무제표 (fnlttSinglAcntAll.json): 지배기업 소유주지분 순이익·자본 (주요계정에 없을 때만)
 - 연결재무제표(CFS)를 우선 쓰고, 없으면 별도재무제표(OFS)로 폴백한다(어느 쪽인지 화면에 표시).
 - 사업보고서 1건에 당기/전기/전전기가 함께 오므로, 연간 3년치는 호출 1번이면 된다.

[분기 손익 변환 규칙]  ※ DART 분기보고서는 '3개월분'과 '누적'을 함께 준다.
 - thstrm_amount     = 해당 분기 3개월 금액   (1분기보고서는 3개월 = 누적)
 - thstrm_add_amount = 사업연도 누적 금액
 따라서
   1분기 = 1분기보고서(11013)의 3개월 금액(thstrm_amount)
   2분기 = 반기보고서(11012)의 3개월 금액(thstrm_amount)
   3분기 = 3분기보고서(11014)의 3개월 금액(thstrm_amount)
   4분기 = 사업보고서(11011) 연간 금액 - (1분기 + 2분기 + 3분기 3개월 금액의 합)
           <- 사업보고서에는 4분기 3개월 값이 없으므로 4분기만 뺄셈으로 만든다.
           1~3분기 중 하나라도 비어 있으면 대신 '연간 - 3분기보고서 누적'으로 계산한다(보조 경로).
 재무상태표(자산·부채·자본)는 시점 값이라 변환하지 않고 기말 잔액을 그대로 쓴다.
 (실측 2025 삼성전자 매출: 1Q 79.14조 + 2Q 74.57조 + 3Q 86.06조 = 3분기 누적 239.77조)
 지배주주 순이익도 위 규칙을 그대로 따른다.

[지배주주 계정 찾기]  (주요계정에는 없으므로 전체 재무제표에서 찾는다. 보고서마다 따로 판정)
 순이익
   1) 표준코드 ProfitLossAttributableToOwnersOfParent / ...AttributableToOrdinaryEquityHoldersOfParentEntity
   2) 계속영업 + 중단영업의 지배주주 귀속분 합산
   3) 손익계산서(IS)에서 이름("지배기업 소유주지분", "지배기업의 소유주에게 귀속되는" 등)
   4) 포괄손익계산서(CIS)의 '지배'·'비지배' 이름 행 쌍 중 합이 당기순이익과 ±0.1% 이내인 쌍만 채택
      CIS의 같은 이름 행은 '총포괄이익' 귀속분일 수 있어(예: 삼성전자) 합계 검산 없이는 쓰지 않는다.
   5) 지배/비지배 귀속 구분 자체가 없으면(비지배지분 없음) 당기순이익 전체를 지배주주 몫으로 본다.
   별도재무제표만 내는 회사(종속회사 없음)는 당기순이익이 곧 지배주주 순이익이다.
 자본
   1) 표준코드 EquityAttributableToOwnersOfParent  2) 이름
   3) 지배자본 행이 없고 비지배지분이 0이거나 없으면 자본총계를 지배자본으로 본다.
 끝내 못 찾으면 당기순이익·자본총계로 계산하고 카드에 사유를 붙인다:
   "(당기순이익 기준)" / "(자본총계 기준)" / "(데이터 부족: 분기·1년 전 자본·시가총액 등이 없음)"

[비율 카드 기준]  카드 5개 모두 같은 기간을 쓴다. PER·PBR·ROE는 네이버 증권 방식에 맞춘다.
 - 손익: 최근 4분기 합산(TTM)      - 재무상태: 최근 분기말
 - 시가총액 = 보통주 + 같은 회사 우선주 시가총액 합계 (FDR 스냅샷, 우선주가 없으면 보통주만)
 - PER = 시가총액 / TTM 지배주주 순이익        (0 이하면 '적자')
 - PBR = 시가총액 / 분기말 지배기업 소유주지분  (못 찾으면 자본총계 + "(자본총계 기준)")
 - ROE = TTM 지배주주 순이익 / ((1년 전 분기말 지배자본 + 최근 분기말 지배자본) / 2) x 100
         1년 전 값이 없으면 최근 분기말 값만으로 나눈다.
 - 부채비율 = 분기말 부채총계 / 분기말 자본총계 x 100
 - 영업이익률 = TTM 영업이익 / TTM 매출액 x 100
 연간 표의 연도별 영업이익률은 해당 연도 연간 값으로 계산한다.

[캐시] data/cache/fin/{종목코드}_{보고서코드}_{연도}_{버전}.json            (주요계정)
       data/cache/fin/{종목코드}_{보고서코드}_{연도}_all{CFS|OFS}_{버전}.json (전체 재무제표)
 확정 공시는 나중에 바뀌지 않으므로 만료 시간을 두지 않는다.
 사이드바 '재무 새로고침' 버튼을 눌렀을 때만 다시 받는다.
 캐시 구조가 바뀌면 CACHE_VERSION을 올려 예전 파일과 섞이지 않게 한다.
"""

import copy
import json
import os
import re
import time                                                                      # [계측]
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st

import dart_guard
import fin_store
import keys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIN_CACHE_DIR = os.path.join(BASE_DIR, "data", "cache", "fin")
CACHE_VERSION = "v2"        # v1(버전 없음) -> v2: 전체 재무제표 캐시 추가
# status 013(조회된 데이터 없음 = 아직 미공시) 응답은 '미공시' 표시 파일로 1일 동안만 기억한다.
# 다음 날에는 다시 물어서 그사이 공시됐으면 정상(000) 응답을 받아 저장한다. 000 규칙은 그대로.
NODATA_TTL = 24 * 60 * 60   # 초

DART_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"
DART_ALL_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
REQUEST_TIMEOUT = 15        # (예전 값) DART 호출 timeout 은 dart_guard(연결 3초·읽기 15초)가 정한다

# 보고서 코드
REPRT_ANNUAL = "11011"      # 사업보고서(연간)
REPRT_Q1 = "11013"          # 1분기보고서
REPRT_H1 = "11012"          # 반기보고서
REPRT_Q3 = "11014"          # 3분기보고서

QUARTER_REPRT = {1: REPRT_Q1, 2: REPRT_H1, 3: REPRT_Q3, 4: REPRT_ANNUAL}

# 공시가 올라온 뒤에야 조회되므로, 분기별로 '이 날짜는 지나야 있다'는 기준을 둔다.
QUARTER_READY = {1: (5, 20), 2: (8, 20), 3: (11, 20), 4: (4, 5)}   # 4분기는 다음 해 4/5

# 계정 이름은 회사마다 조금씩 다르다. 앞에 있는 이름부터 찾는다.
ACCOUNT_ALIASES = {
    "매출액": ["매출액", "영업수익", "수익(매출액)", "영업수익(매출액)", "매출", "순영업수익"],
    "영업이익": ["영업이익", "영업이익(손실)"],
    "당기순이익": ["당기순이익", "당기순이익(손실)"],
    "자산총계": ["자산총계"],
    "부채총계": ["부채총계"],
    "자본총계": ["자본총계"],
}

# 지배주주 계정
CTRL_NI_IDS = ("ifrs-full_ProfitLossAttributableToOwnersOfParent",
               "ifrs-full_ProfitLossAttributableToOrdinaryEquityHoldersOfParentEntity")
CTRL_CONT_IDS = ("ifrs-full_IncomeFromContinuingOperationsAttributableToOwnersOfParent",
                 "ifrs-full_ProfitLossFromContinuingOperationsAttributableToOrdinaryEquityHoldersOfParentEntity")
CTRL_DISC_IDS = ("ifrs-full_IncomeFromDiscontinuedOperationsAttributableToOwnersOfParent",
                 "ifrs-full_ProfitLossFromDiscontinuedOperationsAttributableToOrdinaryEquityHoldersOfParentEntity")
CTRL_EQ_ID = "ifrs-full_EquityAttributableToOwnersOfParent"
NCI_EQ_ID = "ifrs-full_NoncontrollingInterests"
NI_TOTAL_ID = "ifrs-full_ProfitLoss"
EQ_TOTAL_ID = "ifrs-full_Equity"
# 표준코드에 이 문자열이 있으면 '귀속 구분이 있다'고 본다(신용위험 변동 같은 OCI 항목은 제외되도록 구체적으로)
ATTRIBUTION_ID_KEYS = ("AttributableToOwnersOfParent", "AttributableToNoncontrollingInterests",
                       "AttributableToOrdinaryEquityHoldersOfParentEntity")
NI_CHECK_TOL = 0.001        # CIS 검산 허용 오차 ±0.1%
CTRL_NAME_KEYS = ("지배기업 소유주지분", "지배기업의 소유주에게 귀속되는", "지배기업의소유주",
                  "지배기업주주지분", "지배회사지분", "지배회사의 소유주지분", "지배주주지분")

EOK = 100_000_000           # 1억 원


def _sub_tag():
    """[계측] data.sub_tag() (스레드·실행 id)."""
    import data
    return data.sub_tag()


def _ensure_dir():
    os.makedirs(FIN_CACHE_DIR, exist_ok=True)


def _cache_path(code, reprt, year, fs_div=None):
    """주요계정은 fs_div 없이, 전체 재무제표는 fs_div를 붙여 저장한다."""
    kind = f"_all{fs_div}" if fs_div else ""
    return os.path.join(FIN_CACHE_DIR, f"{str(code).zfill(6)}_{reprt}_{year}{kind}_{CACHE_VERSION}.json")


def fetch_report(corp_code, code, year, reprt, refresh=False, fs_div=None):
    """DART 보고서 1건을 받아온다(파일 캐시, 만료 없음). 실패하면 None.

    fs_div를 주면 전체 재무제표(fnlttSinglAcntAll)를, 없으면 주요계정(fnlttSinglAcnt)을 받는다.
    저장본 모드(FIN_MODE=store)에서는 DART 를 부르지 않고 _fetch_report_store 로 읽는다.
    """
    if fin_store.is_store_mode():
        return _fetch_report_store(corp_code, code, year, reprt, fs_div)
    _ensure_dir()
    path = _cache_path(code, reprt, year, fs_div)
    _tag = f"{str(code).zfill(6)} {year} {reprt}{' ' + fs_div if fs_div else ''}"         # [계측]
    if not refresh and os.path.exists(path):
        _ts = time.perf_counter()                                                # [계측]
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
        finally:                                                                 # [계측]
            print(f"[SUB] 캐시읽기 fin {_tag} {time.perf_counter() - _ts:.2f}s {_sub_tag()}", flush=True)

    # 1일 안에 013(미공시)을 받은 보고서는 다시 묻지 않는다(예전과 같이 None).
    nodata_path = path[:-len(".json")] + "_013.json"
    if not refresh and os.path.exists(nodata_path) and time.time() - os.path.getmtime(nodata_path) < NODATA_TTL:
        print(f"[SUB] 미공시 표시 사용(013, 1일) {_tag} {_sub_tag()}", flush=True)   # [계측]
        return None

    if not dart_guard.available():       # DART 불가 상태(차단기): 네트워크에 나가지 않는다. 캐시에도 남기지 않는다
        print(f"[SUB] DART 건너뜀(차단기, 남은 {dart_guard.remaining():.0f}s) {_tag} {_sub_tag()}", flush=True)  # [계측]
        return None
    _ts = time.perf_counter()                                                    # [계측]
    api_key = keys.get_dart_api_key()
    print(f"[SUB] 키조회 DART {time.perf_counter() - _ts:.2f}s {_sub_tag()}", flush=True)   # [계측] 값은 찍지 않는다
    if not api_key or not corp_code:
        print(f"[SUB] fetch_report 건너뜀(키 또는 corp_code 없음) {_tag} {_sub_tag()}", flush=True)  # [계측]
        return None
    params = {"crtfc_key": api_key, "corp_code": corp_code,
              "bsns_year": str(year), "reprt_code": reprt}
    if fs_div:
        params["fs_div"] = fs_div
    _ts = time.perf_counter()                                                    # [계측]
    try:
        res = dart_guard.get(DART_ALL_URL if fs_div else DART_URL, params=params)
        body = res.json()
    except Exception as _exc:
        print(f"[SUB] DART {_tag} 예외 {type(_exc).__name__} {time.perf_counter() - _ts:.2f}s {_sub_tag()}",
              flush=True)                                                        # [계측]
        return None
    print(f"[SUB] DART {_tag} status={body.get('status')} {time.perf_counter() - _ts:.2f}s {_sub_tag()}",
          flush=True)                                                            # [계측]

    if body.get("status") == "013":      # 조회된 데이터 없음(미공시): 1일짜리 표시 파일만 남긴다
        try:
            with open(nodata_path, "w", encoding="utf-8") as f:
                json.dump({"status": "013", "message": body.get("message"),
                           "checked": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, f, ensure_ascii=False)
        except Exception:
            pass
        return None
    if body.get("status") != "000":      # 그 밖의 오류(키·한도 등)는 저장하지 않는다
        return None

    _ts = time.perf_counter()                                                    # [계측]
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False)
    except Exception:
        pass
    print(f"[SUB] 캐시쓰기 fin {_tag} {time.perf_counter() - _ts:.2f}s {_sub_tag()}", flush=True)   # [계측]
    return body


def _fetch_report_store(corp_code, code, year, reprt, fs_div=None):
    """저장본 모드의 fetch_report: 로컬 캐시 -> 재무 저장본(data/fin_store) 순서. DART 는 부르지 않고 아무것도 쓰지 않는다.

    corp_code 는 호출 쪽이 corp_code_map.csv 로 찾은 값만 쓴다(저장본 _targets.csv 는 보지 않는다).
    반환 모양은 fetch_report 와 같다({status, message, list}). 없거나 미공시(013)면 None.
    """
    path = _cache_path(code, reprt, year, fs_div)
    _tag = f"{str(code).zfill(6)} {year} {reprt}{' ' + fs_div if fs_div else ''}"         # [계측]
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    if not corp_code:
        return None
    _ts = time.perf_counter()                                                    # [계측]
    try:
        body = fin_store.read_report(code, year, reprt, fs_div, targets={str(code).zfill(6): corp_code})
    except Exception as _exc:
        print(f"[SUB] 저장본읽기 fin {_tag} 예외 {type(_exc).__name__} {_sub_tag()}", flush=True)  # [계측]
        return None
    print(f"[SUB] 저장본읽기 fin {_tag} {'ok' if body else '없음'} {time.perf_counter() - _ts:.2f}s {_sub_tag()}",
          flush=True)                                                            # [계측]
    return body


def store_missing(code):
    """저장본 모드에서 이 종목의 재무가 저장본에 없으면 True(PC 모드는 항상 False) -> 화면에 저장본 없음 안내."""
    if not fin_store.is_store_mode():
        return False
    return not fin_store.has_company(_corp_code(code))


def fin_enabled():
    """재무를 불러올 수 있는 환경인가: 저장본 모드이거나 DART 키가 있으면 True(PC 모드는 기존 has_dart_key 그대로)."""
    return fin_store.is_store_mode() or keys.has_dart_key()


def _rows(body, fs_div):
    """주요계정 응답에서 연결(CFS)/별도(OFS) 행만 골라낸다."""
    if not body:
        return []
    return [r for r in body.get("list", []) if r.get("fs_div") == fs_div]


def _to_number(text):
    """'333,605,938,000,000' 같은 문자열을 숫자로 바꾼다. 실패하면 None."""
    if text in (None, "", "-"):
        return None
    try:
        return float(str(text).replace(",", "").replace(" ", ""))
    except Exception:
        return None


def _pick(rows, item, field="thstrm_amount"):
    """계정 별칭 순서대로 찾아 (값, 실제 계정명)을 돌려준다. 없으면 (None, None)."""
    for alias in ACCOUNT_ALIASES[item]:
        for row in rows:
            name = (row.get("account_nm") or "").strip()
            if name == alias or name.startswith(alias):
                value = _to_number(row.get(field))
                if value is not None:
                    return value, name
    return None, None


def _eok(value):
    """원 단위 금액을 억 원 단위 정수로 바꾼다."""
    return None if value is None else int(round(value / EOK))


def _ratio(value):
    """비율을 소수 1자리로 반올림한다."""
    return None if value is None else round(float(value), 1)


# ---------------------------------------------------------------------------
# 지배주주 계정 찾기
# ---------------------------------------------------------------------------

def _is_ctrl_name(name):
    name = (name or "").strip()
    return "비지배" not in name and "포괄" not in name and any(k in name for k in CTRL_NAME_KEYS)


def _value(row, field):
    return _to_number(row.get(field))


def _first_by_id(rows, ids, field, sj_list=("IS", "CIS")):
    """sj_list 순서대로, ids 중 하나와 표준코드가 같은 첫 행의 값."""
    for sj in sj_list:
        for row in rows:
            if row.get("sj_div") == sj and row.get("account_id") in ids:
                value = _value(row, field)
                if value is not None:
                    return value
    return None


def _close(a, b, tol=NI_CHECK_TOL):
    """a가 b와 ±tol(비율) 이내로 같은가."""
    if b == 0:
        return a == 0
    return abs(a - b) <= abs(b) * tol


def _has_attribution(rows):
    """손익(IS·CIS)에 지배/비지배 귀속 구분이 하나라도 있는가."""
    for row in rows:
        if row.get("sj_div") not in ("IS", "CIS"):
            continue
        aid = row.get("account_id") or ""
        if any(key in aid for key in ATTRIBUTION_ID_KEYS) or "지배" in (row.get("account_nm") or ""):
            return True
    return False


def _find_ctrl_ni(rows, field="thstrm_amount", total=None):
    """지배기업 소유주지분 순이익을 찾는다. 반환 (값, 방식). 못 찾으면 (None, None).

    rows는 전체 재무제표(fnlttSinglAcntAll) 행. 아래 순서로 찾는다.
     1) 표준코드 ProfitLossAttributableToOwnersOfParent / ...OrdinaryEquityHoldersOfParentEntity  [B3]
     2) 계속영업 + 중단영업의 지배주주 귀속분 합산 (중단영업 행이 없으면 0)              [B2]
     3) 손익계산서(IS)에서 이름으로
     4) 포괄손익계산서(CIS)의 '지배'·'비지배' 이름 행 쌍 중 합이 당기순이익과 ±0.1% 이내인 쌍 [B4]
        (같은 이름이 총포괄이익 귀속분에도 쓰이므로 합계 검산으로만 채택한다. 보고서·필드마다 따로 검산)
     5) 지배/비지배 귀속 구분 자체가 없으면 당기순이익 전체를 지배주주 몫으로 본다            [B1]
    total: 이 보고서의 당기순이익(같은 field). 없으면 표준코드 ProfitLoss 값을 쓴다.
    """
    value = _first_by_id(rows, CTRL_NI_IDS, field)
    if value is not None:
        return value, "표준코드"

    for sj in ("IS", "CIS"):
        cont = _first_by_id(rows, CTRL_CONT_IDS, field, (sj,))
        if cont is not None:
            disc = _first_by_id(rows, CTRL_DISC_IDS, field, (sj,)) or 0
            return cont + disc, "계속+중단"

    for row in rows:
        if row.get("sj_div") == "IS" and _is_ctrl_name(row.get("account_nm")):
            value = _value(row, field)
            if value is not None:
                return value, "이름(IS)"

    net = _first_by_id(rows, (NI_TOTAL_ID,), field)
    if net is None:
        net = total
    if net is not None:
        cis = [r for r in rows if r.get("sj_div") == "CIS"]
        ctrl_rows = [r for r in cis if "지배" in (r.get("account_nm") or "") and "비지배" not in r["account_nm"]]
        nci_rows = [r for r in cis if "비지배" in (r.get("account_nm") or "")]
        nci_values = [v for v in (_value(r, field) for r in nci_rows) if v is not None]
        if not nci_rows:
            nci_values = [0.0]            # 비지배 행이 아예 없으면 지배 행 단독으로 검산
        for row in ctrl_rows:
            ctrl = _value(row, field)
            if ctrl is not None and any(_close(ctrl + nci, net) for nci in nci_values):
                return ctrl, "CIS검산"

        if not _has_attribution(rows):
            return net, "귀속구분없음"
    return None, None


def _find_ctrl_eq(rows, total_equity=None):
    """지배기업 소유주지분 자본(기말). 반환 (값, 방식). 모두 재무상태표(BS)에서만 찾는다.

     1) 표준코드 EquityAttributableToOwnersOfParent  2) 이름
     3) 지배자본 행이 없고 비지배지분이 0이거나 없으면 자본총계를 지배자본으로 본다 [B5]
        ('비지배지분부채'처럼 부채로 분류된 행은 비지배지분으로 보지 않는다)
    """
    value = _first_by_id(rows, (CTRL_EQ_ID,), "thstrm_amount", ("BS",))
    if value is not None:
        return value, "표준코드"
    for row in rows:
        if row.get("sj_div") == "BS" and _is_ctrl_name(row.get("account_nm")):
            value = _value(row, "thstrm_amount")
            if value is not None:
                return value, "이름"

    bs = [r for r in rows if r.get("sj_div") == "BS"]
    nci = [_value(r, "thstrm_amount") for r in bs
           if r.get("account_id") == NCI_EQ_ID
           or ("비지배" in (r.get("account_nm") or "") and "부채" not in r["account_nm"])]
    if all(not v for v in nci):             # 행이 없거나 모두 0(또는 빈 값)
        equity = _first_by_id(rows, (EQ_TOTAL_ID,), "thstrm_amount", ("BS",))
        equity = equity if equity is not None else total_equity
        if equity is not None:
            return equity, "비지배없음"
    return None, None


def _controlling(corp, code, year, reprt, fs_div, main_rows, refresh=False):
    """보고서 1건의 지배주주 값을 돌려준다.

    반환 (순이익[3개월 또는 연간], 누적 순이익, 기말 지배자본, 방식 dict)
    - 별도재무제표(OFS)만 있는 회사는 종속회사가 없어 전부 지배주주 몫이다 -> 당기순이익·자본총계 그대로 [A]
    - 연결(CFS)은 주요계정에 지배주주 계정이 없으므로 전체 재무제표를 받아 찾는다.
    """
    net = _pick(main_rows, "당기순이익")[0]
    net_cum = _pick(main_rows, "당기순이익", "thstrm_add_amount")[0]
    equity = _pick(main_rows, "자본총계")[0]
    if fs_div == "OFS":
        return net, net_cum, equity, {"순이익": "별도", "자본": "별도"}

    body = fetch_report(corp, code, year, reprt, refresh, fs_div="CFS") if fs_div == "CFS" else None
    rows = body.get("list", []) if body else []
    if not rows:
        return None, None, None, {"순이익": None, "자본": None}
    ni, how_ni = _find_ctrl_ni(rows, "thstrm_amount", net)
    ni_cum, _ = _find_ctrl_ni(rows, "thstrm_add_amount", net_cum)
    eq, how_eq = _find_ctrl_eq(rows, equity)
    return ni, ni_cum, eq, {"순이익": how_ni, "자본": how_eq}


# ---------------------------------------------------------------------------
# 기간 계산
# ---------------------------------------------------------------------------

def latest_annual_year(today=None):
    """조회 가능한 가장 최근 '사업연도'. (사업보고서는 다음 해 3월 말 공시)"""
    today = today or datetime.today()
    month, day = QUARTER_READY[4]
    if (today.month, today.day) >= (month, day):
        return today.year - 1
    return today.year - 2


def recent_quarters(count=4, today=None):
    """공시가 끝난 최근 분기를 새 것부터 count개 돌려준다. [(연도, 분기), ...]"""
    today = today or datetime.today()

    # 올해 기준으로 '이미 공시된 분기'를 찾는다.
    year, quarter = today.year, 0
    for q in (1, 2, 3):
        month, day = QUARTER_READY[q]
        if (today.month, today.day) >= (month, day):
            quarter = q
    if quarter == 0:                       # 아직 1분기도 안 나왔으면 작년 4분기부터
        year, quarter = today.year - 1, 4
        if (today.month, today.day) < QUARTER_READY[4]:
            quarter = 3                    # 작년 사업보고서도 아직이면 3분기까지만

    out = []
    while len(out) < count:
        out.append((year, quarter))
        quarter -= 1
        if quarter == 0:
            year, quarter = year - 1, 4
    return out


def quarter_label(key):
    """'2025Q3' -> '2025.3Q' (화면 캡션용)"""
    year, q = str(key).split("Q")
    return f"{year}.{q}Q"


def quarter_text(key):
    """'2025Q3' -> '2025년 3분기' (AI 분석 입력용 고정 표기)"""
    year, q = str(key).split("Q")
    return f"{year}년 {q}분기"


def period_text(quarters):
    """최근 4분기 목록 -> '2025년 3분기~2026년 2분기'"""
    return f"{quarter_text(quarters[0]['분기'])}~{quarter_text(quarters[-1]['분기'])}"


# ---------------------------------------------------------------------------
# 수집
# ---------------------------------------------------------------------------

def _corp_code(code):
    """종목코드 -> DART corp_code. data/corp_code_map.csv 를 먼저 보고, 없는 종목만 corpCode 경로를 쓴다."""
    import industry
    try:
        return industry.corp_code_for(code)
    except Exception:
        return None


def _decide_fs_div(body):
    """연결(CFS)이 있으면 연결, 없으면 별도(OFS)."""
    if _rows(body, "CFS"):
        return "CFS", "연결"
    if _rows(body, "OFS"):
        return "OFS", "별도"
    return None, None


def _statement(rows):
    """한 보고서(행 목록)에서 6개 계정을 뽑아 dict로 만든다."""
    sales, sales_name = _pick(rows, "매출액")
    op, _ = _pick(rows, "영업이익")
    net, _ = _pick(rows, "당기순이익")
    assets, _ = _pick(rows, "자산총계")
    debt, _ = _pick(rows, "부채총계")
    equity, _ = _pick(rows, "자본총계")
    return {
        "매출액": sales, "매출계정명": sales_name,
        "영업이익": op, "당기순이익": net,
        "자산총계": assets, "부채총계": debt, "자본총계": equity,
    }


def load_annual(code, refresh=False, today=None):
    """연간 3개 사업연도를 모은다. 사업보고서 1건에 당기·전기·전전기가 들어 있다."""
    corp = _corp_code(code)
    year = latest_annual_year(today)
    body = fetch_report(corp, code, year, REPRT_ANNUAL, refresh)
    if not body:
        return {"연결구분": None, "연도별": [], "매출계정명": None}

    fs_div, label = _decide_fs_div(body)
    rows = _rows(body, fs_div)

    # 연간 지배주주 순이익: 사업보고서 전체 재무제표 1건에 당기·전기·전전기가 함께 있다.
    # (별도재무제표만 있는 회사는 당기순이익이 곧 지배주주 몫)
    all_rows = []
    if fs_div == "CFS":
        all_body = fetch_report(corp, code, year, REPRT_ANNUAL, refresh, fs_div="CFS")
        all_rows = all_body.get("list", []) if all_body else []

    result = []
    for offset, field in enumerate(["thstrm_amount", "frmtrm_amount", "bfefrmtrm_amount"]):
        sales, sales_name = _pick(rows, "매출액", field)
        net = _pick(rows, "당기순이익", field)[0]
        if fs_div == "OFS":
            ctrl = net
        else:
            ctrl = _find_ctrl_ni(all_rows, field, net)[0] if all_rows else None
        item = {
            "연도": year - offset,
            "매출액": sales,
            "영업이익": _pick(rows, "영업이익", field)[0],
            "당기순이익": net,
            "지배순이익": ctrl,
            "자산총계": _pick(rows, "자산총계", field)[0],
            "부채총계": _pick(rows, "부채총계", field)[0],
            "자본총계": _pick(rows, "자본총계", field)[0],
            "매출계정명": sales_name,
        }
        result.append(item)

    result.reverse()                      # 오래된 연도부터
    return {"연결구분": label, "연도별": result,
            "매출계정명": result[-1]["매출계정명"] if result else None}


def load_quarterly(code, count=4, refresh=False, today=None, ctrl_recent=None):
    """최근 count개 분기의 '3개월분' 손익과 기말 재무상태를 만든다(지배주주 순이익·자본 포함).

    ctrl_recent를 주면 최근 그 개수의 분기만 지배주주 값을 찾는다(전체 재무제표 호출 절약).
    예) count=8, ctrl_recent=4 -> 8개 분기 매출·영업이익, 지배주주 값은 최근 4개 분기만
    """
    corp = _corp_code(code)
    quarters = recent_quarters(count, today)
    label = None
    out = []

    for index, (year, quarter) in enumerate(quarters):
        need_ctrl = ctrl_recent is None or index < ctrl_recent
        if quarter == 4:
            # 4분기 = 연간 - (1분기 + 2분기 + 3분기 3개월 금액의 합)
            annual_body = fetch_report(corp, code, year, REPRT_ANNUAL, refresh)
            if not annual_body:
                continue
            fs_div, label = _decide_fs_div(annual_body)
            annual_rows = _rows(annual_body, fs_div)
            # 1~3분기 보고서도 연간과 같은 연결/별도 기준으로 읽는다.
            q_rows = {q: _rows(fetch_report(corp, code, year, QUARTER_REPRT[q], refresh), fs_div)
                      for q in (1, 2, 3)}

            item = {"분기": f"{year}Q4"}
            for account in ("매출액", "영업이익", "당기순이익"):
                full = _pick(annual_rows, account)[0]
                three_months = [_pick(q_rows[q], account)[0] for q in (1, 2, 3)]
                if full is not None and all(v is not None for v in three_months):
                    item[account] = full - sum(three_months)
                else:
                    # 보조 경로: 1~3분기 중 빈 값이 있으면 3분기보고서 누적으로 뺀다
                    cumulative = _pick(q_rows[3], account, "thstrm_add_amount")[0]
                    item[account] = (full - cumulative) if (full is not None and cumulative is not None) else None
            # 재무상태표는 기말 잔액을 그대로 쓴다
            for account in ("자산총계", "부채총계", "자본총계"):
                item[account] = _pick(annual_rows, account)[0]
            item["매출계정명"] = _pick(annual_rows, "매출액")[1]

            if not need_ctrl:
                out.append(item)
                continue
            # 지배주주 순이익도 같은 규칙: 연간 - (1~3분기 3개월 합), 보조 경로는 3분기 누적
            full_ctrl, _, ctrl_eq, how = _controlling(corp, code, year, REPRT_ANNUAL, fs_div, annual_rows, refresh)
            parts = {q: _controlling(corp, code, year, QUARTER_REPRT[q], fs_div, q_rows[q], refresh)
                     for q in (1, 2, 3)}
            three_months = [parts[q][0] for q in (1, 2, 3)]
            if full_ctrl is not None and all(v is not None for v in three_months):
                item["지배순이익"] = full_ctrl - sum(three_months)
            elif full_ctrl is not None and parts[3][1] is not None:
                item["지배순이익"] = full_ctrl - parts[3][1]
            else:
                item["지배순이익"] = None
            item["지배자본"] = ctrl_eq
            # 4분기 방식은 연간과 1~3분기 방식을 모두 적어 둔다(검증용)
            methods = [how["순이익"]] + [parts[q][3]["순이익"] for q in (1, 2, 3)]
            item["지배순이익방식"] = "/".join(dict.fromkeys(str(m) for m in methods))
            item["지배자본방식"] = how["자본"]
            out.append(item)
        else:
            body = fetch_report(corp, code, year, QUARTER_REPRT[quarter], refresh)
            if not body:
                continue
            fs_div, label = _decide_fs_div(body)
            rows = _rows(body, fs_div)
            item = {"분기": f"{year}Q{quarter}"}
            item.update(_statement(rows))
            if not need_ctrl:
                out.append(item)
                continue
            ctrl_ni, _, ctrl_eq, how = _controlling(corp, code, year, QUARTER_REPRT[quarter], fs_div, rows, refresh)
            item["지배순이익"] = ctrl_ni           # 분기보고서 thstrm_amount = 3개월 값
            item["지배자본"] = ctrl_eq
            item["지배순이익방식"] = how["순이익"]
            item["지배자본방식"] = how["자본"]
            out.append(item)

    out.reverse()                         # 오래된 분기부터
    return {"연결구분": label, "분기별": out}


# ---------------------------------------------------------------------------
# 비율 계산 (모두 파이썬에서 계산한다)
# ---------------------------------------------------------------------------

def _ttm(quarters, account):
    """최근 4분기 합. 4개가 모두 있어야 계산한다."""
    values = [q.get(account) for q in quarters[-4:]]
    if len(values) < 4 or any(v is None for v in values):
        return None
    return sum(values)


def load_year_ago_equity(code, latest_key, refresh=False):
    """최근 분기의 1년 전 분기말 자본총계·지배자본을 가져온다(ROE 평균 자기자본용).

    예) 최근 분기가 2026Q2이면 2025년 반기보고서의 기말 잔액. 4분기는 사업보고서.
    """
    year, quarter = str(latest_key).split("Q")
    year, quarter = int(year) - 1, int(quarter)
    corp = _corp_code(code)
    reprt = QUARTER_REPRT[quarter]
    body = fetch_report(corp, code, year, reprt, refresh)
    if not body:
        return {"분기": f"{year}Q{quarter}", "자본총계": None, "지배자본": None}
    fs_div, _ = _decide_fs_div(body)
    rows = _rows(body, fs_div)
    _, _, ctrl_eq, _ = _controlling(corp, code, year, reprt, fs_div, rows, refresh)
    return {"분기": f"{year}Q{quarter}", "자본총계": _pick(rows, "자본총계")[0], "지배자본": ctrl_eq}


def _average(prev, now):
    """(1년 전 + 최근) / 2. 1년 전 값이 없으면 최근 값만 쓴다."""
    if now is None:
        return None
    return now if prev is None else (prev + now) / 2


def compute_ratios(annual, quarterly, marcap, year_ago=None):
    """비율 카드 5개(PER·PBR·ROE·부채비율·영업이익률)와 보조 비율을 계산한다.

    카드 5개는 모두 '최근 4분기 합산(TTM) 손익 + 최근 분기말 재무상태' 기준이고,
    PER·PBR·ROE는 네이버 증권 방식(우선주 포함 시가총액, 지배주주 기준, 평균 자기자본)을 따른다.
    - PER  = 시가총액 / TTM 지배주주 순이익        (0 이하면 '적자')
    - PBR  = 시가총액 / 분기말 지배기업 소유주지분   (못 찾으면 자본총계, 기준 '자본총계')
    - ROE  = TTM 지배주주 순이익 / 평균 지배자본(1년 전 분기말, 최근 분기말) x 100
      지배주주 계정을 못 찾으면 TTM 당기순이익 / 평균 자본총계로 계산하고 기준을 '당기순이익'으로 표시
    - 부채비율 = 분기말 부채총계 / 분기말 자본총계 x 100
    - 영업이익률 = TTM 영업이익 / TTM 매출액 x 100
    - 매출증감률(보조) = 최근 연간 매출 / 전년 매출 - 1
    """
    year_ago = year_ago or {}
    ratios = {"PER": None, "PBR": None, "ROE": None, "부채비율": None,
              "영업이익률": None, "순이익률": None, "매출증감률": None,
              "PER기준": None, "PBR기준": None, "ROE기준": None, "ROE평균": False,
              "기간": None, "기준분기": None,
              "TTM매출액": None, "TTM영업이익": None, "TTM순이익": None, "TTM지배순이익": None,
              "자본총계": None, "지배자본": None, "1년전지배자본": year_ago.get("지배자본"),
              "시가총액": marcap}

    years = annual.get("연도별") or []
    quarters = (quarterly.get("분기별") or [])[-4:]

    if len(years) >= 2 and years[-2].get("매출액") and years[-1].get("매출액"):
        ratios["매출증감률"] = _ratio((years[-1]["매출액"] / years[-2]["매출액"] - 1) * 100)

    if not quarters:
        ratios.update({"PER기준": "데이터부족", "PBR기준": "데이터부족", "ROE기준": "데이터부족"})
        return ratios

    latest = quarters[-1]
    # 화면·AI 입력 공통 표기: '2025년 3분기~2026년 2분기', '2026년 2분기'
    ratios["기준분기"] = quarter_text(latest["분기"])
    ratios["기간"] = period_text(quarters)

    sales = _ttm(quarters, "매출액")
    op = _ttm(quarters, "영업이익")
    net = _ttm(quarters, "당기순이익")
    ctrl = _ttm(quarters, "지배순이익")
    equity = latest.get("자본총계")
    debt = latest.get("부채총계")
    ctrl_eq = latest.get("지배자본")
    ratios.update({"TTM매출액": sales, "TTM영업이익": op, "TTM순이익": net, "TTM지배순이익": ctrl,
                   "자본총계": equity, "지배자본": ctrl_eq})

    if sales and op is not None:
        ratios["영업이익률"] = _ratio(op / sales * 100)
    if sales and net is not None:
        ratios["순이익률"] = _ratio(net / sales * 100)
    if debt is not None and equity:
        ratios["부채비율"] = _ratio(debt / equity * 100)

    # 기준 표기: 지배주주(표기 없음) / 당기순이익 / 자본총계 / 데이터부족
    # PER: 지배주주 순이익 우선, 없으면 당기순이익. 4분기 합이나 시가총액이 없으면 데이터부족
    per_ni, ratios["PER기준"] = (ctrl, "지배주주") if ctrl is not None else (net, "당기순이익")
    if marcap and per_ni is not None:
        ratios["PER"] = "적자" if per_ni <= 0 else _ratio(marcap / per_ni)
    else:
        ratios["PER기준"] = "데이터부족"

    # ROE: 분자·분모 모두 지배주주가 있어야 지배주주 기준, 아니면 당기순이익 / 자본총계
    #      분모는 (1년 전 분기말 + 최근 분기말) / 2. 1년 전 값이 없으면 데이터부족으로 표시
    if ctrl is not None and ctrl_eq:
        base = _average(year_ago.get("지배자본"), ctrl_eq)
        ratios["ROE"], ratios["ROE기준"] = _ratio(ctrl / base * 100), "지배주주"
        ratios["ROE평균"] = year_ago.get("지배자본") is not None
    elif net is not None and equity:
        base = _average(year_ago.get("자본총계"), equity)
        ratios["ROE"], ratios["ROE기준"] = _ratio(net / base * 100), "당기순이익"
        ratios["ROE평균"] = year_ago.get("자본총계") is not None
    if ratios["ROE"] is None or not ratios["ROE평균"]:
        ratios["ROE기준"] = "데이터부족"

    # PBR: 지배기업 소유주지분 우선, 없으면 자본총계
    pbr_eq, ratios["PBR기준"] = (ctrl_eq, "지배주주") if ctrl_eq else (equity, "자본총계")
    if marcap and pbr_eq:
        ratios["PBR"] = _ratio(marcap / pbr_eq)
    else:
        ratios["PBR기준"] = "데이터부족"
    return ratios


# ---------------------------------------------------------------------------
# 화면에서 쓰는 진입점
# ---------------------------------------------------------------------------

def find_preferred(snapshot, code):
    """같은 회사 우선주 행을 찾는다.

    우선주는 '보통주 이름 + (공백)(숫자)우(영문)(전환)' 형태이고 종목코드 앞 4자리가 같다.
    예) 삼성전자우(005935), 현대차2우B(005387), CJ4우(전환)(00104K), CJ제일제당 우(097955)
    이름을 보통주 이름 전체로 고정해 '성우', '이오플로우' 같은 일반 종목은 걸리지 않게 한다.
    """
    code = str(code).zfill(6)
    hit = snapshot[snapshot["종목코드"] == code]
    if hit.empty:
        return snapshot.iloc[0:0]
    name = str(hit.iloc[0]["종목명"])
    pattern = "^" + re.escape(name) + r"\s?\d?우[A-Z]?(?:\(전환\))?$"
    same_prefix = snapshot["종목코드"].str[:4] == code[:4]
    return snapshot[same_prefix & snapshot["종목명"].str.match(pattern) & (snapshot["종목코드"] != code)]


def _cap_at_base(dl, row):
    """상장주식수 x 기준일 종가(pykrx, data.session_cutoff 이전 마지막 일봉). 계산할 수 없으면 FDR 시가총액, 그것도 없으면 None."""
    shares = row.get("상장주식수")
    if shares is not None and pd.notna(shares) and shares > 0:
        end = datetime.combine(dl.session_cutoff(), datetime.min.time()) + timedelta(days=1)
        df = dl.fetch_ohlcv_raw(row["종목코드"], end - timedelta(days=20), end)
        if df is not None and not df.empty:
            return float(shares) * float(df["종가"].iloc[-1])
    cap = row.get("시가총액")
    return float(cap) if cap is not None and pd.notna(cap) and cap > 0 else None


def market_cap(code):
    """보통주 + 우선주 시가총액 합계. 없으면 None.

    시가총액 = FDR 상장주식수 x pykrx 기준일 종가(지침 v1.4 5.0 기준일과 맞춤). FDR 스냅샷에 시세가 비어 있어도
    (KRX lateInfoMsgCd ME005 등) 상장주식수만 있으면 계산된다.
    반환: {"합계": 원, "보통주": 원, "우선주": [(종목명, 원), ...]}
    """
    import data as dl
    _ts = time.perf_counter()                                                    # [계측] st 캐시 대기(락) 포함
    snapshot = dl.load_market_snapshot()
    print(f"[SUB] load_market_snapshot(market_cap) {time.perf_counter() - _ts:.2f}s {_sub_tag()}", flush=True)  # [계측]
    if snapshot.empty:
        return None
    hit = snapshot[snapshot["종목코드"] == str(code).zfill(6)]
    if hit.empty:
        return None
    _ts = time.perf_counter()                                                    # [계측]
    common = _cap_at_base(dl, hit.iloc[0])
    print(f"[SUB] _cap_at_base 보통주 {str(code).zfill(6)} {time.perf_counter() - _ts:.2f}s {_sub_tag()}", flush=True)  # [계측]
    if common is None:
        return None
    prefs = []
    for _, r in find_preferred(snapshot, code).iterrows():
        _ts = time.perf_counter()                                                # [계측]
        value = _cap_at_base(dl, r)
        print(f"[SUB] _cap_at_base 우선주 {r['종목코드']} {time.perf_counter() - _ts:.2f}s {_sub_tag()}", flush=True)  # [계측]
        if value is not None:
            prefs.append((r["종목명"], value))
    return {"합계": common + sum(v for _, v in prefs), "보통주": common, "우선주": prefs}


def load_season_years(code, refresh=False, today=None):
    """계절성 연도(6시간 캐시). DART 불가 상태에서 만든(빠진) 결과는 st 캐시에 넣지 않는다(indicators.compute 와 같은 규칙).
    load_financials 가 화면 실행마다 1번 부르므로 불가 상태에서는 캐시 없이 계산한다."""
    if dart_guard.available():
        try:
            return _load_season_years_cached(code, refresh, today, dart_guard.state_key())
        except dart_guard.TrippedDuringCache as exc:
            return exc.result
    return _load_season_years(code, refresh, today)


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def _load_season_years_cached(code, refresh, today, dart_state):
    """load_season_years 의 6시간 캐시 본체. 계산 도중 DART 불가가 되면 캐시하지 않도록 예외로 돌려준다."""
    result = _load_season_years(code, refresh, today)
    if not dart_guard.available():
        raise dart_guard.TrippedDuringCache(result)
    return result


def _load_season_years(code, refresh=False, today=None):
    """계절성 판정용(리포트 구성 지침 v1.4 5.10): 직전 완결된 2개 사업연도의 분기별(3개월) 매출·영업이익.

    완결 연도 = 사업보고서까지 공시된 가장 최근 연도(latest_annual_year)와 그 전 해.
    load_quarterly를 '그 해 4분기가 가장 최근 공시 분기인 날짜'로 불러 1~4분기를 받는다(지배주주 값은 찾지 않는다).
    반환: {연도: [1~4분기 dict(오래된 분기부터)]}
    """
    _t = time.perf_counter()                                                     # [계측] st 캐시가 없을 때만 찍힌다
    last = latest_annual_year(today)
    out = {}
    for year in (last - 1, last):
        month, day = QUARTER_READY[4]
        quarters = load_quarterly(code, 4, refresh, today=datetime(year + 1, month, day), ctrl_recent=0)
        out[year] = [x for x in (quarters.get("분기별") or []) if x["분기"].startswith(str(year))]
    print(f"[STEP] 계절성 {code} {time.perf_counter() - _t:.2f}s", flush=True)  # [계측]
    return out


load_season_years.clear = _load_season_years_cached.clear      # 사이드바 '재무 새로고침'이 부르는 캐시 비우기


RUN_MEMO_KEY = "_fin_run_memo"          # app.main 이 화면 실행(rerun)마다 새 dict 로 바꾼다


def _run_memo():
    """이번 화면 실행의 load_financials 메모(dict). Streamlit 스크립트 스레드 밖(작업 스레드·리포트 단독 실행)은 None."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx() is None:
            return None
        memo = st.session_state.get(RUN_MEMO_KEY)
        return memo if isinstance(memo, dict) else None
    except Exception:
        return None


def load_financials(code, name="", refresh=False):
    """연간·분기 재무와 비율을 한 번에 만들어 돌려준다.

    한 번의 화면 실행 안에서는 같은 종목 결과를 재사용한다(재무 섹션·쉽게 읽기·방향 지시계·지표가 각각 부르던 것을
    1번으로). 메모는 app.main 이 실행마다 새로 만들므로 다음 실행에는 남지 않는다. 돌려주는 값은 복사본이다.
    """
    memo = _run_memo()
    memo_key = (str(code).zfill(6), name, bool(refresh))
    if memo is not None and memo_key in memo:
        print(f"[SUB] load_financials 재사용(이번 실행) {memo_key[0]} {_sub_tag()}", flush=True)   # [계측]
        return copy.deepcopy(memo[memo_key])
    _t = time.perf_counter()                                                     # [계측]
    print(f"[SUB] load_financials 시작 {str(code).zfill(6)} {_sub_tag()}", flush=True)   # [계측]
    annual = load_annual(code, refresh)
    print(f"[SUB] load_annual {str(code).zfill(6)} {time.perf_counter() - _t:.2f}s {_sub_tag()}", flush=True)  # [계측]
    _ts = time.perf_counter()                                                    # [계측]
    # 8개 분기: 최근 4분기(표·비율) + 직전 4분기(매출 증감 비교용). 지배주주 값은 최근 4분기만 찾는다.
    quarterly = load_quarterly(code, 8, refresh, ctrl_recent=4)
    print(f"[SUB] load_quarterly {str(code).zfill(6)} {time.perf_counter() - _ts:.2f}s {_sub_tag()}", flush=True)  # [계측]
    all_quarters = quarterly.get("분기별") or []
    recent_keys = {f"{y}Q{q}" for y, q in recent_quarters(4)}
    prior_keys = {f"{y}Q{q}" for y, q in recent_quarters(8)} - recent_keys
    recent = [x for x in all_quarters if x["분기"] in recent_keys]     # 빠진 분기가 있으면 4개 미만
    prior = [x for x in all_quarters if x["분기"] in prior_keys]

    _ts = time.perf_counter()                                                    # [계측]
    cap = market_cap(code)
    print(f"[SUB] market_cap {str(code).zfill(6)} {time.perf_counter() - _ts:.2f}s {_sub_tag()}", flush=True)  # [계측]
    _ts = time.perf_counter()                                                    # [계측]
    year_ago = load_year_ago_equity(code, recent[-1]["분기"], refresh) if recent else None
    print(f"[SUB] load_year_ago_equity {str(code).zfill(6)} {time.perf_counter() - _ts:.2f}s {_sub_tag()}", flush=True)  # [계측]
    ratios = compute_ratios(annual, {"분기별": recent}, cap["합계"] if cap else None, year_ago)
    ratios["우선주"] = cap["우선주"] if cap else []

    label = annual.get("연결구분") or quarterly.get("연결구분")
    _ts = time.perf_counter()                                                    # [계측] st 캐시 대기(락) 포함
    try:
        season = load_season_years(code, refresh)
    except Exception:
        season = {}
    print(f"[SUB] load_season_years(호출) {str(code).zfill(6)} {time.perf_counter() - _ts:.2f}s {_sub_tag()}",
          flush=True)                                                            # [계측]
    print(f"[STEP] 재무 {str(code).zfill(6)} {time.perf_counter() - _t:.2f}s", flush=True)  # [계측] 계절성 포함
    result = {
        "종목코드": str(code).zfill(6),
        "종목명": name,
        "연결구분": label,
        "연간": annual.get("연도별", []),
        "분기": recent,
        "직전분기": prior,
        "계절성연도": season,                 # 지침 v1.4 5.10: {연도: 1~4분기}
        "매출계정명": annual.get("매출계정명"),
        "비율": ratios,
        "수집시각": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if memo is not None:
        memo[memo_key] = copy.deepcopy(result)
    return result


# ---------------------------------------------------------------------------
# [4-2단계] AI 분석에 넘길 재무 블록
# ---------------------------------------------------------------------------

BASIS_NOTE = {"당기순이익": "(당기순이익 기준)", "자본총계": "(자본총계 기준)", "데이터부족": "(데이터 부족)"}


def _sign_word(value):
    return "흑자" if value > 0 else ("적자" if value < 0 else "0")


def _trend_word(values):
    """연속 값이 모두 오르면 상승, 모두 내리면 하락, 그 외 혼조."""
    ups = [b > a for a, b in zip(values, values[1:])]
    downs = [b < a for a, b in zip(values, values[1:])]
    if all(ups):
        return "상승"
    if all(downs):
        return "하락"
    return "혼조"


def _annual_trend_sentence(title, years, values, year_label):
    """연간 이익 추세 문장을 만든다. 반환 (문장, 증가/감소/혼조, 전환 목록).

    예) "연간 영업이익은 2023년→2024년→2025년 순으로 증가"
        "연간 지배주주 순이익은 2023년→2024년→2025년 순으로 감소, 2025년 적자 전환"
        "연간 영업이익은 2023년→2024년→2025년 순으로 혼조, 3개 연도 모두 적자"
    전환 목록: [("2025", "적자 전환"), ...]
    """
    word = {"상승": "증가", "하락": "감소"}.get(_trend_word(values), "혼조")
    turns = []
    for prev, now, y in zip(values, values[1:], years[1:]):
        if prev >= 0 > now:
            turns.append((str(y["연도"]), "적자 전환"))
        elif prev < 0 <= now:
            turns.append((str(y["연도"]), "흑자 전환"))
    sentence = f"연간 {title}은 {year_label} 순으로 {word}"
    if turns:
        sentence += ", " + ", ".join(f"{y}년 {t}" for y, t in turns)
    elif all(v < 0 for v in values):
        sentence += f", {len(values)}개 연도 모두 적자"
    return sentence, word, turns


def _missing_reason(fin):
    """'데이터 부족'이 된 이유를 한 문장으로 만든다."""
    ratios = fin["비율"]
    recent = fin.get("분기") or []
    if len(recent) < 4:
        return f"최근 4분기 중 {len(recent)}개 분기 보고서만 있어 최근 4분기 합산 재무 지표를 산출하지 못함"
    blank = [quarter_text(x["분기"]) for x in recent if x.get("당기순이익") is None]
    if blank:
        return (f"{', '.join(blank)} 순이익 값을 공시에서 확인할 수 없어 "
                "최근 4분기 합산 재무 지표를 산출하지 못함")
    if not ratios.get("ROE평균"):
        return "1년 전 분기말 자본 데이터가 없어 평균 자기자본 기준 ROE를 산출하지 못함"
    if not ratios.get("시가총액"):
        return "시가총액 데이터가 없어 PER·PBR을 산출하지 못함"
    return "재무 데이터가 부족해 재무 지표를 산출하지 못함"


def build_fin_facts(fin, is_finance=False):
    """재무 대소 관계·부호를 파이썬이 판정해 사실 문장과 판정값을 만든다.

    반환 (사실 문장 리스트, 판정 dict). 판정 dict는 사후 방향 검증에 쓴다.
    """
    facts, verdict = [], {}
    recent, prior = fin.get("분기") or [], fin.get("직전분기") or []
    years = fin.get("연간") or []
    ratios = fin["비율"]

    # 1) 최근 4분기 매출 vs 직전 4분기 매출
    if not is_finance and len(recent) == 4 and len(prior) == 4:
        now = [x.get("매출액") for x in recent]
        before = [x.get("매출액") for x in prior]
        if all(v is not None for v in now + before):
            word = "증가" if sum(now) > sum(before) else ("감소" if sum(now) < sum(before) else "같음")
            facts.append(f"최근 4분기({period_text(recent)}) 매출 합계는 직전 4분기 매출 합계보다 {word}")
            verdict["매출4분기"] = word

    # 2) 최근 분기 영업이익 부호와 직전 분기 대비 부호 변화
    ops = [x.get("영업이익") for x in recent]
    if len(ops) >= 2 and ops[-1] is not None and ops[-2] is not None:
        last, before = _sign_word(ops[-1]), _sign_word(ops[-2])
        name_last, name_before = quarter_text(recent[-1]["분기"]), quarter_text(recent[-2]["분기"])
        if last == before:
            change = f"{before} 유지"
        else:
            change = f"{before}에서 {last}로 전환"
        facts.append(f"최근 분기({name_last}) 영업이익은 {last}이며, 직전 분기({name_before}) 대비 {change}")
        verdict["최근분기영업이익"] = last
        verdict["영업이익전환"] = None if last == before else f"{before}->{last}"

    # 3) 최근 4분기 합산 지배주주 순이익 부호
    ttm = ratios.get("TTM지배순이익") if ratios.get("PER기준") == "지배주주" else ratios.get("TTM순이익")
    if ttm is not None:
        facts.append(f"최근 4분기 합산 순이익은 {_sign_word(ttm)}")

    # 4) 연간 영업이익률 추세 / 연간 매출 추세
    year_label = "→".join(f"{y['연도']}년" for y in years)       # '2023년→2024년→2025년'
    if not is_finance and len(years) >= 3:
        margins = [y["영업이익"] / y["매출액"] * 100 if (y.get("매출액") and y.get("영업이익") is not None)
                   else None for y in years]
        if all(m is not None for m in margins):
            word = _trend_word(margins)
            facts.append(f"연간 영업이익률은 {year_label} 순으로 {word}")
            verdict["연간영업이익률"] = word
        sales = [y.get("매출액") for y in years]
        if all(v is not None for v in sales):
            word = {"상승": "증가", "하락": "감소"}.get(_trend_word(sales), "혼조")
            facts.append(f"연간 매출은 {year_label} 순으로 {word}")

    # 5) 연간 영업이익·지배주주 순이익 추세와 흑자/적자 전환 (금융업도 적용)
    if len(years) >= 3:
        for key, title, verdict_key in (("영업이익", "영업이익", "연간영업이익"),
                                        ("지배순이익", "지배주주 순이익", "연간지배순이익")):
            values = [y.get(key) for y in years]
            if any(v is None for v in values):
                continue
            sentence, word, turns = _annual_trend_sentence(title, years, values, year_label)
            facts.append(sentence)
            verdict[verdict_key] = word
            verdict[verdict_key + "전환"] = turns

    # 6) 전년 동기 비교(YoY)와 재무상태 직전 분기 대비 변화
    changes = compute_changes(fin, is_finance)
    for item in changes["사실"]:
        facts.append(item["문장"])
        verdict[item["판정키"]] = item["판정"]

    # 7) PER 산출 불가
    if ratios.get("PER") == "적자":
        facts.append("최근 4분기 합산 순이익이 음수라 PER 산출 불가")

    # 8) 금융업
    if is_finance:
        facts.append("금융업은 매출·영업이익률 비교가 적용되지 않음")
        facts.append("금융업은 예금·보험부채 구조상 부채비율이 높게 나타나며 일반 기업과 직접 비교하지 않음")
    return facts, verdict


# ---------------------------------------------------------------------------
# 전년 동기(YoY)·반기 비교, 재무상태 직전 분기 대비 변화 (KH바텍 리포트 검토 보정)
# ---------------------------------------------------------------------------

BALANCE_ALERT_PCT = 30.0        # 부채·자본총계가 직전 분기 말 대비 이 비율(%) 이상 움직이면 사실 문장을 만든다


def _pct_change(now, before):
    if now is None or before is None or before == 0:
        return None
    return (now / before - 1) * 100


def profit_change(now, before):
    """전년 동기 대비 변화. 기준값이 적자이거나 부호가 바뀌면 증감률 대신 전환 판정을 쓴다.

    반환: {"값": 증감률 또는 None, "판정": 증가/감소/흑자 전환/적자 전환/적자 지속, "문자열": "+12.3%" 또는 판정}
    """
    if now is None or before is None or before == 0:
        return None
    if before > 0 and now < 0:
        return {"값": None, "판정": "적자 전환", "문자열": "적자 전환"}
    if before < 0 and now > 0:
        return {"값": None, "판정": "흑자 전환", "문자열": "흑자 전환"}
    if before < 0 and now <= 0:
        return {"값": None, "판정": "적자 지속", "문자열": "적자 지속"}
    pct = _pct_change(now, before)
    word = "증가" if pct > 0 else ("감소" if pct < 0 else "변동 없음")
    return {"값": round(pct, 1), "판정": word, "문자열": f"{pct:+,.1f}%"}


def _half_label(recent):
    """최근 2개 분기 이름. 2분기로 끝나면 상반기, 4분기로 끝나면 하반기."""
    last_q = int(str(recent[-1]["분기"]).split("Q")[1])
    year = str(recent[-1]["분기"]).split("Q")[0]
    if last_q == 2:
        return f"{year}년 상반기(1~2분기)"
    if last_q == 4:
        return f"{year}년 하반기(3~4분기)"
    return f"최근 2개 분기({quarter_text(recent[-2]['분기'])}~{quarter_text(recent[-1]['분기'])})"


def compute_changes(fin, is_finance=False):
    """최근 분기 YoY, 최근 2개 분기 합 YoY, 부채·자본총계 직전 분기 대비 변화를 계산한다.

    반환: {"문자열": {이름: 표시 문자열}, "사실": [{"문장", "판정키", "판정"}], "YoY": {항목: profit_change 결과}}
      - 사실 문장은 YoY 4종(매출·영업이익 × 최근 분기·2개 분기)은 늘 만들고,
        부채·자본총계는 ±BALANCE_ALERT_PCT% 이상일 때만 만든다.
    """
    out = {"문자열": {}, "사실": [], "YoY": {}}
    recent, prior = fin.get("분기") or [], fin.get("직전분기") or []
    accounts = [("영업이익", "영업이익")] if is_finance else [("매출액", "매출액"), ("영업이익", "영업이익")]

    if len(recent) == 4 and len(prior) == 4:
        q_now, q_before = quarter_text(recent[-1]["분기"]), quarter_text(prior[-1]["분기"])
        half = _half_label(recent)
        for key, title in accounts:
            # 최근 분기 vs 전년 동기
            change = profit_change(recent[-1].get(key), prior[-1].get(key))
            if change:
                out["YoY"][key] = change
                out["문자열"][f"최근 분기 {title}"] = (f"최근 분기({q_now}) {title} 전년 동기({q_before}) 대비 "
                                                   f"{change['문자열']}")
                tail = f"{abs(change['값']):,.1f}% {change['판정']}" if change["값"] is not None else change["판정"]
                out["사실"].append({"문장": f"최근 분기({q_now}) {title}은 전년 동기({q_before}) 대비 {tail}",
                                    "판정키": f"{key}YoY", "판정": change["판정"]})
            # 최근 2개 분기 합 vs 전년 동기
            now2 = [x.get(key) for x in recent[-2:]]
            before2 = [x.get(key) for x in prior[-2:]]
            if all(v is not None for v in now2 + before2):
                change = profit_change(sum(now2), sum(before2))
                if change:
                    out["YoY"][f"반기{key}"] = change
                    out["문자열"][f"{half} {title}"] = f"{half} {title} 합계 전년 동기 대비 {change['문자열']}"
                    tail = f"{abs(change['값']):,.1f}% {change['판정']}" if change["값"] is not None else change["판정"]
                    out["사실"].append({"문장": f"{half} {title} 합계는 전년 동기 대비 {tail}",
                                        "판정키": f"반기{key}YoY", "판정": change["판정"]})

    if len(recent) >= 2:
        for key in ("부채총계", "자본총계"):
            pct = _pct_change(recent[-1].get(key), recent[-2].get(key))
            if pct is None:
                continue
            out["문자열"][key] = f"{key} 직전 분기 말 대비 {pct:+,.1f}%"
            if abs(pct) >= BALANCE_ALERT_PCT:
                word = "증가" if pct > 0 else "감소"
                out["사실"].append({"문장": f"{key}가 직전 분기 말 대비 {abs(pct):,.1f}% {word}",
                                    "판정키": f"{key}QoQ", "판정": word})
    return out


def format_eok(value_won):
    """원 단위 금액을 화면·분석문용 표시 문자열로 바꾼다(억 원 단위 반올림 후).

    1조 이상: "485조 2,720억 원" (억 자리가 0이면 "485조 원")
    1조 미만: "8,643억 원"        음수: 앞에 '-' ("-1,234억 원", "-1조 234억 원")
    """
    if value_won is None:
        return "해당 없음"
    eok = _eok(value_won)
    sign = "-" if eok < 0 else ""
    eok = abs(eok)
    jo, rest = divmod(eok, 10_000)
    if jo == 0:
        return f"{sign}{rest:,}억 원"
    if rest == 0:
        return f"{sign}{jo:,}조 원"
    return f"{sign}{jo:,}조 {rest:,}억 원"


# 비율 문자열 끝 괄호에 붙이는 표기 사유
NOTE_TEXT = {"당기순이익": "당기순이익 기준", "자본총계": "자본총계 기준", "데이터부족": "데이터 부족"}


def format_ratio(name, value, unit, bases=None):
    """비율을 완성 문자열로 만든다. 천 단위 쉼표·소수 1자리·단위·괄호 속 기준 문구 포함.

    예) format_ratio("PER", 15.2, "배", ["우선주 포함 시가총액 기준", "당기순이익 기준"])
        -> "PER 15.2배 (우선주 포함 시가총액 기준, 당기순이익 기준)"
        format_ratio("부채비율", 1282.6, "%") -> "부채비율 1,282.6%"
        PER 값이 '적자'면 -> "PER 산출 불가 (최근 4분기 합산 순이익 적자)"
    """
    if value is None:
        return f"{name} 해당 없음"
    if value == "적자":
        return f"{name} 산출 불가 (최근 4분기 합산 순이익 적자)"
    text = f"{name} {value:,.1f}{unit}"
    bases = [b for b in (bases or []) if b]
    return f"{text} ({', '.join(bases)})" if bases else text


def ai_block(code, name="", industry_group=None):
    """AI 분석 입력용 재무 블록을 만든다.

    - 금액은 표시 문자열("485조 2,720억 원")만 넘긴다(억 원 원값은 넘기지 않는다).
    - 비율도 완성 문자열("PER 12.3배 (우선주 포함 시가총액 기준)")로 넘기고,
      표기 사유(당기순이익 기준 등)는 해당 지표 괄호 끝에 붙인다.
    - 기간은 '2025년 3분기~2026년 2분기', '2026년 2분기 말', 개별 분기는 '2026년 2분기'로 고정한다.
    - 비율은 기준이 다른 두 묶음으로 나눈다.
        손익 비율(최근 4분기 합산): 영업이익률, 순이익률, ROE, PER
        재무상태 비율(최근 분기말):  부채비율, PBR
    재무 데이터가 없거나 '데이터 부족'이면 {"가능": False, "사유": ...} 만 돌려준다.
    """
    if not fin_enabled():
        return {"가능": False, "사유": "DART API 키가 없어 재무 데이터를 제공하지 않음"}
    try:
        fin = load_financials(str(code).zfill(6), name)
    except Exception as exc:
        return {"가능": False, "사유": f"재무 데이터 수집 실패({type(exc).__name__})"}
    if not fin["연간"] and not fin["분기"]:
        return {"가능": False, "사유": "DART에 재무 데이터가 없음"}

    ratios = fin["비율"]
    if "데이터부족" in (ratios.get("PER기준"), ratios.get("PBR기준"), ratios.get("ROE기준")):
        return {"가능": False, "사유": _missing_reason(fin)}

    is_finance = industry_group == "금융"
    sales_name = fin.get("매출계정명") or "매출액"
    facts, verdict = build_fin_facts(fin, is_finance)

    recent = fin["분기"]
    period = period_text(recent)                              # '2025년 3분기~2026년 2분기'
    balance_at = f"{quarter_text(recent[-1]['분기'])} 말"      # '2026년 2분기 말'

    def note(key):
        """표기 사유(당기순이익 기준 등). 지배주주 기준이면 빈 값."""
        return NOTE_TEXT.get(ratios.get(f"{key}기준"))

    return {
        "가능": True,
        "기준": f"{fin['연결구분'] or '연결'}재무제표",
        "출처": "금융감독원 DART",
        "단위": "금액·비율·기간은 표시 문자열 그대로",
        "최근4분기": period,
        "재무상태기준": balance_at,
        "최근4분기합산": {
            sales_name: format_eok(ratios.get("TTM매출액")),
            "영업이익": format_eok(ratios.get("TTM영업이익")),
            # 지배주주 계정을 못 찾았으면 이름을 '당기순이익'으로 바꿔 넘긴다
            **({"지배주주순이익": format_eok(ratios.get("TTM지배순이익"))}
               if ratios.get("TTM지배순이익") is not None
               else {"당기순이익": format_eok(ratios.get("TTM순이익"))}),
        },
        # 비율은 이름·값·단위·기준 문구까지 완성한 문자열로 넘긴다(모델이 기준 문구를 옮기지 않도록).
        "손익비율": {
            "기준": f"최근 4분기 합산({period})",
            "영업이익률": format_ratio("영업이익률", None if is_finance else ratios.get("영업이익률"), "%"),
            "순이익률": format_ratio("순이익률", None if is_finance else ratios.get("순이익률"), "%"),
            "ROE": format_ratio("ROE", ratios.get("ROE"), "%", ["평균 자기자본 기준", note("ROE")]),
            "PER": format_ratio("PER", ratios.get("PER"), "배", ["우선주 포함 시가총액 기준", note("PER")]),
        },
        "재무상태비율": {
            "기준": balance_at,
            "부채비율": format_ratio("부채비율", ratios.get("부채비율"), "%"),
            "PBR": format_ratio("PBR", ratios.get("PBR"), "배", ["우선주 포함 시가총액 기준", note("PBR")]),
        },
        # 전년 동기 비교·재무상태 변화: 증감률도 완성 문자열로 넘긴다(방향은 '사실' 문장이 근거)
        "전년동기비교": {k: v for k, v in compute_changes(fin, is_finance)["문자열"].items()
                    if k not in ("부채총계", "자본총계")},
        "재무상태변화": {k: v for k, v in compute_changes(fin, is_finance)["문자열"].items()
                    if k in ("부채총계", "자본총계")},
        "연간": [{"연도": y["연도"], sales_name: format_eok(y.get("매출액")),
                  "영업이익": format_eok(y.get("영업이익"))} for y in fin["연간"]],
        "분기": [{"분기": quarter_text(x["분기"]), sales_name: format_eok(x.get("매출액")),
                  "영업이익": format_eok(x.get("영업이익"))} for x in recent],
        "사실": facts,
        "판정": verdict,
    }


def clear_cache(code=None):
    """재무 캐시를 지운다(종목코드를 주면 그 종목만). 예전 버전 파일도 함께 지운다."""
    if not os.path.isdir(FIN_CACHE_DIR):
        return 0
    removed = 0
    for filename in os.listdir(FIN_CACHE_DIR):
        if code and not filename.startswith(str(code).zfill(6) + "_"):
            continue
        try:
            os.remove(os.path.join(FIN_CACHE_DIR, filename))
            removed += 1
        except Exception:
            pass
    return removed


# ---------------------------------------------------------------------------
# 표 만들기
# ---------------------------------------------------------------------------

def _row_label(item):
    """표·차트 축 라벨. 공간이 좁으므로 짧게: 연간 '2025', 분기 '26.2Q'."""
    if "연도" in item:
        return item.get("연도")
    year, q = str(item.get("분기")).split("Q")
    return f"{year[2:]}.{q}Q"


def to_table(items, sales_name=None):
    """연간/분기 데이터를 화면 표(억 원 단위)로 바꾼다.

    매출액 계정이 없는 회사(은행·지주 등)는 '해당 없음'으로 표시한다.
    영업이익률은 행마다 그 기간(연간 또는 분기 3개월) 값으로 계산한다.
    """
    if not items:
        return pd.DataFrame()

    columns = []
    for item in items:
        sales = item.get("매출액")
        columns.append({
            "구분": str(_row_label(item)),
            (sales_name or "매출액"): "해당 없음" if sales is None else f"{_eok(sales):,}",
            "영업이익": "-" if item.get("영업이익") is None else f"{_eok(item['영업이익']):,}",
            "당기순이익": "-" if item.get("당기순이익") is None else f"{_eok(item['당기순이익']):,}",
            "자산총계": "-" if item.get("자산총계") is None else f"{_eok(item['자산총계']):,}",
            "부채총계": "-" if item.get("부채총계") is None else f"{_eok(item['부채총계']):,}",
            "자본총계": "-" if item.get("자본총계") is None else f"{_eok(item['자본총계']):,}",
            "영업이익률": "-" if not (item.get("매출액") and item.get("영업이익") is not None)
                        else f"{item['영업이익'] / item['매출액'] * 100:.1f}%",
        })
    return pd.DataFrame(columns)


def to_chart_frame(items):
    """차트용 DataFrame(억 원 + 영업이익률)을 만든다."""
    rows = []
    for item in items:
        sales = item.get("매출액")
        op = item.get("영업이익")
        rows.append({
            "구분": str(_row_label(item)),
            "매출액": _eok(sales) if sales is not None else None,
            "영업이익": _eok(op) if op is not None else None,
            "영업이익률": round(op / sales * 100, 1) if (sales and op is not None) else None,
        })
    return pd.DataFrame(rows)
