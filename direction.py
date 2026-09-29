# -*- coding: utf-8 -*-
"""
direction.py - 방향 지시계·반전 조건·사건 선정·확인 시점·시나리오·핵심 긴장 문장·실적 해설 입력
(docs/리포트_구성지침.md 5장을 그대로 코드화)

원칙 (지침 2장)
 - 판정은 파이썬, 해설은 AI. 이 파일은 AI를 쓰지 않는다. 같은 입력이면 항상 같은 결과가 나온다.
 - 판정 규칙·문장 틀은 지침 문서가 기준이다. 바꾸려면 지침을 먼저 고치고 버전을 올린 뒤 반영한다.
 - REPORT_GUIDE_VERSION은 지침 문서 버전과 같아야 한다(리포트 출처 페이지에 표시). guides.check_versions()가 대조한다.

v1.6 반영(지침 11장 변경 이력)
 - 판정 규칙(5장)은 바뀌지 않았다. v1.6은 서식 규격(12장)·목차·부록 B 출처·면책 개정이며 report.py·charts.py에 반영했다.

v1.5 반영(지침 11장 변경 이력)
 - 5.10 분기 흐름 사실: 최근 4개 분기 각각의 직전 분기 대비 매출·영업이익 방향(늘었/줄었/같았)을 문장으로 만든다.
   같은 방향이 3개 분기 이상 이어질 때만 "{N}개 분기 연속 증가/감소"로 쓴다(flow_facts).
   AI가 '지속적으로·계속·연속·꾸준히'를 쓸 수 있는지는 이 사실 문장에 '연속'이 있는지로 정한다(narrator 검사).

v1.4 반영(지침 11장 변경 이력)
 - 5.0 기준일: 일봉은 data.fetch_ohlcv_raw가 15:40 이전 실행이면 당일 장중 일봉을 잘라 준다(이 파일은 받은 값만 쓴다)
 - 5.9 가격 추세가 방향 탐색이면 가격 표현 = "아직 뚜렷한 추세를 만들지 못했습니다(최근 6개월 평균 대비 {+/-이격도}%)"
 - 5.10 계절성: 직전 완결된 2개 연도(financials.load_season_years)의 분기별 매출로 판정(금융업은 영업이익).
   두 해 모두 최고 분기가 같으면 "계절성 있음: {N}분기 매출이 연중 가장 많습니다", 아니면 "계절성 판단 불가"
 - 5.10 흑자·적자 전환 사실: 최근 8개 분기 영업이익 부호가 바뀐 분기마다 사실 문장
   ("영업이익은 2025년 4분기에 적자에서 흑자로 바뀌었습니다"). 같은 분기 1년 전 비교 문장에서는 '돌아섰다·바뀌었다'를
   쓰지 않는다(전환 시점으로 읽히지 않게).

v1.3 반영(지침 11장 변경 이력)
 - 5.2/5.5 1년 전 같은 분기가 적자면 경계에 배수를 쓰지 않는다.
   최근 분기가 흑자면 경계 = 0원("흑자를 유지하면 개선 쪽, 적자로 돌아서면 악화 쪽 근거"),
   최근 분기도 적자면 적자 폭 기준(1년 전 적자보다 10% 이상 작으면 개선 쪽, 10% 이상 크면 악화 쪽)
 - 5.5 정렬: 가격 조건만으로 바뀌는 행을 평균선 순서 변화가 함께 필요한 행보다 앞에 두고, 각 무리 안에서는 거리순.
   실적 행은 맨 뒤. 결론 문단이 인용하는 "가장 가까운 반전 조건" = 이 표의 첫 행
 - 5.6 방향 확인: 방향어 바로 앞에 코스피·코스닥·지수·증시·시장·업종이 있으면 종목 이야기가 아니므로 반대 방향으로 보지 않는다
 - 5.9 핵심 긴장 문장: 신호 A·B 조합으로 결론 1문장의 뼈대(실적 숫자 1개 + 가격 숫자 1개)를 만든다
 - 5.10 실적 해설 입력: 최근 8개 분기 표, 같은 분기 2년치 비교 사실, 계절성 판정(계절성 있음 / 계절성 판단 불가)
   (v1.3의 '최근 4개 분기 두 묶음' 비교는 v1.4에서 직전 완결 2개 연도 비교로 바뀌었다)
 - 금액·증감 표시: 100% 이상 증가는 배수 표현(쉽게 읽기 지침 증감 표현 규칙). 실적 흐름 근거 문구에도 적용

구성
 5.1 signal_price     : 신호 A 가격 추세(상승 추세 / 하락 추세 / 방향 탐색)
 5.2 signal_earnings  : 신호 B 실적 흐름(개선 / 보합 / 악화 / 판정 불가)
 5.3 signal_volume    : 신호 C 거래 관심도(관심 확대 / 보통 / 관심 축소)
 5.4 overall_state    : 종합 상태 이름(A x B 고정표) + 신호 C 보조 문구
 5.5 reversal_table   : 반전 조건 표(신호 / 지금 판정 / 바뀌는 조건 / 지금과의 거리)
 5.6 select_events    : 사건 최대 5개 + 근거 강도(강함 / 보통 / 약함 / 없음)
 5.7 next_check       : 다음 확인 시점(정기보고서 제출 기한)
 5.8 scenarios        : 시나리오 3개(상방 / 기본 / 하방)와 발동 조건
 5.9 tension_sentence : 핵심 긴장 문장 뼈대
 5.10 earnings_story_input : 8개 분기 표·같은 분기 비교 사실·계절성 판정
 build                : 위 전부를 한 dict로
"""

import re
from datetime import date, timedelta

import easy_read
import financials

REPORT_GUIDE_VERSION = "v1.6"

UP, DOWN, SIDE = "상승 추세", "하락 추세", "방향 탐색"
BETTER, FLAT, WORSE, UNKNOWN = "개선", "보합", "악화", "판정 불가"
HOT, NORMAL, COLD = "관심 확대", "보통", "관심 축소"

