@echo off
REM Start Usage HUD (tray + translucent card)
cd /d "%~dp0"
call .venv\Scripts\activate.bat
start "" usage-hud
