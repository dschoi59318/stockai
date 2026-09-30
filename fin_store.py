# -*- coding: utf-8 -*-
"""
fin_store.py - 재무 저장본(data/fin_store) 형식·경로·읽기 (2026-09-30, 저장 방식 C: 보고서별 parquet)

배경: 클라우드(해외 IP)는 DART 가 ConnectTimeout 으로 막힌다. PC(한국 IP)의 fin_update.py 가 전 종목 재무를 받아
      여기 형식으로 저장하고, 클라우드는 (다음 단계에서) DART 호출 없이 이 파일만 읽는다.
이번 단계: read_report 는 검증용이다. 앱(financials.fetch_report)에는 아직 연결하지 않았다.

파일 (data/fin_store/)
 main_{연도}_{보고서}.parquet : 주요계정(fnlttMultiAcnt). 회사별 CFS·OFS 행
 all_{연도}_{보고서}.parquet  : 전체 재무제표 연결(fnlttSinglAcntAll, fs_div=CFS)의 IS/CIS/BS 행
 _manifest.csv   : (corp_code, 종류, 연도, 보고서)별 상태 000/013/empty, rcept_no, 확인 시각
 _targets.csv    : 종목코드 -> corp_code (우선주는 보통주 corp_code 를 함께 쓴다)
 _progress.json  : fin_update 진행·날짜별 호출 수(이어받기·하루 한도 보호)
 _update_log.txt : fin_update 실행 기록

규칙
 - 필요한 필드만 저장한다(financials 가 실제로 읽는 필드). 금액·계정명은 DART 문자열 그대로.
 - 응답 안 행 순서는 seq 로 보존한다(financials._pick 은 같은 이름 중 먼저 나온 행을 쓴다).
 - 응답에 없던 필드는 null 로 저장하고, 읽을 때는 그 키를 빼서 원래 응답과 같게 돌려준다.
"""

import json
import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORE_DIR = os.path.join(BASE_DIR, "data", "fin_store")
MANIFEST_CSV = "_manifest.csv"
TARGETS_CSV = "_targets.csv"
PROGRESS_JSON = "_progress.json"
LOG_TXT = "_update_log.txt"

# financials 가 읽는 필드(2026-09-30 기준 grep): 주요계정은 _rows(fs_div)·_pick(account_nm, 금액 필드)·sj_div,
# 전체 재무제표는 _find_ctrl_ni/_find_ctrl_eq/_has_attribution(sj_div, account_id, account_nm, 금액 필드)
MAIN_FIELDS = ["fs_div", "sj_div", "account_nm",
               "thstrm_amount", "thstrm_add_amount", "frmtrm_amount", "bfefrmtrm_amount"]
ALL_FIELDS = ["sj_div", "account_id", "account_nm",
              "thstrm_amount", "thstrm_add_amount", "frmtrm_amount", "bfefrmtrm_amount"]
MAIN_FS = ("CFS", "OFS")            # 주요계정에서 남기는 재무제표 구분
ALL_SJ = ("IS", "CIS", "BS")        # 전체 재무제표에서 남기는 표(SCE·CF 는 쓰지 않음)
KINDS = {"main": MAIN_FIELDS, "all": ALL_FIELDS}

MANIFEST_COLUMNS = ["corp_code", "kind", "year", "reprt", "status", "rcept_no", "checked"]


def partition_name(kind, year, reprt):
    """보고서 1건(모든 회사)의 parquet 파일 이름."""
    return f"{kind}_{int(year)}_{reprt}.parquet"


def partition_path(kind, year, reprt, store_dir=STORE_DIR):
    return os.path.join(store_dir, partition_name(kind, year, reprt))


def slim_rows(kind, rows):
    """DART 응답 행 목록 -> 저장할 행(dict) 목록. 필요한 표·필드만, seq 로 원래 순서를 남긴다."""
    fields = KINDS[kind]
    out = []
    for row in rows:
        if kind == "main" and row.get("fs_div") not in MAIN_FS:
            continue
        if kind == "all" and row.get("sj_div") not in ALL_SJ:
            continue
        item = {"seq": len(out)}
        for f in fields:
            item[f] = row.get(f)                      # 없는 필드는 None(저장 시 null)
        out.append(item)
    return out


