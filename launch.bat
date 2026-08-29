@echo off
title Aura Forge
echo ============================================
echo           Aura Forge - Starting...
echo ============================================
echo.

:: Set HERMES_HOME so resolveHermesHome() returns Aura Forge path
:: (The function checks process.env.HERMES_HOME FIRST, before registry)
set HERMES_HOME=C:\Users\HP\AppData\Local\aura-forge

:: Use separate user data dir so GPU cache doesn't conflict with Hermes
set ELECTRON_USER_DATA_DIR=C:\Users\HP\AppData\Roaming\AuraForge

:: Launch AuraForge with separate GPU cache
start "" "C:\Users\HP\Desktop\AuraForge\apps\desktop\release\win-unpacked\AuraForge.exe" --no-sandbox --user-data-dir="C:\Users\HP\AppData\Roaming\AuraForge"

echo Aura Forge launched!
echo   Backend data: %HERMES_HOME%
echo   GPU cache:    %ELECTRON_USER_DATA_DIR%
