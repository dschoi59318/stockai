# -*- coding: utf-8 -*-
"""
events.py - 주가 급변 사건과 공시·뉴스 이벤트 타임라인 (리포트 개편 1단계: 원인 분석용 데이터 수집)

v2 (매칭 품질 개선)
 1. 시장 전체 움직임 분리: 종목 소속 시장 지수(코스피 KS11 / 코스닥 KQ11, FDR)의 일간 등락을 빼고
    '초과 등락'으로 급변을 판정한다. 초과 등락은 기준 미달인데 지수가 ±2% 이상 움직인 날은
    "시장 전체 움직임"으로 따로 표시하고 개별 이벤트를 붙이지 않는다.
 2. 연속 급변일 묶기: 3거래일 이내로 이어진 급변일은 한 사건(시작일~종료일, 누적 등락률, 최대 거래량 배수).
    매칭 창은 시작일 -2거래일 ~ 종료일 +1거래일.
 3. 뉴스를 사건 창별로 검색: 네이버 최신순 300건은 그대로 두고, 사건마다 구글 뉴스 RSS를 추가로 검색.
    제목·날짜·링크(구글 링크 그대로)만 저장. 사건별 뉴스수집: "수집됨" / "수집 범위 밖" / "검색 결과 없음"
 4. 동명 회사 제외: stock_master.csv에서 현재 종목명으로 시작하는 다른 상장 종목명(OCI → OCI홀딩스)을 찾아,
    제목에서 그 이름들을 지운 뒤에도 현재 종목명이 남지 않는 기사는 뺀다.
 5. 공시 중요도: 강함 / 약함 / 보통(두 목록 어디에도 없는 공시).
 6. 사후 조치: 투자주의·투자경고·투자위험 지정, 단기과열, 조회공시 등 급변의 결과로 나오는 공시·뉴스는
    원인 후보에서 빼고 "사후 조치"로 따로 적는다.

v3 (마무리 보정)
 1. 공시 기반 사건: 강한 공시일(그날 또는 다음 거래일) ±2거래일 안에 |초과 등락| >= 1σ인 날이 있으면
    급변 기준 미달이어도 사건으로 추가한다(유형 "공시 기반 사건"). 이미 급변 사건의 매칭 창 안에 있는 공시,
    시장 전체 움직임 날, 급변 사건에 이미 들어간 날은 쓰지 않는다. 매칭 창은 근거 공시일까지 넓힌다.
 2. 동명 제외 강화: (a) 제목에서 종목명 바로 뒤에 한글·영문이 붙으면(OCI미술관, OCIDream) 그 언급은 무효.
    조사(은·는·이·가·의 …)는 붙어도 인정. (b) data/name_exclude.csv(종목코드, 제외어)의 제외어가 제목에 있으면 제외.
 3. 사후 표현 추가(뉴스): "가격제한폭", "장중 N% 상승/하락", "상한가 기록", "하한가 기록"이 있는 순수 시세 보도는
    사후 조치로 분류. 제목에 [특징주]가 있으면 이 규칙을 적용하지 않고 원인 후보로 둔다.
 4. 구글 검색 창 = 매칭 창(거래일 기준)을 달력일로 바꾼 것: after:창시작-1일 before:창끝+1일.
 5. 대표 이벤트: 강한 공시 1건(사건 시작일에 가장 가까운 것) + 원인 설명 기사 1건
    ([특징주] 우선(동명 회사 이름이 있는 [특징주]는 제외), 없으면 창 안 기사들과 겹치는 키워드가 가장 많은 기사,
    같으면 사건 시작일에 가까운 기사). 제외어는 언론사 표기까지 포함한 제목 전체에서 찾는다.

수집 (v1과 같음)
 - DART 공시목록(list.json): 기준일 전 1년, 유형 A 정기공시 / B 주요사항 / D 지분공시 / I 거래소공시.
   제목 머리표 [기재정정]·[첨부정정]·[첨부추가]·[변경등록]·[연장결정]·[발행조건확정], 철회 공시, 같은 날 같은 제목은 뺀다.
 - 네이버 뉴스 검색 API: "종목명" 최신순 최대 300건, 기준일 전 1년, 제목에 종목명이 있는 기사만.
   키: ct_keys.py의 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET (없으면 네이버는 건너뛴다)

급변일 (기준일 전 1년의 거래일, '직전' 창은 당일을 뺀다)
 - 등락: |종목 등락률 - 지수 등락률| >= 직전 20거래일 초과 등락률 표준편차 x 2
 - 거래량: 거래량 >= 직전 60거래일 평균 거래량 x 3
 - 시장 전체 움직임: 위 두 기준 또는 종목 등락률 자체의 2σ 기준에 걸렸지만 '초과 등락이 작고'
   |지수 등락률| >= 2%인 날. '초과 등락이 작다' = 초과 등락 기준(2σ) 미달이면서 |초과 등락| < |지수 등락|
   (지수가 움직임의 절반 넘게를 설명). 큰 급등 직후 2σ가 부풀어 개별 급등(예: 초과 +11.8%, 거래량 24배)이
   시장 움직임으로 잘못 빠지는 것을 막는다.

v4 (리포트 구성 지침 v1.1 5.6)
 - 자기주식 취득·처분 결정, 자기주식 신탁계약 체결·해지 공시는 중요도를 "보통"으로 내린다
   (주요사항보고서여도 강함으로 보지 않는다. 대형주에서 반복되는 일상 공시이기 때문).
   따라서 이 공시는 '강한 공시' 판정·공시 기반 사건의 근거가 되지 않는다.

캐시: data/cache/events/{코드}_{기준일}.json  (기준일 = 일봉 마지막 거래일)
      지침 v1.4 5.0: 일봉·지수 일봉은 data.session_cutoff() 뒤를 잘라 쓰고(15:40 이전 실행 = 직전 거래일까지),
      기준일 15:40 전에 저장된 캐시 파일은 장중 일봉으로 만들어졌을 수 있어 다시 만든다.
"""

