@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64
cd /d "C:\Users\HP\Desktop\AuraForge\apps\bootstrap-installer"
set PATH=%USERPROFILE%\.cargo\bin;%PATH%
npx tauri build
