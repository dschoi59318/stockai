# -*- coding: utf-8 -*-
"""
narrator.py - 리포트 AI 해설 3개 호출 (docs/리포트_구성지침.md 8장)

원칙 (지침 2장)
 - 판정은 파이썬(direction.py·easy_read.py), 해설은 AI. AI는 파이썬이 정한 판정과 근거를 문장으로 풀어 쓸 뿐
   판정을 바꾸거나 새 판정을 만들지 않는다.
 - 호출별 입력은 지침 8장 표의 항목만, 모두 파이썬이 만든 '표시 문자열'로 넘긴다(원값·JSON을 넘기지 않는다).
   금액은 financials.format_eok 표시(조·억), 증감은 100% 이상이면 배수 표현(지침 v1.3 8장).
 - 시스템 프롬프트에는 지침 6장(허용·금지·근거 강도별 서술·문체) 전체를 지침 문서에서 그대로 읽어 넣는다.

호출 (지침 8장)
 (A) conclusion : 결론 문단 + 왜 그런가 3줄      Sonnet  입력: 신호 3개 판정·근거, 종합 상태, 핵심 긴장 문장(5.9),
                                                         반전 조건 표, 확인 시점, 상위 사건 3개
 (B) story      : 실적 해설 + 사건 해설           Haiku   입력: 8개 분기 표·같은 분기 비교·계절성 판정(5.10),
                                                         쉽게 읽기 3장 문장, 사건 표(근거 강도 포함)
 (C) scenario   : 시나리오 해설                   Haiku   입력: 시나리오 표, 종합 상태, 상위 사건, 실적 흐름

v1.5 반영
 - 5.10 (B) 입력에 분기 흐름 사실(최근 4개 분기의 직전 분기 대비 방향, 파이썬)을 넣는다
 - 6.2 '지속적으로·계속·연속·꾸준히'로 분기 흐름을 서술하면 금지 표현(분기 흐름 사실에 '연속'이 있을 때만 허용).
   (B) 실적 해설은 모든 문장, (A)(C)는 '분기'가 든 문장을 본다
 - 치환표에 '지금가는' -> '지금 주가는'. 저장본을 다시 쓸 때도 치환을 적용한다
 - reuse_calls: 지정한 호출은 입력 해시만 같으면 프롬프트(지침 6장 문구 등)가 바뀌어도 저장본을 쓰고 지금 규칙으로 다시 검증한다
   (결과에 '프롬프트변경재사용' 표시)

v1.4 반영
 - 5.10 (B) 입력에 흑자·적자 전환 사실(파이썬)과 계절성 판정 문장(직전 완결 2개 연도)을 넣고,
   실적 해설에 계절성 문장이 정확히 1번 있는지·전환 시점 서술이 파이썬 사실과 같은지 검사(체크리스트 12번)
 - 6.3 원인 단정어 = 때문·영향·원인이·원인으로·덕분·으로 인해. 표의 허용 표현
   ('직접적인 원인은 확인되지 않습니다', '확인되는 원인이 없습니다')은 검사에서 뺀다
 - 6.4 날짜: 입력의 'YYYY-MM-DD'(기간 포함)를 '2026년 4월 22일', '2026년 4월 22~24일'로 바꿔 넘기고,
   출력에 하이픈 날짜가 있으면 오류
 - 검증기 오탐 수정: 숫자가 든 괄호('적자(-23억 원)')는 용어 풀이 괄호로 보지 않는다
 - 캐시 v3

v1.3 반영
 - 결론 구조(지침 4장 1번 2항): 1문장 = 핵심 긴장 문장(가격 숫자 1개 + 실적 숫자 1개, 종합 상태 이름으로 시작하지 않음),
   2문장 = 해석('~모습입니다/~흐름입니다/~로 보입니다'), 3문장 = 근거 1개, 4문장 = 반전 조건 표 첫 행, 5문장(선택) = 확인 시점
 - 금지 표현: '판정됐습니다·판정되었습니다' 추가, 입력과 다른 계절성 서술 검사
 - 근거 강도 표현 검사를 (A)(C)까지 확대: 약함·없음 사건을 인용한 문장에 원인 단정어가 있으면 오류, (A)는 인용 자체가 오류
 - 문장 길이(지침 6.4): 90자 초과 = 오류, 70~90자 = 경고만. 90자를 넘으면 파이썬이 '~고, / ~며, / ~지만,' 위치에서
   두 문장으로 나누어 보고(auto_split), 나눌 수 없거나 나누면 문장 수 한도를 넘을 때만 재생성
 - 비용: Sonnet은 effort 'low'(가장 낮은 사고 수준), 출력 상한은 잘림이 없는 최소값.
   호출·시도마다 입력·출력(본문)·사고 토큰을 따로 기록(usage.output_tokens_details.thinking_tokens)

검증 (지침 9장 4·5·6·7번 + 형식)
실패 시 경로 (지침 8장, 기존과 같음): 치환 -> 같은 모델 재생성 1회 -> Sonnet 보정 1회(첫 모델이 Sonnet이면 생략) -> 경고
캐시: data/cache/narr_{호출}_{코드}_{기준일 YYYYMMDD}_{모델}_v2.md (맨 윗줄 meta 주석에 입력 해시·시도 경로·토큰·비용·검증 결과)
      같은 호출의 입력 해시·프롬프트 해시가 같으면 API를 부르지 않고 저장본을 쓴다.
      '리포트입력해시'는 세 호출이 같은 값(같은 판정 결과에서 나온 입력인지 확인용).
"""

import hashlib
import io
import json
import os
import re
import time                                                                      # [계측]
from datetime import datetime

import direction
import easy_read
import keys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
GUIDE_PATH = os.path.join(BASE_DIR, "docs", "리포트_구성지침.md")
CACHE_VERSION = "v3"

USD_KRW = 1400.0                # 비용 표시용 환율
COST_TARGET_KRW = 60.0          # 지침 8장 비용 목표(리포트 1건, 재생성 포함 평균)

SONNET = "claude-sonnet-5"
HAIKU = "claude-haiku-4-5-20251001"
REPAIR_MODEL = SONNET
# 100만 토큰당 단가(달러). fallback: 날짜 붙은 ID가 거부되면 쓸 대체 ID
MODELS = {
    HAIKU: {"label": "Haiku 4.5", "input_per_mtok": 1.0, "output_per_mtok": 5.0, "fallback": "claude-haiku-4-5"},
    SONNET: {"label": "Sonnet 5", "input_per_mtok": 2.0, "output_per_mtok": 10.0, "fallback": None},
}
# 출력 상한(사고 토큰 포함). 4종목 실측 최대값에 여유를 둔 최소값(잘리면 형식 오류로 재생성되므로 너무 낮추지 않는다).
MAX_TOKENS = {SONNET: 1500, HAIKU: 1000}   # 실측(v1.3 1차): Sonnet 최대 539(사고 0), Haiku 최대 571
SONNET_EFFORT = "low"           # 지침 8장: Sonnet 사고 수준 가장 낮게

CALLS = {
    "conclusion": {"이름": "결론 문단 + 왜 그런가 3줄", "모델": SONNET},
    "story": {"이름": "실적 해설 + 사건 해설", "모델": HAIKU},
    "scenario": {"이름": "시나리오 해설", "모델": HAIKU},
}
CALL_ORDER = ("conclusion", "story", "scenario")

MAX_SENTENCE = 90               # 지침 6.4 한 문장 글자 수(괄호 안 제외) - 넘으면 자동 분할, 안 되면 재생성
WARN_SENTENCE = 70              # 70~90자는 경고만
LINE_LABELS = ("실적", "주가 움직임", "거래")
SCENARIO_NAMES = ("상방", "기본", "하방")
CIRCLED = "①②③④⑤"
STATE_NAMES = sorted(set(direction.STATE_TABLE.values()), key=len, reverse=True)

