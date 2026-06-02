@echo off
cd /d "%~dp0"
wt -d "%~dp0" --title PathikBot cmd /k python -m bot.main
