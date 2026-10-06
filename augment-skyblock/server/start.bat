@echo off
chcp 949 >nul
rem 더블클릭한 창은 스크립트가 끝나거나 오류로 멈추면 바로 닫혀 메시지를 볼 수 없다.
rem 그래서 닫히지 않는 새 창(cmd /k)에서 다시 실행한다.
if /i not "%~1"=="/inner" (
  start "증강 스카이블럭 서버" cmd /k call "%~f0" /inner
  exit /b
)
cd /d "%~dp0"
setlocal EnableExtensions EnableDelayedExpansion
title 증강 스카이블럭 서버
echo [증강 스카이블럭 start.bat 3판]

rem ─────────────────────────────────────────────
rem  처음 실행하면 Java 21 과 Paper 1.21.4 를 자동으로 내려받습니다.
rem  메모리는 아래 숫자를 바꾸세요 (4G = 4기가).
rem  문제가 생기면 이 폴더의 start-log.txt 를 보면 어디서 멈췄는지 알 수 있습니다.
rem ─────────────────────────────────────────────
set "MEMORY=4G"
set "PAPER_URL=https://fill-data.papermc.io/v1/objects/5ee4f542f628a14c644410b08c94ea42e772ef4d29fe92973636b6813d4eaffc/paper-1.21.4-232.jar"
set "PAPER_SIZE=51437498"
set "JAVA_URL=https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jre/hotspot/normal/eclipse"
set "LOG=start-log.txt"

> "%LOG%" echo [%date% %time%] start.bat 3판 시작
>> "%LOG%" echo 폴더: %CD%

rem zip 안에서 바로 실행하면 플러그인과 맵이 없는 임시 폴더에서 돌아간다
if not exist "plugins\AugmentSkyblock.jar" goto notextracted
if not exist "world\level.dat" goto notextracted

rem ── Java 21 찾기: 이 폴더의 runtime, 그다음 설치된 java ──
set "JAVA="
if exist "runtime\bin\java.exe" (
  call :javaok "runtime\bin\java.exe"
  if not errorlevel 1 set "JAVA=runtime\bin\java.exe"
)
if not defined JAVA (
  call :javaok java
  if not errorlevel 1 set "JAVA=java"
)
if defined JAVA goto havejava

echo.
echo [1/2] Java 21 을 내려받는 중입니다... (처음 한 번만, 50MB 정도)
>> "%LOG%" echo Java 21 없음, 내려받기 시작
call :download "%JAVA_URL%" "java21.zip"
if errorlevel 1 goto javafail
if exist "runtime_tmp" rmdir /s /q "runtime_tmp"
mkdir "runtime_tmp"
call :unzip "java21.zip" "runtime_tmp"
if errorlevel 1 goto javafail
if exist "runtime" rmdir /s /q "runtime"
for /d %%d in ("runtime_tmp\*") do move "%%~fd" "runtime" >nul
rmdir /s /q "runtime_tmp" >nul 2>&1
del "java21.zip" >nul 2>&1
call :javaok "runtime\bin\java.exe"
if errorlevel 1 goto javafail
set "JAVA=runtime\bin\java.exe"

:havejava
>> "%LOG%" echo Java: %JAVA%

rem ── Paper 서버 파일 ──
call :papersize
if !PSIZE! GTR 10000000 goto havepaper
echo.
echo [2/2] Paper 1.21.4 서버 파일을 내려받는 중입니다... (50MB 정도)
>> "%LOG%" echo paper.jar 내려받기 시작
call :download "%PAPER_URL%" "paper.jar"
if errorlevel 1 goto paperfail
call :papersize
if not "!PSIZE!"=="%PAPER_SIZE%" goto paperfail

:havepaper
>> "%LOG%" echo paper.jar 크기: !PSIZE!

rem ── EULA ──
findstr /i "eula=true" eula.txt >nul 2>&1
if not errorlevel 1 goto run
echo.
echo ================================================================
echo  마인크래프트 서버를 열려면 Mojang 의 최종 사용자 계약^(EULA^)에
echo  동의해야 합니다.  내용: https://aka.ms/MinecraftEULA
echo ================================================================
:askeula
set "AGREE="
set /p "AGREE=동의하면 Y 를 입력하고 Enter 를 누르세요: "
if /i "!AGREE!"=="Y" goto agreed
echo  Y 를 입력해야 서버를 켤 수 있습니다. 끄려면 창의 X 를 누르세요.
goto askeula
:agreed
> eula.txt echo eula=true
>> "%LOG%" echo EULA 동의

:run
rem ── 메모리 확인: 켜기 전에 Java 가 이 메모리로 뜨는지 먼저 본다 ──
set "XMS=1G"
"%JAVA%" -Xms%XMS% -Xmx%MEMORY% -version >nul 2>"jvm-check.txt"
if not errorlevel 1 goto memok
>> "%LOG%" echo 메모리 %MEMORY% 로 Java 가 뜨지 않음, 2G 로 다시 시도
set "MEMORY=2G"
set "XMS=512M"
"%JAVA%" -Xms%XMS% -Xmx%MEMORY% -version >nul 2>"jvm-check.txt"
if errorlevel 1 goto jvmfail
:memok
del "jvm-check.txt" >nul 2>&1

