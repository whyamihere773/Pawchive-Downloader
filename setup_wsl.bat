@echo off
title Pawchive Downloader - WSL Build Environment Setup
echo ==================================================================
echo   Pawchive Downloader - Setup WSL 2 for Local Linux Builds
echo ==================================================================
echo.
echo Installing Windows Subsystem for Linux (WSL 2)...
echo Requesting administrator privileges (click 'Yes' on the UAC prompt)...
echo.
powershell -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoExit', '-Command', 'Write-Host \"[1/3] Enabling Windows Update service temporarily (required for WSL packages)...\" -ForegroundColor Cyan; Set-Service -Name wuauserv -StartupType Manual -ErrorAction SilentlyContinue; Start-Service -Name wuauserv -ErrorAction SilentlyContinue; Write-Host \"[2/3] Installing WSL & Ubuntu...\" -ForegroundColor Cyan; wsl.exe --install -d Ubuntu; Write-Host \"[3/3] Done! If Windows asks you to reboot, please reboot.\" -ForegroundColor Green; Write-Host \"After reboot, launch Ubuntu from the Start Menu, then run:\" -ForegroundColor Yellow; Write-Host \"  cd /mnt/e/Programming/Project\ Kemono/Project\ Kemono\" -ForegroundColor Yellow; Write-Host \"  ./build_linux.sh\" -ForegroundColor Yellow'"
echo.
echo ==================================================================
echo If you saw a PowerShell window open, follow the instructions there.
echo ==================================================================
pause

