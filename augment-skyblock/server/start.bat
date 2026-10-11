@echo off
rem Augment Skyblock server launcher. All work is done by start.ps1 (PowerShell).
rem This file is ASCII only on purpose: cmd.exe misreads Korean text in batch files on some PCs.
cd /d "%~dp0"
title Augment Skyblock Server
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
echo.
pause