EARN_PCT = 10.0             # 5.2 영업이익 증감률 경계(%)
SALES_FLOOR = -5.0          # 5.2 개선일 때 매출 증감률 하한(%)
VOL_HOT, VOL_COLD = 1.5, 0.7  # 5.3 거래량 배수 경계
EVENT_MAX = 5               # 5.6 최대 사건 수
EVENT_MIN_PCT = 3.0         # 5.6 |누적 초과 등락률| 하한(%)

# 5.4 종합 상태 이름 (A x B, 고정)
STATE_TABLE = {
    (UP, BETTER): "실적과 주가가 함께 오르는 구간",
    (UP, FLAT): "주가가 실적보다 앞서가는 구간",
    (UP, WORSE): "실적 둔화 속 주가 강세 구간",
    (SIDE, BETTER): "실적 개선, 주가 방향 탐색 구간",
    (SIDE, FLAT): "뚜렷한 방향이 없는 구간",
    (SIDE, WORSE): "실적 둔화, 주가 방향 탐색 구간",
    (DOWN, BETTER): "실적 개선에도 주가가 약한 구간",
    (DOWN, FLAT): "주가 약세 구간",
    (DOWN, WORSE): "실적과 주가가 함께 약한 구간",
}
VOLUME_TAG = {HOT: "(거래 관심 확대)", COLD: "(거래 관심 축소)"}

# 5.6 근거 강도
STRONG, MEDIUM, WEAK, NONE = "강함", "보통", "약함", "없음"

# 5.7 정기보고서 제출 기한: 분기·반기 = 분기말 + 45일, 사업보고서 = 연말 + 90일
QUARTER_END = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
REPORT_DAYS = {1: 45, 2: 45, 3: 45, 4: 90}
PERIODIC_RE = re.compile(r"(분기보고서|반기보고서|사업보고서)\s*\((\d{4})\.(\d{2})\)")

ORDER_UP = "3개월 평균이 6개월 평균을 넘어서야 합니다"
ORDER_DOWN = "3개월 평균이 6개월 평균 아래로 내려가야 합니다"

# 5.5 실적 경계 유형(v1.3)
BOUND_RATIO = "배수"          # 1년 전 흑자: 1.1배 / 0.9배
BOUND_ZERO = "흑자 유지"      # 1년 전 적자, 최근 분기 흑자: 0원
BOUND_LOSS = "적자 폭"        # 1년 전 적자, 최근 분기도 적자: 적자 폭 10%

# 5.10 계절성 판정
SEASONAL, SEASON_UNKNOWN = "계절성 있음", "계절성 판단 불가"


# ---------------------------------------------------------------------------
# 표기 도우미
# ---------------------------------------------------------------------------

def won(value):
    return f"{int(value):,}원"


def dist_pct(target, price):
    """현재가에서 목표 가격까지 거리(%, 부호 포함). 목표가 위면 +."""
    return (target / price - 1) * 100


def dist_text(pct):
    """'5.1% 아래' / '5.0% 위' / '지금 충족'"""
    if round(pct, 1) == 0:
        return "지금 충족"
    return f"{abs(pct):.1f}% {'위' if pct > 0 else '아래'}"


def eok(value_won):
    return financials.format_eok(value_won)


def growth_text(now, before, noun="증가", shrink="감소"):
    """증감 표시 문자열(양수끼리 비교). 100% 이상 증가는 배수: '1년 전의 12.9배로 증가' / '56.5% 감소'."""
    pct = (now / before - 1) * 100
    if pct >= 100:
        return f"1년 전의 {now / before:,.1f}배로 {noun}"
    return f"1년 전보다 {abs(pct):.1f}% {noun if pct > 0 else shrink}"


# ---------------------------------------------------------------------------
# 5.1 신호 A: 가격 추세
# ---------------------------------------------------------------------------

def signal_price(ind):
    """현재가·MA60·MA120으로 가격 추세를 판정한다. MA가 없으면 None."""
    ma = ind.get("이동평균") or {}
    p, m60, m120 = ind.get("현재가"), ma.get("MA60"), ma.get("MA120")
    if not (p and m60 and m120):
        return None
    if p > m60 and p > m120 and m60 > m120:
        verdict = UP
        sentence = "지금 주가는 최근 3개월·6개월 평균보다 모두 높고, 3개월 평균도 6개월 평균보다 높은 상승 추세입니다."
    elif p < m60 and p < m120 and m60 < m120:
        verdict = DOWN
        sentence = "지금 주가는 최근 3개월·6개월 평균보다 모두 낮고, 3개월 평균도 6개월 평균보다 낮은 하락 추세입니다."
    else:
        verdict = SIDE
        sentence = (f"지금 주가는 최근 3개월 평균({m60:,}원)보다 {'높고' if p > m60 else '낮고'} "
                    f"6개월 평균({m120:,}원)보다 {'높아' if p > m120 else '낮아'} 방향을 찾는 중입니다.")
    evidence = (f"현재가 {p:,}원, 최근 3개월 평균 {m60:,}원보다 {_hl(p, m60)} "
                f"최근 6개월 평균 {m120:,}원보다 {_hl(p, m120, last=True)}")
    return {"판정": verdict, "근거": evidence, "문장": sentence, "현재가": p, "MA60": m60, "MA120": m120,
            "MA120_이격도": ma.get("MA120_이격도")}


def _hl(p, m, last=False):
    if p == m:
        return "같음" if last else "같고"
    if last:
        return "높음" if p > m else "낮음"
    return "높고" if p > m else "낮고"


# ---------------------------------------------------------------------------
# 5.2 신호 B: 실적 흐름
# ---------------------------------------------------------------------------

def _pct(now, before):
    return (now / before - 1) * 100


