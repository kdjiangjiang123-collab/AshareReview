@echo off
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install streamlit pandas numpy akshare openai plotly python-dotenv --quiet
)

echo ========================================
echo   A-Share Review starting...
echo ========================================
start /b streamlit run app.py --server.headless true --browser.gatherUsageStats false

:check
timeout /t 1 /nobreak >nul
powershell -Command "try { (Invoke-WebRequest -Uri http://127.0.0.1:8501 -UseBasicParsing -TimeoutSec 1).StatusCode } catch { exit 1 }" >nul 2>&1
if errorlevel 1 goto check

start "" http://127.0.0.1:8501
pause