# 블록별 문장 수 한도(자동 분할이 넘으면 안 되는 값): (호출, 섹션) -> (한 줄 단위 여부, 최소, 최대)
SENTENCE_LIMITS = {
    ("conclusion", "결론"): (False, 4, 5),
    ("conclusion", "왜 그런가"): (True, 1, 2),
    ("story", "실적 해설"): (False, 3, 4),
    ("story", "사건 해설"): (True, 1, 2),
    ("scenario", "상방"): (False, 2, 3),
    ("scenario", "기본"): (False, 2, 3),
    ("scenario", "하방"): (False, 2, 3),
}


# ===========================================================================
# 지침 6장 (프롬프트 규칙)
# ===========================================================================

def guide_section6():
    """지침 문서에서 '## 6. AI 표현 규칙'부터 '## 7.' 앞까지를 그대로 읽는다. 문서 버전도 함께 돌려준다."""
    with io.open(GUIDE_PATH, "r", encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"^## 6\. AI 표현 규칙.*?(?=^## 7\.)", text, re.S | re.M)
    if not m:
        raise RuntimeError("리포트 구성 지침에서 6장(AI 표현 규칙)을 찾지 못했습니다.")
    version = re.search(r"^버전:\s*(v[\d.]+)", text, re.M)
    return m.group(0).strip(), (version.group(1) if version else None)


COMMON_RULES = """[추가 규칙 - 파이썬 리포트와 맞추기 위한 것]
- 판정은 이미 파이썬이 규칙으로 정했습니다. 입력의 판정·근거를 풀어 쓰기만 하고, 판정을 바꾸거나 새 판정을 만들지 않습니다.
  '판정됐습니다', '판정되었습니다'는 쓰지 않습니다(판정 결과는 리포트의 박스와 표가 보여 줍니다).
- '진입'은 6.2 금지어입니다. 추세·구간이 바뀌는 것은 '들어서다', '바뀌다'로 씁니다.
- 숫자·금액·비율·배수·날짜는 입력에 적힌 표시 그대로만 씁니다. 새로 계산하거나 반올림하거나 단위를 바꾸지 않습니다.
  (예: 입력이 '12.9배로 늘었'이면 '1191.4%'로 바꾸지 않습니다. '146조 7,252억 원'을 '1,467,252억 원'으로 바꾸지 않습니다.)
- 입력에 없는 사건·날짜·원인·회사 정보는 쓰지 않습니다. 지침 6장의 예시 문장(협동로봇 부품 수주 등)은 형식 예시일 뿐이므로,
  이 종목 입력에 없는 예시 속 사건·말은 옮기지 않습니다.
- 종합 상태 이름은 입력의 [종합 상태 이름] 문자열을 한 글자도 바꾸지 않고 씁니다. 다음 이름들 가운데 입력과 다른 이름은 쓰지 않습니다: {states}
- 용어 풀이 괄호(예: 영업이익(본업으로 남긴 돈))는 쓰지 않습니다. 풀이는 파이썬이 리포트 전체에서 처음 나오는 곳에 붙입니다.
- 60일·120일 이동평균은 '최근 3개월 평균', '최근 6개월 평균'으로만 씁니다. '이동평균', 'MA', '60일', '120일'이라고 쓰지 않습니다.
- 날짜는 입력처럼 '2026년 4월 22일', 기간은 '2026년 4월 22~24일'로 씁니다. '2026-04-22' 같은 하이픈 표기는 쓰지 않습니다.
- 모든 문장은 '~니다.'로 끝나는 합쇼체로 쓰고, 한 문장은 괄호 안을 빼고 70자 안팎(90자를 넘지 않게)으로 씁니다.
  한 문장에는 사실 하나, 숫자는 두 개까지만 넣습니다. 길어지면 두 문장으로 나눕니다.
- 출력 형식에 정한 제목·줄 말고 다른 머리말, 맺음말, 목록 기호, 굵은 글씨(**)는 쓰지 않습니다."""


def system_prompt():
    section6, version = guide_section6()
    head = ("당신은 한국 주식 종목 리포트의 해설을 쓰는 작성자입니다. "
            "주식을 처음 보는 사람도 읽을 수 있게 쉬운 말로 씁니다.\n\n"
            f"[리포트 구성 지침 {version} 6장 - 아래 규칙을 그대로 지킵니다]\n")
    return head + section6 + "\n\n" + COMMON_RULES.format(states=", ".join(STATE_NAMES))


# ===========================================================================
# 입력 만들기 (지침 8장 표의 항목만, 모두 표시 문자열)
# ===========================================================================

GLOSSES = sorted(set(easy_read.TERM_GLOSS.values()) | set(easy_read.PROFIT_GLOSS.values()), key=len, reverse=True)


def unglossed(text):
    """쉽게 읽기 문장의 용어 풀이 괄호를 뗀다(AI가 풀이를 따라 쓰지 않게)."""
    for g in GLOSSES:
        text = text.replace(f"({g})", "")
    return text


def _state_base(d):
    """종합 상태 이름(거래 관심도 보조 문구를 뺀 5.4 이름)."""
    return re.sub(r"\s*\(거래 관심 (확대|축소)\)$", "", d["종합 상태"])


def _signals_block(d):
    lines = []
    for key in ("가격 추세", "실적 흐름", "거래 관심도"):
        sig = d[key] or {"판정": "판정 불가", "근거": "자료 부족"}
        lines.append(f"- {key}: {sig['판정']} - {sig['근거']}")
    return "\n".join(lines)


def _event_line(e, strength=True):
    text = (f"- {e['번호']} {e['기간']} | 누적 등락 {e['누적등락']} | 대표 공시: {e['대표공시']} | "
            f"대표 기사: {e['대표기사']}")
    return text + (f" | 근거 강도: {e['근거강도']}" if strength else "")


def top_events(d, n=3):
    """상위 사건: 선정 사건 중 |누적 초과 등락률| 큰 순서로 n개."""
    return sorted(d["사건"], key=lambda e: -abs(e["누적초과등락률"]))[:n]


def _tension_block(d):
    t = d.get("핵심긴장")
    if not t:
        return "[핵심 긴장 문장 뼈대]\n없음(가격 추세 자료 부족) - 1문장은 가격 추세 근거로 씁니다."
    nums = " / ".join(x for x in (t["실적 숫자"], t["가격 숫자"]) if x)
    return (f"[핵심 긴장 문장 뼈대 - 조합: {t['조합']}]\n{t['뼈대']}.\n"
            f"(이 문장의 숫자 {nums}는 그대로 둡니다)")


def _story_block(d):
    s = d["실적해설입력"]
    turns = "\n".join(f"- {t['문장']}" for t in s["전환사실"]) or "- 최근 8개 분기 동안 영업이익의 흑자·적자가 바뀐 분기가 없습니다."
    return "\n\n".join([
        "[분기 표 - 최근 8개 분기, 각 분기 3개월 값]\n" + ("\n".join(f"- {r}" for r in s["분기표"]) or "분기 재무 자료 없음"),
        "[같은 분기 1년 전 비교 - 파이썬 계산]\n" + ("\n".join(f"- {f}" for f in s["비교사실"]) or "없음"),
        "[흑자·적자 전환 사실 - 파이썬 계산, 전환 시점은 이 문장으로만 씁니다]\n" + turns,
        "[분기 흐름 사실 - 파이썬 계산, 직전 분기 대비 방향은 이 문장으로만 씁니다]\n"
        + ("\n".join(f"- {f}" for f in s["흐름사실"]) or "- 없음"),
        f"[계절성 판정 - 파이썬 판정({s['계절성표시']}), 실적 해설에 이 문장을 1번 그대로 씁니다]\n{s['계절성문장']}",
    ])