def signal_earnings(ind, fin):
    """최근 6개월(2개 분기 합)과 1년 전 같은 6개월의 영업이익(금융업 외에는 매출도)으로 판정한다."""
    half = easy_read.half_year(fin)
    finance = easy_read.is_finance(ind, fin)
    base = {"금융업": finance}
    if not half:
        return {**base, "판정": UNKNOWN, "근거": "공시된 분기 자료가 부족해 판정하지 못했습니다", "사유": "분기 자료 부족"}
    op_now, op_before = half["영업이익"]
    s_now, s_before = half["매출액"]
    if op_now is None or op_before is None:
        return {**base, "판정": UNKNOWN, "근거": "영업이익 자료가 부족해 판정하지 못했습니다", "사유": "영업이익 없음"}
    sales_pct = None
    if not finance:
        if s_now is None or s_before is None or s_before <= 0:
            return {**base, "판정": UNKNOWN, "근거": "매출 자료가 부족해 판정하지 못했습니다", "사유": "매출 비교 불가"}
        sales_pct = _pct(s_now, s_before)
    sales_ok = finance or sales_pct >= SALES_FLOOR

    if op_before > 0 and op_now > 0:
        op_pct = _pct(op_now, op_before)
        if op_pct >= EARN_PCT and sales_ok:
            verdict = BETTER
        elif op_pct <= -EARN_PCT:
            verdict = WORSE
        else:
            verdict = FLAT
        change = growth_text(op_now, op_before)
    elif op_before < 0 and op_now < 0:                 # 두 기간 모두 영업적자: 적자 폭
        loss_pct = _pct(abs(op_now), abs(op_before))
        verdict = BETTER if loss_pct <= -EARN_PCT else (WORSE if loss_pct >= EARN_PCT else FLAT)
        op_pct = None
        change = f"1년 전 {eok(op_before)}보다 적자 폭 " + (
            f"{abs(op_now) / abs(op_before):,.1f}배로 확대" if loss_pct >= 100
            else f"{abs(loss_pct):.1f}% {'축소' if loss_pct < 0 else '확대'}")
    elif op_before <= 0 < op_now:                      # 적자 -> 흑자
        verdict = BETTER if sales_ok else FLAT
        op_pct = None
        change = f"1년 전 {eok(op_before)}에서 흑자 전환"
    else:                                              # 흑자 -> 적자(또는 0)
        verdict = WORSE
        op_pct = None
        change = f"1년 전 {eok(op_before)}에서 적자 전환"
    evidence = f"최근 6개월 영업이익 {eok(op_now)}, {change}"
    if not finance and verdict == FLAT and op_pct is not None and op_pct >= EARN_PCT and not sales_ok:
        evidence += f"(매출 {abs(sales_pct):.1f}% 감소로 개선 조건 미충족)"
    return {**base, "판정": verdict, "근거": evidence, "기간": half["기간"],
            "영업이익": (op_now, op_before), "매출액": (s_now, s_before),
            "영업이익증감률": op_pct, "매출증감률": sales_pct}


# ---------------------------------------------------------------------------
# 5.3 신호 C: 거래 관심도
# ---------------------------------------------------------------------------

def signal_volume(ind):
    ratio = (ind.get("거래량") or {}).get("거래량비율_5일대60일")
    if ratio is None:
        return {"판정": UNKNOWN, "근거": "거래량 자료가 부족합니다", "배수": None}
    verdict = HOT if ratio >= VOL_HOT else (COLD if ratio <= VOL_COLD else NORMAL)
    return {"판정": verdict, "근거": f"최근 5일 거래량이 최근 3개월 평균의 {ratio:.2f}배", "배수": ratio}


# ---------------------------------------------------------------------------
# 5.4 종합 상태
# ---------------------------------------------------------------------------

def overall_state(a, b, c):
    if a is None:
        return "가격 추세 판정 불가"
    if b["판정"] == UNKNOWN:
        name = f"{a['판정']} 구간 (실적 판정 불가)"
    else:
        name = STATE_TABLE[(a["판정"], b["판정"])]
    tag = VOLUME_TAG.get(c["판정"])
    return f"{name} {tag}" if tag else name


# ---------------------------------------------------------------------------
# 5.5 반전 조건
# ---------------------------------------------------------------------------

def price_transitions(a):
    """신호 A의 현재 판정에서 다른 판정으로 가는 가격 조건을 모두 계산한다.

    반환: [{"목표", "방향"(위/아래), "가격", "거리", "순서조건"(문구|None), "순서만", "문구", "변화문구"}]
    MA60·MA120은 기준일 값으로 고정해 계산한다.
    """
    p, m60, m120 = a["현재가"], a["MA60"], a["MA120"]
    hi, lo = max(m60, m120), min(m60, m120)
    order_up = None if m60 > m120 else ORDER_UP          # 상승 추세에 필요한 순서
    order_down = None if m60 < m120 else ORDER_DOWN      # 하락 추세에 필요한 순서
    out = []

    def add(target, direction, price, order):
        to = f"{target}{easy_read.josa(target, '으로', '로')} 바뀜"
        pct = dist_pct(price, p)
        # 가격 조건은 이미 충족했고 평균선 순서만 남은 경우(지침 5.5): 거리 = 두 평균의 차이(%)
        met = (direction == "위" and p > price) or (direction == "아래" and p < price)
        if met and order:
            side = "위" if direction == "위" else "아래"
            gap = abs(m120 / m60 - 1) * 100            # 3개월 평균이 6개월 평균까지 움직여야 하는 폭
            verb = "넘으면" if direction == "위" else "아래로 내려가면"
            verb2 = "넘어" if direction == "위" else "아래로 내려가"
            out.append({"목표": target, "방향": direction, "가격": price, "거리값": gap,
                        "거리": f"두 평균의 차이 {gap:.1f}%", "순서조건": order, "순서만": True,
                        "문구": f"주가는 이미 두 평균 {side}에 있고, 3개월 평균({m60:,}원)이 "
                                f"6개월 평균({m120:,}원)을 {verb} {target}",
                        "변화문구": f"3개월 평균({m60:,}원)이 6개월 평균({m120:,}원)을 {verb2} {to}"
                                    f"(주가는 이미 두 평균 {side})"})
            return
        if direction == "위":
            cond = f"{price:,}원 위로 올라서"
            cond += f"고 {order.replace('넘어서야 합니다', '넘으면')}" if order else "면"
        else:
            cond = f"{price:,}원 아래로 내려가"
            cond += f"고 {order.replace('내려가야 합니다', '내려가면')}" if order else "면"
        dist = dist_text(pct) + (" + 평균선 순서 변화" if order else "")
        move = "위로 올라서" if direction == "위" else "아래로 내려가"
        if order:
            tail = order.replace("넘어서야 합니다", "넘어").replace("내려가야 합니다", "내려가")
            change = f"주가가 {price:,}원 {move}고 {tail} {to}"
        else:
            change = f"주가가 {price:,}원 {move}며 {to}"
        out.append({"목표": target, "방향": direction, "가격": price, "거리값": pct, "거리": dist,
                    "순서조건": order, "순서만": False, "문구": f"{cond} {target}", "변화문구": change})

    if a["판정"] == SIDE:
        add(UP, "위", hi, order_up)
        add(DOWN, "아래", lo, order_down)
    elif a["판정"] == UP:
        add(SIDE, "아래", hi, None)                     # 두 평균 중 높은 쪽(MA60) 아래면 상승 조건이 깨진다
        add(DOWN, "아래", lo, order_down)
    else:
        add(SIDE, "위", lo, None)                       # 두 평균 중 낮은 쪽(MA60) 위면 하락 조건이 깨진다
        add(UP, "위", hi, order_up)
    return out


