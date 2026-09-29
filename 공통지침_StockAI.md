공통지침 — StockAI (국내 주식 종목 분석 리포트 · Streamlit 앱)
============================================================
갱신: 2026-09-28 (ControlTower 공통 구조 연결)

이 문서는 StockAI 가 ControlTower 공통 구조(_secrets · _engine · _guides)와
어떻게 이어지는지, 그리고 이 폴더의 지침 문서가 어디에 있고 무엇이 정본인지만 적는다.
판정 규칙·문장 틀·서식 규격 자체는 docs\ 의 지침 문서에 있다.


============================================================
[0] 이 폴더에서 제일 먼저 알 것
============================================================
1. **이 폴더는 두 갈래(_python / _claude)가 아니다.** 평면 구조 + Streamlit 앱이다.
   기능폴더_재작업_지침.md [1] "프로젝트 성격에 따라 data\ output\ 처럼 단순해도 된다"를 따른다.
   AI 해설(narrator.py)은 리포트를 만들 때마다 호출하므로 "_python 산출물 == _claude 산출물"
   (재작업 지침 규칙7)이 성립하지 않는다. 대신 AI 저장본(data\cache\narr_*)으로 재현한다.
2. **교재 독자용 겸용이다.** 독자 환경에는 _secrets · _engine 이 없다.
   그래서 자동탐색은 못 찾아도 멈추지 않는다(keys.py -> api_secrets.py 폴백, 게이트는 건너뜀).
   NEW_REPORT_GUIDE 2-1·2-2 의 표준 패턴(못 찾으면 FileNotFoundError)과 이 점만 다르다.
3. **지침 문서가 먼저, 코드가 나중이다.** 규칙을 바꾸려면 docs\ 의 지침을 고치고 버전을 올린 뒤
   코드에 반영한다. 코드 상수(REPORT_GUIDE_VERSION · EASY_READ_GUIDE_VERSION)와 문서 버전이 다르면
   guides.check_versions() 가 경고한다(리포트 생성 시·앱 화면).
4. **리포트 구성 지침 6장(AI 표현 규칙)은 AI 프롬프트에 그대로 들어간다.**
   6장 문구나 문서의 '버전:' 줄이 바뀌면 프롬프트 해시가 바뀌어 저장본을 못 쓰고 AI 를 다시 부른다.
   검증 빌드는 reuse_ai=("conclusion", "story", "scenario") 로 저장본을 재사용한다.


============================================================
[1] 지침 문서 지도 — 무엇이 정본인가
============================================================
  docs\리포트_구성지침.md      정본. 구성·판정 규칙(5장)·AI 표현 규칙(6장)·서식 규격(12장)
                               direction.py · narrator.py · report.py 가 따른다
  docs\쉽게읽기_작성지침.md    정본. 쉽게 읽기 문장 틀·용어 풀이·금지 표현 (easy_read.py)
  docs\개별지침_StockAI.md     설계도. ControlTower 표준 목차(0·A~I) — 소스맵, 인프라,
                               차트 세트, 공통규칙 충돌 해소 기록(I절)
  공통지침_StockAI.md          이 문서. 공통 구조 연결과 문서 지도

  두 정본과 개별지침이 어긋나면 **두 정본이 우선**이다. 개별지침은 정본을 요약·참조한다.


============================================================
[2] 상속하는 공통 규격
============================================================
0. D:\ControlTower\_guides\COMMON_RULES.md               공통 규칙 ([불변 원칙 0] 포함)
1. D:\ControlTower\_guides\PREMIUM_STANDARD_v3_골격.md    정본 (2절 서식 규격을 v1.6 에서 채택)
2. D:\ControlTower\_guides\NEW_REPORT_GUIDE.md            인프라 연결 (2절 자동탐색)
3. D:\ControlTower\_engine\standards\STORYBOARD.md        품질 헌법 (충돌은 개별지침 I절에서 판정)
4. D:\ControlTower\_guides\기능폴더_재작업_지침.md         폴더 규격 (두 갈래는 적용하지 않음 — [0]-1)

  ※ _guides\v3_표현금지어.md 는 이름과 달리 ImportFood 전용 내용(전문 문어체·비유 배제)이다.
    StockAI 의 쉬운 말 원칙과 정면으로 충돌하므로 상속하지 않는다(개별지침 I절 14번).


============================================================
[3] 공통 구조 연결 (배관)
============================================================
[키] keys.py
  상위 폴더로 올라가며 _secrets\ct_keys.py 를 찾는다. 못 찾으면 None -> api_secrets.py.
  쓰는 ct_keys 상수명(값은 어디에도 적지 않는다):
    CLAUDE_API_KEY          AI 해설 (keys 논리명 ANTHROPIC_API_KEY)
    FSS_KEY                 DART 재무·공시·기업개황 (keys 논리명 DART_API_KEY)
    NAVER_CLIENT_ID / NAVER_CLIENT_SECRET   뉴스 검색 (events.py)

[엔진] report.py _find_engine_dir()
  상위 폴더로 올라가며 _engine\engine\ 이 있는 _engine 을 찾는다. 못 찾으면 게이트를 건너뛴다.
  쓰는 것은 v3_gate.run_gate **하나뿐**이다(verify 전용, enforce=False).
  _engine 은 고치지 않는다. 게이트 도메인 프로파일(V3_DOMAIN)은 report.py 에 둔다.
  docx_kit·chartkit 등 나머지 엔진 부품은 쓰지 않는다(판정 근거: 개별지침 A절).

[지침 버전] guides.py
  read_version(path) 로 docs\ 지침의 '버전:' 줄을 읽고 check_versions() 로 코드 상수와 대조한다.

[게이트] v3 관문
  report.build_report 가 docx 저장 직후 run_gate(enforce=False) 를 부른다. 문서는 고치지 않는다.
  결과는 리포트 옆(output\_gate_report.txt)에 이어 붙이고, 앱에는 치명·경고 건수를 보인다.
  **게이트는 서식을 보지 내용을 보지 않는다.** 판정·문장 검증은 direction·easy_read·narrator 의
  자체 검사(지침 체크리스트)가 맡는다.


============================================================
[4] 폴더 지도
============================================================
  Finance\StockAI\
    공통지침_StockAI.md       이 문서
    run.bat                   앱 실행(Streamlit)
    app.py                    화면
    report.py                 Word 리포트 조립 + 게이트 호출
    charts.py heatmap.py      그림 (리포트용 PNG 는 report=True 경로로 v3 규격)
    data.py indicators.py financials.py industry.py events.py   수집·계산
    direction.py easy_read.py narrator.py                      판정·문장·AI 해설
    keys.py guides.py         배관
    api_secrets.py            교재 독자용 빈 키 파일 (git 제외)
    docs\                     지침 3종
    data\                     종목 마스터·업종 매핑·보유종목, cache\(일봉·재무·사건·AI 저장본)
    output\                   리포트 docx + _gate_report.txt, _old\(이전 판)
  Finance\_backup\            작업 전 백업(StockAI_<작업>_<날짜>)


============================================================
[5] 등록
============================================================
  D:\ControlTower\INDEX.md  10. 금융 섹션 [StockAI]