# 지침 v1.4 6.4: 날짜는 '2026년 4월 22일', 기간은 '2026년 4월 22~24일'
ISO_RANGE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})\s*~\s*(\d{4})-(\d{2})-(\d{2})")
ISO_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def kr_period(y1, m1, d1, y2, m2, d2):
    y1, m1, d1, y2, m2, d2 = map(int, (y1, m1, d1, y2, m2, d2))
    if (y1, m1, d1) == (y2, m2, d2):
        return f"{y1}년 {m1}월 {d1}일"
    if y1 == y2 and m1 == m2:
        return f"{y1}년 {m1}월 {d1}~{d2}일"
    if y1 == y2:
        return f"{y1}년 {m1}월 {d1}일~{m2}월 {d2}일"
    return f"{y1}년 {m1}월 {d1}일~{y2}년 {m2}월 {d2}일"


def kr_dates(text):
    """입력 문자열의 'YYYY-MM-DD'와 'YYYY-MM-DD~YYYY-MM-DD'를 한글 날짜 표기로 바꾼다."""
    text = ISO_RANGE_RE.sub(lambda m: kr_period(*m.groups()), text)
    return ISO_DATE_RE.sub(lambda m: kr_period(*m.groups(), *m.groups()), text)


def build_inputs(ind, fin, d, easy):
    """세 호출의 사용자 입력 문자열. 반환: {호출: 입력 문자열}"""
    name, code = ind["종목명"], ind["종목코드"]
    head = f"[종목] {name} ({code}) · 기준일 {ind['기준일']}"
    state = f"[종합 상태] {d['종합 상태']}\n[종합 상태 이름] {_state_base(d)}"
    reversal = "\n".join(f"{i}. {r['신호']} | 지금 판정: {r['지금 판정']} | 바뀌는 조건: {r['바뀌는 조건']} | "
                         f"지금과의 거리: {r['지금과의 거리']}" for i, r in enumerate(d["반전조건"], 1)) or "없음"
    tops = "\n".join(_event_line(e) for e in top_events(d)) or "선정된 사건 없음"
    events_all = "\n".join(_event_line(e) for e in d["사건"]) or "선정된 사건 없음"
    ch3 = "\n".join(f"- {unglossed(s)}" for s in easy["장"][3]["문장"])
    scen = "\n".join(f"- {s['시나리오']} | 발동 조건: {s['발동 조건']} | 지금 상태에서의 거리: {s['지금 상태에서의 거리']}"
                     for s in d["시나리오"]) or "없음"
    b = d["실적 흐름"]
    inputs = {
        "conclusion": "\n\n".join([
            head,
            "[방향 지시계 - 신호 3개 판정과 근거]\n" + _signals_block(d),
            state,
            _tension_block(d),
            "[반전 조건 표 - 1번이 결론 4문장에 쓸 '가장 가까운 반전 조건']\n" + reversal,
            f"[다음 확인 시점]\n{d['확인시점']['문장']}",
            "[상위 사건 3개 - 시장 대비 누적 등락이 큰 순서, 번호는 리포트 사건 표 번호]\n" + tops,
        ]),
        "story": "\n\n".join([
            head,
            _story_block(d),
            "[쉽게 읽기 3장 문장 - 최근 6개월과 1년 전 비교]\n" + ch3,
            "[사건 표 - 기간 순, 번호는 리포트 사건 표 번호]\n" + events_all,
        ]),
        "scenario": "\n\n".join([
            head,
            "[시나리오 표]\n" + scen,
            state,
            "[상위 사건 - 시장 대비 누적 등락이 큰 순서]\n" + tops,
            f"[실적 흐름]\n{b['판정']} - {b['근거']}",
        ]),
    }
    return {call: kr_dates(text) for call, text in inputs.items()}      # 지침 v1.4 6.4 날짜 표기


FORMATS = {
    "conclusion": """[할 일] 입력으로 '결론' 한 문단과 '왜 그런가' 3줄을 씁니다.

[출력 형식 - 이 형식만 씁니다]
## 결론
(한 문단, 4~5문장)
## 왜 그런가
실적: (한 문장)
주가 움직임: (한 문장)
거래: (한 문장)

[결론 문단 구조 - 지침 4장 1번 2항]
- 1문장: [핵심 긴장 문장 뼈대]를 자연스럽게 다듬어 씁니다. 뼈대의 숫자는 그대로 두고, 실적 숫자 1개와 가격 숫자 1개를 한 문장에 대비시킵니다.
  종목명은 앞에 붙여도 되지만, 종합 상태 이름으로 시작하지 않고 이 문단 어디에도 종합 상태 이름을 쓰지 않습니다.
- 2문장: 1문장이 뜻하는 바를 해석합니다. 반드시 '~모습입니다.', '~흐름입니다.', '~로 보입니다.' 가운데 하나로 끝냅니다.
- 3문장: 해석을 뒷받침하는 근거 1개(근거 강도 강함·보통 사건 1개, 또는 신호 근거의 다른 숫자 1개).
- 4문장: 반전 조건 표 1번 조건을 조건과 거리 숫자로 씁니다.
- 5문장(선택): 다음 확인 시점.

[왜 그런가 3줄]
- '실적:'은 실적 흐름, '주가 움직임:'은 가격 추세와 상위 사건, '거래:'는 거래 관심도를 한 문장씩 씁니다.
- 근거 강도가 약함·없음인 사건은 결론과 3줄 어디에도 인용하지 않습니다.
- 줄 끝에 섹션 안내(예: '(2장 참고)')는 쓰지 않습니다. 파이썬이 붙입니다.""",
    "story": """[할 일] 입력으로 '실적 해설'과 '사건 해설'을 씁니다.

[출력 형식 - 이 형식만 씁니다]
## 실적 해설
(한 문단, 3~4문장)
## 사건 해설
① (1~2문장)
② (1~2문장)
(사건 표의 모든 번호를 순서대로 한 줄씩, 줄 맨 앞에 번호만 씁니다)

[실적 해설 - 3문장 또는 4문장, 5문장 이상 쓰지 않습니다]
- 1~2문장: 매출·영업이익의 증감이 어느 분기에서 왔는지 분기 표와 같은 분기 1년 전 비교 숫자로 설명합니다.
- 3문장: [계절성 판정] 문장을 그대로 1번 씁니다. '계절'이라는 말은 이 문장에만 씁니다.
  스스로 계절성을 판단하거나 판정과 다른 말을 쓰지 않습니다.
- 4문장(선택): 최근 6개월과 1년 전 비교 1개, 또는 [흑자·적자 전환 사실] 1개.
- 흑자·적자로 '바뀌었다·돌아섰다·전환했다'는 시점은 [흑자·적자 전환 사실]에 적힌 분기로만 씁니다.
  분기 표를 보고 전환 시점을 스스로 정하지 않습니다.
- 분기 사이의 증감 방향(직전 분기보다 늘었다·줄었다)은 [분기 흐름 사실]로만 씁니다.
  '지속적으로', '계속', '연속', '꾸준히'는 [분기 흐름 사실]에 '연속'이 있을 때만 씁니다.

[사건 해설]
- 사건마다 1~2문장. 각 사건의 '근거 강도'에 맞는 지침 6.3 표현만 씁니다.
- 근거 강도 강함: "~이 공시된 시기입니다", "~기사가 나온 시기로, 이 사건과 관련된 것으로 보입니다"
- 근거 강도 보통: "~기사가 나온 시기와 겹칩니다" (원인으로 단정하지 않습니다)
- 근거 강도 약함: "같은 시기에 ~가 있었지만 직접적인 원인은 확인되지 않습니다"
- 근거 강도 없음: "공시·뉴스로 확인되는 원인이 없습니다"
- 약함·없음 사건 문장에는 '때문', '영향', '원인은', '덕분', '으로 인해'를 쓰지 않습니다.
- 기사 제목은 필요한 부분만 짧게 옮기고, 제목 끝의 언론사 이름은 쓰지 않습니다.""",
    "scenario": """[할 일] 시나리오 표의 세 시나리오를 각각 해설합니다.

[출력 형식 - 이 형식만 씁니다]
## 상방
(2~3문장)
## 기본
(2~3문장)
## 하방
(2~3문장)

[시나리오 해설 - 시나리오마다 2~3문장]
- 1문장: 가격 조건만 씁니다. 2문장: 실적 조건만 씁니다(실적 조건이 없으면 지금 상태가 이어지는 조건). 3문장(선택): 상위 사건·실적 흐름과 연결.
  가격 조건과 실적 조건을 한 문장에 함께 넣지 않습니다(문장이 90자를 넘습니다).
- 모든 문장을 '~면 ~수 있습니다' 또는 '~이 확인되면 ~에 가까워집니다' 꼴의 조건부 표현으로 끝냅니다.
  '관전 포인트입니다', '~인 셈입니다'처럼 조건 없이 끝나는 문장은 쓰지 않습니다.
- 상위 사건·실적 흐름도 따로 사실 문장으로 쓰지 말고 조건문 안에 넣습니다.
- 지침 6.1의 예시 속 말('협동로봇', '수주')은 다른 회사 예시이므로 쓰지 않습니다. 이 입력에 있는 사건만 씁니다.
- 근거 강도가 약함·없음인 사건을 언급하는 문장에는 '때문', '영향', '원인은', '덕분', '으로 인해'를 쓰지 않습니다.
- 확률, 목표 가격, 기간 예측은 쓰지 않습니다.""",
}


