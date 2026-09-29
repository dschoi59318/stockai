# -*- coding: utf-8 -*-
"""
easy_read.py - '쉽게 읽기' 섹션 (docs/쉽게읽기_작성지침.md v1.2를 그대로 코드화)

원칙 (지침 2장)
 - AI를 쓰지 않는다. 파이썬이 지침의 문장 틀에 숫자를 채운다. 같은 입력이면 항상 같은 문장이 나온다.
 - 이 파일의 문장 틀·용어 풀이·금지 표현·데이터 없음 문장은 지침 문서가 기준이다.
   문장을 바꾸려면 지침 문서를 먼저 고치고 버전을 올린 뒤 이 파일에 반영한다.
 - EASY_READ_GUIDE_VERSION은 지침 문서의 버전과 같아야 한다(리포트 출처 페이지에 표시).

구성 (지침 4장, 8개 장 + 10장 숫자 풀이 표)
 0 이 회사는 어떤 회사인가요? / 1 지금 주가는 1년 중 어디쯤인가요?(52주 범위 막대)
 2 최근 주가는 어떻게 움직였나요?(수익률 막대 3개) / 3 회사는 돈을 벌고 있나요?
 4 회사의 빚은 어느 정도인가요? / 5 주가와 회사 이익을 함께 보면? / 6 앞으로 지켜볼 숫자 3가지 / 7 한 줄 정리

v1.1 반영(지침 13장 변경 이력)
 - 3장 금액·판정 문장 분리, 흑자/적자 괄호 풀이, 새 계산 증감률 소수 첫째 자리, 100% 이상 증가는 배수 표현,
   전환 문장은 1년 전 같은 분기 기준, 금융업 3장 기간 표기
 - 4장 금융업 문장 '크게'→'높게', 원 단위 값 천 단위 쉼표 / 5장 5문장·안내 문장 교체
 - 6장 항목 단축·합쇼체, 금융업 1번 항목, 이격도 0% 문장 / 7장 배수·부호 변화·금융업·상장 1년 미만 변형
 - 1장 상장 1년 미만·최고/최저 같음 문장, 2장 0% 문장과 연결어 규칙 / 9장 일부 문장만 대체
 - 11장 체크리스트 9번(용어 첫 등장 괄호 풀이, 5장 예외)·10번(합쇼체) 추가
v1.2 반영(지침 13장 변경 이력)
 - 첫 등장 괄호 풀이는 코드가 섹션 전체를 앞에서부터 훑어 동적으로 붙인다(apply_gloss).
   장별 함수는 지침 문장 틀 그대로(풀이 포함) 문장을 만들고, apply_gloss가 풀이를 모두 뗀 뒤
   섹션에서 처음 나오는 자리에만 다시 붙인다. 5장 주가수익비율·주가순자산비율은 예외,
   '회사 전체 가격(시가총액)' 형태는 풀이가 붙은 것으로 본다.
 - '최근 6개월 평균 주가' 용어표에서 제거 / 금융업 3장 끝 문장 교체('매출' 제거)
 - 3장 영업이익 부호 전환 대체 문장에 괄호 풀이 추가, 매출 전년 0 이하 문장 확정
 - 7장 금융업 영업이익 부호 전환 문구, 5장 짝 문장 데이터 없음(2문장 → 고정 문장 1문장) 확정
 한 문장 글자 수는 공백을 포함해 세고, 괄호와 괄호 안 글자는 뺀다(지침 3장).
"""

import math
import re

EASY_READ_GUIDE_VERSION = "v1.2"

# 지침 4장: 장 제목(질문형, 고정)과 순서
CHAPTER_TITLES = [
    "이 회사는 어떤 회사인가요?",
    "지금 주가는 1년 중 어디쯤인가요?",
    "최근 주가는 어떻게 움직였나요?",
    "회사는 돈을 벌고 있나요?",
    "회사의 빚은 어느 정도인가요?",
    "주가와 회사 이익을 함께 보면?",
    "앞으로 지켜볼 숫자 3가지",
    "한 줄 정리",
]
TABLE_TITLE = "숫자 풀이"

# 지침 6장: 용어 고정 풀이 (쉽게 읽기에서는 이 풀이만 쓴다)
TERM_GLOSS = {
    "매출": "물건과 서비스를 판 돈",
    "영업이익": "본업으로 남긴 돈",
    "순이익": "세금 등을 빼고 최종으로 남은 돈",
    "흑자 / 적자": "번 돈이 쓴 돈보다 많음 / 적음",
    "거래량": "사고판 주식 수",
    "시가총액": "회사 전체 가격(주가 × 주식 수)",
    "부채비율": "회사 자기 돈 대비 빚의 크기",
    "순자산": "빚을 빼고 남은 재산",
    "주가수익비율(PER)": "회사 전체 가격이 1년 순이익의 몇 배인지",
    "주가순자산비율(PBR)": "회사 전체 가격이 순자산의 몇 배인지",
    "자기자본이익률(ROE)": "회사 자기 돈으로 1년에 몇 %를 벌었는지",
    "52주 최고·최저": "지난 1년 동안 거래된 가장 높은·낮은 가격",
    "수익률": "그 기간 동안 주가가 오르내린 비율",
}

# 지침 8장: 금지 표현 (쉽게 읽기 섹션 어디에도 쓰지 않는다)
FORBIDDEN = {
    "평가": ["좋다", "나쁘다", "양호", "우수", "부진", "안정적", "불안", "건전", "위험", "탄탄"],
    "가격 판단": ["싸다", "비싸다", "저평가", "고평가", "저렴", "매력", "부담", "적정"],
    "전망": ["기대", "우려", "전망", "예상", "가능성", "회복", "반등", "돌파", "신호", "추세 전환"],
    "권유": ["매수", "매도", "사세요", "파세요", "추천", "목표가", "진입", "손절", "익절", "필요가 있습니다"],
    "강조 수식": ["크게", "급격히", "무려", "불과", "겨우", "상당히", "현저히"],
    "전문 약어 단독 사용": ["MA", "YoY", "TTM", "QoQ"],
}

