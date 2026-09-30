# -*- coding: utf-8 -*-
"""
fin_update.py - (PC 전용) 전 종목 재무를 DART 에서 받아 data/fin_store 에 저장한다. (2026-09-30)

클라우드(해외 IP)는 DART 가 막혀 있으므로 PC(한국 IP)에서만 실행한다. 최초 채우기(1~2일)와 분기 실적 발표 뒤에 실행.
저장 형식은 fin_store.py (보고서별 parquet, 필요한 필드만, 금액 문자열 그대로).

단계
 1) 대상: data/stock_master.csv 중 corp_code 가 있는 상장사(corp_code_map.csv -> corpcode.pkl 순).
          우선주는 보통주(코드 끝자리 0) corp_code 를 함께 쓴다(_targets.csv 에만 기록, 따로 받지 않음).
 2) 주요계정: fnlttMultiAcnt 로 100개사씩(최대 100건, 2026-09-30 실측: 101건부터 status 021).
    응답에 없는 회사는 013(미공시) 마커.
 3) 전체 재무제표: fnlttSinglAcntAll(fs_div=CFS) - 연결재무제표(CFS)가 있는 회사만. IS/CIS/BS·필요 필드만.
 4) 업종: company.json - industry_map.csv 에 없는 종목만 받아 파일 끝에 추가(기존 행은 그대로).
 받을 보고서 목록은 앱(financials)과 같은 규칙(needed_reports)으로 정한다.

규칙
 - 013(미공시)은 manifest 에 마커로 저장하고 1일 뒤 다시 묻는다. 그 밖의 오류는 저장하지 않고 다음 실행 때 재시도.
 - 이어받기: manifest(_manifest.csv)에 000 인 보고서는 건너뛴다. 묶음마다 저장(체크포인트)하므로 중단해도 이어진다.
 - 하루 한도 보호: 날짜별 호출 수(_progress.json)가 --max-calls(기본 18,000)에 닿으면 저장하고 멈춘다.
   status 020(요청 제한 초과)을 받아도 즉시 멈춘다.
 - --quarter: 공시목록(list.json, 정기공시 A, 최종보고서만)으로 기간 안에 제출·정정된 보고서만 받는다
   (manifest 의 rcept_no 와 다르면 정정으로 보고 다시 받는다).

사용
 python fin_update.py                     전 종목 (없는 보고서만)
 python fin_update.py --sample 20 --no-push
 python fin_update.py --quarter           분기 갱신(새 보고서·정정만)
 옵션: --codes 005930,060720 (먼저 넣을 종목) --since YYYYMMDD(--quarter 시작일) --max-calls N --skip-industry --no-push
 --no-push 가 없으면 끝난 뒤 data/fin_store·data/industry_map.csv 를 커밋하고 push 한다.
키는 keys.get_dart_api_key() 로 읽고 출력하지 않는다.
"""

import argparse
import csv
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta

logging.getLogger("streamlit").setLevel(logging.ERROR)   # financials 를 가져올 때 나는 st 캐시 경고 줄이기

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

import fin_store as fs
import financials
import industry
import keys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STOCK_MASTER = os.path.join(BASE_DIR, "data", "stock_master.csv")
CORP_CODE_CSV = os.path.join(BASE_DIR, "data", "corp_code_map.csv")
INDUSTRY_CSV = os.path.join(BASE_DIR, "data", "industry_map.csv")

MULTI_URL = "https://opendart.fss.or.kr/api/fnlttMultiAcnt.json"
ALL_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
COMPANY_URL = "https://opendart.fss.or.kr/api/company.json"
LIST_URL = "https://opendart.fss.or.kr/api/list.json"

MULTI_BATCH = 100               # fnlttMultiAcnt 최대 회사 수(실측)
MAX_CALLS_DEFAULT = 18_000      # 하루 한도 2만 중 보호선
SLEEP = 0.2                     # 호출 간격(초당 5건 이하, industry.DART_SLEEP 과 같음)
TIMEOUT = (5, 30)               # (연결, 읽기) 초
NODATA_TTL = financials.NODATA_TTL      # 013 마커를 다시 묻기까지(1일)
ALL_CHECKPOINT = 25             # 전체 재무제표·업종: 이만큼 받을 때마다 저장
MAX_CONN_ERRORS = 5             # 연속 연결 오류가 이만큼이면 멈춤(네트워크 문제)
LIST_MAX_DAYS = 90              # list.json 을 회사 지정 없이 부를 때 기간(3개월 이내)

