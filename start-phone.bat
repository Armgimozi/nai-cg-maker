@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==== NAI 스튜디오 + 휴대폰 터널 ====
echo.
echo 1) 서버를 새 창에서 시작합니다...
start "NAI Server" cmd /k "cd /d "%~dp0" && python run.py --no-browser --host 0.0.0.0 --byok"
echo 2) 터널을 시작합니다. 잠시 후 아래 상자 안에 나오는
echo      https://....trycloudflare.com
echo    주소(또는 그 QR)를 휴대폰 브라우저에서 여세요.
echo    (이 창을 닫으면 휴대폰 접속이 끊깁니다. URL 은 켤 때마다 바뀝니다.)
echo.
timeout /t 4 >nul
cloudflared.exe tunnel --protocol http2 --url http://localhost:8765
echo.
echo (터널이 종료되었습니다.)
pause >nul