def input_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ===========================================================================
# 파싱
# ===========================================================================

def _sections(text):
    """'## 제목' 단위로 나눈다. 반환: {제목: [줄]}"""
    out, current = {}, None
    for line in (text or "").splitlines():
        m = re.match(r"^\s*##\s*(.+?)\s*$", line)
        if m:
            current = m.group(1)
            out[current] = []
        elif current is not None and line.strip():
            out[current].append(line.strip())
    return out


def parse(call, text):
    """호출별 출력을 구조로 바꾼다. 형식이 어긋난 부분은 None/빈 값으로 둔다."""
    sec = _sections(text)
    if call == "conclusion":
        lines = {}
        for line in sec.get("왜 그런가", []):
            m = re.match(r"^(실적|주가 움직임|거래)\s*:\s*(.+)$", line)
            if m:
                lines[m.group(1)] = m.group(2).strip()
        return {"결론": " ".join(sec.get("결론", [])) or None, "3줄": lines}
    if call == "story":
        events = {}
        for line in sec.get("사건 해설", []):
            m = re.match(r"^([①②③④⑤])\s*(.+)$", line)
            if m:
                events[m.group(1)] = m.group(2).strip()
        return {"실적": " ".join(sec.get("실적 해설", [])) or None, "사건": events}
    return {name: (" ".join(sec.get(name, [])) or None) for name in SCENARIO_NAMES}


def body_texts(call, parsed):
    """검증 대상 본문 조각 목록 [(위치 이름, 텍스트)]."""
    if call == "conclusion":
        return [("결론", parsed["결론"] or "")] + [(f"왜 그런가 {k}", v) for k, v in parsed["3줄"].items()]
    if call == "story":
        return [("실적 해설", parsed["실적"] or "")] + [(f"사건 {k}", v) for k, v in parsed["사건"].items()]
    return [(k, v or "") for k, v in parsed.items()]


# ===========================================================================
# 문장 길이 자동 분할 (지침 v1.3 6.4)
# ===========================================================================

def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p for p in parts if p]


def plain_len(sentence):
    """괄호와 괄호 안 글자를 뺀 길이(지침 6.4)."""
    prev = None
    while prev != sentence:
        prev, sentence = sentence, re.sub(r"\([^()]*\)", "", sentence)
    return len(sentence.strip())


CONNECTIVES = ("지만", "으며", "며", "고")          # 지침 6.4 분할 위치: 쉼표·연결어미('~고,', '~며,', '~지만,')
NOT_CONNECTIVE = ("최고", "재고", "보고", "참고", "광고", "사고", "신고", "잔고", "공고", "경고")
ENDS_FORMAL_RE = re.compile(r"니다(\([^()]*\))?\.?$")   # 합쇼체 종결(끝의 괄호 보충은 허용: '…예정입니다(… 기준).')
COND_CLAUSE_RE = re.compile(r"[가-힣](으면|면)[\s,]")
LINE_PREFIX_RE = re.compile(r"^((?:실적|주가 움직임|거래)\s*:\s*|[①②③④⑤]\s*)")


def _formal(stem):
    """용언 어간 + 합쇼체 종결(줄었 -> 줄었습니다, 바뀌 -> 바뀝니다, 구간이 -> 구간입니다, 알 -> 압니다)."""
    last = stem[-1]
    if not ("가" <= last <= "힣"):
        return None
    jong = (ord(last) - 0xAC00) % 28
    if jong == 0:
        return stem[:-1] + chr(ord(last) + 17) + "니다"          # 받침 없음: ㅂ 받침 + 니다
    if jong == 8:
        return stem[:-1] + chr(ord(last) - 8 + 17) + "니다"      # ㄹ 받침: ㄹ 탈락 + ㅂ니다
    return stem + "습니다"


QUOTE_ENDINGS = ("라고", "다고", "자고", "냐고", "려고", "라며", "다며", "자며")   # 인용·목적 어미(연결어미로 보지 않음)
AUX_NEXT = ("있", "싶", "나서", "나니", "보니", "말", "계")                       # '~고 있다/싶다/나서' 보조 용언


def split_long(sentence):
    """90자 넘는 문장을 연결어미('~고', '~며', '~지만') 위치에서 두 문장으로 나눈다(지침 6.4).

    쉼표가 붙은 위치('~고,')를 먼저 쓰고, 없으면 쉼표 없는 연결어미 위치도 쓴다.
    괄호 안, 인용·목적 어미('~라고', '~려고'), 보조 용언('~고 있다'), 조건 하나를 이루는 두 절('~고, ~하면')은 나누지 않는다.
    두 문장 모두 90자 이내가 되는 곳 중 쉼표 위치 우선, 그다음 길이가 가장 고른 곳. 나눌 수 없으면 None.
    """
    best = None
    for m in re.finditer(r"([가-힣]+)(,?)\s+(?=(\S+))", sentence):
        word, comma, nxt = m.group(1), m.group(2), m.group(3)
        before = sentence[:m.start(1)]
        if word in NOT_CONNECTIVE or word.endswith(QUOTE_ENDINGS) or before.count("(") != before.count(")"):
            continue
        if not comma and nxt.startswith(AUX_NEXT):
            continue
        ending = next((e for e in CONNECTIVES if word.endswith(e) and len(word) > len(e)), None)
        if not ending:
            continue
        formal = _formal(word[:-len(ending)])
        if not formal:
            continue
        first = before + formal + "."
        rest = sentence[m.end():]
        second = ("하지만 " if ending == "지만" else "") + rest
        if not ENDS_FORMAL_RE.search(second) or plain_len(first) < 10 or plain_len(second) < 10:
            continue
        if COND_CLAUSE_RE.search(second) and not COND_CLAUSE_RE.search(first):
            continue                                # '~고, ~하면'처럼 조건 하나를 이루는 두 절은 나누지 않는다
        if plain_len(first) > MAX_SENTENCE or plain_len(second) > MAX_SENTENCE:
            continue
        score = (0 if comma else 1, max(plain_len(first), plain_len(second)))
        if best is None or score < best[0]:
            best = (score, first, second)
    return None if best is None else (best[1], best[2])


