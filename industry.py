# -*- coding: utf-8 -*-
"""
industry.py - 업종 매핑 생성/조회

동작 방식
 1) DART 기업개황 API로 종목별 KSIC 업종코드(induty_code)를 받아
 2) KSIC 앞 2자리를 사람이 읽기 쉬운 업종그룹으로 묶어
 3) data/industry_map.csv 에 저장한다.

앱은 평소 CSV만 읽고, 사이드바의 "업종 정보 갱신" 버튼을 눌렀을 때만 DART를 다시 호출한다.
저장본 모드(FIN_MODE=store, 클라우드)에서는 DART 를 전혀 부르지 않는다: corp_code 는 corp_code_map.csv 만,
업종은 industry_map.csv 만 본다(없으면 '기타', 저장하지 않음).
"""

import io
import os
import time
import pickle
import zipfile
import xml.etree.ElementTree as ET

import pandas as pd
import requests

import dart_guard
import fin_store
import keys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
INDUSTRY_CSV = os.path.join(DATA_DIR, "industry_map.csv")
INDUSTRY_SAMPLE_CSV = os.path.join(DATA_DIR, "industry_map_sample.csv")
CORPCODE_PKL = os.path.join(CACHE_DIR, "corpcode.pkl")
# 저장소에 함께 올리는 상장사 고유번호 표(stock_code, corp_code, corp_name). corpCode.xml 다운로드 없이 먼저 찾는다.
CORP_CODE_CSV = os.path.join(DATA_DIR, "corp_code_map.csv")

CORPCODE_TTL_DAYS = 30          # corpCode.xml 캐시 유효기간
DART_SLEEP = 0.2                # 초당 5건 이하 (0.2초 간격)
ETC = "기타"

# ---------------------------------------------------------------------------
# KSIC(한국표준산업분류) 중분류 2자리 -> 업종그룹 (비슷한 분류끼리 묶어 20개 내외)
# ---------------------------------------------------------------------------
KSIC_GROUPS = {
    "01": "농림어업", "02": "농림어업", "03": "농림어업",
    "05": "광업/에너지", "06": "광업/에너지", "07": "광업/에너지", "08": "광업/에너지",
    "10": "음식료/담배", "11": "음식료/담배", "12": "음식료/담배",
    "13": "섬유/의복", "14": "섬유/의복", "15": "섬유/의복",
    "16": "목재/종이/인쇄", "17": "목재/종이/인쇄", "18": "목재/종이/인쇄",
    "19": "화학/정유", "20": "화학/정유", "22": "화학/정유",
    "21": "제약바이오",
    "23": "철강/비금속", "24": "철강/비금속", "25": "철강/비금속",
    "26": "전기전자",
    "27": "의료정밀/광학",
    "28": "전기장비",
    "29": "기계/장비",
    "30": "자동차/부품",
    "31": "조선/운송장비",
    "32": "기타제조", "33": "기타제조",
    "35": "전기가스/환경", "36": "전기가스/환경", "37": "전기가스/환경",
    "38": "전기가스/환경", "39": "전기가스/환경",
    "41": "건설", "42": "건설",
    "45": "유통/도소매", "46": "유통/도소매", "47": "유통/도소매",
    "49": "운송/물류", "50": "운송/물류", "51": "운송/물류", "52": "운송/물류",
    "55": "기타서비스", "56": "기타서비스",
    "58": "소프트웨어/IT서비스", "62": "소프트웨어/IT서비스", "63": "소프트웨어/IT서비스",
    "59": "미디어/엔터", "90": "미디어/엔터", "91": "미디어/엔터",
    "60": "통신/방송", "61": "통신/방송",
    "64": "금융", "65": "금융", "66": "금융",
    "68": "부동산",
    "70": "연구개발/전문서비스", "71": "연구개발/전문서비스",
    "72": "연구개발/전문서비스", "73": "연구개발/전문서비스",
    "74": "기타서비스", "75": "기타서비스",
    "85": "교육", "86": "의료/헬스케어", "87": "의료/헬스케어",
}


def _ensure_dirs():
    """data/ 와 data/cache/ 폴더를 만들어 둔다."""
    os.makedirs(CACHE_DIR, exist_ok=True)