import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import pandas as pd
import requests

import data as dl
import dart_guard
import keys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS_CACHE_DIR = os.path.join(BASE_DIR, "data", "cache", "events")
NAME_EXCLUDE_CSV = os.path.join(BASE_DIR, "data", "name_exclude.csv")
EVENTS_VERSION = "v4"
REQUEST_TIMEOUT = 15

DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
GOOGLE_NEWS_URL = "https://news.google.com/rss/search"
GOOGLE_PAUSE = 0.5          # 구글 RSS 연속 호출 간격(초)
KST = timedelta(hours=9)

# DART 공시 유형(pblntf_ty) -> 분류 이름
DISCLOSURE_TYPES = {"A": "정기공시", "B": "주요사항", "D": "지분공시", "I": "거래소공시"}
# 단순 반복 공시로 보고 빼는 제목 머리표
SKIP_PREFIXES = ("[기재정정]", "[첨부정정]", "[첨부추가]", "[변경등록]", "[연장결정]", "[발행조건확정]")

# 5. 공시 중요도 (공백을 지운 제목에 이 말이 있으면). 주요사항보고서(유형 B)는 전부 강함.
STRONG_KEYWORDS = ("잠정", "영업실적", "매출액또는손익구조", "유상증자", "전환사채", "신주인수권부사채",
                   "공급계약", "타법인주식", "합병", "분할", "최대주주변경")
WEAK_KEYWORDS = ("기업설명회", "IR", "주주총회소집", "감사보고서제출", "의결권대리행사", "주주명부폐쇄", "기준일",
                 "정보보호", "대량보유상황보고서(약식)", "분기보고서", "반기보고서", "사업보고서")
# v4. 자기주식 일상 공시: 공백을 지운 제목에 '자기주식'과 함께 이 말이 있으면 '보통'(주요사항이어도)
TREASURY_WORDS = ("취득", "처분", "신탁")
# 6. 사후 조치 (급변의 결과로 나오는 공시·뉴스)
POST_KEYWORDS = ("투자주의", "투자경고", "투자위험", "단기과열", "조회공시")
# v3-3. 순수 시세 보도(뉴스, 공백을 지운 제목 기준). [특징주]가 있으면 적용하지 않는다.
PRICE_ONLY_PATTERNS = (r"가격제한폭", r"장중[\d.,]+%대?(상승|하락)", r"상한가기록", r"하한가기록")
FEATURE_TAG = "[특징주]"

# v3-2(a). 종목명 바로 뒤에 붙어도 되는 조사·접미어(이 말 전체가 한글 덩어리일 때만 인정)
PARTICLES = frozenset((
    "은", "는", "이", "가", "을", "를", "의", "와", "과", "도", "만", "에", "로", "으로", "엔", "랑", "이랑",
    "에서", "에게", "에도", "에선", "에는", "에서도", "에서는", "으로는", "로는", "으로서", "로서", "와의", "과의",
    "보다", "까지", "부터", "처럼", "이나", "나", "만의", "만큼", "마저", "조차",
    "이다", "이며", "이자", "이고", "이라", "이란", "였다", "이었다", "였던",
    "측", "측은", "측이", "측의", "측도", "측에", "발", "주", "주가", "주가는", "주가가", "주식", "주주", "株",
))

NEWS_MAX = 300              # 네이버 뉴스 최대 수집 건수(100건씩 3번)
LOOKBACK_DAYS = 365         # 공시·뉴스·급변일 모두 기준일 전 1년
PRICE_EXTRA_DAYS = 120      # 급변 기준(20일·60일 창)을 위한 앞쪽 여유 달력일
VOL_WINDOW = 20             # 초과 등락률 표준편차 창(거래일)
VOL_MULT = 2.0              # 초과 등락 기준 배수
DISC_MULT = 1.0             # 공시 기반 사건: 초과 등락 기준 배수
DISC_RANGE = 2              # 공시 기반 사건: 강한 공시일 ±2거래일
VOLUME_WINDOW = 60          # 거래량 평균 창(거래일)
VOLUME_MULT = 3.0           # 거래량 기준 배수
MARKET_MOVE_PCT = 2.0       # 시장 전체 움직임: 지수 등락률 절댓값 기준(%)
GROUP_GAP = 3               # 급변일 사이가 3거래일 이내면 한 사건
WINDOW_BEFORE = 2           # 매칭 창: 시작일 -2거래일
WINDOW_AFTER = 1            #          종료일 +1거래일
INDEX_CODES = {"KOSPI": ("KS11", "코스피"), "KOSDAQ": ("KQ11", "코스닥")}

NO_EVENT = "확인된 이벤트 없음"
NEWS_OK, NEWS_OUT, NEWS_NONE = "수집됨", "수집 범위 밖", "검색 결과 없음"
KIND_SPIKE, KIND_DISC = "급변", "공시 기반 사건"