def auto_split(call, text):
    """출력 전체에서 90자 넘는 문장을 나눈다. 블록 문장 수 한도를 넘게 되면 나누지 않는다.

    반환: (새 텍스트, 분할 기록 목록)
    """
    lines = text.splitlines()
    section = None
    counts = {}                                   # 섹션 단위 한도용 현재 문장 수
    for line in lines:
        m = re.match(r"^\s*##\s*(.+?)\s*$", line)
        if m:
            section = m.group(1)
        elif section and line.strip():
            body = LINE_PREFIX_RE.sub("", line.strip())
            counts[section] = counts.get(section, 0) + len(split_sentences(body))
    out, done, section = [], [], None
    for line in lines:
        m = re.match(r"^\s*##\s*(.+?)\s*$", line)
        if m or not line.strip():
            section = m.group(1) if m else section
            out.append(line)
            continue
        per_line, _, hi = SENTENCE_LIMITS.get((call, section), (False, 0, 99))
        prefix_m = LINE_PREFIX_RE.match(line.strip())
        prefix = prefix_m.group(1) if prefix_m else ""
        sents = split_sentences(line.strip()[len(prefix):])
        new = []
        for i, s in enumerate(sents):
            if plain_len(s) > MAX_SENTENCE:
                current = len(new) + len(sents) - i if per_line else counts.get(section, 0)
                pieces = split_long(s)
                if pieces and current + 1 <= hi:
                    new.extend(pieces)
                    done.append(f"{section}: {plain_len(s)}자 -> {plain_len(pieces[0])}자 + {plain_len(pieces[1])}자")
                    if not per_line:
                        counts[section] = counts.get(section, 0) + 1
                    continue
            new.append(s)
        out.append(prefix + " ".join(new))
    return "\n".join(out), done


# ===========================================================================
# 검증
# ===========================================================================

NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
JO_EOK_RE = re.compile(r"(-?\d[\d,]*)\s*조(?:\s*(\d[\d,]*)\s*억)?")
ALLOWED_PLAIN = {1.0, 2.0, 3.0, 4.0, 5.0, 6.0}      # '3개월', '6개월', '2개 분기', '1문장' 같은 문장 틀 숫자
TOLERANCE = 0.005

# 지침 6.2 금지 표현
FORBIDDEN = {
    "권유": ["매수", "매도", "사세요", "파세요", "추천", "비중 확대", "비중 축소", "비중확대", "비중축소",
             "진입", "손절", "익절", "담으세요"],
    "목표·보장": ["목표가", "목표주가", "적정주가", "수익 보장", "반드시", "확실히"],
    "단정 예측": ["오를 것입니다", "내릴 것입니다", "상승할 것", "하락할 것", "도달할 것"],
    "가치 판단": ["저평가", "고평가", "싸다", "비싸다"],
    "명령형": ["하세요", "하십시오", "해야 합니다"],
    "판정 서술": ["판정됐", "판정되었"],                     # v1.3: 본문 문장의 '판정됐습니다·판정되었습니다'
}
# '순매수·순매도'는 수급 사실(기사 제목)이라 권유로 보지 않는다
FORBIDDEN_EXEMPT = {"매수": ("순매수",), "매도": ("순매도",)}
# 지침 6.3 검증: 약함·없음 사건 문장의 원인 단정어
CAUSAL_WORDS = ("때문", "영향", "원인이", "원인으로", "덕분", "으로 인해")      # 지침 v1.4 6.3
# 지침 v1.4 6.3: 표의 허용 표현("직접적인 원인은 확인되지 않습니다", "확인되는 원인이 없습니다")은 검사에서 뺀다
CAUSAL_EXEMPT_RE = re.compile(r"원인은\s*확인되지\s*않|확인되는\s*원인이\s*없")


def causal_hits(sentence):
    text = CAUSAL_EXEMPT_RE.sub("", sentence)
    return [w for w in CAUSAL_WORDS if w in text]
# 지침 6장 예시 문장에만 있는 말(입력에 없으면 예시를 옮긴 것으로 본다)
GUIDE_EXAMPLE_TERMS = ("협동로봇", "수주")
# 이동평균 용어(지침 6.4)
MA_WORDS_RE = re.compile(r"이동평균|(?<![A-Za-z])MA\s*\d*(?![A-Za-z])|(?<![\d,])(60|120)일")
# (C) 조건부 표현
CONDITIONAL_RE = re.compile(r"(으면|[가-힣]면[\s,]|경우|수 있|가까워|전까지|때에는|이라면|다면)")
# (A) 결론 2문장 해석 어미
INTERPRET_RE = re.compile(r"(모습입니다|흐름입니다|로 보입니다)\.?$")
# 계절성 서술(지침 v1.3 6.2): 판정과 반대되는 말
SEASON_DENY = ("판단하기 어렵", "판단할 수 없", "판단 불가", "판단이 어렵", "알기 어렵", "확인되지", "없습니다", "어렵습니다")

REPLACEMENTS = {                  # 1단계 치환(뜻이 그대로인 용어만)
    "60일 이동평균": "최근 3개월 평균", "120일 이동평균": "최근 6개월 평균",
    "60일 평균": "최근 3개월 평균", "120일 평균": "최근 6개월 평균",
    "최근 최근": "최근", "**": "",
    # '진입'(6.2 권유 목록)이 '추세·구간에 들어선다'는 뜻으로만 쓰인 경우
    "추세에 진입": "추세에 들어서", "추세로 진입": "추세로 들어서", "구간에 진입": "구간에 들어서", "구간으로 진입": "구간으로 들어서",
    "추세 진입": "추세 전환",
    "지금가는": "지금 주가는",                               # v1.5: KH바텍 (A) 오탈자
}
WARN_KEY = "문장 길이 경고(70~90자)"


def _to_float(token):
    try:
        return float(token.replace(",", ""))
    except Exception:
        return None


def _jo_value(m):
    jo, eok = _to_float(m.group(1)), (_to_float(m.group(2)) if m.group(2) else 0.0)
    if jo is None or eok is None:
        return None
    return abs(jo) * 10_000 + eok


def allowed_numbers(input_text):
    """입력 문자열에 적힌 숫자 집합(절댓값)과 조·억 금액 집합(억 원)."""
    jo = {round(_jo_value(m), 2) for m in JO_EOK_RE.finditer(input_text) if _jo_value(m) is not None}
    plain = {round(abs(v), 3) for v in (_to_float(t) for t in NUMBER_RE.findall(input_text)) if v is not None}
    return plain | ALLOWED_PLAIN, jo


def check_numbers(text, input_text):
    """지침 9장 4번: 출력 숫자·날짜(연·월·일 숫자)가 입력에 있는가."""
    plain, jo = allowed_numbers(input_text)
    bad = []

    def sub_jo(m):
        v = _jo_value(m)
        if v is None or not any(abs(v - a) <= TOLERANCE for a in jo):
            bad.append(m.group(0).strip())
        return " "

    text = JO_EOK_RE.sub(sub_jo, text)
    for token in NUMBER_RE.findall(text):
        v = _to_float(token)
        if v is None:
            continue
        if not any(abs(abs(v) - a) <= TOLERANCE for a in plain):
            bad.append(token)
    return sorted(set(bad), key=bad.index)


