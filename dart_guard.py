# -*- coding: utf-8 -*-
"""
dart_guard.py - DART(opendart.fss.or.kr) 호출 공통 차단기 (2026-09-30)

근거: 클라우드에서 DART 요청이 전부 ConnectTimeout(15초)으로 실패해 종목 1개에 약 18회 x 15초 = 256~272초가 걸렸다.

규칙
 - 모든 DART 호출은 get() 을 거친다: 연결 timeout 3초, 읽기 timeout 15초(corpCode.xml 은 호출 쪽에서 읽기 시간만 늘린다).
 - ConnectTimeout / ConnectionError 가 1번이라도 나면 "DART 불가" 상태를 BLOCK_SECONDS(10분) 동안 유지한다.
   그동안 get() 은 네트워크에 나가지 않고 즉시 DartUnavailable 을 던진다(캐시 읽기는 호출 쪽에서 그대로 한다).
 - 읽기 timeout(ReadTimeout)·HTTP 오류·status 오류(010/013 등)는 차단 사유가 아니다(기존 처리 규칙 그대로).
 - 상태는 프로세스 전체(모든 세션·스레드)가 함께 쓴다.
 - 실패 결과를 캐시에 남기지 않도록 호출 쪽은 available()/state_key() 로 확인한다.
"""

import threading
import time

import requests

CONNECT_TIMEOUT = 3
READ_TIMEOUT = 15
BLOCK_SECONDS = 10 * 60

# 화면 안내 문구(재무 섹션·방향 지시계 실적 칸)
UNAVAILABLE_MESSAGE = "DART 서버에 연결할 수 없어 재무를 불러오지 못했습니다(일시적). 잠시 후 재무 새로고침"

_lock = threading.Lock()
_state = {"until": 0.0, "trips": 0, "reason": None}


class DartUnavailable(Exception):
    """DART 불가 상태라 호출을 건너뛰었거나, 이번 호출에서 연결 실패로 불가 상태가 됐다."""


class TrippedDuringCache(Exception):
    """st 캐시 함수 계산 도중 DART 불가가 됐다: 결과(result)는 돌려주되 캐시하지 않기 위한 예외."""

    def __init__(self, result):
        super().__init__("DART 불가 상태로 바뀜 - 캐시하지 않음")
        self.result = result


def available():
    """지금 DART 를 호출해도 되는가(불가 상태가 아니면 True)."""
    return time.time() >= _state["until"]


def remaining():
    """불가 상태가 풀리기까지 남은 초(가능 상태면 0)."""
    return max(0.0, _state["until"] - time.time())


def state_key():
    """캐시 구분용 상태 값: 가능 'ok', 불가 'down<차단 번호>'(풀린 뒤에는 다시 쓰이지 않는다)."""
    return "ok" if available() else f"down{_state['trips']}"


def trip(reason):
    """불가 상태로 바꾼다(이미 불가면 시각을 늘리지 않는다)."""
    with _lock:
        if available():
            _state["trips"] += 1
            _state["until"] = time.time() + BLOCK_SECONDS
            _state["reason"] = reason
            print(f"[DART] 차단기 작동: {reason} -> {BLOCK_SECONDS // 60}분 동안 DART 호출 건너뜀", flush=True)


def reset():
    """불가 상태를 푼다(검증용)."""
    with _lock:
        _state["until"] = 0.0
        _state["reason"] = None


def get(url, params=None, session=None, read_timeout=READ_TIMEOUT, **kwargs):
    """DART GET. 불가 상태면 즉시 DartUnavailable. 연결 실패면 불가 상태로 바꾸고 DartUnavailable."""
    if not available():
        raise DartUnavailable(f"DART 불가 상태(남은 {remaining():.0f}초)")
    sender = session or requests
    try:
        return sender.get(url, params=params, timeout=(CONNECT_TIMEOUT, read_timeout), **kwargs)
    except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as exc:
        trip(type(exc).__name__)
        raise DartUnavailable(type(exc).__name__) from exc