REPORT_NAME = re.compile(r"(사업보고서|반기보고서|분기보고서)\s*\((\d{4})\.(\d{2})\)")


class StopRun(Exception):
    """하루 한도·020·연속 연결 오류로 이번 실행을 멈춘다(저장은 하고 멈춘다)."""


# ---------------------------------------------------------------------------
# 받을 보고서 목록 (financials 와 같은 규칙)
# ---------------------------------------------------------------------------

def _quarter_reports(year, quarter):
    """분기 1개의 3개월 값을 만드는 데 쓰는 주요계정 보고서. 4분기 = 사업보고서 - 1~3분기."""
    if quarter == 4:
        return [(year, financials.REPRT_ANNUAL)] + [(year, financials.QUARTER_REPRT[q]) for q in (1, 2, 3)]
    return [(year, financials.QUARTER_REPRT[quarter])]


def needed_reports(today=None):
    """앱(load_financials)이 부르는 보고서 목록 -> (주요계정 [(연도, 보고서)], 전체 재무제표 [(연도, 보고서)]).

    주요계정: 연간(latest_annual_year 사업보고서) + 최근 8분기 + 계절성 2개 연도(1~4분기) + 1년 전 분기말.
    전체 재무제표(CFS 회사만): 연간 + 최근 4분기(지배주주 값) + 1년 전 분기말.
    """
    today = today or datetime.today()
    last = financials.latest_annual_year(today)
    quarters = financials.recent_quarters(8, today)
    main, full = [(last, financials.REPRT_ANNUAL)], [(last, financials.REPRT_ANNUAL)]
    for index, (year, quarter) in enumerate(quarters):
        main += _quarter_reports(year, quarter)
        if index < 4:
            full += _quarter_reports(year, quarter)
    month, day = financials.QUARTER_READY[4]
    for year in (last - 1, last):                             # load_season_years
        for y, q in financials.recent_quarters(4, datetime(year + 1, month, day)):
            main += _quarter_reports(y, q)
    y, q = quarters[0]                                        # load_year_ago_equity
    main.append((y - 1, financials.QUARTER_REPRT[q]))
    full.append((y - 1, financials.QUARTER_REPRT[q]))
    order = lambda items: sorted(set(items), key=lambda x: (x[0], x[1]))
    return order(main), order(full)


# ---------------------------------------------------------------------------
# 진행·manifest·로그
# ---------------------------------------------------------------------------

