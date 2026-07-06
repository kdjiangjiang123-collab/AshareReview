@echo off
chcp 65001 >nul
title 安装依赖 - A股复盘助手

cd /d "%~dp0"

echo ╔══════════════════════════╗
echo ║  A股复盘助手 - 安装依赖  ║
echo ╚══════════════════════════╝
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未找到 Python！
    echo 请先安装 Python: https://www.python.org/downloads/
    echo 安装时勾选 "Add Python to PATH"
    pause
    exit /b 1
)

echo ✅ Python 版本:
python --version
echo.

echo 📥 正在安装依赖包...
pip install -r requirements.txt --quiet

if %errorlevel% equ 0 (
    echo.
    echo ╔══════════════════════════╗
    echo ║  ✅ 安装成功!           ║
    echo ║  双击 "启动复盘助手.bat" ║
    echo ║  即可启动               ║
    echo ╚══════════════════════════╝
) else (
    echo ❌ 安装失败，请检查网络后重试
)

pause
