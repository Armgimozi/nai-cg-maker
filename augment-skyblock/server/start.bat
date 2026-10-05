@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title 증강 스카이블럭 서버

rem ─────────────────────────────────────────────
rem  처음 실행하면 Java 21 과 Paper 1.21.4 를 자동으로 내려받습니다.
rem  메모리는 아래 숫자를 바꾸세요 (4G = 4기가).
rem ─────────────────────────────────────────────
set MEMORY=4G
set PAPER_URL=https://fill-data.papermc.io/v1/objects/5ee4f542f628a14c644410b08c94ea42e772ef4d29fe92973636b6813d4eaffc/paper-1.21.4-232.jar
set JAVA_URL=https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jre/hotspot/normal/eclipse

set JAVA=java
if exist "runtime\bin\java.exe" set JAVA=runtime\bin\java.exe

"%JAVA%" -version >nul 2>&1
if errorlevel 1 goto getjava
set JVER=
for /f "tokens=3" %%v in ('"%JAVA%" -version 2^>^&1 ^| findstr /i "version"') do set JVER=%%~v
for /f "delims=." %%m in ("!JVER!") do set JMAJOR=%%m
if "!JMAJOR!"=="" goto getjava
if !JMAJOR! LSS 21 goto getjava
goto havejava

:getjava
echo.
echo [1/2] Java 21 을 내려받는 중입니다... (처음 한 번만, 50MB 정도)
curl -L -o java21.zip "%JAVA_URL%"
if errorlevel 1 goto javafail
if exist runtime_tmp rmdir /s /q runtime_tmp
mkdir runtime_tmp
tar -xf java21.zip -C runtime_tmp
if errorlevel 1 goto javafail
for /d %%d in (runtime_tmp\*) do move "%%d" runtime >nul
rmdir /s /q runtime_tmp
del java21.zip
set JAVA=runtime\bin\java.exe
if not exist "%JAVA%" goto javafail
goto havejava

:javafail
echo.
echo Java 를 자동으로 받지 못했습니다.
echo https://adoptium.net 에서 "Temurin 21" 을 설치한 뒤 다시 실행하세요.
pause
exit /b 1

:havejava
if not exist paper.jar (
  echo.
  echo [2/2] Paper 1.21.4 서버를 내려받는 중입니다...
  curl -L -o paper.jar "%PAPER_URL%"
  if errorlevel 1 (
    echo Paper 를 받지 못했습니다. https://papermc.io/downloads/all 에서 1.21.4 를 받아
    echo 이 폴더에 paper.jar 라는 이름으로 넣어 주세요.
    pause
    exit /b 1
  )
)

findstr /i "eula=true" eula.txt >nul 2>&1
if errorlevel 1 (
  echo.
  echo 마인크래프트 서버를 열려면 Mojang 의 최종 사용자 계약^(EULA^)에 동의해야 합니다.
  echo 내용: https://aka.ms/MinecraftEULA
  set /p AGREE=동의하면 Y 를 입력하고 Enter: 
  if /i not "!AGREE!"=="Y" (
    echo 동의하지 않아 서버를 켜지 않습니다.
    pause
    exit /b 1
  )
  echo eula=true> eula.txt
)

echo.
echo 서버를 켭니다. "Done" 이 나오면 마인크래프트 1.21.4 에서 localhost 로 접속하세요.
echo 서버를 끌 때는 이 창에 stop 을 입력하세요.
echo.
"%JAVA%" -Xms2G -Xmx%MEMORY% -jar paper.jar nogui
pause