# ---------------------------------------------------------------------------
# 키
# ---------------------------------------------------------------------------

def naver_keys():
    """(client_id, client_secret). 둘 중 하나라도 없으면 None."""
    cid, secret = keys.get_key("NAVER_CLIENT_ID"), keys.get_key("NAVER_CLIENT_SECRET")
    return (cid, secret) if cid and secret else None


def has_naver_key():
    """네이버 검색 키 준비 여부만 알려준다(값은 출력하지 않는다)."""
    return naver_keys() is not None


# ---------------------------------------------------------------------------
# 분류 도우미
# ---------------------------------------------------------------------------

def _compact(text):
    return re.sub(r"\s+", "", text or "")


def is_post_action(title):
    """급변의 결과로 나오는 공시·뉴스(투자주의 지정, 단기과열, 조회공시 등)인가."""
    t = _compact(title)
    return any(k in t for k in POST_KEYWORDS)


def is_post_news(title):
    """뉴스용 사후 판정: 사후 조치 + 순수 시세 보도([특징주]는 원인 후보로 둔다)."""
    if is_post_action(title):
        return True
    t = _compact(title)
    if FEATURE_TAG in t:
        return False
    return any(re.search(p, t) for p in PRICE_ONLY_PATTERNS)


def is_treasury_stock(title):
    """자기주식 취득·처분 결정, 자기주식 신탁계약 체결·해지 공시인가(지침 v1.1 5.6)."""
    t = _compact(title)
    return "자기주식" in t and any(w in t for w in TREASURY_WORDS)


def disclosure_weight(title, category):
    """공시 중요도: '사후' / '강함' / '약함' / '보통'."""
    t = _compact(title)
    if is_post_action(t):
        return "사후"
    if is_treasury_stock(t):
        return "보통"
    if category == "주요사항" or any(k in t for k in STRONG_KEYWORDS):
        return "강함"
    if any(k in t for k in WEAK_KEYWORDS):
        return "약함"
    return "보통"


def similar_names(name):
    """stock_master.csv에서 현재 종목명으로 시작하는 다른 상장 종목명(긴 이름 먼저)."""
    try:
        names = dl.load_ticker_list()["종목명"].astype(str).tolist()
    except Exception:
        return []
    return sorted({n for n in names if n != name and n.startswith(name)}, key=len, reverse=True)


def load_name_excludes(code):
    """data/name_exclude.csv(종목코드, 제외어)에서 이 종목의 제외어 목록."""
    try:
        df = pd.read_csv(NAME_EXCLUDE_CSV, dtype={"종목코드": str}, encoding="utf-8-sig")
    except Exception:
        return []
    df["종목코드"] = df["종목코드"].str.strip().str.zfill(6)
    words = df.loc[df["종목코드"] == str(code).zfill(6), "제외어"].dropna().astype(str).str.strip()
    return [w for w in words if w]


def _strip_source(title):
    """구글 제목 끝의 ' - 언론사'를 뗀다."""
    return re.sub(r"\s+-\s+[^-]+$", "", title)


def _standalone(title, name):
    """제목 안 종목명 중 하나라도 뒤에 다른 한글·영문이 붙지 않은(조사는 허용) 언급이 있는가."""
    for m in re.finditer(re.escape(name), title):
        rest = title[m.end():]
        if re.match(r"[A-Za-z]", rest):
            continue                                   # OCIDream
        run = re.match(r"[가-힣]+", rest)
        if run is None or run.group() in PARTICLES:
            return True
    return False


def title_filter(title, name, others, excludes=()):
    """제목 판정: None(통과) / '제목불일치' / '동명제외' / '제외어'."""
    if name not in title:
        return "제목불일치"
    low = title.casefold()                             # 제외어는 언론사(oracle.com 등)까지 본다
    if any(w.casefold() in low for w in excludes):
        return "제외어"
    t = _strip_source(title)
    for other in others:
        t = t.replace(other, " ")
    return None if _standalone(t, name) else "동명제외"


def _story_key(title):
    """같은 기사 판별용: 구글 제목 끝의 ' - 언론사'를 떼고 공백을 지운다."""
    return _compact(_strip_source(title))


# ---------------------------------------------------------------------------
# DART 공시목록
# ---------------------------------------------------------------------------

def _skip_disclosure(item):
    """단순 반복 공시(정정·첨부 등)와 철회 공시는 뺀다."""
    title = item.get("report_nm", "").strip()
    if title.startswith(SKIP_PREFIXES):
        return True
    return "철" in (item.get("rm") or "")