# 지침 9장: 데이터 없음 처리
NO_DATA = {
    "공시 부족": "공시된 자료가 부족해 이 항목은 계산하지 못했습니다.",
    "상장 기간 부족": "상장한 지 오래되지 않아 이 항목은 계산하지 못했습니다.",
}

# 지침 10장: 숫자 풀이 표 (항목·순서·뜻 고정)
TABLE_ROWS = [
    ("현재가", "{기준일} 정규장 종가"),
    ("52주 위치", "지난 1년 가격 범위에서의 위치"),
    ("1개월 수익률", "최근 1개월 동안 주가가 오르내린 비율"),
    ("최근 1년 영업이익", "최근 4개 분기에 본업으로 남긴 돈"),
    ("부채비율", "회사 자기 돈 대비 빚의 크기"),
    ("주가수익비율(PER)", "회사 전체 가격이 1년 순이익의 몇 배인지"),
    ("주가순자산비율(PBR)", "회사 전체 가격이 순자산의 몇 배인지"),
    ("자기자본이익률(ROE)", "회사 자기 돈으로 1년에 몇 %를 벌었는지"),
]

MARKET_NAMES = {"KOSPI": "유가증권시장(코스피)", "KOSDAQ": "코스닥 시장"}
DEBT_ALERT_PCT = 30.0            # 4장 3문장: 부채총계 직전 분기 대비 ±30% 이상일 때만


# ---------------------------------------------------------------------------
# 표기 도우미 (지침 7장)
# ---------------------------------------------------------------------------

def josa(word, with_final="은", without_final="는"):
    """받침 여부로 조사를 고른다. 한글은 받침, 숫자·영문은 읽는 소리 기준(예: OCI→는, LG→는, NAVER→는)."""
    last = str(word).strip()[-1:]
    if not last:
        return without_final
    if "가" <= last <= "힣":
        has_final = (ord(last) - 0xAC00) % 28 != 0
    elif last.isdigit():
        has_final = last in "013678"          # 영·일·삼·육·칠·팔
    elif last.isascii() and last.isalpha():
        has_final = last.upper() in "LMNR"    # 엘·엠·엔·알
    else:
        has_final = False
    return with_final if has_final else without_final


def round_half_up(value):
    """소수 첫째 자리에서 반올림한 정수(지침 1장 위치, 4장 원 단위)."""
    return int(math.floor(value + 0.5)) if value >= 0 else -int(math.floor(-value + 0.5))


def date_kr(iso):
    """'2026-09-23' -> '2026년 9월 23일'"""
    y, m, d = str(iso)[:10].split("-")
    return f"{y}년 {int(m)}월 {int(d)}일"


def quarter_kr(key):
    """'2026Q2' -> '2026년 2분기'"""
    y, q = str(key).split("Q")
    return f"{y}년 {q}분기"


def period_kr(keys):
    """최근 2개 분기 -> '2026년 1~2분기'(같은 해) / '2025년 4분기~2026년 1분기'(해가 바뀜)"""
    (y1, q1), (y2, q2) = [str(k).split("Q") for k in keys]
    return f"{y1}년 {q1}~{q2}분기" if y1 == y2 else f"{y1}년 {q1}분기~{y2}년 {q2}분기"


def rate2(value):
    """주가 수익률·52주 대비·이격도: 본문 값 그대로(소수 둘째 자리) 절댓값 문자열(지침 7장)."""
    return f"{abs(value):,.2f}"


def rate1(value):
    """쉽게 읽기에서 새로 계산한 증감률(6개월 매출·영업이익, 부채 증감): 소수 첫째 자리 절댓값(지침 7장)."""
    return f"{abs(value):,.1f}"


def change_phrase(now, before, ending="습니다", sales=False):
    """3장·7장 증감 표현. 계산이 의미 없으면 None.

    영업이익(sales=False): 전년 0 이하이거나 부호가 바뀌면(올해 0 이하) None
    매출(sales=True): 전년 0 이하일 때만 None (매출에는 부호 변화가 없다)
    ending='습니다' -> '19.7% 줄었습니다' / '12.9배로 늘었습니다'
    ending='며'     -> '19.7% 줄었으며'   / '12.9배로 늘었으며'
    """
    if now is None or before is None or before <= 0 or now < 0 or (now == 0 and not sales):
        return None
    pct = (now / before - 1) * 100
    grow, shrink = ("늘었습니다", "줄었습니다") if ending == "습니다" else ("늘었으며", "줄었으며")
    if pct >= 100:
        return f"{now / before:,.1f}배로 {grow}"
    return f"{rate1(pct)}% {grow if pct > 0 else shrink}"


def amount(value_won):
    """금액: 전문가용 본문과 같은 표시 문자열(financials.format_eok)."""
    import financials
    return financials.format_eok(value_won)


def _sign(value):
    return 0 if round(value, 2) == 0 else (1 if value > 0 else -1)


def _sum(items, key):
    values = [x.get(key) for x in items]
    return None if any(v is None for v in values) else sum(values)


# ---------------------------------------------------------------------------
# 장별 문장 (지침 5장)
# ---------------------------------------------------------------------------

def _chapter0(ind, fin):
    name = ind["종목명"]
    market = MARKET_NAMES.get(ind.get("시장"), ind.get("시장"))
    group = (ind.get("업종대비") or {}).get("업종그룹") or "기타"
    s1 = f"{name}{josa(name)} {market}에 상장된 {group} 업종 회사입니다."
    quarters = (fin or {}).get("분기") or []
    if not quarters:
        return [s1, NO_DATA["공시 부족"]]
    s2 = f"이 내용은 {date_kr(ind['기준일'])} 종가와 {quarter_kr(quarters[-1]['분기'])}까지 공시된 재무제표를 바탕으로 합니다."
    return [s1, s2]


