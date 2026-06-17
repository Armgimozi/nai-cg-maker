@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo NAI 프롬프트 스튜디오를 시작합니다...
python run.py
echo.
echo (서버가 종료되었습니다. 창을 닫으려면 아무 키나 누르세요.)
pause >nul