def fetch_disclosures(code, start, end):
    """기간 안의 공시(4개 유형)를 받아 분류·중요도를 붙여 돌려준다.

    반환: {"목록": [{"날짜", "분류", "중요도", "제목", "접수번호", "제출인"}], "제외": 건수, "오류": 문자열|None}
    """
    import financials
    import fin_store
    if fin_store.is_store_mode():           # 저장본 모드(클라우드): DART 공시를 부르지 않는다
        return {"목록": [], "제외": 0, "오류": "저장본 모드: DART 공시 미조회"}
    api_key = keys.get_dart_api_key()
    corp = financials._corp_code(code)
    if not api_key or not corp:
        return {"목록": [], "제외": 0, "오류": "DART 키 또는 고유번호 없음"}
    items, skipped, error = [], 0, None
    seen = set()
    for kind, label in DISCLOSURE_TYPES.items():
        page = 1
        while True:
            params = {"crtfc_key": api_key, "corp_code": corp, "bgn_de": start.strftime("%Y%m%d"),
                      "end_de": end.strftime("%Y%m%d"), "pblntf_ty": kind, "page_no": page, "page_count": 100}
            try:
                body = dart_guard.get(DART_LIST_URL, params=params).json()     # 차단기 경유(연결 3초·읽기 15초)
            except Exception as exc:
                error = f"{label}: {type(exc).__name__}"
                break
            if body.get("status") == "013":          # 조회된 데이터 없음
                break
            if body.get("status") != "000":
                error = f"{label}: {body.get('status')} {body.get('message')}"
                break
            for item in body.get("list", []):
                if _skip_disclosure(item):
                    skipped += 1
                    continue
                key = (item["rcept_dt"], label, item["report_nm"].strip())
                if key in seen:                        # 같은 날 같은 제목 중복
                    skipped += 1
                    continue
                seen.add(key)
                title = re.sub(r"\s+", " ", item["report_nm"]).strip()
                items.append({
                    "날짜": f"{item['rcept_dt'][:4]}-{item['rcept_dt'][4:6]}-{item['rcept_dt'][6:]}",
                    "분류": label,
                    "중요도": disclosure_weight(title, label),
                    "제목": title,
                    "접수번호": item["rcept_no"],
                    "제출인": item.get("flr_nm", ""),
                })
            if page >= int(body.get("total_page", 1)):
                break
            page += 1
    items.sort(key=lambda x: (x["날짜"], x["분류"], x["제목"]))
    return {"목록": items, "제외": skipped, "오류": error}


# ---------------------------------------------------------------------------
# 뉴스: 네이버(최신순 300건) + 구글 RSS(사건 창별)
# ---------------------------------------------------------------------------