def _position(ind):
    """52주 위치(%) 정수와 구간. 계산할 수 없으면 None."""
    w52, cur = ind.get("52주") or {}, ind.get("현재가")
    low, high = w52.get("52주_최저"), w52.get("52주_최고")
    if not (low and high and cur) or high <= low:
        return None
    pos = round_half_up((cur - low) / (high - low) * 100)
    zone = "아래쪽" if pos <= 33 else ("가운데" if pos <= 66 else "위쪽")
    return {"위치": pos, "구간": zone, "최저": low, "최고": high, "현재가": cur}


def _listing_short(ind):
    """상장 1년 미만(1년 수익률을 계산할 수 없음)."""
    return (ind.get("기간수익률") or {}).get("1년") is None


def _chapter1(ind):
    p = _position(ind)
    if not p:
        return [NO_DATA["상장 기간 부족"]], None
    short = _listing_short(ind)
    lead = "상장 후 지금까지" if short else "지난 1년 동안"
    s1 = f"{lead} 주가는 가장 낮을 때 {p['최저']:,}원, 가장 높을 때 {p['최고']:,}원이었습니다."
    s2 = f"지금 주가 {p['현재가']:,}원은 이 범위의 {p['구간']}, 아래에서 {p['위치']}% 지점에 있습니다."
    w52 = ind["52주"]
    span = "상장 후" if short else "지난 1년"
    if p["현재가"] == p["최고"]:
        s3 = f"지금 주가는 {span} 가장 높은 가격입니다."
    elif p["현재가"] == p["최저"]:
        s3 = f"지금 주가는 {span} 가장 낮은 가격입니다."
    else:                                      # 상장 1년 미만이어도 3문장 틀은 그대로
        s3 = (f"가장 높았을 때보다 {rate2(w52['52주최고_대비'])}% 낮고, "
              f"가장 낮았을 때보다 {rate2(w52['52주최저_대비'])}% 높습니다.")
    figure = {"종류": "범위", "최저": p["최저"], "최고": p["최고"], "현재가": p["현재가"],
              "제목": "상장 후 주가 범위" if short else "지난 1년 주가 범위"}
    return [s1, s2, s3], figure


def _chapter2(ind):
    r = ind.get("기간수익률") or {}
    r1, r6, r12 = r.get("1개월"), r.get("6개월"), r.get("1년")
    if r1 is None:
        return [NO_DATA["상장 기간 부족"]], None
    if _sign(r1) == 0:
        sentences = ["최근 1개월 동안 주가는 변동이 없었습니다."]
    else:
        sentences = [f"최근 1개월 동안 주가는 {rate2(r1)}% {'올랐습니다' if r1 > 0 else '내렸습니다'}."]
    if r6 is None or r12 is None:
        sentences.append(NO_DATA["상장 기간 부족"])       # 이 문장만 대체(지침 9장)
    else:
        # 연결어: 부호가 다르면 '하지만', 같거나 둘 중 하나가 0이면 '그리고'
        link = "하지만" if _sign(r1) * _sign(r6) < 0 else "그리고"
        part6 = ("6개월 전과 같고" if _sign(r6) == 0
                 else f"6개월 전보다는 {rate2(r6)}% {'높고' if r6 > 0 else '낮고'}")
        part12 = ("1년 전과 같습니다" if _sign(r12) == 0
                  else f"1년 전보다는 {rate2(r12)}% {'높습니다' if r12 > 0 else '낮습니다'}")
        sentences.append(f"{link} {part6}, {part12}.")
    ratio = (ind.get("거래량") or {}).get("거래량비율_5일대60일")
    sentences.append(f"최근 5일 동안 하루 평균 거래량(사고판 주식 수)은 최근 3개월 평균의 {ratio:.2f}배입니다."
                     if ratio is not None else NO_DATA["상장 기간 부족"])
    items = [(label, value) for label, value in (("1개월", r1), ("6개월", r6), ("1년", r12)) if value is not None]
    return sentences, {"종류": "수익률", "항목": items}


def is_finance(ind, fin):
    """금융업: 업종그룹이 '금융'이거나 매출 계정이 없는 회사."""
    if (ind.get("업종대비") or {}).get("업종그룹") == "금융":
        return True
    recent = (fin or {}).get("분기") or []
    return bool(recent) and all(x.get("매출액") is None for x in recent)


def half_year(fin):
    """최근 6개월(최근 2개 분기 합)과 1년 전 같은 6개월. 분기보고서 3개월 값을 그대로 더한다."""
    recent, prior = (fin or {}).get("분기") or [], (fin or {}).get("직전분기") or []
    if len(recent) < 4 or len(prior) < 4:
        return None
    now, before = recent[-2:], prior[-2:]
    out = {"기간": period_kr([x["분기"] for x in now])}
    for key in ("매출액", "영업이익"):
        out[key] = (_sum(now, key), _sum(before, key))
    return out


def _state(value):
    return "흑자" if value > 0 else "적자"


