@echo off
REM 切换到脚本所在目录
cd /d %~dp0

REM 直接使用虚拟环境里的 Python 运行
".venv\Scripts\python.exe" run_qt.py

pause