def ksic_to_group(induty_code):
    """KSIC 코드(3~5자리)의 앞 2자리를 업종그룹 이름으로 바꾼다. 못 찾으면 '기타'."""
    if not induty_code:
        return ETC
    code2 = str(induty_code).strip()[:2]
    return KSIC_GROUPS.get(code2, ETC)


# ---------------------------------------------------------------------------
# 1) 종목코드 -> DART corp_code 매핑 (corpCode.xml, 30일 캐시)
# ---------------------------------------------------------------------------

def _sub_tag():
    """[계측] data.sub_tag() (스레드·실행 id)."""
    import data
    return data.sub_tag()


_corp_csv_map = None                     # corp_code_map.csv 내용(프로세스에서 한 번 읽는다)


def _load_corp_csv():
    """data/corp_code_map.csv -> {stock_code: corp_code}. 파일이 없거나 읽지 못하면 빈 dict."""
    global _corp_csv_map
    if _corp_csv_map is None:
        _ts = time.perf_counter()                                                # [계측]
        try:
            df = pd.read_csv(CORP_CODE_CSV, dtype=str, encoding="utf-8-sig")
            _corp_csv_map = dict(zip(df["stock_code"].str.zfill(6), df["corp_code"].str.zfill(8)))
        except Exception:
            _corp_csv_map = {}
        print(f"[SUB] 캐시읽기 corp_code_map.csv ({len(_corp_csv_map)}사) {time.perf_counter() - _ts:.2f}s "
              f"{_sub_tag()}", flush=True)                                       # [계측]
    return _corp_csv_map


def corp_code_for(code):
    """종목코드 -> DART corp_code. corp_code_map.csv 를 먼저 보고, 표에 없는 종목일 때만
    기존 경로(load_corp_code_map: corpcode.pkl 30일 캐시, 없으면 corpCode.xml 다운로드)를 쓴다. 없으면 None."""
    code = str(code).zfill(6)
    hit = _load_corp_csv().get(code)
    if hit:
        return hit
    if fin_store.is_store_mode():           # 저장본 모드: corp_code_map.csv 만 본다
        return None
    return load_corp_code_map().get(code)


def load_corp_code_map(force=False):
    """DART corpCode.xml(zip)을 받아 {종목코드: corp_code} 딕셔너리를 만든다(30일 캐시)."""
    if fin_store.is_store_mode():           # 저장본 모드: corpCode.xml 을 받지 않는다(corp_code_map.csv 만)
        return {}
    _ensure_dirs()

    # 캐시가 30일 이내면 그대로 사용
    if not force and os.path.exists(CORPCODE_PKL):
        age_days = (time.time() - os.path.getmtime(CORPCODE_PKL)) / 86400
        if age_days < CORPCODE_TTL_DAYS:
            _ts = time.perf_counter()                                            # [계측]
            try:
                with open(CORPCODE_PKL, "rb") as f:
                    return pickle.load(f)
            except Exception:
                pass
            finally:                                                             # [계측]
                print(f"[SUB] 캐시읽기 corpcode.pkl {time.perf_counter() - _ts:.2f}s {_sub_tag()}", flush=True)
    print(f"[SUB] corpCode 캐시 없음/만료 -> 다운로드 {_sub_tag()}", flush=True)  # [계측]

    api_key = keys.get_dart_api_key()
    if not api_key:
        raise RuntimeError("DART API 키가 없습니다. api_secrets.py의 DART_API_KEY를 채워 주세요.")

    _t = time.perf_counter()                                                     # [계측]
    res = dart_guard.get(                   # 차단기 경유(불가 상태면 즉시 DartUnavailable). zip 이 커서 읽기만 60초
        "https://opendart.fss.or.kr/api/corpCode.xml",
        params={"crtfc_key": api_key}, read_timeout=60,
    )
    res.raise_for_status()

    # 응답이 zip이 아니면(키 오류 등) 본문이 XML 에러 메시지로 온다.
    if res.content[:2] != b"PK":
        raise RuntimeError("DART corpCode 응답이 zip이 아닙니다(키 또는 권한 확인 필요).")

    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        xml_bytes = zf.read(zf.namelist()[0])

    root = ET.fromstring(xml_bytes)
    mapping = {}
    for item in root.iter("list"):
        stock_code = (item.findtext("stock_code") or "").strip()
        corp_code = (item.findtext("corp_code") or "").strip()
        if len(stock_code) == 6 and corp_code:   # 상장사만 남긴다
            mapping[stock_code] = corp_code

    with open(CORPCODE_PKL, "wb") as f:
        pickle.dump(mapping, f)
    print(f"[STEP] corpCode - {time.perf_counter() - _t:.2f}s", flush=True)     # [계측] 다운로드했을 때만
    return mapping