def _chapter3(ind, fin):
    half = half_year(fin)
    ratios = (fin or {}).get("비율") or {}
    if not half:
        return [NO_DATA["공시 부족"]]
    finance = is_finance(ind, fin)
    period = half["기간"]
    sentences = []

    # 1문장(매출) - 금융업은 뺀다
    if not finance:
        now, before = half["매출액"]
        phrase = change_phrase(now, before, sales=True)
        if now is None or before is None:
            sentences.append(NO_DATA["공시 부족"])
        elif phrase:
            sentences.append(f"최근 6개월({period}) 매출(물건과 서비스를 판 돈)은 {amount(now)}으로, "
                             f"1년 전 같은 기간({amount(before)})보다 {phrase}.")
        else:   # 전년 매출 0 이하(지침 v1.2 확정 문장)
            sentences.append(f"최근 6개월({period}) 매출(물건과 서비스를 판 돈)은 {amount(now)}이고, "
                             f"1년 전 같은 기간에는 매출이 없었습니다.")

    # 2문장(영업이익) - 금융업은 기간을 붙인 문장으로 바꾼다
    now, before = half["영업이익"]
    phrase = change_phrase(now, before)
    lead = f"최근 6개월({period}) 영업이익" if finance else "같은 기간 영업이익"
    if now is None or before is None:
        sentences.append(NO_DATA["공시 부족"])
    elif phrase and finance:
        sentences.append(f"{lead}(본업으로 남긴 돈)은 {amount(now)}으로, "
                         f"1년 전 같은 기간({amount(before)})보다 {phrase}.")
    elif phrase:
        sentences.append(f"{lead}(본업으로 남긴 돈)은 {amount(now)}으로, 1년 전({amount(before)})보다 {phrase}.")
    else:   # 전년 0 이하·부호 전환(지침 v1.2 대체 문장, 금융업은 앞머리만 기간 표기)
        gloss = "번 돈이 쓴 돈보다 많음" if before > 0 else "번 돈이 쓴 돈보다 적음"
        sentences.append(f"{lead}(본업으로 남긴 돈)은 {amount(now)}이고, "
                         f"1년 전 같은 기간은 {amount(before)}으로 {_state(before)}({gloss})였습니다.")

    # 3문장(최근 1년 금액)·4문장(판정)
    op_ttm = ratios.get("TTM영업이익")
    net_ttm = ratios.get("TTM지배순이익") if ratios.get("TTM지배순이익") is not None else ratios.get("TTM순이익")
    if op_ttm is None or net_ttm is None:
        sentences.append(NO_DATA["공시 부족"])
    else:
        sentences.append(f"최근 1년(4개 분기) 동안 영업이익은 {amount(op_ttm)}, "
                         f"순이익(세금 등을 빼고 최종으로 남은 돈)은 {amount(net_ttm)}입니다.")
        gloss = "번 돈이 쓴 돈보다 많음" if net_ttm > 0 else "번 돈이 쓴 돈보다 적음"
        sentences.append(f"최근 1년 합산 순이익은 {_state(net_ttm)}({gloss})입니다.")

    # 5문장(전환): 최근 분기와 1년 전 같은 분기의 영업이익 부호가 다를 때만
    recent, prior = fin["분기"], fin["직전분기"]
    q_now, q_before = recent[-1].get("영업이익"), prior[-1].get("영업이익")
    if q_now is not None and q_before is not None and (q_now > 0) != (q_before > 0):
        sentences.append(f"최근 분기({quarter_kr(recent[-1]['분기'])}) 영업이익은 1년 전 같은 분기의 "
                         f"{_state(q_before)}에서 {_state(q_now)}로 바뀌었습니다.")

    if finance:
        sentences.append("금융회사는 일반 회사와 돈을 버는 구조가 달라 영업이익만 비교합니다.")
    return sentences


def debt_change(fin):
    """부채총계 직전 분기 대비 증감률(%) 원값. 없으면 None."""
    recent = (fin or {}).get("분기") or []
    if len(recent) < 2:
        return None
    now, before = recent[-1].get("부채총계"), recent[-2].get("부채총계")
    if now is None or not before:
        return None
    return (now / before - 1) * 100


def _chapter4(ind, fin):
    ratios = (fin or {}).get("비율") or {}
    debt = ratios.get("부채비율")
    if debt is None:
        return [NO_DATA["공시 부족"]]
    s1 = f"{ratios['기준분기']} 말 기준 부채비율(회사 자기 돈 대비 빚의 크기)은 {debt:,.1f}%입니다."
    if is_finance(ind, fin):
        s2 = "은행·보험회사는 고객 예금과 보험금이 빚으로 잡혀서 부채비율이 일반 회사보다 높게 나옵니다."
    else:
        s2 = f"회사 자기 돈이 100원이라면 빚이 {round_half_up(debt):,}원 있다는 뜻입니다."
    sentences = [s1, s2]
    change = debt_change(fin)       # 빚의 증감률은 직전 분기와 비교(3장 규칙은 3장에만 적용)
    if change is not None and abs(change) >= DEBT_ALERT_PCT:
        sentences.append(f"직전 분기보다 빚이 {rate1(change)}% {'늘었습니다' if change > 0 else '줄었습니다'}.")
    return sentences


def _chapter5(fin):
    ratios = (fin or {}).get("비율") or {}
    per, pbr = ratios.get("PER"), ratios.get("PBR")
    sentences = []
    if per == "적자":
        sentences.append("최근 1년 순이익이 적자여서 주가수익비율은 계산할 수 없습니다.")
    elif per is None:
        sentences.append(NO_DATA["공시 부족"])
    else:
        sentences.append(f"주가수익비율은 {per:,.1f}배입니다.")
        sentences.append(f"회사 전체 가격(시가총액)이 최근 1년 순이익의 {per:,.1f}배라는 뜻입니다.")
    if pbr is None:
        sentences.append(NO_DATA["공시 부족"])
    else:
        sentences.append(f"주가순자산비율은 {pbr:,.1f}배입니다.")
        sentences.append(f"회사 전체 가격이 장부상 순자산(빚을 빼고 남은 재산)의 {pbr:,.1f}배라는 뜻입니다.")
    sentences.append("이 두 숫자만으로 지금 주가 수준을 판단할 수는 없습니다.")
    return sentences