class Runner:
    def __init__(self, args):
        self.args = args
        self.store = fs.STORE_DIR
        os.makedirs(self.store, exist_ok=True)
        self.key = keys.get_dart_api_key()
        if not self.key:
            raise SystemExit("DART API 키가 없습니다(api_secrets.py 또는 _secrets).")
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.progress = self._load_progress()
        self.manifest = {}                  # (corp, kind, year, reprt) -> dict
        for rec in fs.load_manifest(self.store).to_dict("records"):
            self.manifest[(rec["corp_code"], rec["kind"], int(rec["year"]), rec["reprt"])] = rec
        self.stats = {"호출": 0, "호출_API별": {}, "성공": 0, "013": 0, "없음(empty)": 0, "오류": 0,
                      "저장행": 0, "업종추가": 0}
        self.conn_errors = 0
        self.t0 = time.perf_counter()

    # --- 기록 ---
    def log(self, text):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}"
        print(line, flush=True)
        with open(os.path.join(self.store, fs.LOG_TXT), "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _load_progress(self):
        path = os.path.join(self.store, fs.PROGRESS_JSON)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"version": 1, "calls": {}, "runs": []}

    def save_progress(self, **extra):
        self.progress.update(extra)
        path = os.path.join(self.store, fs.PROGRESS_JSON)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.progress, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)

    def save_manifest(self):
        rows = sorted(self.manifest.values(), key=lambda r: (r["kind"], int(r["year"]), r["reprt"], r["corp_code"]))
        df = pd.DataFrame(rows, columns=fs.MANIFEST_COLUMNS)
        path = os.path.join(self.store, fs.MANIFEST_CSV)
        df.to_csv(path + ".tmp", index=False, encoding="utf-8-sig")
        os.replace(path + ".tmp", path)

    def mark(self, corp, kind, year, reprt, status, rcept_no=""):
        self.manifest[(corp, kind, int(year), reprt)] = {
            "corp_code": corp, "kind": kind, "year": str(int(year)), "reprt": reprt, "status": status,
            "rcept_no": rcept_no or "", "checked": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    def is_done(self, corp, kind, year, reprt):
        """000(받음)·empty 이거나 1일 안에 013 을 받았으면 True(다시 묻지 않음)."""
        rec = self.manifest.get((corp, kind, int(year), reprt))
        if not rec:
            return False
        if rec["status"] in ("000", "empty"):
            return True
        if rec["status"] == "013":
            try:
                age = time.time() - datetime.strptime(rec["checked"], "%Y-%m-%d %H:%M:%S").timestamp()
                return age < NODATA_TTL
            except Exception:
                return False
        return False

    # --- 호출 ---
    def call(self, api, url, params):
        """DART GET 1회. 하루 한도·020·연속 연결 오류면 StopRun. 반환: 응답 dict 또는 None(오류)."""
        used = self.progress["calls"].get(self.today, 0)
        if used >= self.args.max_calls:
            raise StopRun(f"하루 한도 보호: 오늘 호출 {used:,}회 >= {self.args.max_calls:,}회")
        self.progress["calls"][self.today] = used + 1
        self.stats["호출"] += 1
        self.stats["호출_API별"][api] = self.stats["호출_API별"].get(api, 0) + 1
        time.sleep(SLEEP)
        try:
            res = requests.get(url, params={"crtfc_key": self.key, **params}, timeout=TIMEOUT)
            body = res.json()
            self.conn_errors = 0
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as exc:
            self.conn_errors += 1
            self.stats["오류"] += 1
            self.log(f"  연결 오류 {api} {type(exc).__name__} (연속 {self.conn_errors})")
            if self.conn_errors >= MAX_CONN_ERRORS:
                raise StopRun(f"연속 연결 오류 {self.conn_errors}회")
            return None
        except Exception as exc:
            self.stats["오류"] += 1
            self.log(f"  오류 {api} {type(exc).__name__}")
            return None
        if body.get("status") == "020":
            raise StopRun(f"DART 요청 제한 초과(020): {body.get('message')}")
        return body


# ---------------------------------------------------------------------------
# parquet 저장(보고서별 파일에 회사 행을 바꿔 넣기)
# ---------------------------------------------------------------------------

def _schema(kind):
    fields = [pa.field("corp_code", pa.string()), pa.field("seq", pa.int32())]
    fields += [pa.field(name, pa.string()) for name in fs.KINDS[kind]]
    return pa.schema(fields)


def write_partition(store, kind, year, reprt, new_rows, replace_corps):
    """보고서 파일에서 replace_corps 회사 행을 지우고 new_rows 를 넣어 다시 쓴다(임시 파일 -> 이름 바꾸기)."""
    if not new_rows and not replace_corps:
        return
    path = fs.partition_path(kind, year, reprt, store)
    columns = ["corp_code", "seq"] + fs.KINDS[kind]
    frames = []
    if os.path.exists(path):
        old = pd.read_parquet(path)
        frames.append(old[~old["corp_code"].isin(set(replace_corps))])
    if new_rows:
        frames.append(pd.DataFrame(new_rows, columns=columns))
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)
    df = df.sort_values(["corp_code", "seq"]).reset_index(drop=True)
    df["seq"] = df["seq"].astype("int32")
    table = pa.Table.from_pandas(df[columns], schema=_schema(kind), preserve_index=False)
    tmp = path + ".tmp"
    pq.write_table(table, tmp, compression="zstd")
    os.replace(tmp, path)