FLOW_WORDS = ("지속적으로", "계속", "연속", "꾸준히")          # 지침 v1.5 6.2


def check_flow_words(call, parts, d):
    """지침 v1.5 6.2: '지속적으로·계속·연속·꾸준히'로 분기 흐름을 서술했는가(분기 흐름 사실에 '연속'이 있으면 허용).

    (B) 실적 해설은 모든 문장, 그 밖의 본문은 '분기'가 든 문장만 분기 흐름 서술로 본다.
    """
    if d["실적해설입력"].get("흐름연속"):
        return []
    hits = []
    for where, t in parts:
        for s in split_sentences(t):
            if where != "실적 해설" and "분기" not in s:
                continue
            words = [w for w in FLOW_WORDS if w in s]
            if words:
                hits.append(f"{'·'.join(words)}(분기 흐름, 파이썬 사실에 '연속' 없음): {where} {s[:25]}…")
    return hits


def check_forbidden(text):
    """지침 9장 5번: 6.2 금지 표현."""
    hits = []
    for kind, words in FORBIDDEN.items():
        for w in words:
            t = text
            for ok in FORBIDDEN_EXEMPT.get(w, ()):
                t = t.replace(ok, "")
            if w in t:
                hits.append(f"{w}({kind})")
    return hits


def check_season(text, d):
    """지침 v1.4 5.10·6.2(체크리스트 12번 앞부분): 실적 해설에 계절성 문장이 정확히 1번 있고 판정과 같은가."""
    s_in = d["실적해설입력"]
    verdict = s_in["계절성"]
    sents = [s for s in split_sentences(text) if "계절" in s]
    bad = [] if len(sents) == 1 else [f"계절성 문장 {len(sents)}개(1개여야 함)"]
    for s in sents:
        denies = any(w in s for w in SEASON_DENY)
        if verdict == direction.SEASONAL and (denies or f"{s_in['계절성분기']}분기" not in s):
            bad.append(f"판정 '{s_in['계절성표시']}'과 다름: {s[:30]}…")
        if verdict == direction.SEASON_UNKNOWN and not denies:
            bad.append(f"판정 '{verdict}'과 다름: {s[:30]}…")
    return bad


QUARTER_RE = re.compile(r"(\d{4})년\s*(\d)(?:\s*~\s*(\d))?분기")
TURN_VERB_RE = re.compile(r"돌아서|돌아섰|전환|바뀌|바뀐|반전")


def _turn_way(sentence):
    if "적자에서 흑자" in sentence or "흑자로" in sentence or "흑자 전환" in sentence:
        return "적자에서 흑자로"
    if "흑자에서 적자" in sentence or "적자로" in sentence or "적자 전환" in sentence:
        return "흑자에서 적자로"
    return None


def check_turns(text, d, fin_items=None):
    """체크리스트 12번 뒷부분: 흑자·적자 전환 시점 서술이 파이썬 사실 문장과 같은가.

    전환 동사(돌아서다·전환·바뀌다)와 흑자/적자가 함께 있고 분기가 적힌 문장을 본다.
    그 문장의 분기 중 하나가 파이썬 전환 사실(같은 방향)이면 통과. '1년 전'이 있는 문장은 같은 분기 1년 전 비교로 보고
    그 분기의 1년 전 부호가 실제로 반대면 통과. 분기가 없는 문장(최근 6개월 합계 등)은 시점 서술이 아니므로 넘긴다.
    """
    s_in = d["실적해설입력"]
    facts = {(t["분기"], t["방향"]) for t in s_in["전환사실"]}
    yoy = s_in.get("전년부호전환") or set()
    bad = []
    for s in split_sentences(text):
        if not (("흑자" in s or "적자" in s) and TURN_VERB_RE.search(s)):
            continue
        way = _turn_way(s)
        quarters = []
        for m in QUARTER_RE.finditer(s):
            y, q1, q2 = int(m.group(1)), int(m.group(2)), int(m.group(3) or m.group(2))
            quarters += [f"{y}Q{q}" for q in range(q1, q2 + 1)]
        if not quarters or way is None:
            continue
        if any((q, way) in facts for q in quarters):
            continue
        if "1년 전" in s and any((q, way) in yoy for q in quarters):
            continue
        bad.append(f"전환 시점이 파이썬 사실과 다름: {s[:40]}…")
    return bad


def _date_forms(iso):
    y, m, dd = str(iso)[:10].split("-")
    # '4월 22~24일'처럼 기간 앞머리로만 쓰인 경우도 잡는다(v1.4 한글 기간 표기)
    return (f"{y}-{m}-{dd}", f"{m}-{dd}", f"{int(m)}월 {int(dd)}일", f"{int(m)}월 {int(dd)}~")


def _has_form(sentence, form):
    """숫자 경계를 지켜 찾는다('11월 14일'이 '1월 14일'로 잡히지 않게)."""
    return re.search(rf"(?<!\d){re.escape(form)}(?!\d)", sentence) is not None


def _months(e):
    return {int(e["시작일"][5:7]), int(e["종료일"][5:7])}


def _exact_mention(sentence, e):
    """사건 번호 또는 시작·종료일(ISO·'M월 D일')로 가리키는가."""
    return e["번호"] in sentence or any(_has_form(sentence, f) for day in (e["시작일"], e["종료일"])
                                        for f in _date_forms(day))


def _month_mention(sentence, e):
    """사건 달('1월' - 뒤에 '○일'이 없을 때)로 가리키는가."""
    return any(re.search(rf"(?<!\d){mo}월(?!\s*\d+\s*일)", sentence) for mo in _months(e))


def check_strength_mentions(call, parts, d):
    """지침 v1.3 6.3: 약함·없음 사건 인용 검사를 (A)(C)까지 확대.

    사건을 가리키는 문장 = 사건 번호·날짜가 있거나, 사건 달이 있고 그 달에 강함·보통 사건이 없는 문장.
    (A) 약함·없음 사건을 가리키면 오류 / (C) 약함·없음 사건을 가리키는 문장에 원인 단정어가 있으면 오류.
    """
    weak_levels = (direction.WEAK, direction.NONE)
    weak = [e for e in d["사건"] if e["근거강도"] in weak_levels]
    strong_months = set().union(*[_months(e) for e in d["사건"] if e["근거강도"] not in weak_levels] or [set()])
    out = []
    for where, t in parts:
        for s in split_sentences(t):
            for e in weak:
                if not (_exact_mention(s, e) or (_month_mention(s, e) and not (_months(e) & strong_months))):
                    continue
                if call == "conclusion":
                    out.append(f"{where}: 근거 강도 {e['근거강도']} 사건 {e['번호']}({e['기간']}) 인용")
                else:
                    words = causal_hits(s)
                    if words:
                        out.append(f"{where}: 사건 {e['번호']}(근거 강도 {e['근거강도']})에 {', '.join(words)}")
    return out


def check_state(call, full_text, d):
    """지침 9장 7번: 종합 상태 이름을 바꾸거나 다른 상태 이름을 만들지 않았는가."""
    base = _state_base(d)
    problems = [f"다른 상태 이름 '{n}'" for n in STATE_NAMES if n != base and n in full_text]
    for m in re.finditer(r"'([^']{4,30}구간)'", full_text):
        if m.group(1) != base and m.group(1) not in d["종합 상태"]:
            problems.append(f"새 상태 이름 '{m.group(1)}'")
    return problems