def _next_quarter(key):
    y, q = map(int, str(key).split("Q"))
    return (y + 1, 1) if q == 4 else (y, q + 1)


def earnings_boundaries(fin, b):
    """다음 분기의 1년 전 같은 분기 영업이익을 기준으로 개선·악화 경계 금액을 계산한다(지침 v1.3 5.2·5.5).

    유형
     - 배수(1년 전 흑자)              : 개선 = 1년 전 x 1.1 초과, 악화 = 1년 전 x 0.9 미만
     - 흑자 유지(1년 전 적자, 최근 분기 흑자): 경계 = 0원. 흑자 유지면 개선 쪽, 적자 전환이면 악화 쪽
     - 적자 폭(1년 전 적자, 최근 분기도 적자): 적자가 1년 전 x 0.9보다 작으면 개선 쪽, 1년 전 x 1.1보다 크면 악화 쪽
    """
    if b["판정"] == UNKNOWN:
        return None
    recent = (fin or {}).get("분기") or []
    if not recent:
        return None
    ny, nq = _next_quarter(recent[-1]["분기"])
    ago_key = f"{ny - 1}Q{nq}"
    ago = next((x for x in recent + ((fin or {}).get("직전분기") or []) if x["분기"] == ago_key), None)
    base = ago.get("영업이익") if ago else None
    last = recent[-1].get("영업이익")
    if base is None:
        return None
    if base > 0:
        kind, better, worse = BOUND_RATIO, base * 1.1, base * 0.9
    elif last is not None and last > 0:
        kind, better, worse = BOUND_ZERO, 0.0, 0.0
    else:                           # 적자 폭 10% 축소가 개선, 10% 확대가 악화(5.2 적자 규칙)
        kind, better, worse = BOUND_LOSS, base * 0.9, base * 1.1
    return {"분기": f"{ny}년 {nq}분기", "분기키": f"{ny}Q{nq}", "1년전": base, "1년전분기": easy_read.quarter_kr(ago_key),
            "최근분기": easy_read.quarter_kr(recent[-1]["분기"]), "최근분기영업이익": last,
            "유형": kind, "개선경계": better, "악화경계": worse}


def earnings_conditions(bounds):
    """반전 조건 표 문구 {개선, 악화} (유형별 문구, 지침 v1.3 5.5)."""
    q, base = bounds["분기"], bounds["1년전"]
    if bounds["유형"] == BOUND_RATIO:
        return {BETTER: f"{q} 영업이익이 {eok(bounds['개선경계'])}(1년 전 {eok(base)}의 1.1배)을 넘으면 개선 쪽 근거",
                WORSE: f"{q} 영업이익이 {eok(bounds['악화경계'])}(1년 전 {eok(base)}의 0.9배)에 못 미치면 악화 쪽 근거"}
    if bounds["유형"] == BOUND_ZERO:
        tail = f"(경계 0원, 1년 전 {eok(base)})"
        return {BETTER: f"{q} 영업이익이 흑자를 유지하면{tail} 개선 쪽 근거",
                WORSE: f"{q} 영업이익이 적자로 돌아서면{tail} 악화 쪽 근거"}
    loss = eok(abs(base))
    return {BETTER: f"{q} 영업적자가 {eok(abs(bounds['개선경계']))}보다 작으면(1년 전 적자 {loss}에서 10% 이상 축소) 개선 쪽 근거",
            WORSE: f"{q} 영업적자가 {eok(abs(bounds['악화경계']))}보다 크면(1년 전 적자 {loss}에서 10% 이상 확대) 악화 쪽 근거"}


def reversal_table(a, b, bounds):
    """표 행: {"신호", "지금 판정", "바뀌는 조건", "지금과의 거리"}.

    정렬(지침 v1.3 5.5): 가격 조건만으로 바뀌는 행 -> 평균선 순서 변화가 함께 필요한 행(순서만 남은 행 포함),
    각 무리 안에서는 거리가 가까운 순서. 실적 행은 거리 숫자가 없으므로 맨 뒤.
    """
    rows = []
    if a:
        trans = sorted(price_transitions(a), key=lambda x: (x["순서조건"] is not None, abs(x["거리값"])))
        for t in trans:
            rows.append({"신호": "가격 추세", "지금 판정": a["판정"], "바뀌는 조건": t["문구"],
                         "지금과의 거리": t["거리"], "거리값": abs(t["거리값"]), "순서조건": t["순서조건"]})
    if bounds:
        texts = earnings_conditions(bounds)
        conds = {BETTER: [texts[WORSE]], WORSE: [texts[BETTER]], FLAT: [texts[BETTER], texts[WORSE]]}[b["판정"]]
        for cond in conds:
            rows.append({"신호": "실적 흐름", "지금 판정": b["판정"], "바뀌는 조건": cond,
                         "지금과의 거리": "다음 분기 공시", "거리값": None, "순서조건": None})
    return rows


