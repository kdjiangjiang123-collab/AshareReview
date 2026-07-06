import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# ── Application root ──────────────────────────────────────────
# PyInstaller (--onedir): EXE sits next to _internal/, we want data at EXE level.
# Dev mode: project root is two levels above this file (config/ → root/).
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

# Belt-and-suspenders: if we somehow landed inside _internal/, go up one level.
if BASE_DIR.name == "_internal":
    BASE_DIR = BASE_DIR.parent

# Load .env from the application root
load_dotenv(BASE_DIR / ".env")

# ── Data directory ────────────────────────────────────────────
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = str(DATA_DIR / "trades.db")

# ── DeepSeek API ──────────────────────────────────────────────
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_CHAT_MODEL = os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-chat")
DEEPSEEK_REASONER_MODEL = os.getenv("DEEPSEEK_REASONER_MODEL", "deepseek-reasoner")

# Model selection defaults
INTRODAY_MODEL = DEEPSEEK_CHAT_MODEL        # 盘中要速度
AFTERMARKET_MACRO_MODEL = DEEPSEEK_CHAT_MODEL
AFTERMARKET_MICRO_MODEL = DEEPSEEK_CHAT_MODEL
AFTERMARKET_SCENARIO_MODEL = DEEPSEEK_REASONER_MODEL  # 情景推演要深度

# LLM parameters
LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 4096
LLM_MAX_TOKENS_INTRODAY = 2048  # 盘中分析不用太长

# akshare
AKSHARE_RETRY = 3
AKSHARE_RETRY_DELAY = 2  # seconds