def check_conclusion_structure(parsed, d):
    """지침 v1.3 4장 1번 2항: 1문장 = 핵심 긴장(숫자 2개, 상태 이름으로 시작 안 함), 2문장 = 해석 어미,
    4문장 = 반전 조건 표 첫 행."""
    sents = split_sentences(parsed["결론"] or "")
    problems = []
    if not sents:
        return problems
    t = d.get("핵심긴장")
    first = sents[0]
    if t:
        for key in ("실적 숫자", "가격 숫자"):
            if t[key] and t[key] not in first:
                problems.append(f"1문장에 {key} '{t[key]}' 없음")
    base = _state_base(d)
    if base in (parsed["결론"] or ""):
        problems.append("결론 문단에 종합 상태 이름을 씀")
    if len(sents) >= 2 and not INTERPRET_RE.search(sents[1]):
        problems.append("2문장이 '~모습입니다/~흐름입니다/~로 보입니다'로 끝나지 않음")
    rows = d["반전조건"]
    if rows and len(sents) >= 4:
        nums = set(NUMBER_RE.findall(rows[0]["바뀌는 조건"] + " " + rows[0]["지금과의 거리"])) - {"3", "6", "0"}
        if nums and not any(n in sents[3] for n in nums):
            problems.append(f"4문장이 반전 조건 표 1번({rows[0]['바뀌는 조건'][:25]}…)이 아님")
    return problems


def validate(call, text, input_text, d):
    """호출 출력 검증. 반환: ({항목: [문제...]}, parsed). 빈 목록이면 통과. WARN_KEY 항목은 경고(실패 아님)."""
    parsed = parse(call, text)
    parts = body_texts(call, parsed)
    full = " ".join(t for _, t in parts)
    out = {
        "숫자·날짜(9장 4번)": check_numbers(full, input_text),
        "금지 표현(9장 5번)": check_forbidden(full) + check_flow_words(call, parts, d),
        "근거 강도 표현(9장 6번)": check_strength_mentions(call, parts, d) if call != "story" else [],
        "종합 상태 이름(9장 7번)": check_state(call, full, d),
        "문장 길이(90자)": [],
        WARN_KEY: [],
        "합쇼체": [],
        "형식": [],
        "이동평균 용어": [f"{where}: {m.group(0)}" for where, t in parts for m in MA_WORDS_RE.finditer(t)],
        "용어 풀이 괄호": [],
        "지침 예시 복제": [f"'{w}'(입력에 없음)" for w in GUIDE_EXAMPLE_TERMS if w in full and w not in input_text],
        "계절성 서술": check_season(parsed["실적"] or "", d) if call == "story" else [],
        "흑자·적자 전환 시점": check_turns(parsed["실적"] or "", d) if call == "story" else [],
        "날짜 표기": [],
    }
    for where, t in parts:
        for s in split_sentences(t):
            n = plain_len(s)
            if n > MAX_SENTENCE:
                out["문장 길이(90자)"].append(f"{where} {n}자: {s[:30]}…")
            elif n > WARN_SENTENCE:
                out[WARN_KEY].append(f"{where} {n}자")
            if not ENDS_FORMAL_RE.search(s):
                out["합쇼체"].append(f"{where}: …{s[-20:]}")
        for term in ("매출", "영업이익", "순이익", "흑자", "적자", "거래량", "부채비율", "시가총액"):
            for m in re.finditer(term + r"\(([^()]*)\)", t):
                if re.search(r"\d", m.group(1)):         # v1.4: '적자(-23억 원)'처럼 숫자가 든 괄호는 풀이가 아니다
                    continue
                out["용어 풀이 괄호"].append(f"{where}: {term}({m.group(1)})")
        for m in ISO_DATE_RE.finditer(t):                # v1.4 6.4: 하이픈 날짜 표기 금지
            out["날짜 표기"].append(f"{where}: {m.group(0)}")

    fmt = out["형식"]
    if call == "conclusion":
        n = len(split_sentences(parsed["결론"] or ""))
        if not 4 <= n <= 5:
            fmt.append(f"결론 {n}문장(4~5문장)")
        fmt.extend(check_conclusion_structure(parsed, d))
        for label in LINE_LABELS:
            line = parsed["3줄"].get(label)
            if not line:
                fmt.append(f"'{label}:' 줄 없음")
            elif not 1 <= len(split_sentences(line)) <= 2:
                fmt.append(f"'{label}:' 줄이 1~2문장이 아님")
    elif call == "story":
        n = len(split_sentences(parsed["실적"] or ""))
        if not 3 <= n <= 4:
            fmt.append(f"실적 해설 {n}문장(3~4문장)")
        want = [e["번호"] for e in d["사건"]]
        got = list(parsed["사건"])
        if got != want:
            fmt.append(f"사건 번호 {''.join(got) or '없음'} (입력 {''.join(want) or '없음'})")
        strength = {e["번호"]: e["근거강도"] for e in d["사건"]}
        for num, line in parsed["사건"].items():
            k = len(split_sentences(line))
            if not 1 <= k <= 2:
                fmt.append(f"사건 {num} {k}문장(1~2문장)")
            if strength.get(num) in (direction.WEAK, direction.NONE):
                words = causal_hits(line)
                if words:
                    out["근거 강도 표현(9장 6번)"].append(
                        f"사건 {num}(근거 강도 {strength[num]})에 {', '.join(words)}")
    else:
        for name in SCENARIO_NAMES:
            body = parsed[name]
            if not body:
                fmt.append(f"'## {name}' 없음")
                continue
            sents = split_sentences(body)
            if not 2 <= len(sents) <= 3:
                fmt.append(f"{name} {len(sents)}문장(2~3문장)")
            for s in sents:
                if not CONDITIONAL_RE.search(s):
                    fmt.append(f"{name} 조건부 표현 아님: {s[:30]}…")
    return out, parsed


def failures(check):
    return [f"{k}: " + " / ".join(v[:5]) for k, v in check.items() if v and k != WARN_KEY]


# ===========================================================================
# 호출·저장
# ===========================================================================

META_PREFIX, META_SUFFIX = "<!-- meta: ", " -->"


def cache_path(call, code, base_date, model):
    day = str(base_date).replace("-", "")[:8]
    return os.path.join(CACHE_DIR, f"narr_{call}_{str(code).zfill(6)}_{day}_{model}_{CACHE_VERSION}.md")


def _save(path, text, meta):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(META_PREFIX + json.dumps(meta, ensure_ascii=False) + META_SUFFIX + "\n" + text)


def load_cached(path):
    if not os.path.exists(path):
        return None
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            head, _, body = f.read().partition("\n")
        return json.loads(head[len(META_PREFIX):-len(META_SUFFIX)]), body
    except Exception:
        return None


def estimate_cost_krw(model, input_tokens, output_tokens):
    """output_tokens = 사고 토큰을 포함한 전체 출력 토큰(과금 기준)."""
    spec = MODELS.get(model) or next(v for k, v in MODELS.items() if v.get("fallback") == model)
    return ((input_tokens / 1e6) * spec["input_per_mtok"] + (output_tokens / 1e6) * spec["output_per_mtok"]) * USD_KRW


def short(model_id):
    return "Haiku" if "haiku" in model_id else ("Sonnet" if "sonnet" in model_id else model_id)


