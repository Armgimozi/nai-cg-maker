@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

rem ===== 설정 =====
rem 지원 버전: 1.21.5 ~ 26.3 (자바 에디션). 바꾸려면 아래 숫자만 고치세요.
set MC_VERSION=1.21.11
set RAM=4G

title 아오오니 저택 서버 (%MC_VERSION%)

where java > nul 2>&1
if errorlevel 1 (
  echo [오류] Java 가 설치되어 있지 않습니다.
  echo        1.21.x 는 Java 21, 26.x 는 Java 25 이상이 필요합니다.
  echo        https://adoptium.net 에서 설치한 뒤 다시 실행하세요.
  pause
  exit /b 1
)

if not exist server.jar (
  echo [아오오니 저택] Minecraft %MC_VERSION% 서버 파일을 Mojang 에서 내려받습니다...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $m = Invoke-RestMethod 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'; $v = $m.versions | Where-Object { $_.id -eq $env:MC_VERSION } | Select-Object -First 1; if (-not $v) { throw ('Unknown version ' + $env:MC_VERSION) }; $j = Invoke-RestMethod $v.url; Invoke-WebRequest $j.downloads.server.url -OutFile 'server.jar'; Write-Host ('Required Java: ' + $j.javaVersion.majorVersion)"
  if errorlevel 1 (
    echo [오류] 서버 파일을 받지 못했습니다. 인터넷 연결과 MC_VERSION 값을 확인하세요.
    pause
    exit /b 1
  )
)

findstr /c:"eula=true" eula.txt > nul 2>&1
if errorlevel 1 (
  echo.
  echo 서버를 실행하려면 Minecraft EULA 에 동의해야 합니다.
  echo   https://aka.ms/MinecraftEULA
  set /p AGREE=EULA 에 동의하십니까? [Y/N]: 
  call :checkagree
  if errorlevel 1 exit /b 1
)

echo [아오오니 저택] 서버를 시작합니다. 종료하려면 이 창에 stop 을 입력하세요.
java -Xms1G -Xmx%RAM% -jar server.jar nogui
pause
exit /b 0

:checkagree
if /i "%AGREE%"=="Y" (
  > eula.txt echo eula=true
  exit /b 0
)
echo 동의하지 않아 종료합니다.
pause
exit /b 1