def partition_corps_with_cfs(store, year, reprt):
    """주요계정 파일에서 연결(CFS) 행이 있는 회사 집합."""
    path = fs.partition_path("main", year, reprt, store)
    if not os.path.exists(path):
        return set()
    df = pd.read_parquet(path, columns=["corp_code", "fs_div"])
    return set(df.loc[df["fs_div"] == "CFS", "corp_code"])


# ---------------------------------------------------------------------------
# 대상 종목
# ---------------------------------------------------------------------------

def build_targets(runner):
    """stock_master -> corp_code. 반환: (targets DataFrame, 받을 회사 목록[corp, 대표 종목코드, 이름])."""
    master = pd.read_csv(STOCK_MASTER, dtype=str, keep_default_na=False)
    master["종목코드"] = master["종목코드"].str.zfill(6)
    cmap = pd.read_csv(CORP_CODE_CSV, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    mapping = dict(zip(cmap["stock_code"].str.zfill(6), cmap["corp_code"]))
    missing = [c for c in master["종목코드"] if c not in mapping and c[-1] == "0"]
    if missing:                                   # 표에 없는 보통주만 corpcode.pkl(30일 캐시, 없으면 다운로드 1회)
        pkl_fresh = os.path.exists(industry.CORPCODE_PKL) and \
            (time.time() - os.path.getmtime(industry.CORPCODE_PKL)) / 86400 < industry.CORPCODE_TTL_DAYS
        if not pkl_fresh:
            runner.progress["calls"][runner.today] = runner.progress["calls"].get(runner.today, 0) + 1
            runner.stats["호출"] += 1
            runner.stats["호출_API별"]["corpCode.xml"] = 1
        try:
            extra = industry.load_corp_code_map()
            for c in missing:
                if extra.get(c):
                    mapping[c] = extra[c]
        except Exception as exc:
            runner.log(f"corpCode 보충 실패({type(exc).__name__}) - corp_code_map.csv 만 사용")
    rows = []
    for code, name, market in master[["종목코드", "종목명", "시장"]].itertuples(index=False):
        if code in mapping:
            rows.append((code, mapping[code], name, market, "직접"))
        elif code[-1] != "0" and (code[:5] + "0") in mapping:
            rows.append((code, mapping[code[:5] + "0"], name, market, "우선주->보통주"))
    targets = pd.DataFrame(rows, columns=["stock_code", "corp_code", "name", "market", "basis"])
    companies = targets[targets["basis"] == "직접"].drop_duplicates("corp_code")
    companies = list(companies[["corp_code", "stock_code", "name"]].itertuples(index=False, name=None))
    skipped = len(master) - len(targets)
    return targets, companies, skipped


def pick_sample(companies, codes, n):
    """--codes 종목을 먼저, 그다음 목록 순서로 n개(n 없으면 전부)."""
    first = [c for code in codes for c in companies if c[1] == code]
    rest = [c for c in companies if c not in first]
    picked = first + rest
    return picked[:n] if n else picked


# ---------------------------------------------------------------------------
# 1) 주요계정 (fnlttMultiAcnt)
# ---------------------------------------------------------------------------

def fetch_main(runner, reports, corps_by_report):
    for year, reprt in reports:
        todo = corps_by_report(year, reprt)
        if not todo:
            continue
        runner.log(f"주요계정 {year} {reprt}: {len(todo)}개사 ({(len(todo) + MULTI_BATCH - 1) // MULTI_BATCH}회 호출)")
        for i in range(0, len(todo), MULTI_BATCH):
            batch = todo[i:i + MULTI_BATCH]
            body = runner.call("fnlttMultiAcnt", MULTI_URL,
                               {"corp_code": ",".join(batch), "bsns_year": str(year), "reprt_code": reprt})
            if body is None:
                continue
            status = body.get("status")
            if status not in ("000", "013"):
                runner.stats["오류"] += len(batch)
                runner.log(f"  status {status} {body.get('message')} - 저장 안 함(다음 실행 때 재시도)")
                continue
            by_corp = {}
            for row in body.get("list", []) if status == "000" else []:
                by_corp.setdefault(row.get("corp_code"), []).append(row)
            new_rows = []
            for corp in batch:
                rows = by_corp.get(corp)
                if rows:
                    slim = fs.slim_rows("main", rows)
                    new_rows += [{"corp_code": corp, **r} for r in slim]
                    runner.mark(corp, "main", year, reprt, "000", rows[0].get("rcept_no"))
                    runner.stats["성공"] += 1
                else:
                    runner.mark(corp, "main", year, reprt, "013")
                    runner.stats["013"] += 1
            write_partition(runner.store, "main", year, reprt, new_rows, batch)
            runner.stats["저장행"] += len(new_rows)
            runner.save_manifest()
            runner.save_progress()


# ---------------------------------------------------------------------------
# 2) 전체 재무제표 (fnlttSinglAcntAll, CFS 회사만)
# ---------------------------------------------------------------------------

def fetch_all(runner, reports, corps_by_report):
    for year, reprt in reports:
        todo = corps_by_report(year, reprt)
        if not todo:
            continue
        runner.log(f"전체 재무제표 {year} {reprt}: {len(todo)}개사(연결 CFS)")
        pending, replaced = [], []

        def flush():
            write_partition(runner.store, "all", year, reprt, pending, replaced)
            runner.stats["저장행"] += len(pending)
            runner.save_manifest()
            runner.save_progress()
            pending.clear()
            replaced.clear()

        try:
            for n, corp in enumerate(todo, start=1):
                body = runner.call("fnlttSinglAcntAll", ALL_URL,
                                   {"corp_code": corp, "bsns_year": str(year), "reprt_code": reprt, "fs_div": "CFS"})
                if body is None:
                    continue
                status = body.get("status")
                if status == "000":
                    rows = body.get("list", [])
                    pending.extend({"corp_code": corp, **r} for r in fs.slim_rows("all", rows))
                    replaced.append(corp)
                    runner.mark(corp, "all", year, reprt, "000", rows[0].get("rcept_no") if rows else "")
                    runner.stats["성공"] += 1
                elif status == "013":
                    replaced.append(corp)
                    runner.mark(corp, "all", year, reprt, "013")
                    runner.stats["013"] += 1
                else:
                    runner.stats["오류"] += 1
                    runner.log(f"  {corp} status {status} {body.get('message')} - 저장 안 함")
                if n % ALL_CHECKPOINT == 0:
                    flush()
        finally:
            flush()                                  # 멈출 때도 받은 것까지 저장


# ---------------------------------------------------------------------------
# 3) 업종 (company.json) -> industry_map.csv 끝에 추가
# ---------------------------------------------------------------------------

def fetch_industry(runner, companies):
    existing = pd.read_csv(INDUSTRY_CSV, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    have = set(existing["종목코드"].str.zfill(6))
    todo = [(corp, code, name) for corp, code, name in companies
            if code not in have and not runner.is_done(corp, "company", 0, "company")]
    if not todo:
        runner.log("업종: 추가할 종목 없음")
        return
    runner.log(f"업종(company.json): {len(todo)}개 종목")
    pending = []

    def flush():
        if not pending:
            return
        with open(INDUSTRY_CSV, "a", encoding="utf-8", newline="") as f:     # 기존 행은 그대로, 끝에 추가
            writer = csv.writer(f, lineterminator="\r\n")
            writer.writerows(pending)
        runner.stats["업종추가"] += len(pending)
        pending.clear()
        runner.save_manifest()
        runner.save_progress()

    try:
        for n, (corp, code, name) in enumerate(todo, start=1):
            body = runner.call("company.json", COMPANY_URL, {"corp_code": corp})
            if body is None:
                continue
            if body.get("status") != "000":
                runner.stats["오류"] += 1
                runner.log(f"  업종 {code} status {body.get('status')} {body.get('message')} - 저장 안 함")
                continue
            induty = (body.get("induty_code") or "").strip()
            if not induty:                          # 업종코드가 비어 있음: 저장하지 않고 다시 묻지도 않는다
                runner.mark(corp, "company", 0, "company", "empty")
                runner.stats["없음(empty)"] += 1
                continue
            pending.append([code, name, induty, industry.ksic_to_group(induty)])
            runner.mark(corp, "company", 0, "company", "000")
            runner.stats["성공"] += 1
            if n % ALL_CHECKPOINT == 0:
                flush()
    finally:
        flush()


# ---------------------------------------------------------------------------
# --quarter: 공시목록으로 새 보고서·정정만
# ---------------------------------------------------------------------------

def _reprt_from_name(report_nm):
    """'[기재정정]반기보고서 (2026.06)' -> (2026, '11012'). 12월 결산 기준 월(03/06/09/12)만 다룬다."""
    m = REPORT_NAME.search(report_nm or "")
    if not m:
        return None
    kind, year, month = m.group(1), int(m.group(2)), m.group(3)
    table = {("사업보고서", "12"): financials.REPRT_ANNUAL, ("반기보고서", "06"): financials.REPRT_H1,
             ("분기보고서", "03"): financials.REPRT_Q1, ("분기보고서", "09"): financials.REPRT_Q3}
    reprt = table.get((kind, month))
    return (year, reprt) if reprt else None


def quarter_filings(runner, corps, since):
    """기간 안에 제출(정정 포함, 최종보고서만)된 정기공시 -> {(연도, 보고서): {corp: rcept_no}}."""
    end = datetime.now()
    start = max(since, end - timedelta(days=LIST_MAX_DAYS))
    runner.log(f"공시목록(list.json) {start:%Y-%m-%d} ~ {end:%Y-%m-%d} 정기공시")
    found, skipped_months, page = {}, 0, 1
    wanted = set(corps)
    while True:
        body = runner.call("list.json", LIST_URL, {"bgn_de": start.strftime("%Y%m%d"), "end_de": end.strftime("%Y%m%d"),
                                                   "pblntf_ty": "A", "last_reprt_at": "Y",
                                                   "page_no": page, "page_count": 100})
        if body is None or body.get("status") not in ("000", "013"):
            raise StopRun(f"공시목록 조회 실패: {None if body is None else body.get('status')}")
        if body.get("status") == "013":
            break
        for item in body.get("list", []):
            if item.get("corp_code") not in wanted:
                continue
            key = _reprt_from_name(item.get("report_nm"))
            if key is None:
                skipped_months += 1
                continue
            found.setdefault(key, {})[item["corp_code"]] = item.get("rcept_no", "")
        if page >= int(body.get("total_page", 1)):
            break
        page += 1
    runner.log(f"  대상 보고서 {sum(len(v) for v in found.values())}건 (12월 결산이 아닌 보고서 {skipped_months}건 제외)")
    return found, end


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

def git_push(runner, message):
    def git(*cmd):
        name = subprocess.run(["git", "config", "user.name"], cwd=BASE_DIR, capture_output=True, text=True).stdout.strip()
        ident = [] if name else ["-c", "user.name=dschoi59318", "-c", "user.email=dschoi59318@gmail.com"]
        return subprocess.run(["git", *ident, *cmd], cwd=BASE_DIR, capture_output=True, text=True)
    git("add", "data/fin_store", "data/industry_map.csv")
    if git("diff", "--cached", "--quiet").returncode == 0:
        runner.log("git: 바뀐 저장본 없음(커밋 안 함)")
        return
    result = git("commit", "-m", message)
    runner.log(f"git commit: {result.stdout.strip().splitlines()[0] if result.stdout.strip() else result.stderr.strip()}")
    result = git("push")
    runner.log("git push: " + ("완료" if result.returncode == 0 else f"실패 {result.stderr.strip()[:200]}"))


def main():
    parser = argparse.ArgumentParser(description="DART 재무 저장본(data/fin_store) 채우기 - PC 전용")
    parser.add_argument("--sample", type=int, default=0, help="N개 회사만(검증용)")
    parser.add_argument("--codes", default="", help="먼저 넣을 종목코드(쉼표)")
    parser.add_argument("--quarter", action="store_true", help="공시목록으로 새 보고서·정정만 받기")
    parser.add_argument("--since", default="", help="--quarter 시작일 YYYYMMDD(없으면 지난 분기 갱신일, 최대 90일)")
    parser.add_argument("--max-calls", type=int, default=MAX_CALLS_DEFAULT, help="하루 호출 보호선")
    parser.add_argument("--skip-industry", action="store_true", help="업종(company.json) 단계 건너뛰기")
    parser.add_argument("--no-push", action="store_true", help="끝난 뒤 커밋·push 하지 않기")
    args = parser.parse_args()

    runner = Runner(args)
    mode = "분기 갱신(--quarter)" if args.quarter else "전체(없는 보고서만)"
    runner.log(f"===== fin_update 시작: {mode}, sample={args.sample or '전체'}, 오늘 이미 호출 "
               f"{runner.progress['calls'].get(runner.today, 0):,}회 / 보호선 {args.max_calls:,}회")
    stopped = None
    try:
        targets, companies, skipped = build_targets(runner)
        codes = [c.strip().zfill(6) for c in args.codes.split(",") if c.strip()]
        companies = pick_sample(companies, codes, args.sample)
        targets.to_csv(os.path.join(runner.store, fs.TARGETS_CSV), index=False, encoding="utf-8-sig")
        corps = [c[0] for c in companies]
        runner.log(f"대상 종목 {len(targets)}개(우선주 포함, corp_code 없는 {skipped}개 제외) -> 받을 회사 {len(corps)}개")
        main_reports, all_reports = needed_reports()
        runner.log(f"보고서: 주요계정 {len(main_reports)}건 {main_reports}")
        runner.log(f"        전체 재무제표 {len(all_reports)}건 {all_reports}")
        runner.save_progress(state="running", mode=mode, started=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        if args.quarter:
            since = (datetime.strptime(args.since, "%Y%m%d") if args.since else
                     datetime.strptime(runner.progress.get("last_quarter_end", "19000101"), "%Y%m%d"))
            filings, list_end = quarter_filings(runner, corps, since)

            def changed(kind):
                def pick(year, reprt):
                    got = filings.get((year, reprt), {})
                    out = []
                    for corp, rcept in got.items():
                        rec = runner.manifest.get((corp, kind, int(year), reprt))
                        if not rec or rec["status"] != "000" or rec["rcept_no"] != rcept:
                            out.append(corp)
                    return sorted(out)
                return pick
            main_pick = changed("main")
            fetch_main(runner, main_reports, main_pick)

            def all_pick(year, reprt):
                cfs = partition_corps_with_cfs(runner.store, year, reprt) | \
                    partition_corps_with_cfs(runner.store, year, financials.REPRT_ANNUAL)
                return [c for c in changed("all")(year, reprt) if c in cfs]
            fetch_all(runner, all_reports, all_pick)
        else:
            def main_pick(year, reprt):
                return [c for c in corps if not runner.is_done(c, "main", year, reprt)]
            fetch_main(runner, main_reports, main_pick)

            def all_pick(year, reprt):
                # 앱은 그 보고서(4분기 재료인 1~3분기는 사업보고서)의 연결/별도 판정이 CFS 일 때만 전체 재무제표를 부른다.
                cfs = partition_corps_with_cfs(runner.store, year, reprt) | \
                    partition_corps_with_cfs(runner.store, year, financials.REPRT_ANNUAL)
                return [c for c in corps if c in cfs and not runner.is_done(c, "all", year, reprt)]
            fetch_all(runner, all_reports, all_pick)

        if not args.skip_industry:
            fetch_industry(runner, companies)
        if args.quarter:
            runner.progress["last_quarter_end"] = list_end.strftime("%Y%m%d")
    except StopRun as exc:
        stopped = str(exc)
        runner.log(f"멈춤: {stopped} - 여기까지 저장. 다시 실행하면 이어서 받습니다.")
    finally:
        runner.save_manifest()

    elapsed = time.perf_counter() - runner.t0
    size = sum(os.path.getsize(os.path.join(runner.store, f)) for f in os.listdir(runner.store)
               if f.endswith(".parquet"))
    summary = {**runner.stats, "걸린시간초": round(elapsed, 1), "저장본parquet_MB": round(size / 1e6, 2),
               "오늘누적호출": runner.progress["calls"].get(runner.today, 0), "멈춤": stopped}
    runner.progress.setdefault("runs", []).append({"끝": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                                   "모드": mode, **summary})
    runner.save_progress(state="stopped" if stopped else "done")
    runner.log("요약 " + json.dumps(summary, ensure_ascii=False))
    if not args.no_push:
        git_push(runner, f"fin: store update {runner.today} ({runner.stats['성공']}건)")
    return 2 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
