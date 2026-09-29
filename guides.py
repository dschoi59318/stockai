# -*- coding: utf-8 -*-
r"""
guides.py - 지침 문서 위치와 버전 대조

지침 문서는 프로젝트 안 docs\ 에 둔다(공통지침_StockAI.md [2]: 개별지침은 프로젝트 폴더 안).
공통 규칙(ControlTower\_guides)은 상속만 하고 코드가 읽지 않는다.

코드 상수(direction.REPORT_GUIDE_VERSION, easy_read.EASY_READ_GUIDE_VERSION)는 리포트 출처 페이지에
찍히는 "코드가 구현한 지침 버전"이다. 지침 문서를 고치고 버전을 올렸는데 코드 반영을 잊으면 두 값이 갈라진다.
read_version()으로 문서의 '버전:' 줄을 읽고, check_versions()가 코드 상수와 다르면 경고 문장을 돌려준다.
경고만 한다 - 리포트 생성은 멈추지 않는다(출처 페이지에는 코드 상수가 그대로 찍힌다).

 - read_version(path)   : 문서 맨 위 '버전: vX.Y' 줄의 값. 파일이 없거나 줄이 없으면 None
 - check_versions()     : [경고 문장, ...] (같으면 빈 목록)
"""

import io
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(BASE_DIR, "docs")

REPORT_GUIDE_PATH = os.path.join(DOCS_DIR, "리포트_구성지침.md")
EASY_READ_GUIDE_PATH = os.path.join(DOCS_DIR, "쉽게읽기_작성지침.md")

# narrator.guide_section6과 같은 형식('버전: v1.5')을 읽는다.
VERSION_RX = re.compile(r"^버전:\s*(v[\d.]+)", re.M)


def read_version(path):
    """지침 문서의 '버전:' 줄 값(예: 'v1.6'). 파일이 없거나 줄이 없으면 None."""
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    m = VERSION_RX.search(text)
    return m.group(1) if m else None


def check_versions():
    """두 지침 문서 버전과 코드 상수를 대조한다. 반환: 경고 문장 목록(일치하면 빈 목록)."""
    import direction
    import easy_read
    pairs = (
        ("리포트 구성 지침", REPORT_GUIDE_PATH, "direction.REPORT_GUIDE_VERSION", direction.REPORT_GUIDE_VERSION),
        ("쉽게 읽기 지침", EASY_READ_GUIDE_PATH, "easy_read.EASY_READ_GUIDE_VERSION", easy_read.EASY_READ_GUIDE_VERSION),
    )
    warnings = []
    for label, path, const_name, const in pairs:
        doc = read_version(path)
        if doc is None:
            warnings.append(f"{label} 문서의 버전을 읽지 못했습니다({os.path.basename(path)}).")
        elif doc != const:
            warnings.append(f"{label} 문서는 {doc}인데 코드 상수 {const_name}는 {const}입니다. "
                            "지침을 코드에 반영했는지 확인하세요.")
    return warnings


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("리포트 구성 지침:", read_version(REPORT_GUIDE_PATH))
    print("쉽게 읽기 지침:", read_version(EASY_READ_GUIDE_PATH))
    found = check_versions()
    print("\n".join(found) if found else "코드 상수와 일치")