# ---------------------------------------------------------------------------
# 2) DART 기업개황으로 업종코드 수집
# ---------------------------------------------------------------------------

def fetch_induty_code(corp_code, api_key, session=None):
    """기업개황 API 1건 호출 -> KSIC 업종코드 문자열. 실패하면 None."""
    try:
        res = dart_guard.get(               # 차단기 경유(연결 3초·읽기 15초, 불가 상태면 즉시 실패 -> None)
            "https://opendart.fss.or.kr/api/company.json",
            params={"crtfc_key": api_key, "corp_code": corp_code}, session=session,
        )
        body = res.json()
        if body.get("status") != "000":
            return None
        return (body.get("induty_code") or "").strip() or None
    except Exception:
        return None


def build_industry_map(target_df, progress_cb=None):
    """대상 종목들의 업종을 DART에서 수집해 industry_map.csv로 저장한다.

    target_df: 종목코드 / 종목명 컬럼을 가진 DataFrame (코스피·코스닥 시총 상위 종목)
    progress_cb: 진행률 콜백 (0.0~1.0, 설명문자열)
    """
    _ensure_dirs()

    api_key = keys.get_dart_api_key()
    if not api_key:
        raise RuntimeError("DART API 키가 없습니다.")

    if fin_store.is_store_mode():           # 저장본 모드: 업종 갱신(DART)은 PC 에서만 한다
        raise RuntimeError("저장본 모드에서는 업종 정보를 갱신하지 않습니다(PC 에서 갱신).")
    session = requests.Session()

    rows = []
    total = len(target_df)
    for i, (_, row) in enumerate(target_df.iterrows(), start=1):
        code = str(row["종목코드"]).zfill(6)
        name = row.get("종목명", "")
        corp_code = corp_code_for(code)     # corp_code_map.csv 먼저, 없는 종목만 기존 corpCode 경로

        induty = fetch_induty_code(corp_code, api_key, session) if corp_code else None
        rows.append({
            "종목코드": code,
            "종목명": name,
            "KSIC코드": induty or "",
            "업종그룹": ksic_to_group(induty),
        })

        if progress_cb and (i % 5 == 0 or i == total):
            progress_cb(i / total, f"업종 수집 {i}/{total}")
        time.sleep(DART_SLEEP)          # 초당 5건 제한

    if not dart_guard.available():      # DART 불가 상태면 '기타'로 채워진 결과를 저장하지 않는다
        raise RuntimeError(dart_guard.UNAVAILABLE_MESSAGE)
    result = pd.DataFrame(rows)
    result.to_csv(INDUSTRY_CSV, index=False, encoding="utf-8-sig")
    return result


# ---------------------------------------------------------------------------
# 3) 앱에서 쓰는 조회 함수
# ---------------------------------------------------------------------------

def _append_row(code, name, ksic, group):
    """industry_map.csv에 한 종목을 추가(있으면 갱신)하고 저장한다."""
    _ensure_dirs()
    current = load_industry_map()
    code = str(code).zfill(6)
    current = current[current["종목코드"] != code]          # 기존 줄이 있으면 지우고 새로 넣는다
    row = pd.DataFrame([{"종목코드": code, "종목명": name, "KSIC코드": ksic or "", "업종그룹": group}])
    merged = pd.concat([current, row], ignore_index=True)
    merged.to_csv(INDUSTRY_CSV, index=False, encoding="utf-8-sig")
    return merged