def _call_claude(model, system, user):
    """Claude API 호출. 반환: {"text", "input", "output_total", "thinking", "model", "stop"}

    output_total = 과금되는 전체 출력(사고 포함), thinking = usage.output_tokens_details.thinking_tokens
    """
    import anthropic
    api_key = keys.get_anthropic_api_key()
    if not api_key:
        raise RuntimeError("API 키가 없습니다. api_secrets.py에 ANTHROPIC_API_KEY를 입력하세요.")
    client = anthropic.Anthropic(api_key=api_key)
    candidates = [model] + ([MODELS[model]["fallback"]] if MODELS.get(model, {}).get("fallback") else [])
    last = None
    for candidate in candidates:
        try:
            extra = {"output_config": {"effort": SONNET_EFFORT}} if model == SONNET else {}
            _t = time.perf_counter()                                             # [계측]
            r = client.messages.create(model=candidate, max_tokens=MAX_TOKENS[model], system=system,
                                       messages=[{"role": "user", "content": user}], **extra)
            print(f"[NET] api.anthropic.com/v1/messages({candidate}) {time.perf_counter() - _t:.2f}s", flush=True)  # [계측]
            text = "".join(b.text for b in r.content if b.type == "text")
            details = getattr(r.usage, "output_tokens_details", None)
            thinking = (getattr(details, "thinking_tokens", 0) or 0) if details else 0
            return {"text": text, "input": r.usage.input_tokens, "output_total": r.usage.output_tokens,
                    "thinking": thinking, "model": candidate, "stop": r.stop_reason}
        except anthropic.NotFoundError as exc:          # 모델 ID가 없을 때만 대체 ID로
            last = exc
    raise last


def apply_replacements(text):
    changed = []
    for old, new in REPLACEMENTS.items():
        if old in text:
            changed.append(f"{old}->{new}({text.count(old)})")
            text = text.replace(old, new)
    return text, changed


def _attempt(call, model, system, user, input_text, d, label):
    r = _call_claude(model, system, user)
    text, replaced = apply_replacements(r["text"].strip())
    text, splits = auto_split(call, text)
    check, parsed = validate(call, text, input_text, d)
    if r["stop"] == "max_tokens":
        check["형식"].insert(0, f"출력이 {MAX_TOKENS[model]} 토큰에서 잘림")
    fails = failures(check)
    return {"단계": label, "model": r["model"], "text": text, "parsed": parsed, "검증": check, "실패항목": fails,
            "통과": not fails, "input_tokens": r["input"], "output_tokens": r["output_total"] - r["thinking"],
            "thinking_tokens": r["thinking"], "output_total_tokens": r["output_total"], "stop": r["stop"],
            "cost_krw": estimate_cost_krw(r["model"], r["input"], r["output_total"]), "치환": replaced, "분할": splits}


def _retry_prompt(user, fails):
    return (user + "\n\n[직전 답변에서 확인된 문제]\n" + "\n".join(f"- {f}" for f in fails)
            + "\n\n위 문제를 모두 고쳐, 같은 출력 형식으로 처음부터 다시 씁니다.")


def run_call(call, ind, d, inputs, report_hash, force=False, reuse=False):
    """호출 하나: 캐시 확인 -> 호출·치환·분할·검증 -> 재생성 -> Sonnet 보정. 결과 dict를 돌려준다."""
    spec = CALLS[call]
    model = spec["모델"]
    system = system_prompt()
    input_text = inputs[call]
    user = input_text + "\n\n" + FORMATS[call]
    h_in, h_prompt = input_hash(input_text), input_hash(system + FORMATS[call])
    path = cache_path(call, ind["종목코드"], ind["기준일"], model)

    cached = None if force else load_cached(path)
    same_prompt = bool(cached) and cached[0].get("프롬프트해시") == h_prompt
    if cached and cached[0].get("호출입력해시") == h_in and (same_prompt or reuse):
        meta, text = cached
        text, replaced = apply_replacements(text)                   # 치환표가 늘었으면 저장본에도 적용(v1.5)
        text, _ = auto_split(call, text)
        check, parsed = validate(call, text, input_text, d)         # 저장본도 지금 규칙으로 다시 검증
        return {**meta, "text": text, "parsed": parsed, "검증": check, "통과": not failures(check),
                "cached": True, "path": path, "이번비용": 0.0, "저장본치환": replaced,
                "프롬프트변경재사용": not same_prompt, "리포트입력해시": report_hash}

    attempts = [_attempt(call, model, system, user, input_text, d, f"{short(model)} 1회")]
    if not attempts[-1]["통과"]:
        attempts.append(_attempt(call, model, system, _retry_prompt(user, attempts[-1]["실패항목"]),
                                 input_text, d, f"{short(model)} 재생성"))
    if not attempts[-1]["통과"] and model != REPAIR_MODEL:
        attempts.append(_attempt(call, REPAIR_MODEL, system, _retry_prompt(user, attempts[-1]["실패항목"]),
                                 input_text, d, f"{short(REPAIR_MODEL)} 보정"))
    final = attempts[-1]
    total = lambda key: sum(a[key] for a in attempts)
    meta = {
        "호출": call, "호출이름": spec["이름"], "model": final["model"], "기준일": ind["기준일"],
        "호출입력해시": h_in, "프롬프트해시": h_prompt, "리포트입력해시": report_hash,
        "지침버전": direction.REPORT_GUIDE_VERSION,
        "input_tokens": total("input_tokens"), "output_tokens": total("output_tokens"),
        "thinking_tokens": total("thinking_tokens"), "output_total_tokens": total("output_total_tokens"),
        "cost_krw": round(total("cost_krw"), 2),
        "시도경로": " → ".join(a["단계"] for a in attempts), "시도수": len(attempts),
        "통과": final["통과"], "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "시도별": [{"단계": a["단계"], "model": a["model"], "입력": a["input_tokens"], "출력": a["output_tokens"],
                    "사고": a["thinking_tokens"], "출력합계": a["output_total_tokens"], "종료": a["stop"],
                    "비용": round(a["cost_krw"], 2), "통과": a["통과"], "실패항목": a["실패항목"],
                    "경고": a["검증"].get(WARN_KEY, []), "치환": a["치환"], "분할": a["분할"]}
                   for a in attempts],
    }
    _save(path, final["text"], meta)
    return {**meta, "text": final["text"], "parsed": final["parsed"], "검증": final["검증"],
            "cached": False, "path": path, "이번비용": meta["cost_krw"]}


def report_input_hash(inputs):
    """세 호출 입력을 합친 해시(세 호출이 같은 판정 결과에서 나온 입력인지 확인용)."""
    return input_hash("\n\n".join(inputs[c] for c in CALL_ORDER))


def narrate(ind, fin, d, easy, force=False, reuse_calls=()):
    """세 호출을 차례로 실행한다. API 키가 없으면 None.

    reuse_calls: 입력 해시만 같으면 프롬프트가 바뀌어도 저장본을 쓸 호출 이름들(지금 규칙으로 다시 검증).
    반환: {"결과": {호출: 결과}, "입력": {호출: 입력}, "리포트입력해시", "이번비용", "누적비용", "오류": {호출: 사유}}
    """
    if not keys.has_api_key():
        return None
    inputs = build_inputs(ind, fin, d, easy)
    rh = report_input_hash(inputs)
    out = {"결과": {}, "입력": inputs, "리포트입력해시": rh, "오류": {}}
    for call in CALL_ORDER:
        try:
            out["결과"][call] = run_call(call, ind, d, inputs, rh, force=force, reuse=call in reuse_calls)
        except Exception as exc:
            out["오류"][call] = f"{type(exc).__name__}: {exc}"
    res = out["결과"].values()
    out["이번비용"] = round(sum(r["이번비용"] for r in res), 2)
    out["누적비용"] = round(sum(r["cost_krw"] for r in res), 2)
    return out


def failed_items(result):
    """최종 검증에 걸린 항목 이름 목록(경고 제외)."""
    return [k for k, v in (result or {}).get("검증", {}).items() if v and k != WARN_KEY]
