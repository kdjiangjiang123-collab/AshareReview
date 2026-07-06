@echo off
chcp 65001 >nul
title Build A股复盘助手 EXE

cd /d "%~dp0"

echo ========================================
echo   A股复盘助手 - EXE Builder
echo   预计 5-10 分钟，输出约 300-500MB
echo ========================================
echo.

:: ── Find system Python ──────────────────────────────────────
set PYTHON=C:\python\python.exe
if not exist "%PYTHON%" (
    echo 查找系统中 Python...
    for %%p in (python.exe) do set PYTHON=%%~$PATH:p
)
if "%PYTHON%"=="" (
    echo [X] 未找到 Python，请安装 Python 3.10+
    echo     https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python: %PYTHON%
%PYTHON% --version
echo.

:: ── Create clean venv ───────────────────────────────────────
set VENV=%~dp0build_venv
if exist "%VENV%" (
    echo 清理旧的虚拟环境...
    rmdir /s /q "%VENV%"
)

echo 创建虚拟环境...
%PYTHON% -m venv "%VENV%"
if %errorlevel% neq 0 (
    echo [X] 创建虚拟环境失败
    pause
    exit /b 1
)

:: ── Install deps ────────────────────────────────────────────
call "%VENV%\Scripts\activate.bat"
echo 安装依赖中（首次较慢）...
pip install streamlit pandas numpy akshare openai plotly python-dotenv pyinstaller --quiet 2>nul
if %errorlevel% neq 0 (
    echo [!] 部分依赖安装失败，尝试继续...
)

:: ── Clean old builds ────────────────────────────────────────
echo 清理旧构建...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del *.spec 2>nul

:: ── Build EXE ───────────────────────────────────────────────
echo.
echo ========================================
echo   开始打包...
echo ========================================

pyinstaller --onedir --clean --noconfirm ^
    --name "A股复盘助手" ^
    --add-data "app.py;." ^
    --add-data "config;config" ^
    --add-data "db;db" ^
    --add-data "market_data;market_data" ^
    --add-data "analysis;analysis" ^
    --add-data "ui;ui" ^
    --add-data ".env.example;." ^
    --hidden-import streamlit ^
    --hidden-import streamlit.web.bootstrap ^
    --hidden-import streamlit.runtime ^
    --hidden-import pandas ^
    --hidden-import plotly ^
    --hidden-import plotly.express ^
    --hidden-import openai ^
    --hidden-import akshare ^
    --hidden-import requests ^
    --hidden-import numpy ^
    --collect-data streamlit ^
    --exclude-module torch ^
    --exclude-module tensorflow ^
    --exclude-module scipy ^
    --exclude-module matplotlib ^
    --exclude-module PIL ^
    --exclude-module cv2 ^
    --exclude-module sklearn ^
    --exclude-module numba ^
    --exclude-module transformers ^
    --exclude-module bokeh ^
    --exclude-module altair ^
    --exclude-module dask ^
    --exclude-module sqlalchemy ^
    --exclude-module boto3 ^
    --exclude-module PyQt5 ^
    --exclude-module zmq ^
    --exclude-module websockets ^
    --exclude-module pytest ^
    --exclude-module jsonschema ^
    --exclude-module cryptography ^
    --exclude-module lxml ^
    --exclude-module pydantic ^
    --exclude-module orjson ^
    --exclude-module pydub ^
    --exclude-module sphinx ^
    --exclude-module jupyterlab ^
    --exclude-module IPython ^
    --exclude-module nbformat ^
    --exclude-module xarray ^
    --exclude-module statsmodels ^
    --exclude-module tables ^
    --exclude-module h5py ^
    --exclude-module openpyxl ^
    --exclude-module rich ^
    --exclude-module uvicorn ^
    run_exe.py

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   打包成功！
    echo   输出目录: dist\A股复盘助手\
    echo   EXE 文件: dist\A股复盘助手\A股复盘助手.exe
    echo ========================================
    echo.
    echo 【分发说明】
    echo   1. 把整个 "A股复盘助手" 文件夹复制给对方
    echo   2. 对方双击 A股复盘助手.exe 启动
    echo   3. 首次运行会弹出 .env 文件，需填入 DeepSeek API Key
    echo   4. 注册 Key: https://platform.deepseek.com
    echo   5. 对方电脑需 Win10+ x64，可能需要 VC++ 运行库
    echo.
) else (
    echo [X] 打包失败，请检查上方错误信息
)

:: ── Cleanup ──────────────────────────────────────────────────
call deactivate 2>nul
echo 按任意键关闭...
pause