def _clean_title(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def fetch_news(name, start, end, others=(), excludes=()):
    """네이버 뉴스 검색(최신순, 최대 300건) -> 기간 안 + 제목에 종목명이 단독으로 있는 기사만.

    반환: {"목록": [{"날짜", "제목", "링크", "출처", "사후"}], "받은건수", "기간밖", "제목불일치", "동명제외",
           "제외어", "가장오래된날짜", "오류"}
    """
    pair = naver_keys()
    out = {"목록": [], "받은건수": 0, "기간밖": 0, "제목불일치": 0, "동명제외": 0, "제외어": 0,
           "가장오래된날짜": None, "오류": None}
    if not pair:
        out["오류"] = "네이버 검색 키 없음"
        return out
    headers = {"X-Naver-Client-Id": pair[0], "X-Naver-Client-Secret": pair[1]}
    seen = set()
    for start_no in range(1, NEWS_MAX + 1, 100):
        params = {"query": name, "display": 100, "start": start_no, "sort": "date"}
        try:
            res = requests.get(NAVER_NEWS_URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
            body = res.json()
        except Exception as exc:
            out["오류"] = type(exc).__name__
            break
        if res.status_code != 200:
            out["오류"] = f"{res.status_code} {body.get('errorMessage', '')}"
            break
        batch = body.get("items", [])
        for item in batch:
            out["받은건수"] += 1
            try:
                day = parsedate_to_datetime(item["pubDate"]).date()
            except Exception:
                continue
            if out["가장오래된날짜"] is None or day.isoformat() < out["가장오래된날짜"]:
                out["가장오래된날짜"] = day.isoformat()
            if not (start.date() <= day <= end.date()):
                out["기간밖"] += 1
                continue
            title = _clean_title(item.get("title"))
            reason = title_filter(title, name, others, excludes)
            if reason:
                out[reason] += 1
                continue
            link = item.get("originallink") or item.get("link")
            if link in seen:
                continue
            seen.add(link)
            out["목록"].append({"날짜": day.isoformat(), "제목": title, "링크": link,
                               "출처": "네이버", "사후": is_post_news(title)})
        if len(batch) < 100:
            break
    out["목록"].sort(key=lambda x: (x["날짜"], x["제목"]))
    return out


def fetch_google_news(name, after, before, others=(), excludes=()):
    """구글 뉴스 RSS 검색 1회: q="종목명" after:… before:…. 제목에 종목명이 단독으로 있는 기사만.

    반환: {"목록": [...], "받은건수", "제목불일치", "동명제외", "제외어", "오류"}
    """
    out = {"목록": [], "받은건수": 0, "제목불일치": 0, "동명제외": 0, "제외어": 0, "오류": None}
    query = f'"{name}" after:{after.strftime("%Y-%m-%d")} before:{before.strftime("%Y-%m-%d")}'
    params = {"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    try:
        res = requests.get(GOOGLE_NEWS_URL, params=params, timeout=REQUEST_TIMEOUT,
                           headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code != 200:
            out["오류"] = f"HTTP {res.status_code}"
            return out
        items = ET.fromstring(res.content).findall("./channel/item")
    except Exception as exc:
        out["오류"] = type(exc).__name__
        return out
    for item in items:
        out["받은건수"] += 1
        title = _clean_title(item.findtext("title"))
        try:
            day = (parsedate_to_datetime(item.findtext("pubDate")) + KST).date()   # GMT -> 한국 날짜
        except Exception:
            continue
        reason = title_filter(title, name, others, excludes)
        if reason:
            out[reason] += 1
            continue
        out["목록"].append({"날짜": day.isoformat(), "제목": title, "링크": item.findtext("link"),
                           "출처": "구글", "사후": is_post_news(title)})
    return out


# ---------------------------------------------------------------------------
# 지수와 급변일
# ---------------------------------------------------------------------------

def stock_market(code):
    """stock_master.csv의 시장(KOSPI/KOSDAQ). 없으면 KOSPI로 본다."""
    try:
        df = dl.load_ticker_list()
        row = df[df["종목코드"] == str(code).zfill(6)]
        if not row.empty and row.iloc[0]["시장"] in INDEX_CODES:
            return row.iloc[0]["시장"]
    except Exception:
        pass
    return "KOSPI"


def fetch_index_returns(market, start, end):
    """소속 시장 지수 일간 등락률(%) Series. 실패하면 None."""
    import FinanceDataReader as fdr
    try:
        df = fdr.DataReader(INDEX_CODES[market][0], start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        close = df["Close"].astype(float)
        close.index = pd.to_datetime(close.index)
        close = dl.trim_to_session(close)          # 지침 v1.4 5.0: 당일 장중 지수 일봉 제외
        return close.pct_change() * 100
    except Exception:
        return None


def excess_stats(df, index_ret):
    """일간 등락률·지수 등락률·초과 등락률과 직전 창 기준값."""
    ret = df["종가"].pct_change() * 100
    mkt = index_ret.reindex(df.index).fillna(0.0) if index_ret is not None else pd.Series(0.0, index=df.index)
    excess = ret - mkt
    return {
        "ret": ret, "mkt": mkt, "excess": excess,
        "sigma_x": excess.shift(1).rolling(VOL_WINDOW).std(),          # 직전 20거래일 초과 등락
        "sigma_r": ret.shift(1).rolling(VOL_WINDOW).std(),             # 직전 20거래일 종목 등락(시장 움직임 판별용)
        "vol_avg": df["거래량"].shift(1).rolling(VOLUME_WINDOW).mean(),  # 직전 60거래일
    }


def _day_row(df, st, i):
    vol_avg = st["vol_avg"].iloc[i]
    vol_x = df["거래량"].iloc[i] / vol_avg if vol_avg > 0 else 0
    return {"날짜": df.index[i].strftime("%Y-%m-%d"), "등락률": round(float(st["ret"].iloc[i]), 2),
            "지수등락률": round(float(st["mkt"].iloc[i]), 2), "초과등락률": round(float(st["excess"].iloc[i]), 2),
            "거래량배수": round(float(vol_x), 2)}


def find_spikes(df, st, start):
    """급변일과 시장 전체 움직임 날을 나눠 돌려준다.

    반환: (spikes, market_days)
      spikes      = [{"날짜", "등락률", "지수등락률", "초과등락률", "초과기준", "거래량배수", "조건", "위치"}]
      market_days = [{"날짜", "등락률", "지수등락률", "초과등락률", "거래량배수"}]
    """
    ret, mkt, excess = st["ret"], st["mkt"], st["excess"]
    sigma_x, sigma_r, vol_avg = st["sigma_x"], st["sigma_r"], st["vol_avg"]
    spikes, market_days = [], []
    for i, day in enumerate(df.index):
        if day < pd.Timestamp(start) or pd.isna(ret.iloc[i]) or pd.isna(sigma_x.iloc[i]) or pd.isna(vol_avg.iloc[i]):
            continue
        x_flag = abs(excess.iloc[i]) >= VOL_MULT * sigma_x.iloc[i]
        row = _day_row(df, st, i)
        v_flag = row["거래량배수"] >= VOLUME_MULT
        r_flag = abs(ret.iloc[i]) >= VOL_MULT * sigma_r.iloc[i]
        if not (x_flag or v_flag or r_flag):
            continue
        small_excess = not x_flag and abs(excess.iloc[i]) < abs(mkt.iloc[i])
        if small_excess and abs(mkt.iloc[i]) >= MARKET_MOVE_PCT:
            market_days.append(row)                    # 초과 등락은 작고 지수가 ±2% 이상
            continue
        if not (x_flag or v_flag):
            continue                                   # 종목 등락만 컸고 초과 등락·거래량은 기준 미달
        row.update({"초과기준": round(float(VOL_MULT * sigma_x.iloc[i]), 2),
                    "조건": (["초과등락"] if x_flag else []) + (["거래량"] if v_flag else []),
                    "위치": i})
        spikes.append(row)
    return spikes, market_days


def _make_event(g, close, idx_close, kind, basis=None):
    a, b = g[0]["위치"], g[-1]["위치"]
    base = max(a - 1, 0)
    cum = (close.iloc[b] / close.iloc[base] - 1) * 100
    cum_idx = (idx_close.iloc[b] / idx_close.iloc[base] - 1) * 100 if idx_close is not None else 0.0
    ev = {
        "유형": kind,
        "시작일": g[0]["날짜"], "종료일": g[-1]["날짜"], "급변일수": len(g),
        "누적등락률": round(float(cum), 2), "누적지수등락률": round(float(cum_idx), 2),
        "누적초과등락률": round(float(cum - cum_idx), 2),
        "최대거래량배수": max(x["거래량배수"] for x in g),
        "급변일": [{k: v for k, v in x.items() if k != "위치"} for x in g],
        "위치": (a, b),
    }
    if basis:
        ev["근거공시"] = basis
    return ev


def _index_close(df, index_ret):
    if index_ret is None:
        return None
    return (1 + index_ret.reindex(df.index).fillna(0.0) / 100).cumprod()


def group_spikes(spikes, df, index_ret):
    """3거래일 이내로 이어진 급변일을 한 사건으로 묶는다."""
    groups = []
    for s in spikes:
        if groups and s["위치"] - groups[-1][-1]["위치"] <= GROUP_GAP:
            groups[-1].append(s)
        else:
            groups.append([s])
    idx_close = _index_close(df, index_ret)
    return [_make_event(g, df["종가"], idx_close, KIND_SPIKE) for g in groups]


def disclosure_events(events, disclosures, df, st, index_ret, start, market_days):
    """강한 공시일 ±2거래일 안에 |초과 등락| >= 1σ인 날이 있으면 '공시 기반 사건'을 만든다.

    이미 급변 사건의 매칭 창 안에 있는 공시, 시장 전체 움직임 날, 급변 사건에 들어간 날은 쓰지 않는다.
    """
    dates = list(df.index)
    windows = [_window(dates, *ev["위치"]) for ev in events]
    used = {i for ev in events for i in range(ev["위치"][0], ev["위치"][1] + 1)}
    market = {m["날짜"] for m in market_days}
    excess, sigma_x = st["excess"], st["sigma_x"]
    groups = []                                        # [[행...], [근거 공시...]]
    for d in disclosures:
        if d["중요도"] != "강함" or any(lo <= d["날짜"] <= hi for lo, hi in windows):
            continue
        i_d = int(df.index.searchsorted(pd.Timestamp(d["날짜"])))   # 공시일 또는 다음 거래일
        if i_d >= len(dates):
            continue
        rows = []
        for i in range(max(0, i_d - DISC_RANGE), min(len(dates) - 1, i_d + DISC_RANGE) + 1):
            if (i in used or dates[i] < pd.Timestamp(start) or pd.isna(sigma_x.iloc[i])
                    or pd.isna(excess.iloc[i]) or dates[i].strftime("%Y-%m-%d") in market):
                continue
            if abs(excess.iloc[i]) >= DISC_MULT * sigma_x.iloc[i]:
                row = _day_row(df, st, i)
                row.update({"초과기준": round(float(DISC_MULT * sigma_x.iloc[i]), 2), "조건": ["공시+1σ"], "위치": i})
                rows.append(row)
        if not rows:
            continue
        basis = {"날짜": d["날짜"], "제목": d["제목"]}
        if groups and rows[0]["위치"] - groups[-1][0][-1]["위치"] <= GROUP_GAP:
            merged = {r["위치"]: r for r in groups[-1][0] + rows}
            groups[-1][0] = [merged[k] for k in sorted(merged)]
            groups[-1][1].append(basis)
        else:
            groups.append([rows, [basis]])
    idx_close = _index_close(df, index_ret)
    return [_make_event(rows, df["종가"], idx_close, KIND_DISC, basis) for rows, basis in groups]


def _window(dates, a, b):
    """매칭 창: 시작일 -2거래일 ~ 종료일 +1거래일. 기준일 너머는 달력으로 연장(거래일 1일 = 2일)."""
    last = len(dates) - 1
    lo = dates[max(0, a - WINDOW_BEFORE)]
    hi_idx = b + WINDOW_AFTER
    hi = dates[hi_idx] if hi_idx <= last else dates[last] + timedelta(days=(hi_idx - last) * 2)
    return lo.strftime("%Y-%m-%d"), hi.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# 대표 이벤트
# ---------------------------------------------------------------------------

_TAIL_PARTICLES = "은는이가을를의와과도에로"


def _keywords(title, name, others):
    """기사 제목의 키워드(2글자 이상, 종목명·언론사·머리표 제외, 끝 조사 1글자 제거)."""
    t = re.sub(r"\[[^\]]*\]", " ", _strip_source(title))
    for other in others:
        t = t.replace(other, " ")
    t = t.replace(name, " ")
    words = set()
    for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", t):
        if len(w) > 2 and w[-1] in _TAIL_PARTICLES:
            w = w[:-1]
        words.add(w)
    return words


def keyword_scores(news, name, others):
    """기사마다 키워드 점수(창 안 다른 기사와 겹치는 키워드 수의 합). 반환: [(점수, 기사)]"""
    kws = [_keywords(n["제목"], name, others) for n in news]
    df_count = Counter(w for k in kws for w in k)
    return [(sum(df_count[w] - 1 for w in k), n) for k, n in zip(kws, news)]


def article_score(ev, title, name, others):
    """사건 창 안 원인 후보 기사(사후 제외) 기준으로 제목 title의 키워드 점수를 다시 계산한다.

    [특징주] 기사로 뽑혀 점수가 기록되지 않은 대표 기사의 점수가 필요할 때 쓴다(리포트 구성 지침 v1.2 방향 확인).
    """
    cand = [n for n in ev.get("뉴스") or [] if not n.get("사후")]
    return next((score for score, n in keyword_scores(cand, name, others) if n["제목"] == title), 0)


def pick_cause_article(news, name, others, start_date):
    """원인 설명 기사 1건: [특징주] 우선, 그 안에서(없으면 전체에서) 다른 기사와 겹치는 키워드가 가장 많은 기사.

    [특징주]라도 동명 회사 이름(OCI홀딩스)이 제목에 있으면 우선하지 않는다. 점수가 같으면 사건 시작일에 가까운 기사.
    """
    if not news:
        return None
    scored = keyword_scores(news, name, others)
    featured = [x for x in scored if FEATURE_TAG in _compact(x[1]["제목"])
                and not any(o in x[1]["제목"] for o in others)]
    pool = featured or scored
    t0 = datetime.strptime(start_date, "%Y-%m-%d")
    best = min(pool, key=lambda x: (-x[0], abs((datetime.strptime(x[1]["날짜"], "%Y-%m-%d") - t0).days),
                                    x[1]["날짜"]))
    return best[1], best[0], bool(featured)


def pick_strong(strong, start_date):
    """강한 공시 1건: 사건 시작일에 가장 가까운 것(같으면 이른 날짜, 주요사항 먼저)."""
    t0 = datetime.strptime(start_date, "%Y-%m-%d")
    return min(strong, key=lambda d: (abs((datetime.strptime(d["날짜"], "%Y-%m-%d") - t0).days),
                                      d["날짜"], d["분류"] != "주요사항"))


# ---------------------------------------------------------------------------
# 매칭
# ---------------------------------------------------------------------------

def match_events(events, dates, disclosures, naver, name, others, excludes, naver_oldest, use_google=True):
    """사건마다 창 안의 공시·뉴스를 붙이고 대표 이벤트·판정·뉴스 수집 여부를 정한다."""
    timeline = []
    for ev in events:
        a, b = ev.pop("위치")
        lo, hi = _window(dates, a, b)
        for basis in ev.get("근거공시", []):             # 공시 기반 사건: 근거 공시일까지 창을 넓힌다
            lo, hi = min(lo, basis["날짜"]), max(hi, basis["날짜"])
        # 뉴스: 네이버(창 안) + 구글(매칭 창과 같은 기간 검색, 경계일 포함되게 앞뒤 1일)
        google = None
        if use_google:
            after = datetime.strptime(lo, "%Y-%m-%d") - timedelta(days=1)
            before = datetime.strptime(hi, "%Y-%m-%d") + timedelta(days=1)
            google = fetch_google_news(name, after, before, others, excludes)
            time.sleep(GOOGLE_PAUSE)
        news, seen = [], set()
        for n in naver + ((google or {}).get("목록") or []):
            if lo <= n["날짜"] <= hi and _story_key(n["제목"]) not in seen:
                seen.add(_story_key(n["제목"]))
                news.append(n)
        news.sort(key=lambda x: (x["날짜"], x["출처"], x["제목"]))
        google_ok = google is not None and google["오류"] is None
        naver_covers = naver_oldest is not None and naver_oldest <= lo
        if news:
            status = NEWS_OK
        elif google_ok or naver_covers:
            status = NEWS_NONE
        else:
            status = NEWS_OUT

        d_hit = [d for d in disclosures if lo <= d["날짜"] <= hi]
        post = ([{"날짜": d["날짜"], "종류": "공시", "제목": d["제목"]} for d in d_hit if d["중요도"] == "사후"]
                + [{"날짜": n["날짜"], "종류": "뉴스", "제목": n["제목"]} for n in news if n["사후"]])
        strong = [d for d in d_hit if d["중요도"] == "강함"]
        normal = [d for d in d_hit if d["중요도"] == "보통"]
        weak = [d for d in d_hit if d["중요도"] == "약함"]
        cand_news = [n for n in news if not n["사후"]]
        cause = pick_cause_article(cand_news, name, others, ev["시작일"])
        cause_rep = []
        if cause:
            n, score, featured = cause
            cause_rep = [{"종류": "뉴스", "역할": "원인 기사", "선정": "특징주" if featured else f"키워드 {score}",
                          **_brief_news(n)}]
        if strong:
            verdict = "강한 공시"
            rep = [{"종류": "공시", "역할": "강한 공시", **_brief(pick_strong(strong, ev["시작일"]))}] + cause_rep
        elif normal or cand_news:
            verdict = "매칭됨"
            rep = cause_rep + ([{"종류": "공시", "역할": "공시", **_brief(normal[0])}] if normal else [])
        elif weak:
            verdict, rep = "약한 연결", [{"종류": "공시", "역할": "약한 공시", **_brief(d)} for d in weak]
        else:
            verdict, rep = NO_EVENT, []
        timeline.append({
            **ev, "창": [lo, hi],
            "판정": verdict, "대표이벤트": rep,
            "공시": [_brief(d) for d in d_hit],
            "뉴스": [_brief_news(n) for n in news],
            "사후조치": post,
            "뉴스수집": status,
            "구글검색": None if google is None else {
                "기간": [after.strftime("%Y-%m-%d"), before.strftime("%Y-%m-%d")],
                "받은건수": google["받은건수"], "남은건수": len(google["목록"]),
                "동명제외": google["동명제외"], "제외어": google["제외어"], "오류": google["오류"]},
        })
    return timeline


def _brief(d):
    return {"날짜": d["날짜"], "분류": d["분류"], "중요도": d["중요도"], "제목": d["제목"]}


def _brief_news(n):
    return {"날짜": n["날짜"], "출처": n["출처"], "제목": n["제목"], "링크": n["링크"], "사후": n["사후"]}


# ---------------------------------------------------------------------------
# 전체
# ---------------------------------------------------------------------------

def _cache_path(code, base_date):
    return os.path.join(EVENTS_CACHE_DIR, f"{str(code).zfill(6)}_{base_date}.json")


def build_events(code, name, market=None, refresh=False, today=None, use_google=True):
    """종목 하나의 공시·뉴스·급변 사건 타임라인을 만든다(기준일별 파일 캐시). 실패하면 None."""
    code = str(code).zfill(6)
    end = today or dl.now_kst().date()              # 한국시간 날짜(서버 시간대 무관)
    fetch_start = end - timedelta(days=LOOKBACK_DAYS + PRICE_EXTRA_DAYS)
    df = dl.fetch_ohlcv_raw(code, fetch_start, end)
    if df is None or df.empty:
        return None
    base = df.index[-1]
    base_date = base.strftime("%Y-%m-%d")
    path = _cache_path(code, base_date)
    # 지침 v1.4 5.0: 기준일 15:40 전에 만든 캐시는 장중 일봉으로 계산됐을 수 있으므로 쓰지 않는다
    if not refresh and os.path.exists(path) and dl.closed_after(path, base_date):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("버전") == EVENTS_VERSION:
                return cached
        except Exception:
            pass

    market = market if market in INDEX_CODES else stock_market(code)
    index_ret = fetch_index_returns(market, fetch_start, end)
    start = base - timedelta(days=LOOKBACK_DAYS)
    others = similar_names(name)
    excludes = load_name_excludes(code)
    disclosures = fetch_disclosures(code, start, base)
    news = fetch_news(name, start, base, others, excludes)
    st = excess_stats(df, index_ret)
    spikes, market_days = find_spikes(df, st, start)
    events = group_spikes(spikes, df, index_ret)
    events += disclosure_events(events, disclosures["목록"], df, st, index_ret, start, market_days)
    events.sort(key=lambda e: e["시작일"])
    timeline = match_events(events, list(df.index), disclosures["목록"], news["목록"], name, others, excludes,
                            news["가장오래된날짜"], use_google=use_google)

    counts = {label: 0 for label in DISCLOSURE_TYPES.values()}
    weights = {"강함": 0, "보통": 0, "약함": 0, "사후": 0}
    for d in disclosures["목록"]:
        counts[d["분류"]] += 1
        weights[d["중요도"]] += 1
    confirmed = sum(1 for t in timeline if t["판정"] in ("강한 공시", "매칭됨"))
    result = {
        "버전": EVENTS_VERSION,
        "종목코드": code, "종목명": name, "시장": market, "지수": INDEX_CODES[market][1],
        "지수오류": index_ret is None,
        "기준일": base_date,
        "기간": [start.strftime("%Y-%m-%d"), base_date],
        "기준": {"초과등락": f"|종목 등락률 - {INDEX_CODES[market][1]} 등락률| >= 직전 {VOL_WINDOW}거래일 표준편차 x {VOL_MULT:g}",
                 "거래량": f"거래량 >= 직전 {VOLUME_WINDOW}거래일 평균 x {VOLUME_MULT:g}",
                 "시장전체": f"초과 등락 기준 미달 + |초과 등락| < |지수 등락| + |지수 등락률| >= {MARKET_MOVE_PCT:g}%",
                 "공시기반": f"강한 공시일 ±{DISC_RANGE}거래일 안 |초과 등락| >= 직전 {VOL_WINDOW}거래일 표준편차 x {DISC_MULT:g}",
                 "묶기": f"급변일 사이 {GROUP_GAP}거래일 이내",
                 "매칭창": f"시작일 -{WINDOW_BEFORE}거래일 ~ 종료일 +{WINDOW_AFTER}거래일",
                 "구글검색": "매칭 창 앞뒤 1일(달력일)"},
        "동명회사": others,
        "제외어": excludes,
        "공시": {"분류별": counts, "중요도별": weights, "합계": len(disclosures["목록"]),
                 "제외": disclosures["제외"], "오류": disclosures["오류"], "목록": disclosures["목록"]},
        "뉴스": {"건수": len(news["목록"]), "받은건수": news["받은건수"], "기간밖": news["기간밖"],
                 "제목불일치": news["제목불일치"], "동명제외": news["동명제외"], "제외어": news["제외어"],
                 "가장오래된날짜": news["가장오래된날짜"], "오류": news["오류"], "목록": news["목록"]},
        "시장전체움직임": market_days,
        "사건": timeline,
        "요약": {"급변일수": len(spikes), "사건수": len(timeline), "시장전체움직임일수": len(market_days),
                 "공시기반사건": sum(1 for t in timeline if t["유형"] == KIND_DISC),
                 "강한공시": sum(1 for t in timeline if t["판정"] == "강한 공시"),
                 "매칭됨": sum(1 for t in timeline if t["판정"] == "매칭됨"),
                 "약한연결": sum(1 for t in timeline if t["판정"] == "약한 연결"),
                 "이벤트없음": sum(1 for t in timeline if t["판정"] == NO_EVENT),
                 "원인확인": confirmed,
                 "원인확인비율": round(confirmed / len(timeline) * 100, 1) if timeline else None,
                 "뉴스수집": {s: sum(1 for t in timeline if t["뉴스수집"] == s) for s in (NEWS_OK, NEWS_NONE, NEWS_OUT)}},
    }
    if not dart_guard.available():      # DART 불가 상태에서 만든 결과(공시 누락)는 캐시에 남기지 않는다
        return result
    import fin_store
    if fin_store.is_store_mode():       # 저장본 모드 결과(공시 미조회)도 캐시에 남기지 않는다(PC 캐시와 섞이지 않게)
        return result
    try:
        os.makedirs(EVENTS_CACHE_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
    except Exception:
        pass
    return result