def _chapter6(ind, fin):
    ma = ind.get("이동평균") or {}
    ma120, gap = ma.get("MA120"), ma.get("MA120_이격도")
    first = ("1. 다음 분기 영업이익: 1년 전 같은 분기와 비교한 증감입니다." if is_finance(ind, fin)
             else "1. 다음 분기 매출과 영업이익: 1년 전 같은 분기와 비교한 증감입니다.")
    items = [first]
    if ma120 is None or gap is None:
        items.append("2. 최근 6개월 평균 주가: " + NO_DATA["상장 기간 부족"])
    elif _sign(gap) == 0:
        items.append(f"2. 최근 6개월 평균 주가: 지금 주가는 6개월 평균 {ma120:,}원과 같습니다.")
    else:
        items.append(f"2. 최근 6개월 평균 주가: 지금 주가는 6개월 평균 {ma120:,}원보다 "
                     f"{rate2(gap)}% {'높습니다' if gap > 0 else '낮습니다'}.")
    ratio = (ind.get("거래량") or {}).get("거래량비율_5일대60일")
    items.append(f"3. 거래량: 최근 5일 하루 평균은 최근 3개월 평균의 {ratio:.2f}배입니다."
                 if ratio is not None else "3. 거래량: " + NO_DATA["상장 기간 부족"])
    return items


def _chapter7(ind, fin):
    name = ind["종목명"]
    p = _position(ind)
    half = half_year(fin)
    ratios = (fin or {}).get("비율") or {}
    net_ttm = ratios.get("TTM지배순이익") if ratios.get("TTM지배순이익") is not None else ratios.get("TTM순이익")
    if not p or not half or net_ttm is None:
        return [NO_DATA["공시 부족"]]
    key, label = ("영업이익", "영업이익") if is_finance(ind, fin) else ("매출액", "매출")
    now, before = half[key]
    if now is None or before is None:
        return [NO_DATA["공시 부족"]]
    phrase = change_phrase(now, before, ending="며", sales=(key == "매출액"))
    middle = (f"최근 6개월 {label}은 1년 전보다 {phrase}" if phrase
              else f"최근 6개월 {label}은 {amount(now)}이며")      # 전년 0 이하·부호 변화로 증감 표현을 못 쓴 경우
    scope = "상장 후 범위의" if _listing_short(ind) else "1년 범위의"
    return [f"{name}{josa(name)} 주가가 {scope} {p['구간']}에 있고, {middle}, "
            f"최근 1년 합산 순이익은 {_state(net_ttm)}입니다."]


def _table(ind, fin):
    """지침 10장 숫자 풀이 표: (지표, 이 종목 값, 뜻)"""
    ratios = (fin or {}).get("비율") or {}
    p = _position(ind)
    r1 = (ind.get("기간수익률") or {}).get("1개월")
    missing = "자료 없음"

    def ratio_text(key, unit):
        value = ratios.get(key)
        if value is None:
            return missing
        if value == "적자":
            return "계산 불가(순이익 적자)"
        return f"{value:,.1f}{unit}"

    values = [
        f"{ind['현재가']:,}원",
        f"아래에서 {p['위치']}%" if p else missing,
        f"{r1:+.2f}%" if r1 is not None else missing,
        amount(ratios["TTM영업이익"]) if ratios.get("TTM영업이익") is not None else missing,
        ratio_text("부채비율", "%"),
        ratio_text("PER", "배"),
        ratio_text("PBR", "배"),
        ratio_text("ROE", "%"),
    ]
    return [(label, value, meaning.replace("{기준일}", date_kr(ind["기준일"])))
            for (label, meaning), value in zip(TABLE_ROWS, values)]


def build(ind, fin):
    """쉽게 읽기 전체를 만든다. ind: indicators.compute 결과, fin: financials.load_financials 결과(없으면 None).

    반환: {"버전", "장": [{"제목", "문장": [...], "그림": dict|None}], "풀이표": [(지표, 값, 뜻)]}
    """
    s1, fig1 = _chapter1(ind)
    s2, fig2 = _chapter2(ind)
    chapters = [
        (_chapter0(ind, fin), None),
        (s1, fig1),
        (s2, fig2),
        (_chapter3(ind, fin), None),
        (_chapter4(ind, fin), None),
        (_chapter5(fin), None),
        (_chapter6(ind, fin), None),
        (_chapter7(ind, fin), None),
    ]
    glossed = apply_gloss([sentences for sentences, _ in chapters])     # 첫 등장 풀이(동적)
    return {
        "버전": EASY_READ_GUIDE_VERSION,
        "장": [{"제목": title, "문장": sentences, "그림": figure}
               for title, sentences, (_, figure) in zip(CHAPTER_TITLES, glossed, chapters)],
        "풀이표": _table(ind, fin),
    }


# ---------------------------------------------------------------------------
# 첫 등장 괄호 풀이 (지침 3장, v1.2: 코드가 섹션 전체를 앞에서부터 훑어 동적으로 붙인다)
# ---------------------------------------------------------------------------

# 용어 -> (본문에서 찾는 패턴, 고정 풀이). 흑자·적자는 한 용어이고 나온 단어에 맞는 풀이를 붙인다.
# 주가수익비율·주가순자산비율은 5장에서 뒤 문장이 풀이하므로 대상에서 뺀다(지침 3장 예외).
GLOSS_RULES = [
    ("매출", r"매출", TERM_GLOSS["매출"]),
    ("영업이익", r"영업이익", TERM_GLOSS["영업이익"]),
    ("순이익", r"(?<!지배주주 )순이익", TERM_GLOSS["순이익"]),
    ("흑자 / 적자", r"흑자|적자", None),
    ("거래량", r"거래량", TERM_GLOSS["거래량"]),
    ("시가총액", r"시가총액", TERM_GLOSS["시가총액"]),
    ("부채비율", r"부채비율", TERM_GLOSS["부채비율"]),
    ("순자산", r"(?<!주가)순자산", TERM_GLOSS["순자산"]),
    ("52주 최고·최저", r"52주 최고·최저", TERM_GLOSS["52주 최고·최저"]),
    ("수익률", r"수익률", TERM_GLOSS["수익률"]),
    ("자기자본이익률", r"자기자본이익률", TERM_GLOSS["자기자본이익률(ROE)"]),
]
PROFIT_GLOSS = {"흑자": "번 돈이 쓴 돈보다 많음", "적자": "번 돈이 쓴 돈보다 적음"}
REVERSED_FORM = "회사 전체 가격("        # '회사 전체 가격(시가총액)': 쉬운 말 뒤 괄호에 용어(풀이가 붙은 것으로 본다)