# ---------------------------------------------------------------------------
# 5.6 사건 선정과 근거 강도
# ---------------------------------------------------------------------------

# 5.6 방향 확인: 사건 방향과 반대 방향의 말
OPPOSITE_WORDS = {1: ("하락", "약세", "급락", "내림"), -1: ("상승", "강세", "급등", "오름")}
# v1.3: 방향어 바로 앞에 이 말이 있으면 지수·시장 이야기(종목 이야기가 아님)
MARKET_WORDS = ("코스피", "코스닥", "지수", "증시", "시장", "업종")


def opposite_word(title, move):
    """[특징주] 제목에 사건(move 부호)과 반대 방향의 말이 있으면 그 말, 없으면 None.

    방향어 바로 앞(공백만 사이에 둔 경우 포함)에 코스피·코스닥·지수·증시·시장·업종이 있으면 건너뛴다.
    """
    sign = 1 if move > 0 else -1
    for word in OPPOSITE_WORDS[sign]:
        for m in re.finditer(re.escape(word), title):
            if title[:m.start()].rstrip().endswith(MARKET_WORDS):
                continue
            return word
    return None


def evidence_strength(ev, name="", others=()):
    """사건의 근거 강도(지침 5.6 표 + 방향 확인). 반환: (강도, 방향확인 문구|None)"""
    reps = ev.get("대표이벤트") or []
    article = next((r for r in reps if r.get("역할") == "원인 기사"), None)
    if ev.get("판정") == "강한 공시":
        return STRONG, None
    if article and article.get("선정") == "특징주":
        word = opposite_word(article["제목"], ev["누적초과등락률"])
        if word is None:
            return STRONG, None
        import events as ev_mod                       # 반대 방향 [특징주]: 그 기사의 키워드 점수로 다시 판정
        score = ev_mod.article_score(ev, article["제목"], name, others)
        return (MEDIUM if score > 0 else WEAK), f"[특징주] 제목의 '{word}'{easy_read.josa(word, '이', '가')} 사건 방향과 반대(키워드 {score})"
    if article:
        m = re.match(r"키워드 (\d+)", article.get("선정") or "")
        return (MEDIUM if (m and int(m.group(1)) > 0) else WEAK), None
    if ev.get("판정") in ("약한 연결", "매칭됨"):     # 약한 공시·보통 공시만 있고 기사가 없음
        return WEAK, None
    return NONE, None


def select_events(events):
    """공시 기반 사건을 포함한 모든 사건을 |누적 초과 등락률| 큰 순서로 최대 5개(우선권 없음, 3% 미만 제외).

    반환: 기간 순으로 정렬하고 번호(①~⑤)를 붙인 사건 목록. 5개가 안 되면 있는 만큼만.
    """
    pool = [e for e in ((events or {}).get("사건") or []) if abs(e["누적초과등락률"]) >= EVENT_MIN_PCT]
    chosen = sorted(pool, key=lambda e: -abs(e["누적초과등락률"]))[:EVENT_MAX]
    chosen.sort(key=lambda e: e["시작일"])
    name, others = (events or {}).get("종목명", ""), (events or {}).get("동명회사") or []
    out = []
    for i, ev in enumerate(chosen):
        strength, check = evidence_strength(ev, name, others)
        reps = ev.get("대표이벤트") or []
        disc_rep = next((r for r in reps if r["종류"] == "공시"), None)
        news_rep = next((r for r in reps if r["종류"] == "뉴스"), None)
        out.append({
            "번호": "①②③④⑤"[i], "시작일": ev["시작일"], "종료일": ev["종료일"], "유형": ev.get("유형", "급변"),
            "기간": ev["시작일"] if ev["시작일"] == ev["종료일"] else f"{ev['시작일']}~{ev['종료일']}",
            "누적등락률": ev["누적등락률"], "누적초과등락률": ev["누적초과등락률"],
            "누적등락": f"{ev['누적등락률']:+.2f}% (시장 대비 {ev['누적초과등락률']:+.2f}%)",
            "대표공시": f"{disc_rep['날짜']} {disc_rep['제목']}" if disc_rep else "-",
            "대표기사": f"{news_rep['날짜']} {news_rep['제목']}" if news_rep else "-",
            "근거강도": strength, "방향확인": check, "판정": ev.get("판정"),
        })
    return out


def market_days_sentence(events):
    n = len((events or {}).get("시장전체움직임") or [])
    return f"지난 1년 중 {n}일은 종목 자체보다 시장 전체 흐름으로 크게 움직였습니다."


# ---------------------------------------------------------------------------
# 5.7 다음 확인 시점
# ---------------------------------------------------------------------------

