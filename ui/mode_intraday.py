"""Intraday analysis page — quick market scan for in-session decisions."""

import streamlit as st
from datetime import datetime

from analysis.analyzer import run_intraday_analysis
from analysis.portfolio_analyzer import analyze_portfolio
from market_data.fetcher import fetch_intraday_data
from ui.components import render_index_cards, render_sector_bars, render_portfolio_card
from db.analysis_repo import save_analysis
from db.holding_repo import get_holdings


def render():
    st.title("📡 盘中研判")
    st.caption(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Check API key
    api_key = st.session_state.get('deepseek_api_key', '')
    if not api_key:
        st.warning("⚠️ 未配置 DeepSeek API Key，请在侧边栏 ⚙️ 设置 中配置")
        return

    # ─── Quick Data Refresh ───
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🔄 刷新数据 + AI研判", type="primary", use_container_width=True):
            st.session_state['intraday_loading'] = True

    with col2:
        auto_refresh = st.checkbox("自动刷新", value=False)
    with col3:
        if auto_refresh:
            interval = st.selectbox("间隔", [5, 10, 15, 30], index=1, label_visibility="collapsed")

    # ─── Auto refresh logic ───
    if auto_refresh:
        st.session_state['intraday_loading'] = True
        import time
        time.sleep(interval * 60)

    # ─── Market Data Display ───
    # Always show current data if available
    if st.session_state.get('intraday_loading'):
        with st.spinner("正在拉取市场数据..."):
            try:
                data = fetch_intraday_data()
                st.session_state['intraday_data'] = data
            except Exception as e:
                st.error(f"数据获取失败: {e}")
                st.session_state['intraday_loading'] = False
                return

        # Show data
        data = st.session_state.get('intraday_data', {})
        if data:
            st.subheader("📊 市场概况")

            # Index cards
            index_data = data.get('index_data', {})
            if index_data:
                render_index_cards(index_data)

            # Breadth
            breadth = data.get('breadth_data', {})
            if breadth:
                st.caption(
                    f"上涨 {breadth.get('up_count', 0)} 家 · "
                    f"下跌 {breadth.get('down_count', 0)} 家 · "
                    f"涨停约 {breadth.get('zt_count_realtime', '-')} 家 · "
                    f"成交 {breadth.get('total_amount_yi', '-')} 亿"
                )

            # Sector rankings
            sector_data = data.get('sector_data', {})
            leading = sector_data.get('leading_sectors', [])
            lagging = sector_data.get('lagging_sectors', [])

            col_a, col_b = st.columns(2)
            with col_a:
                if leading:
                    render_sector_bars(leading, "领涨板块", ascending=True)
            with col_b:
                if lagging:
                    render_sector_bars(lagging, "领跌板块", ascending=False)

            # Holdings snapshot
            holdings = data.get('holdings_snapshot', [])
            if holdings:
                st.subheader("💼 持仓跟踪")
                hdf = [
                    {
                        '代码': h.get('stock_code', ''),
                        '名称': h.get('stock_name', ''),
                        '成本': h.get('cost_price', 0),
                        '现价': h.get('current_price', '-'),
                        '今日涨跌': f"{h.get('today_pct', 0):+.2f}%" if h.get('today_pct') is not None else '-',
                        '浮盈浮亏': f"{h.get('pnl_pct', 0):+.2f}%" if h.get('pnl_pct') is not None else '-',
                    }
                    for h in holdings
                ]
                st.dataframe(hdf, use_container_width=True, hide_index=True)

                # ─── Deep Portfolio Analysis ───
                st.divider()
                col_btn, col_info = st.columns([2, 3])
                with col_btn:
                    run_deep = st.button(
                        "🔬 深度分析持仓",
                        type="primary",
                        use_container_width=True,
                        help="拉取每只持仓的K线+技术指标，DeepSeek逐只深度诊断"
                    )
                with col_info:
                    st.caption("计算MA5/10/20 + MACD + KDJ + BOLL + RSI + 量比 → AI逐只诊断")

                if run_deep:
                    _run_portfolio_analysis()
                elif st.session_state.get('portfolio_results'):
                    _show_portfolio_results()

        # ─── AI Analysis ───
        with st.spinner("🤖 DeepSeek 正在分析盘中局势..."):
            try:
                analysis = run_intraday_analysis()
                st.session_state['intraday_analysis'] = analysis
            except Exception as e:
                st.error(f"AI分析失败: {e}")
                st.session_state['intraday_loading'] = False
                return

        st.session_state['intraday_loading'] = False

    # Display cached analysis
    analysis = st.session_state.get('intraday_analysis')
    if analysis:
        st.divider()
        st.subheader("🤖 AI 盘中研判")

        analysis_text = analysis.get('analysis_text', '')
        if analysis_text:
            # Display as formatted markdown sections
            sections = _parse_intraday_sections(analysis_text)
            for title, content in sections:
                with st.expander(title, expanded=True):
                    st.markdown(content)

        # Save option
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("💾 保存本次分析"):
                try:
                    save_analysis(
                        analysis_date=datetime.now().strftime('%Y-%m-%d'),
                        analysis_type='intraday',
                        model_used='deepseek-chat',
                        analysis_data={
                            'snapshot_time': analysis.get('snapshot_time', ''),
                            'analysis_text': analysis_text,
                        }
                    )
                    st.success("已保存")
                except Exception as e:
                    st.error(f"保存失败: {e}")

        # Market data details
        with st.expander("📋 查看完整市场数据"):
            st.code(analysis.get('market_text', ''), language='markdown')


def _parse_intraday_sections(text: str) -> list[tuple[str, str]]:
    """Parse the intraday analysis text into titled sections."""
    if not text:
        return [("分析结果", "暂无内容")]

    sections = []
    lines = text.split('\n')
    current_title = ""
    current_content = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect section headers (various patterns)
        is_header = False
        if stripped.startswith('###') or stripped.startswith('##'):
            is_header = True
            title = stripped.lstrip('#').strip()
        elif (stripped.startswith('**') and stripped.endswith('**') and len(stripped) < 30):
            is_header = True
            title = stripped.strip('*')
        elif (stripped[0].isdigit() and '. ' in stripped[:4]):
            # "1. Title" pattern
            is_header = True
            title = stripped.split('. ', 1)[-1]
        elif '：' in stripped and len(stripped) < 30 and not current_content:
            is_header = True
            title = stripped.rstrip('：')

        if is_header:
            if current_title or current_content:
                sections.append((current_title or "分析", '\n'.join(current_content)))
            current_title = title
            current_content = []
        else:
            current_content.append(stripped)

    # Last section
    if current_title or current_content:
        sections.append((current_title or "分析", '\n'.join(current_content)))

    if not sections and text:
        sections = [("AI分析结果", text)]

    return sections


# ─── Portfolio Deep Analysis ───────────────────────────────────

def _run_portfolio_analysis():
    """Fetch K-line + indicators for all holdings, send to DeepSeek."""
    holdings_db = get_holdings(active_only=True)
    if not holdings_db:
        st.warning("当前没有持仓，请先在交易录入中添加持仓")
        return

    with st.spinner("📊 拉取每只持仓K线 + 计算MA/MACD/KDJ/BOLL/RSI/量比 + AI分析中..."):
        try:
            results = analyze_portfolio(holdings_db)
        except Exception as e:
            st.error(f"分析失败: {e}")
            return

    st.session_state['portfolio_results'] = results
    st.session_state['portfolio_time'] = datetime.now().strftime('%H:%M:%S')
    st.rerun()


def _show_portfolio_results():
    """Render cached portfolio analysis cards."""
    results = st.session_state.get('portfolio_results', [])
    ptime = st.session_state.get('portfolio_time', '')

    if not results:
        return

    st.divider()
    st.subheader(f"🔬 持仓深度分析 ({ptime})")
    st.caption("近30日K线 + 7项技术指标 → DeepSeek逐只诊断趋势·价位·信号·风险·操作倾向")

    for r in results:
        render_portfolio_card(r)

    if st.button("🔄 重新分析", use_container_width=True):
        del st.session_state['portfolio_results']
        st.rerun()