def _gloss_for(rule, word):
    return PROFIT_GLOSS[word] if rule[0] == "흑자 / 적자" else rule[2]


def _is_reversed(sentence, start):
    return sentence[max(0, start - len(REVERSED_FORM)):start] == REVERSED_FORM


def apply_gloss(chapter_sentences):
    """장별 문장 목록(list[list[str]])을 받아, 용어 풀이 괄호를 모두 뗀 뒤
    섹션 안에서 각 용어가 처음 나오는 자리에만 고정 풀이를 붙여 돌려준다."""
    # 1) 문장 틀에 적힌 풀이 괄호를 모두 뗀다
    stripped = []
    for sentences in chapter_sentences:
        out = []
        for s in sentences:
            for rule in GLOSS_RULES:
                s = re.sub(rf"({rule[1]})\(([^()]*(?:\([^()]*\))?[^()]*)\)",
                           lambda m, r=rule: m.group(1) if m.group(2) == _gloss_for(r, m.group(1)) else m.group(0), s)
            out.append(s)
        stripped.append(out)
    # 2) 앞에서부터 훑어 첫 등장에만 붙인다
    done = set()
    result = []
    for sentences in stripped:
        out = []
        for s in sentences:
            inserts = []
            for rule in GLOSS_RULES:
                if rule[0] in done:
                    continue
                m = re.search(rule[1], s)
                if not m:
                    continue
                done.add(rule[0])
                if rule[0] == "시가총액" and _is_reversed(s, m.start()):
                    continue                     # 이미 풀이된 형태
                inserts.append((m.end(), f"({_gloss_for(rule, m.group(0))})"))
            for pos, text in sorted(inserts, reverse=True):
                s = s[:pos] + text + s[pos:]
            out.append(s)
        result.append(out)
    return result


def to_text(result):
    """비교·보고용 평문(장 제목 + 문장 + 표)."""
    lines = []
    for i, chapter in enumerate(result["장"]):
        lines.append(f"{i}장. {chapter['제목']}")
        lines.extend(chapter["문장"])
        lines.append("")
    lines.append(TABLE_TITLE)
    lines.extend(" | ".join(row) for row in result["풀이표"])
    return "\n".join(lines)


# ===========================================================================
# 지침 11장 검증 체크리스트 (자동 검사 10항목)
# ===========================================================================

ABBR_RE = re.compile(r"(?<![A-Za-z])(MA\d*|PER|PBR|ROE|YoY|TTM|QoQ)(?![A-Za-z])")
MAX_CHARS = 60


def _plain(sentence):
    """괄호와 괄호 안 글자를 뺀 문장(글자 수 계산용, 지침 3장)."""
    previous = None
    while previous != sentence:              # 중첩 괄호까지 제거
        previous = sentence
        sentence = re.sub(r"\([^()]*\)", "", sentence)
    return sentence


