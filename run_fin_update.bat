@echo off
rem 재무 저장본(data/fin_store) 갱신 - PC 전용. 옵션은 fin_update.py 와 같음 (예: --quarter, --sample 20 --no-push)
rem 끝나면(--no-push 가 없을 때) data/fin_store 와 data/industry_map.csv 를 커밋하고 push 한다.
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" "%~dp0fin_update.py" %*
exit /b %errorlevel%