def ensure_industry(code, name=""):
    """종목의 업종그룹을 돌려준다.

    industry_map.csv에 없으면 DART 기업개황을 '그 종목만' 1회 호출해 업종을 구하고
    CSV에 추가 저장한다(다음부터는 호출 없이 재사용).
    조회에 실패하면 저장하지 않고 '기타'를 돌려줘, 나중에 다시 시도할 수 있게 둔다.
    """
    code = str(code).zfill(6)
    _ts = time.perf_counter()                                                    # [계측]
    imap = load_industry_map()
    print(f"[SUB] 캐시읽기 industry_map.csv {time.perf_counter() - _ts:.2f}s {_sub_tag()}", flush=True)  # [계측]
    hit = imap[imap["종목코드"] == code] if not imap.empty else imap
    if not imap.empty and not hit.empty:
        return str(hit.iloc[0]["업종그룹"])
    if fin_store.is_store_mode():           # 저장본 모드: DART 기업개황을 부르지 않고 저장도 하지 않는다
        return ETC

    api_key = keys.get_dart_api_key()
    if not api_key:
        print(f"[SUB] ensure_industry 키 없음 {code} {_sub_tag()}", flush=True)  # [계측]
        return ETC

    _ts = time.perf_counter()                                                    # [계측]
    try:
        corp_code = corp_code_for(code)     # corp_code_map.csv 먼저, 없으면 기존 corpCode 경로
    except Exception as _exc:
        print(f"[SUB] corp_code_for 예외 {type(_exc).__name__} {time.perf_counter() - _ts:.2f}s {_sub_tag()}",
              flush=True)                                                        # [계측]
        return ETC
    print(f"[SUB] corp_code_for {code} {time.perf_counter() - _ts:.2f}s {_sub_tag()}", flush=True)  # [계측]

    if not corp_code:                       # 우선주·리츠 등 DART 기업개황에 없는 종목
        return ETC

    _ts = time.perf_counter()                                                    # [계측]
    induty = fetch_induty_code(corp_code, api_key)
    print(f"[SUB] DART company.json {code} {'ok' if induty else '없음'} {time.perf_counter() - _ts:.2f}s "
          f"{_sub_tag()}", flush=True)                                           # [계측]
    if not induty:
        return ETC

    group = ksic_to_group(induty)
    _ts = time.perf_counter()                                                    # [계측]
    _append_row(code, name or code, induty, group)
    print(f"[SUB] 캐시쓰기 industry_map.csv {time.perf_counter() - _ts:.2f}s {_sub_tag()}", flush=True)  # [계측]
    return group


def load_industry_map():
    """industry_map.csv를 읽어 DataFrame으로 반환. 없으면 샘플, 그것도 없으면 빈 표."""
    for path in (INDUSTRY_CSV, INDUSTRY_SAMPLE_CSV):
        if os.path.exists(path):
            try:
                df = pd.read_csv(path, dtype={"종목코드": str, "KSIC코드": str})
                df["종목코드"] = df["종목코드"].astype(str).str.zfill(6)
                if "업종그룹" not in df.columns:
                    df["업종그룹"] = ETC
                df["업종그룹"] = df["업종그룹"].fillna(ETC)
                return df
            except Exception:
                continue
    return pd.DataFrame(columns=["종목코드", "종목명", "KSIC코드", "업종그룹"])


def attach_industry(df, code_col="종목코드", ensure=False, name_col="종목명"):
    """종목 DataFrame에 '업종그룹' 컬럼을 붙인다. 매핑이 없으면 '기타'.

    ensure=True 이면 매핑에 없는 종목만 DART를 1회씩 호출해 채운다.
    (종목 수가 적은 보유종목 화면에서만 쓴다. 200종목 히트맵에서는 쓰지 않는다.)
    """
    imap = load_industry_map()
    out = df.copy()
    codes = out[code_col].astype(str).str.zfill(6)

    lookup = dict(zip(imap["종목코드"], imap["업종그룹"])) if not imap.empty else {}
    out["업종그룹"] = codes.map(lookup).fillna(ETC)

    if ensure:
        missing = [c for c in codes.unique() if c not in lookup]
        if missing:
            names = dict(zip(codes, out[name_col])) if name_col in out.columns else {}
            filled = {c: ensure_industry(c, names.get(c, "")) for c in missing}
            out["업종그룹"] = codes.map(lambda c: lookup.get(c) or filled.get(c, ETC))
    return out
