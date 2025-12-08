@echo off
REM D87-3.3 자동 모니터링 배치 스크립트
REM Orchestrator 완료 후 자동으로 분석 실행

cd /d "%~dp0\.."

echo [%date% %time%] 모니터링 시작...

:LOOP
timeout /t 300 /nobreak > nul

REM Advisory 및 Strict 세션 완료 여부 확인
if not exist "logs\d87-3\d87_3_advisory_3h\kpi_*.json" (
    echo [%date% %time%] Advisory 세션 진행 중...
    goto LOOP
)

if not exist "logs\d87-3\d87_3_strict_3h\kpi_*.json" (
    echo [%date% %time%] Strict 세션 진행 중...
    goto LOOP
)

echo [%date% %time%] 세션 완료 감지! 분석 시작...

REM Post-analysis 실행
python scripts\d87_3_post_analysis.py

echo [%date% %time%] 분석 완료!

exit /b 0