def _allowed_numbers(ind, fin):
    """쉽게 읽기에 나올 수 있는 숫자 집합.

    - 전문가용 본문 입력값(indicators 결과, 재무 원자료·비율)과 같은 값
    - 지침이 쉽게 읽기에서 직접 계산하라고 정한 값(1장 위치, 4장 원 단위, 3장 6개월 합·증감률, 4장 부채 증감률)
      은 이 검사 함수 안에서 원자료로부터 따로 다시 계산해 넣는다(생성 코드와 독립).
    - 문장 틀에 고정된 숫자(1개월·6개월·1년·3개월·5일·100원·4개 분기 등)
    """
    allowed = set()

    def collect(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                collect(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                collect(v)
        elif isinstance(obj, bool):
            return
        elif isinstance(obj, (int, float)):
            allowed.add(round(abs(float(obj)), 2))
        elif isinstance(obj, str):
            for token in re.findall(r"\d[\d,]*(?:\.\d+)?", obj):
                allowed.add(round(float(token.replace(",", "")), 2))

    collect(ind)
    ratios = (fin or {}).get("비율") or {}
    collect({k: v for k, v in ratios.items() if isinstance(v, (int, float))})
    import financials
    for key in ("TTM영업이익", "TTM지배순이익", "TTM순이익"):
        if isinstance(ratios.get(key), (int, float)):
            collect(financials.format_eok(ratios[key]))

    # 쉽게 읽기 고유 계산값(검사용 독립 재계산)
    w52, cur = ind.get("52주") or {}, ind.get("현재가")
    if w52.get("52주_최고") and w52.get("52주_최저") and cur:
        allowed.add(float(math.floor((cur - w52["52주_최저"]) / (w52["52주_최고"] - w52["52주_최저"]) * 100 + 0.5)))
    if isinstance(ratios.get("부채비율"), (int, float)):
        allowed.add(float(math.floor(ratios["부채비율"] + 0.5)))
    recent, prior = (fin or {}).get("분기") or [], (fin or {}).get("직전분기") or []
    if len(recent) >= 4 and len(prior) >= 4:
        for key in ("매출액", "영업이익"):
            a = [x.get(key) for x in recent[-2:]]
            b = [x.get(key) for x in prior[-2:]]
            if None not in a + b:
                collect(financials.format_eok(sum(a)))
                collect(financials.format_eok(sum(b)))
                if sum(b) > 0 and sum(a) > 0:
                    pct = (sum(a) / sum(b) - 1) * 100
                    allowed.add(round(abs(pct), 1))              # 증감률: 소수 첫째 자리
                    allowed.add(round(sum(a) / sum(b), 1))       # 100% 이상 증가: 배수(소수 첫째 자리)
    if len(recent) >= 2 and recent[-2].get("부채총계"):
        allowed.add(round(abs((recent[-1]["부채총계"] / recent[-2]["부채총계"] - 1) * 100), 1))
    return allowed


FIXED_NUMBERS = {0, 1, 2, 3, 4, 5, 6, 60, 100, 120}


def _number_tokens(text):
    """문장 속 숫자(연도·분기·월·일 표기는 뺀다). '485조 2,720억'은 조·억 숫자를 따로 본다."""
    text = re.sub(r"\d{4}년\s*\d{1,2}월\s*\d{1,2}일", " ", text)
    text = re.sub(r"\d{4}년\s*\d(?:~\d)?분기", " ", text)
    text = re.sub(r"\d{4}년", " ", text)
    return [round(float(t.replace(",", "")), 2) for t in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]


def check(result, ind, fin, report_text=None):
    """지침 11장 체크리스트 10항목을 검사한다. 반환: [(번호, 항목, 통과 여부, 상세)]"""
    chapters = result["장"]
    body = [s for ch in chapters for s in ch["문장"]]
    everything = "\n".join([ch["제목"] for ch in chapters] + body)
    out = []

    # 1. 8개 장이 모두 있고 순서가 같은가
    titles = [ch["제목"] for ch in chapters]
    out.append((1, "8개 장·순서", titles == CHAPTER_TITLES, "" if titles == CHAPTER_TITLES else str(titles)))

    # 2. 모든 숫자가 입력값 또는 원자료 독립 재계산 값과 같은가
    allowed = _allowed_numbers(ind, fin)
    bad = []
    for sentence in body + [row[1] for row in result["풀이표"]]:
        for value in _number_tokens(sentence):
            if value in FIXED_NUMBERS:
                continue
            if not any(abs(value - a) < 0.005 for a in allowed):
                bad.append(f"{value:g} ← {sentence[:40]}")
    out.append((2, "숫자가 입력값·재계산값과 같음", not bad, "; ".join(bad[:6])))

    # 3. 금지 표현 0건
    hits = [f"{word}({kind})" for kind, words in FORBIDDEN.items() for word in words
            if (re.search(r"(?<![A-Za-z])" + word + r"(?![A-Za-z])", everything) if word.isascii() else word in everything)]
    out.append((3, "금지 표현 0건", not hits, ", ".join(hits)))

    # 4. 한 문장 60자 이내(공백 포함, 괄호 안 제외, 7장 제외)
    long_ones = []
    for ch in chapters[:7]:
        for sentence in ch["문장"]:
            plain = _plain(sentence)
            if len(plain) > MAX_CHARS:
                long_ones.append(f"{len(plain)}자: {sentence[:30]}…")
    out.append((4, "한 문장 60자 이내", not long_ones, "; ".join(long_ones)))

    # 5. 영문 약어는 숫자 풀이 표에만
    abbr = sorted(set(ABBR_RE.findall(everything)))
    out.append((5, "영문 약어는 표에만", not abbr, ", ".join(abbr)))

    # 6. 방향어가 실제 부호와 맞는가 (원자료로 다시 판정)
    out.append((6, "방향어와 부호 일치", *_check_directions(chapters, ind, fin)))

    # 7. 같은 입력으로 두 번 생성해 글자 하나까지 같은가
    again = build(ind, fin)
    same = to_text(again) == to_text(result)
    out.append((7, "두 번 생성 결과 동일", same, "" if same else "다른 결과"))

    # 8. 리포트 출처 페이지에 지침 버전 표시
    if report_text is None:
        out.append((8, "출처 페이지 지침 버전", None, "리포트 없이 검사(해당 없음)"))
    else:
        mark = f"쉽게 읽기 지침 {EASY_READ_GUIDE_VERSION}"
        out.append((8, "출처 페이지 지침 버전", mark in report_text, "" if mark in report_text else f"'{mark}' 없음"))

    # 9. 6장 용어가 처음 나올 때 고정 풀이 괄호(5장 예외)
    missing = check_term_gloss(chapters)
    out.append((9, "용어 첫 등장 괄호 풀이", not missing, "; ".join(missing)))

    # 10. 모든 문장이 합쇼체로 끝나는가(목록 항목 포함)
    not_formal = [s[-25:] for s in body if not re.search(r"(니다|습니다)\.$", s.strip())]
    out.append((10, "합쇼체", not not_formal, "; ".join(not_formal)))
    return out


# 9번 검사용(생성 코드와 따로 둔 목록): 용어 -> (본문에서 찾는 패턴, 허용하는 괄호 풀이 목록)
#  - 흑자·적자는 한 용어로 보고, 처음 나온 쪽에 맞는 풀이('많음'/'적음')를 요구한다.
#  - 5장의 주가수익비율·주가순자산비율은 뒤 문장이 풀이하므로 예외(지침 3장).
#  - '회사 전체 가격(시가총액)'처럼 쉬운 말 뒤 괄호에 용어를 넣은 형태도 풀이가 붙은 것으로 본다(지침 3장).
#  - 두 번째부터는 용어만 쓴다: 두 번째 이후 등장에 풀이 괄호가 붙어 있으면 실패로 본다.
GLOSS_TERMS = [
    ("매출", r"매출", ["물건과 서비스를 판 돈"]),
    ("영업이익", r"영업이익", ["본업으로 남긴 돈"]),
    ("순이익", r"(?<!지배주주 )순이익", ["세금 등을 빼고 최종으로 남은 돈"]),
    ("흑자 / 적자", r"흑자|적자", ["번 돈이 쓴 돈보다 많음", "번 돈이 쓴 돈보다 적음"]),
    ("거래량", r"거래량", ["사고판 주식 수"]),
    ("시가총액", r"시가총액", ["회사 전체 가격(주가 × 주식 수)"]),
    ("부채비율", r"부채비율", ["회사 자기 돈 대비 빚의 크기"]),
    ("순자산", r"(?<!주가)순자산", ["빚을 빼고 남은 재산"]),
    ("52주 최고·최저", r"52주\s*최[고저]", ["지난 1년 동안 거래된 가장 높은·낮은 가격"]),
    ("수익률", r"수익률", ["그 기간 동안 주가가 오르내린 비율"]),
    ("자기자본이익률(ROE)", r"자기자본이익률", ["회사 자기 돈으로 1년에 몇 %를 벌었는지"]),
]


def check_term_gloss(chapters):
    """6장 용어가 섹션 안에서 처음 나올 때만 고정 풀이 괄호가 붙어 있는지. 문제 목록을 돌려준다."""
    text = "\n".join(s for ch in chapters for s in ch["문장"])
    problems = []

    def where(pos):
        before = text[:pos].count("\n")
        count = 0
        for i, ch in enumerate(chapters):
            count += len(ch["문장"])
            if before < count:
                return i
        return "?"

    for term, pattern, glosses in GLOSS_TERMS:
        matches = list(re.finditer(pattern, text))
        if not matches:
            continue
        for n, match in enumerate(matches):
            after = text[match.end():]
            has = any(after.startswith(f"({g})") for g in glosses)
            if n == 0:
                ok = has
                if term == "흑자 / 적자":            # 처음 나온 쪽에 맞는 풀이
                    want = glosses[0] if match.group(0) == "흑자" else glosses[1]
                    ok = after.startswith(f"({want})")
                if term == "시가총액" and text[max(0, match.start() - 9):match.start()] == "회사 전체 가격(":
                    ok = True                        # '회사 전체 가격(시가총액)' 형태
                if not ok:
                    problems.append(f"{term}: {where(match.start())}장 첫 등장에 풀이 없음")
            elif has:
                problems.append(f"{term}: {where(match.start())}장 두 번째 이후 등장에 풀이 중복")
    return problems


def _check_directions(chapters, ind, fin):
    """방향어(올랐/내렸, 높/낮, 늘었/줄었, 배로 늘었, 흑자/적자, 전환)를 원자료 부호와 대조한다."""
    problems = []
    r = ind.get("기간수익률") or {}
    ch2 = " ".join(chapters[2]["문장"])
    if r.get("1개월") is not None:
        if "올랐습니다" in ch2 and r["1개월"] <= 0:
            problems.append("2장 1개월: 올랐습니다 ↔ 부호")
        if "내렸습니다" in ch2 and r["1개월"] >= 0:
            problems.append("2장 1개월: 내렸습니다 ↔ 부호")
    m = re.search(r"6개월 전보다는 [\d.,]+% (높고|낮고)", ch2)
    if m and r.get("6개월") is not None and (m.group(1) == "높고") != (r["6개월"] > 0):
        problems.append("2장 6개월 방향")
    m = re.search(r"1년 전보다는 [\d.,]+% (높습니다|낮습니다)", ch2)
    if m and r.get("1년") is not None and (m.group(1) == "높습니다") != (r["1년"] > 0):
        problems.append("2장 1년 방향")

    recent, prior = (fin or {}).get("분기") or [], (fin or {}).get("직전분기") or []
    ch3 = chapters[3]["문장"]
    if len(recent) >= 4 and len(prior) >= 4:
        for key, marker in (("매출액", "매출("), ("영업이익", "영업이익(")):
            a = [x.get(key) for x in recent[-2:]]
            b = [x.get(key) for x in prior[-2:]]
            if None in a + b:
                continue
            for sentence in ch3:
                if marker in sentence and ("늘었습니다" in sentence or "줄었습니다" in sentence):
                    if ("늘었습니다" in sentence) != (sum(a) > sum(b)):
                        problems.append(f"3장 {key} 증감 방향")
        b_op = [x.get("영업이익") for x in prior[-2:]]
        for sentence in ch3:
            m = re.search(r"1년 전 같은 기간은 .*?으로 (흑자|적자)", sentence)
            if m and None not in b_op and (m.group(1) == "흑자") != (sum(b_op) > 0):
                problems.append("3장 전년 영업이익 흑자/적자")
        q_now, q_before = recent[-1].get("영업이익"), prior[-1].get("영업이익")
        joined = " ".join(ch3)
        m = re.search(r"1년 전 같은 분기의 (흑자|적자)에서 (흑자|적자)로", joined)
        if m and q_now is not None and q_before is not None:
            if (m.group(1) == "흑자") != (q_before > 0) or (m.group(2) == "흑자") != (q_now > 0):
                problems.append("3장 전환 방향")
    ratios = (fin or {}).get("비율") or {}
    net = ratios.get("TTM지배순이익") if ratios.get("TTM지배순이익") is not None else ratios.get("TTM순이익")
    for idx in (3, 7):
        text = " ".join(chapters[idx]["문장"])
        m = re.search(r"합산 순이익은 (흑자|적자)", text)
        if m and net is not None and (m.group(1) == "흑자") != (net > 0):
            problems.append(f"{idx}장 순이익 흑자/적자")
    ch4 = " ".join(chapters[4]["문장"])
    change = debt_change(fin)
    if change is not None and abs(change) >= DEBT_ALERT_PCT and "빚이" in ch4 \
            and (("늘었습니다" in ch4.split("빚이")[-1]) != (change > 0)):
        problems.append("4장 부채 증감 방향")
    ma = ind.get("이동평균") or {}
    ch6 = " ".join(chapters[6]["문장"])
    m = re.search(r"평균 [\d,]+원보다 [\d.,]+% (높습니다|낮습니다)", ch6)
    if m and ma.get("MA120_이격도") is not None and (m.group(1) == "높습니다") != (ma["MA120_이격도"] > 0):
        problems.append("6장 6개월 평균 대비 방향")
    return (not problems, "; ".join(problems))
