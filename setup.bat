@echo off
setlocal
cd /d "%~dp0"

where git >nul 2>nul
if errorlevel 1 (
  echo ERROR: Git is required.
  exit /b 1
)

echo Initializing pinned NESRecomp, recomp-ui and SDL2 submodules...
git submodule update --init --recursive
if errorlevel 1 exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\bootstrap.ps1"
if errorlevel 1 exit /b 1

echo Setup complete. Use:
echo   powershell -ExecutionPolicy Bypass -File tools\build.ps1 C:\Games\Excitebike.nes
exit /b 0