echo.
echo 서버를 켭니다. 아래에 "Done" 이 나오면 마인크래프트 1.21.4 에서 localhost 로 접속하세요.
echo 처음에는 마인크래프트 서버 파일을 한 번 더 받느라 1분쯤 걸립니다.
echo 서버를 끌 때는 이 창에 stop 을 입력하세요.
echo.
>> "%LOG%" echo [%time%] 서버 실행: "%JAVA%" -Xms%XMS% -Xmx%MEMORY% -jar paper.jar nogui
"%JAVA%" -Xms%XMS% -Xmx%MEMORY% -jar paper.jar nogui
set "CODE=!errorlevel!"
>> "%LOG%" echo [%time%] 서버 종료 코드: !CODE!
echo.
if "!CODE!"=="0" (
  echo 서버가 꺼졌습니다.
) else (
  echo 서버가 오류로 꺼졌습니다. 위쪽의 빨간 글씨나 ERROR 줄을 확인하세요.
  echo  - "Could not reserve" 또는 "heap" 이 보이면: start.bat 을 메모장으로 열어 MEMORY=4G 를 2G 로 바꾸세요.
  echo  - "FAILED TO BIND TO PORT" 가 보이면: 서버가 이미 하나 켜져 있습니다. 다른 서버 창을 닫으세요.
  echo  - 자세한 기록: logs\latest.log
)
echo.
pause
exit /b 0

rem ───────────── 실패했을 때 ─────────────
:notextracted
echo.
echo 압축을 먼저 모두 풀어 주세요.
echo zip 파일을 연 상태에서 바로 start.bat 을 실행하면 플러그인과 맵이 없어 서버가 켜지지 않습니다.
echo zip 파일을 마우스 오른쪽 버튼으로 눌러 "압축 풀기" 를 한 뒤,
echo 풀린 AugmentSkyblock-Server 폴더 안의 start.bat 을 실행하세요.
>> "%LOG%" echo 실패: 압축을 풀지 않음 ^(plugins 또는 world 없음^)
echo.
pause
exit /b 1

:jvmfail
echo.
echo Java 가 시작되지 않았습니다. Java 가 남긴 말:
type "jvm-check.txt"
>> "%LOG%" echo 실패: Java 시작 ^(아래는 Java 가 남긴 말^)
type "jvm-check.txt" >> "%LOG%"
echo.
echo 이 창을 사진으로 찍어 보내 주거나, runtime 폴더를 지운 뒤 다시 실행해 보세요.
echo.
pause
exit /b 1

:javafail
echo.
echo Java 21 을 자동으로 받지 못했습니다. 인터넷 연결을 확인하거나,
echo https://adoptium.net 에서 "Temurin 21" ^(Windows x64, .msi^) 을 설치한 뒤 다시 실행하세요.
>> "%LOG%" echo 실패: Java 21 받기
echo.
pause
exit /b 1

:paperfail
del "paper.jar" >nul 2>&1
echo.
echo Paper 서버 파일을 받지 못했습니다. 인터넷 연결을 확인하고 다시 실행하거나,
echo https://papermc.io/downloads/all 에서 1.21.4 를 받아 이 폴더에 paper.jar 라는 이름으로 넣어 주세요.
>> "%LOG%" echo 실패: paper.jar 받기 ^(크기 !PSIZE!^)
echo.
pause
exit /b 1

rem ───────────── 작은 도구들 ─────────────

rem %1 = java 실행 파일. 버전이 21 이상이면 errorlevel 0
:javaok
%1 -version 2>&1 | findstr /r /c:"version \"2[1-9]" /c:"version \"[3-9][0-9]" >nul
exit /b %errorlevel%

rem %1 = 주소, %2 = 저장할 파일. curl 이 안 되면 PowerShell 로 한 번 더
:download
del "%~2" >nul 2>&1
where curl >nul 2>&1
if errorlevel 1 goto download_ps
curl -fL --retry 3 --connect-timeout 30 -o "%~2" "%~1"
if not errorlevel 1 if exist "%~2" exit /b 0
>> "%LOG%" echo curl 실패, PowerShell 로 다시 시도
:download_ps
del "%~2" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri '%~1' -OutFile '%~2'"
if errorlevel 1 exit /b 1
if not exist "%~2" exit /b 1
exit /b 0

rem %1 = zip, %2 = 풀 폴더. tar 가 안 되면 PowerShell 로
:unzip
tar -xf "%~1" -C "%~2" >nul 2>&1
if not errorlevel 1 exit /b 0
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force -LiteralPath '%~1' -DestinationPath '%~2'"
exit /b %errorlevel%

rem paper.jar 크기를 PSIZE 에 (없으면 0)
:papersize
set "PSIZE=0"
if exist "paper.jar" for %%A in ("paper.jar") do set "PSIZE=%%~zA"
exit /b 0