def load_targets(store_dir=STORE_DIR):
    """_targets.csv -> {종목코드: corp_code}. 없으면 빈 dict."""
    path = os.path.join(store_dir, TARGETS_CSV)
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    return dict(zip(df["stock_code"].str.zfill(6), df["corp_code"]))


def load_manifest(store_dir=STORE_DIR):
    """_manifest.csv -> DataFrame(문자열). 없으면 빈 표."""
    path = os.path.join(store_dir, MANIFEST_CSV)
    if not os.path.exists(path):
        return pd.DataFrame(columns=MANIFEST_COLUMNS)
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def read_report(code, year, reprt, fs_div=None, store_dir=STORE_DIR, targets=None):
    """저장본에서 보고서 1건을 읽어 financials.fetch_report 와 같은 모양으로 돌려준다(검증용, 앱 미연결).

    fs_div='CFS' 면 전체 재무제표, 없으면 주요계정. 저장본에 없거나 013(미공시)이면 None(fetch_report 와 같음).
    반환: {"status": "000", "message": "정상", "list": [행 dict, ...]}  (행에는 저장한 필드 중 값이 있는 것만)
    """
    targets = targets if targets is not None else load_targets(store_dir)
    corp = targets.get(str(code).zfill(6))
    if not corp:
        return None
    kind = "all" if fs_div else "main"
    path = partition_path(kind, year, reprt, store_dir)
    if not os.path.exists(path):
        return None
    part = pd.read_parquet(path, filters=[("corp_code", "==", corp)])
    if part.empty:
        return None
    part = part.sort_values("seq")
    fields = KINDS[kind]
    rows = []
    for rec in part[fields].to_dict("records"):
        rows.append({k: v for k, v in rec.items() if v is not None and not (isinstance(v, float) and pd.isna(v))})
    return {"status": "000", "message": "정상", "list": rows}


def compare_with_cache(code, cache_dir=None, store_dir=STORE_DIR, targets=None):
    """검증용: data/cache/fin 의 원본 JSON 과 저장본을 필요한 필드 기준으로 비교한다.

    반환: {"비교": 파일 수, "일치": 수, "불일치": [(파일, 사유)], "저장본없음": [파일]}
    원본 JSON 도 저장할 때와 같은 규칙(slim_rows)으로 줄여서 행 순서까지 비교한다.
    """
    cache_dir = cache_dir or os.path.join(BASE_DIR, "data", "cache", "fin")
    code = str(code).zfill(6)
    out = {"비교": 0, "일치": 0, "불일치": [], "저장본없음": []}
    if not os.path.isdir(cache_dir):
        return out
    for name in sorted(os.listdir(cache_dir)):
        if not name.startswith(code + "_") or not name.endswith("_v2.json"):
            continue
        parts = name[:-len("_v2.json")].split("_")       # 코드_보고서_연도[_allCFS]
        reprt, year = parts[1], int(parts[2])
        kind = "all" if len(parts) > 3 else "main"
        with open(os.path.join(cache_dir, name), "r", encoding="utf-8") as f:
            original = json.load(f).get("list", [])
        want = [{k: v for k, v in r.items() if k != "seq" and v is not None} for r in slim_rows(kind, original)]
        got = read_report(code, year, reprt, "CFS" if kind == "all" else None, store_dir, targets)
        out["비교"] += 1
        if got is None:
            out["저장본없음"].append(name)
            continue
        if want == got["list"]:
            out["일치"] += 1
            continue
        reason = f"행 수 {len(want)} vs {len(got['list'])}"
        for i, (a, b) in enumerate(zip(want, got["list"])):
            if a != b:
                keys = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
                reason += f", 첫 차이 행 {i}: {keys} 원본={[a.get(k) for k in keys]} 저장본={[b.get(k) for k in keys]}"
                break
        out["불일치"].append((name, reason))
    return out