def latest_periodic(events, fin=None):
    """DART 공시목록에서 이미 공시된 가장 늦은 정기보고서 분기 (연, 분기, 제목).

    공시목록에 정기보고서가 없으면 재무 자료의 마지막 분기(정기보고서에서 읽은 값)로 대신한다.
    """
    found = []
    for d in ((events or {}).get("공시") or {}).get("목록") or []:
        m = PERIODIC_RE.search(d["제목"])
        if m:
            found.append((int(m.group(2)), (int(m.group(3)) - 1) // 3 + 1, d["제목"]))
    if found:
        return max(found)
    recent = (fin or {}).get("분기") or []
    if recent:
        y, q = map(int, recent[-1]["분기"].split("Q"))
        return y, q, "재무 자료 마지막 분기"
    return None


def next_check(base_date, events=None, fin=None):
    """정기보고서가 아직 공시되지 않은 가장 이른 분기와 그 제출 기한(지침 5.7)."""
    last = latest_periodic(events, fin)
    if last is None:
        return {"분기": None, "기한": None, "문장": "공시된 자료가 부족해 다음 확인 시점을 계산하지 못했습니다.",
                "잠정실적이력": False, "근거": None}
    y, q = (last[0] + 1, 1) if last[1] == 4 else (last[0], last[1] + 1)
    m, d = QUARTER_END[q]
    due = date(y, m, d) + timedelta(days=REPORT_DAYS[q])
    label = f"{y}년 연간(4분기 포함)" if q == 4 else f"{y}년 {q}분기"
    sentence = f"{label} 실적은 {easy_read.date_kr(due.isoformat())} 전후로 공시될 예정입니다(정기보고서 제출 기한 기준)."
    prelim = False
    for d in ((events or {}).get("공시") or {}).get("목록") or []:
        if "잠정" in d["제목"] and "실적" in d["제목"]:
            prelim = True
            break
    if prelim:
        sentence += " 이 회사는 정기보고서보다 먼저 잠정실적을 공시해 왔습니다."
    return {"분기": label, "기한": due.isoformat(), "문장": sentence, "잠정실적이력": prelim,
            "근거": f"공시된 마지막 정기보고서: {last[2]}"}


# ---------------------------------------------------------------------------
# 5.8 시나리오
# ---------------------------------------------------------------------------

def _scenario_earnings(bounds):
    """시나리오 실적 조건 (상방, 기본, 하방). 기본은 경계 사이(경계가 0원 하나면 없음)."""
    if not bounds:
        return None, None, None
    q = bounds["분기"]
    if bounds["유형"] == BOUND_RATIO:
        return (f"{q} 영업이익 {eok(bounds['개선경계'])} 초과(실적 개선 쪽)",
                f"{q} 영업이익이 {eok(bounds['악화경계'])}~{eok(bounds['개선경계'])} 사이",
                f"{q} 영업이익 {eok(bounds['악화경계'])} 미만(실적 악화 쪽)")
    if bounds["유형"] == BOUND_ZERO:
        return (f"{q} 영업이익 흑자 유지(실적 개선 쪽)", None, f"{q} 영업이익 적자 전환(실적 악화 쪽)")
    small, large = eok(abs(bounds["개선경계"])), eok(abs(bounds["악화경계"]))
    return (f"{q} 영업적자 {small} 미만(실적 개선 쪽)", f"{q} 영업적자가 {small}~{large} 사이",
            f"{q} 영업적자 {large} 초과(실적 악화 쪽)")


def scenarios(a, b, bounds):
    """상방 / 기본 / 하방. 확률·목표 가격·기간 예측은 넣지 않는다."""
    if a is None:
        return []
    trans = {t["목표"]: t for t in price_transitions(a)}
    p = a["현재가"]
    earn_up, earn_mid, earn_down = _scenario_earnings(bounds)
    earn_dist = "다음 분기 공시" if bounds else None

    def join(price_cond, earn_cond):
        return price_cond + (f" + {earn_cond}" if earn_cond else "")

    def dist(price_dist, earn_cond):
        return price_dist + (f" / 실적: {earn_dist}" if earn_cond else "")

    verdict = a["판정"]
    hi, lo = max(a["MA60"], a["MA120"]), min(a["MA60"], a["MA120"])
    # 상방
    if verdict == UP:
        up = ("상승 추세 유지(주가가 " + f"{hi:,}원 위)", "지금 충족")
    else:
        t = trans[UP if verdict == SIDE else SIDE]
        up = (t["변화문구"], t["거리"])
    # 하방
    if verdict == DOWN:
        down = ("하락 추세 유지(주가가 " + f"{lo:,}원 아래)", "지금 충족")
    else:
        t = trans[DOWN if verdict == SIDE else SIDE]
        down = (t["변화문구"], t["거리"])
    # 기본: 지금 판정 유지
    order_only = next((t for t in trans.values() if t["순서만"]), None)
    if verdict == SIDE and order_only:      # 가격 조건은 충족, 평균선 순서만 남음(지침 5.8)
        base = ("평균선 순서가 바뀌기 전까지 방향 탐색 유지", order_only["거리"])
    elif verdict == SIDE:
        base = (f"주가가 {lo:,}원~{hi:,}원 사이에 머물러 방향 탐색 유지", "지금 범위 안")
    elif verdict == UP:
        base = (f"주가가 {hi:,}원 위에 머물러 상승 추세 유지", f"경계까지 {dist_text(dist_pct(hi, p))}")
    else:
        base = (f"주가가 {lo:,}원 아래에 머물러 하락 추세 유지", f"경계까지 {dist_text(dist_pct(lo, p))}")
    return [
        {"시나리오": "상방", "발동 조건": join(up[0], earn_up), "지금 상태에서의 거리": dist(up[1], earn_up)},
        {"시나리오": "기본", "발동 조건": join(base[0], earn_mid), "지금 상태에서의 거리": dist(base[1], earn_mid)},
        {"시나리오": "하방", "발동 조건": join(down[0], earn_down), "지금 상태에서의 거리": dist(down[1], earn_down)},
    ]


# ---------------------------------------------------------------------------
# 5.9 핵심 긴장 문장
# ---------------------------------------------------------------------------

def _earnings_stem(b):
    """실적 숫자 표현(연결어미를 붙일 어간). 반환: (어간, 실적 숫자 표시 문자열)

    예: ('최근 6개월 영업이익은 1년 전보다 56.5% 줄었', '56.5%') / ('… 1년 전의 12.9배로 늘었', '12.9배')
    """
    now, before = b["영업이익"]
    if before > 0 and now > 0:
        pct = _pct(now, before)
        if pct >= 100:
            num = f"{now / before:,.1f}배"
            return f"최근 6개월 영업이익은 1년 전의 {num}로 늘었", num
        num = f"{abs(pct):.1f}%"
        return f"최근 6개월 영업이익은 1년 전보다 {num} {'늘었' if pct > 0 else '줄었'}", num
    if before < 0 and now < 0:
        loss = _pct(abs(now), abs(before))
        if loss >= 100:
            num = f"{abs(now) / abs(before):,.1f}배"
            return f"최근 6개월 영업적자는 1년 전의 {num}로 커졌", num
        num = f"{abs(loss):.1f}%"
        return f"최근 6개월 영업적자는 1년 전보다 {num} {'줄었' if loss < 0 else '커졌'}", num
    num = eok(now)
    if before <= 0 < now:
        return f"최근 6개월 영업이익은 {num}으로 1년 전 적자에서 흑자로 돌아섰", num
    return f"최근 6개월 영업이익은 {num}으로 1년 전 흑자에서 적자로 돌아섰", num


def tension_sentence(a, b):
    """결론 1문장의 뼈대(지침 v1.3 5.9). AI는 숫자를 바꾸지 않고 문장만 다듬는다.

    반환: {"조합", "뼈대", "실적 숫자", "가격 숫자"} 또는 None(가격 추세·이격도 없음)
    """
    if a is None or a.get("MA120_이격도") is None:
        return None
    gap = a["MA120_이격도"]
    if a["판정"] == SIDE:                                # v1.4: 방향 탐색은 추세가 없다는 표현 + 이격도(부호 포함)
        price_num = f"{gap:+.2f}%"
        price = f"아직 뚜렷한 추세를 만들지 못했습니다(최근 6개월 평균 대비 {price_num})"
    elif round(gap, 2) == 0:
        price, price_num = "최근 6개월 평균과 같습니다", None
    else:
        price_num = f"{easy_read.rate2(gap)}%"
        price = f"최근 6개월 평균보다 {price_num} {'높습니다' if gap > 0 else '낮습니다'}"
    if b["판정"] == UNKNOWN:
        return {"조합": "실적 판정 불가", "뼈대": f"주가는 {price}", "실적 숫자": None, "가격 숫자": price_num}
    stem, earn_num = _earnings_stem(b)
    pair = (a["판정"], b["판정"])
    if FLAT in pair:
        kind, text = "보합 포함", f"{stem}고, 주가는 {price}"
    elif pair in ((UP, BETTER), (DOWN, WORSE)):
        kind, text = "방향이 같음", f"{stem}고, 주가도 {price}"
    else:
        kind, text = "방향이 엇갈림", f"{stem}지만, 주가는 {price}"
    return {"조합": kind, "뼈대": text, "실적 숫자": earn_num, "가격 숫자": price_num}


# ---------------------------------------------------------------------------
# 5.10 실적 해설 입력
# ---------------------------------------------------------------------------

def _yoy_phrase(now, before, sales=False):
    """같은 분기 1년 전 대비 표현(완결 서술어). 부호가 다르면 None(전환 시점으로 읽히지 않게 따로 쓴다)."""
    if now is None or before is None:
        return None
    if before > 0 and (now > 0 or (sales and now == 0)):
        if round(now, -8) == round(before, -8):
            return "같았습니다"
        return easy_read.change_phrase(now, before, sales=sales)
    return None


def _state_word(value):
    return "흑자" if value > 0 else "적자"


def turn_facts(fin):
    """최근 8개 분기 영업이익 부호가 바뀐 분기마다 사실 문장(지침 v1.4 5.10).

    반환: [{"분기": '2025Q4', "방향": '적자에서 흑자로', "문장": …}] (바뀐 적이 없으면 빈 목록)
    """
    items = [x for x in ((fin or {}).get("직전분기") or []) + ((fin or {}).get("분기") or [])
             if x.get("영업이익") is not None and x["영업이익"] != 0]
    out = []
    for prev, cur in zip(items, items[1:]):
        if (prev["영업이익"] > 0) != (cur["영업이익"] > 0):
            way = "적자에서 흑자로" if cur["영업이익"] > 0 else "흑자에서 적자로"
            out.append({"분기": cur["분기"], "방향": way,
                        "문장": f"영업이익은 {easy_read.quarter_kr(cur['분기'])}에 {way} 바뀌었습니다."})
    return out


FLOW_WORDS = {1: ("늘었", "증가했"), -1: ("줄었", "감소했"), 0: ("같았", "같았")}
FLOW_RUN = 3                    # 같은 방향이 이 개수 이상 이어져야 '연속'


def flow_facts(fin):
    """분기 흐름 사실(지침 v1.5 5.10): 최근 4개 분기의 직전 분기 대비 매출·영업이익 방향.

    예: "매출은 2025년 3분기에 늘었고, 2025년 4분기·2026년 1분기에 줄었고, 2026년 2분기에 늘었습니다."
        같은 방향 3개 분기 이상: "영업이익은 2025년 4분기~2026년 2분기에 3개 분기 연속 감소했습니다."
    반환: {"문장": [문장], "연속": bool(어느 문장에든 '연속'이 있는가), "방향": {계정: [(분기, -1/0/1)]}}
    """
    items = ((fin or {}).get("직전분기") or [])[-1:] + ((fin or {}).get("분기") or [])
    out, dirs = [], {}
    for key, name in (("매출액", "매출"), ("영업이익", "영업이익")):
        steps = []
        for prev, cur in zip(items, items[1:]):
            a, b = prev.get(key), cur.get(key)
            if a is None or b is None:
                steps = []
                break
            diff = round(b / 1e8) - round(a / 1e8)              # 억 원 단위로 비교(표시 값과 같은 기준)
            steps.append((cur["분기"], (diff > 0) - (diff < 0)))
        if not steps:
            continue
        dirs[name] = steps
        runs = []
        for q, sign in steps:
            if runs and runs[-1][1] == sign:
                runs[-1][0].append(q)
            else:
                runs.append(([q], sign))
        clauses = []
        for quarters, sign in runs:
            if len(quarters) >= FLOW_RUN and sign != 0:
                span = f"{easy_read.quarter_kr(quarters[0])}~{easy_read.quarter_kr(quarters[-1])}"
                clauses.append(f"{span}에 {len(quarters)}개 분기 연속 {FLOW_WORDS[sign][1]}")
            else:
                clauses.append("·".join(easy_read.quarter_kr(q) for q in quarters) + f"에 {FLOW_WORDS[sign][0]}")
        body = "고, ".join(clauses) + "습니다."
        out.append(f"{name}{easy_read.josa(name, '은', '는')} {body}")
    return {"문장": out, "연속": any("연속" in s for s in out), "방향": dirs}


def season_verdict(fin, finance=False):
    """계절성 판정(지침 v1.4 5.10): 직전 완결된 2개 연도의 분기별 매출(금융업은 영업이익) 최고 분기 비교.

    반환: {"판정", "표시", "문장", "연도", "최고분기": {연도: N}, "사유"}
    """
    years = (fin or {}).get("계절성연도") or {}
    key, label = ("영업이익", "영업이익") if finance else ("매출액", "매출")
    josa = easy_read.josa(label, "이", "가")
    peaks, reason = {}, None
    for year in sorted(years):
        qs = years[year]
        values = {int(x["분기"][-1]): x.get(key) for x in qs}
        if sorted(values) != [1, 2, 3, 4] or any(v is None for v in values.values()):
            reason = f"{year}년 분기 {label} 자료가 모두 있지 않아"
            break
        peaks[year] = max(values, key=values.get)
    ys = sorted(years)
    span = "년과 ".join(str(y) for y in ys) + "년" if ys else "직전 2개 연도"
    if len(ys) != 2 and reason is None:
        reason = "직전 완결된 2개 연도 자료가 없어"
    if reason is None and len(set(peaks.values())) == 1:
        n = next(iter(peaks.values()))
        return {"판정": SEASONAL, "표시": f"계절성 있음: {n}분기 {label}{josa} 연중 가장 많습니다",
                "문장": f"{span} 모두 {n}분기 {label}{josa} 연중 가장 많아 계절성이 있습니다.",
                "연도": ys, "최고분기": peaks, "분기": n, "사유": None}
    if reason is None:
        detail = ", ".join(f"{y}년 {q}분기" for y, q in peaks.items())
        reason = f"연중 {label} 최고 분기가 {detail}로 달라"
    return {"판정": SEASON_UNKNOWN, "표시": SEASON_UNKNOWN,
            "문장": f"{span} {reason} 계절성은 판단할 수 없습니다." if "자료" not in reason
                    else f"{reason} 계절성은 판단할 수 없습니다.",
            "연도": ys, "최고분기": peaks, "분기": None, "사유": reason}


def earnings_story_input(fin, ind=None):
    """최근 8개 분기 표, 같은 분기 1년 전 비교, 흑자·적자 전환 사실, 계절성 판정(지침 v1.4 5.10).

    반환: {"분기표": [행], "비교사실": [문장], "전환사실": [dict], "계절성": 판정, "계절성표시", "계절성문장", …}
    """
    recent, prior = (fin or {}).get("분기") or [], (fin or {}).get("직전분기") or []
    items = prior + recent
    rows = []
    for x in items:
        parts = []
        if x.get("매출액") is not None:
            parts.append(f"매출 {eok(x['매출액'])}")
        if x.get("영업이익") is not None:
            parts.append(f"영업이익 {eok(x['영업이익'])}")
        if x.get("매출액") and x.get("영업이익") is not None:
            parts.append(f"영업이익률 {x['영업이익'] / x['매출액'] * 100:.1f}%")
        rows.append(f"{easy_read.quarter_kr(x['분기'])}: " + (", ".join(parts) or "자료 없음"))

    facts, yoy_flips = [], set()
    by_key = {x["분기"]: x for x in items}
    for x in recent:
        y, q = map(int, x["분기"].split("Q"))
        ago = by_key.get(f"{y - 1}Q{q}")
        if not ago:
            continue
        label = easy_read.quarter_kr(x["분기"])
        for key, name in (("매출액", "매출"), ("영업이익", "영업이익")):
            now, before = x.get(key), ago.get(key)
            if now is None or before is None:
                continue
            head = f"{label} {name}은 {eok(now)}"
            phrase = _yoy_phrase(now, before, sales=(key == "매출액"))
            if phrase == "같았습니다":
                facts.append(f"{head}으로, 1년 전 같은 분기({eok(before)})와 같았습니다.")
            elif phrase:
                facts.append(f"{head}으로, 1년 전 같은 분기({eok(before)})보다 {phrase}.")
            elif key == "영업이익":             # 부호가 다른(또는 둘 다 적자인) 같은 분기 비교: 상태만 적는다
                both = (now > 0) == (before > 0)
                if not both:
                    yoy_flips.add((x["분기"], "적자에서 흑자로" if now > 0 else "흑자에서 적자로"))
                facts.append(f"{head}이고, 1년 전 같은 분기({eok(before)}){'도' if both else '는'} "
                             f"{_state_word(before)}였습니다.")

    finance = easy_read.is_finance(ind or {}, fin) if fin else False
    season = season_verdict(fin, finance)
    flow = flow_facts(fin)
    return {"분기표": rows, "비교사실": facts, "전환사실": turn_facts(fin), "전년부호전환": yoy_flips,
            "흐름사실": flow["문장"], "흐름연속": flow["연속"],
            "계절성": season["판정"], "계절성표시": season["표시"], "계절성문장": season["문장"],
            "계절성분기": season["분기"], "계절성연도": season["연도"], "계절성최고분기": season["최고분기"],
            "계절성사유": season["사유"], "계절성기준": "영업이익" if finance else "매출"}


# ---------------------------------------------------------------------------
# 전체
# ---------------------------------------------------------------------------

def indicator(ind, fin):
    """방향 지시계만(앱 상단 박스용, 사건 데이터 없이 계산)."""
    a = signal_price(ind)
    b = signal_earnings(ind, fin)
    c = signal_volume(ind)
    return {"가격 추세": a, "실적 흐름": b, "거래 관심도": c, "종합 상태": overall_state(a, b, c)}


def build(ind, fin, events=None):
    """5.1~5.10 전부. events: events.build_events 결과(없으면 사건·잠정실적 이력은 비운다)."""
    box = indicator(ind, fin)
    a, b = box["가격 추세"], box["실적 흐름"]
    bounds = earnings_boundaries(fin, b)
    return {
        "버전": REPORT_GUIDE_VERSION,
        "기준일": ind["기준일"],
        **box,
        "반전조건": reversal_table(a, b, bounds),
        "실적경계": bounds,
        "사건": select_events(events),
        "시장전체문장": market_days_sentence(events) if events else None,
        "확인시점": next_check(ind["기준일"], events, fin),
        "시나리오": scenarios(a, b, bounds),
        "핵심긴장": tension_sentence(a, b),
        "실적해설입력": earnings_story_input(fin, ind),
    }
