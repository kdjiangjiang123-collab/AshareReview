"""A股复盘助手 — Main Entry Point.

Streamlit app with two modes:
- 盘中研判: Quick market scan during trading hours
- 盘后复盘: Full daily review after market close

First-run: if .env is missing or API key not configured, show a setup page.
"""

import streamlit as st
import os
from datetime import datetime

# Page config (must be the first Streamlit call)
st.set_page_config(
    page_title="A股复盘助手",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dotenv import load_dotenv
load_dotenv()

from db.schema import init_db
from ui.mode_intraday import render as render_intraday
from ui.mode_aftermarket import render as render_aftermarket
from ui.mode_trade import render as render_trade


def _env_path() -> str:
    """Return path to the .env file in the app directory."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def _api_key_configured() -> bool:
    """Return True if DEEPSEEK_API_KEY is set and not the placeholder."""
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        return False
    if "你的key" in key or "your-key" in key.lower() or key.startswith("sk-你的"):
        return False
    return True


def _render_setup():
    """First-run setup page — no API key configured yet."""
    st.title("🔑 首次使用 · 配置 DeepSeek API Key")

    st.markdown("""
    #### 欢迎使用 A股复盘助手！

    本工具通过 **DeepSeek** 驱动 AI 分析，需要你提供一个 API Key。

    **获取 Key 只需一分钟：**
    1. 打开 [platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys)
    2. 注册 / 登录（支持微信扫码）
    3. 点击「创建 API Key」→ 复制

    > 💰 DeepSeek 的 chat 模型极其便宜，正常使用**一个月几块钱**就够了。
    """)

    st.divider()

    api_key = st.text_input(
        "请粘贴你的 DeepSeek API Key",
        type="password",
        placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        help="Key 以 sk- 开头，只保存在你本地的 .env 文件中，不会上传。",
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        save = st.button("✅ 保存并开始使用", type="primary", use_container_width=True)

    if save:
        key = api_key.strip()
        if not key:
            st.error("❌ 请输入 API Key")
        elif not key.startswith("sk-"):
            st.error("❌ API Key 格式不正确，应以 sk- 开头")
        else:
            with open(_env_path(), "w", encoding="utf-8") as f:
                f.write("# A股复盘助手 — DeepSeek API 配置\n")
                f.write(f"DEEPSEEK_API_KEY={key}\n")
                f.write("DEEPSEEK_BASE_URL=https://api.deepseek.com/v1\n")
                f.write("DEEPSEEK_CHAT_MODEL=deepseek-chat\n")
                f.write("DEEPSEEK_REASONER_MODEL=deepseek-reasoner\n")
            load_dotenv(override=True)
            import analysis.llm_client as _llm
            _llm._client = None
            st.session_state['deepseek_api_key'] = key
            st.success("✅ 配置成功！即将刷新…")
            st.rerun()

    st.divider()
    st.caption("Key 保存在本地 .env 文件。如需更换，直接编辑项目目录下的 .env 后重启即可。")


def main():
    # Initialize database on first run
    init_db()

    # Silently load API key from .env
    if 'deepseek_api_key' not in st.session_state:
        st.session_state['deepseek_api_key'] = os.getenv("DEEPSEEK_API_KEY", "")

    # ─── First-run: no API key → show setup page ───
    if not _api_key_configured():
        _render_setup()
        return

    # ─── Sidebar ───
    with st.sidebar:
        st.title("📈 A股复盘助手")
        st.caption("交易者的AI复盘伙伴")

        st.divider()

        # Mode selection
        st.subheader("模式选择")
        mode = st.radio(
            "选择模式",
            ["📡 盘中研判", "📝 盘后复盘", "💼 交易持仓"],
            label_visibility="collapsed",
        )

        st.divider()

        # Time indicator
        now = datetime.now()
        hour = now.hour
        if 9 <= hour < 15:
            trading_status = "🟢 交易时段"
        elif hour == 15 and now.minute < 30:
            trading_status = "🟡 刚收盘"
        elif hour < 9:
            trading_status = "⏳ 盘前"
        else:
            trading_status = "🔴 已收盘"

        st.caption(f"{trading_status} | {now.strftime('%H:%M:%S')}")

        st.divider()
        st.caption("数据完全本地存储 · 不上传任何交易信息")
        st.caption("AI分析通过DeepSeek API · 数据仅用于当次分析请求")

    # ─── Main Content ───
    if "📡" in mode:
        render_intraday()
    elif "📝" in mode:
        render_aftermarket()
    else:
        render_trade()


if __name__ == "__main__":
    main()
