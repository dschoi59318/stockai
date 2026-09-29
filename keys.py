# -*- coding: utf-8 -*-
r"""
keys.py - API 키 로더

우선순위
 1) ControlTower\_secrets\ct_keys.py  (개인 공용 키 저장소, git에 올라가지 않음)
    이 파일 위치에서 상위 폴더로 올라가며 _secrets\ct_keys.py 를 찾는다(NEW_REPORT_GUIDE 2-1 자동탐색).
    폴더를 옮기거나 섹션 폴더가 끼어도 그대로 찾는다. 못 찾으면 예외 없이 None -> 2)로 넘어간다.
 2) 같은 폴더의 api_secrets.py           (교재 독자용 빈 템플릿)
 3) st.secrets                          (Streamlit Cloud 의 Secrets / .streamlit/secrets.toml)
 4) os.environ                          (환경변수)
    3)·4)는 1)·2)에서 못 찾았을 때만 본다 - 로컬 결과는 그대로다. streamlit 이 없거나 secrets.toml 이 없어도
    예외 없이 넘어간다. 이름 후보(KEY_ALIASES, DART 는 FSS_KEY 포함)는 네 곳 모두 같다.

주의: 파일 이름을 secrets.py로 두면 파이썬 표준 라이브러리 secrets 모듈을 가려
      numpy/pandas import가 깨진다. 그래서 api_secrets.py로 둔다.

다루는 키 (ct_keys.py 상수명은 공통지침_StockAI.md 참조)
 - ANTHROPIC_API_KEY : Claude API (3단계 AI 분석에서 사용). CLAUDE_API_KEY 이름도 함께 찾는다.
 - DART_API_KEY      : DART 기업개황(업종 매핑)에서 사용. ct_keys.py에서는 FSS_KEY
 - NAVER_CLIENT_ID / NAVER_CLIENT_SECRET : 네이버 뉴스 검색(events.py)
"""

import os
import sys
import importlib.util
from pathlib import Path


def _find_secrets_dir(start):
    """start에서 상위 폴더로 올라가며 _secrets\\ct_keys.py 가 있는 폴더를 찾는다. 없으면 None.

    존재 확인은 폴더 유무가 아니라 그 안의 ct_keys.py 유무로 한다(NEW_REPORT_GUIDE 2-1).
    표준 패턴과 달리 못 찾아도 예외를 던지지 않는다 - 교재 독자 환경에는 _secrets 가 없고,
    그때는 api_secrets.py 로 넘어가야 하기 때문이다.
    """
    for d in (start, *start.parents):
        cand = d / "_secrets"
        if (cand / "ct_keys.py").is_file():
            return str(cand)
    return None


# 공용 키 저장소 경로 (개인 환경). 독자는 이 폴더가 없어도 api_secrets.py로 동작한다(None).
CT_SECRETS_DIR = _find_secrets_dir(Path(__file__).resolve().parent)

# 같은 폴더의 api_secrets.py 절대 경로
LOCAL_SECRETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_secrets.py")

# 키 이름 후보: 저장소마다 상수 이름이 달라서 순서대로 찾는다.
KEY_ALIASES = {
    "ANTHROPIC_API_KEY": ("CLAUDE_API_KEY", "ANTHROPIC_API_KEY"),
    "DART_API_KEY": ("DART_API_KEY", "OPENDART_KEY", "DART_KEY", "FSS_KEY"),
}


def _load_ct_keys_module():
    """_secrets 폴더를 sys.path에 넣고 ct_keys 모듈을 가져온다. 폴더가 없거나 실패하면 None."""
    if CT_SECRETS_DIR is None:
        return None
    try:
        if CT_SECRETS_DIR not in sys.path:
            sys.path.insert(0, CT_SECRETS_DIR)
        import ct_keys
        return ct_keys
    except Exception:
        return None


def _load_local_secrets_module():
    """같은 폴더 api_secrets.py를 파일 경로로 직접 읽어온다(독립 이름 사용). 실패하면 None."""
    try:
        if not os.path.exists(LOCAL_SECRETS_PATH):
            return None
        spec = importlib.util.spec_from_file_location("stockai_secrets", LOCAL_SECRETS_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def _st_secret(name):
    """st.secrets[name] (없거나 streamlit·secrets.toml 이 없으면 None)."""
    try:
        import streamlit as st
        value = st.secrets.get(name)
        return str(value) if value else None
    except Exception:
        return None


def get_key(logical_name):
    """논리 키 이름으로 값을 찾는다. ct_keys -> api_secrets -> st.secrets -> os.environ 순서, 없으면 None."""
    candidates = KEY_ALIASES.get(logical_name, (logical_name,))
    for module in (_load_ct_keys_module(), _load_local_secrets_module()):
        if module is None:
            continue
        for name in candidates:
            value = getattr(module, name, None)
            if value:
                return value
    for lookup in (_st_secret, os.environ.get):
        for name in candidates:
            value = lookup(name)
            if value:
                return value
    return None


def get_anthropic_api_key():
    """Claude API 키 (CLAUDE_API_KEY -> ANTHROPIC_API_KEY 순으로 찾는다)."""
    return get_key("ANTHROPIC_API_KEY")


def get_dart_api_key():
    """DART OpenAPI 키 (업종 매핑 수집에 사용)."""
    return get_key("DART_API_KEY")


def has_api_key():
    """Claude 키 준비 여부만 알려준다 (키 값 자체는 화면에 출력하지 않는다)."""
    return get_anthropic_api_key() is not None


def has_dart_key():
    """DART 키 준비 여부만 알려준다."""
    return get_dart_api_key() is not None
