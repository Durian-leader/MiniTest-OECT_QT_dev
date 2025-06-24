@echo off
chcp 65001 >nul

@echo off
REM 切换到脚本所在目录
cd /d %~dp0

echo [1/3] 创建虚拟环境 .venv（如果不存在）...
if not exist ".venv" (
    python -m venv .venv
    if errorlevel 1 (
        echo ❌ 创建虚拟环境失败，确保你已正确安装 Python！
        pause
        exit /b
    )
) else (
    echo ✅ 已存在虚拟环境 .venv，跳过创建
)

echo [2/3] 激活虚拟环境...
call .venv\Scripts\activate.bat

echo [3/3] 升级 pip 并安装 requirements.txt 中的依赖...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo ❌ 安装依赖失败，请检查 requirements.txt 是否正确
    pause
    exit /b
)


pause
