"""Reusable Streamlit UI components."""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import pandas as pd


def render_kline_chart(df: pd.DataFrame, stock_name: str = "", stock_code: str = ""):
    """Render an interactive candlestick chart with MA overlays and volume.

    Args:
        df: DataFrame with columns [open, high, low, close, volume],
            indexed by date.
        stock_name: display name
        stock_code: display code
    """
    if df is None or df.empty:
        st.info("暂无K线数据")
        return

    # ── Calculate MAs ──
    df = df.copy()
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma10'] = df['close'].rolling(10).mean()
    df['ma20'] = df['close'].rolling(20).mean()

    # ── Color scheme ──
    RED = '#ef5350'
    GREEN = '#26a69a'
    colors = [RED if row['close'] >= row['open'] else GREEN
              for _, row in df.iterrows()]

    # ── Build subplots: main chart + volume ──
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
    )

    # --- Candlestick ---
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'], high=df['high'],
        low=df['low'], close=df['close'],
        name='K线',
        increasing_line_color=RED,
        decreasing_line_color=GREEN,
        showlegend=False,
    ), row=1, col=1)

    # --- MA lines ---
    for ma, col, w in [('ma5', '#f4a742', 1.2), ('ma10', '#42a5f5', 1.2), ('ma20', '#ab47bc', 1.5)]:
        if not df[ma].isna().all():
            fig.add_trace(go.Scatter(
                x=df.index, y=df[ma],
                mode='lines', name=ma.upper(),
                line=dict(color=col, width=w),
                showlegend=True,
            ), row=1, col=1)

    # --- Volume bars ---
    vol_colors = [RED if df['close'].iloc[i] >= df['open'].iloc[i] else GREEN
                  for i in range(len(df))]
    fig.add_trace(go.Bar(
        x=df.index, y=df['volume'],
        name='成交量', marker_color=vol_colors,
        opacity=0.5, showlegend=False,
    ), row=2, col=1)

    # ── Layout ──
    title = f"{stock_name} ({stock_code})" if stock_name else "K线图"
    fig.update_layout(
        title=dict(text=title, font=dict(size=18)),
        xaxis=dict(rangeslider=dict(visible=False)),
        yaxis=dict(title='价格', side='right'),
        yaxis2=dict(title='成交量(手)', tickformat=',.0f', separatethousands=True),
        height=550,
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode='x unified',
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02,
            xanchor='left', x=0, font=dict(size=11),
        ),
        template='plotly_white',
    )

    # ── Price range annotation ──
    last_close = df['close'].iloc[-1]
    first_close = df['close'].iloc[0]
    chg = (last_close - first_close) / first_close * 100 if first_close else 0
    chg_color = RED if chg >= 0 else GREEN
    chg_emoji = '📈' if chg >= 0 else '📉'
    fig.add_annotation(
        xref='paper', yref='paper', x=0.01, y=0.99,
        text=f"{chg_emoji} {chg:+.2f}%  | 最高 {df['high'].max():.2f}  |  最低 {df['low'].min():.2f}",
        showarrow=False, font=dict(color=chg_color, size=12),
        bgcolor='rgba(255,255,255,0.8)', align='left',
    )

    st.plotly_chart(fig, use_container_width=True)


def render_index_cards(indices: dict):
    """Render KPI-style cards for major indices."""
    if not indices:
        st.info("暂无指数数据")
        return

    cols = st.columns(len(indices))
    for i, (name, idx) in enumerate(indices.items()):
        pct = idx.get('pct', 0)
        close = idx.get('close', 0)
        delta_color = "inverse"  # A股：涨红跌绿
        if pct > 0:
            emoji = "🔴"
        elif pct < 0:
            emoji = "🟢"
        else:
            emoji = "⚪"

        with cols[i]:
            st.metric(
                label=f"{emoji} {name}",
                value=f"{close:.2f}" if close else "-",
                delta=f"{pct:+.2f}%" if pct else None,
                delta_color=delta_color,
            )


def render_breadth_bar(breadth: dict):
    """Render market breadth as a horizontal bar chart."""
    if not breadth:
        return

    up = breadth.get('up_count', 0)
    down = breadth.get('down_count', 0)
    flat = breadth.get('flat_count', 0)

    fig = go.Figure(go.Bar(
        x=[up, down, flat],
        y=['上涨', '下跌', '平盘'],
        orientation='h',
        marker_color=['#ef5350', '#4caf50', '#9e9e9e'],
        text=[up, down, flat],
        textposition='inside',
    ))
    fig.update_layout(
        height=150,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(visible=False),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_sector_bars(sectors: list, title: str, ascending: bool = True):
    """Render sector ranking as horizontal bar chart."""
    if not sectors:
        return

    df = pd.DataFrame(sectors)
    df = df.sort_values('pct', ascending=ascending)

    color = '#ef5350' if ascending else '#4caf50'  # A股：涨红跌绿

    fig = go.Figure(go.Bar(
        x=df['pct'],
        y=df['name'],
        orientation='h',
        marker_color=color,
        text=[f"{v:+.2f}%" for v in df['pct']],
        textposition='outside',
    ))
    fig.update_layout(
        title=title,
        height=300,
        margin=dict(l=10, r=50, t=30, b=10),
        xaxis=dict(title='涨跌幅(%)'),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_pnl_curve(trades: list):
    """Render cumulative P&L curve."""
    sells = [t for t in trades if t.get('trade_type') == 'sell' and t.get('profit_loss') is not None]
    if not sells:
        st.info("暂无卖出记录，盈亏曲线需要卖出数据")
        return

    sells_sorted = sorted(sells, key=lambda x: x['trade_date'])
    cumulative = 0
    dates = []
    pnls = []
    for s in sells_sorted:
        cumulative += s['profit_loss']
        dates.append(s['trade_date'])
        pnls.append(cumulative)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=pnls, mode='lines+markers',
        line=dict(color='#ef5350', width=2),
        fill='tozeroy',
        fillcolor='rgba(239,83,80,0.1)',
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(
        title="累计盈亏曲线",
        height=350,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(title='日期'),
        yaxis=dict(title='累计盈亏'),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_win_rate_pie(wins: int, total: int):
    """Render win rate as a donut chart."""
    if total == 0:
        return

    losses = total - wins
    fig = go.Figure(go.Pie(
        labels=['盈利', '亏损'],
        values=[wins, losses],
        hole=0.6,
        marker_colors=['#ef5350', '#4caf50'],
        textinfo='label+percent',
    ))
    fig.update_layout(
        height=300,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_monthly_heatmap(monthly_data: list):
    """Render monthly P&L as bar chart."""
    if not monthly_data:
        return

    df = pd.DataFrame(monthly_data)
    # Fill None/NaN with 0 to avoid comparison errors
    pnl_values = df.get('total_pnl', []).fillna(0)
    colors = ['#ef5350' if v > 0 else '#4caf50' for v in pnl_values]

    fig = go.Figure(go.Bar(
        x=df['month'],
        y=pnl_values,
        marker_color=colors,
        text=[f"{v:.0f}" for v in pnl_values],
        textposition='outside',
    ))
    fig.update_layout(
        title="月度盈亏",
        height=350,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(title='月份'),
        yaxis=dict(title='盈亏'),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def status_badge(phase: str) -> str:
    """Return emoji for sentiment phase."""
    badges = {
        '冰点期': '🥶',
        '修复期': '🌤️',
        '主升期': '🔥',
        '高潮期': '🚀',
        '退潮期': '🌧️',
        '混沌期': '🌫️',
    }
    return badges.get(phase, '❓')


def render_portfolio_card(result: dict):
    """Render a single stock's deep analysis as a rich info card."""
    profile = result.get('profile', {})
    analysis = result.get('analysis', {})

    code = profile.get('code', '')
    name = profile.get('name', '')
    current_price = profile.get('current_price', 0)
    today_pct = profile.get('today_pct', 0)
    pnl_pct = profile.get('pnl_pct', 0)
    cost = profile.get('cost', 0)
    ind = profile.get('indicators', {})

    assessment = analysis.get('assessment', '持有')
    assessment_map = {
        '持有': ('✋', '#ff9800'),
        '减仓观察': ('👇', '#f44336'),
        '可加仓': ('👆', '#4caf50'),
        '倾向清仓': ('🚪', '#d32f2f'),
    }
    icon, color = assessment_map.get(assessment, ('❓', '#9e9e9e'))

    trend = analysis.get('trend', '')
    trend_icon = {
        '上升趋势': '📈', '下降趋势': '📉',
        '区间震荡': '📊', '潜在转折': '🔄'
    }.get(trend, '📊')

    with st.container(border=True):
        # Header: name, price, cost, assessment
        c1, c2, c3, c4 = st.columns([2, 1.5, 1.5, 1])
        with c1:
            st.markdown(f"### {name} `{code}`")
        with c2:
            pc = "#ef5350" if today_pct >= 0 else "#4caf50"
            st.markdown(
                f"<span style='font-size:1.4em;font-weight:bold;color:{pc}'>"
                f"{current_price:.2f}</span> "
                f"<span style='color:{pc}'>{today_pct:+.2f}%</span>",
                unsafe_allow_html=True,
            )
        with c3:
            cc = "#ef5350" if pnl_pct >= 0 else "#4caf50"
            st.markdown(
                f"成本 {cost:.2f} | "
                f"<span style='color:{cc};font-weight:bold'>浮{pnl_pct:+.2f}%</span>",
                unsafe_allow_html=True,
            )
        with c4:
            st.markdown(
                f"<span style='font-size:1.2em;color:{color}'>{icon} {assessment}</span>",
                unsafe_allow_html=True,
            )

        # Indicator row
        st.markdown("---")
        i1, i2, i3, i4, i5, i6, i7 = st.columns(7)
        with i1:
            st.metric("MA5", ind.get('ma5', '-'))
        with i2:
            st.metric("MA20", ind.get('ma20', '-'))
        with i3:
            ms = ind.get('macd_signal', '')
            mi = '🟢' if '金叉' in ms else '🔴' if '死叉' in ms else '⚪'
            st.metric(f"{mi} MACD", ind.get('dif', '-'))
        with i4:
            kv = ind.get('k', 0)
            kc = 'inverse' if kv > 70 else 'normal' if kv < 30 else 'off'
            st.metric("KDJ-K", f"{kv:.0f}", delta_color=kc)
        with i5:
            rv = ind.get('rsi14', 50)
            rc = 'inverse' if rv > 70 else 'normal' if rv < 30 else 'off'
            st.metric("RSI14", f"{rv:.0f}", delta_color=rc)
        with i6:
            st.metric("量比", ind.get('vol_ratio', '-'))
        with i7:
            st.metric("趋势", f"{trend_icon} {trend[:2]}..")

        # Analysis details
        st.markdown("---")
        a1, a2 = st.columns(2)
        with a1:
            st.caption(f"**信号**: {analysis.get('signal_summary', '-')}")
            st.caption(f"**支撑**: {analysis.get('support', '-')} | **压力**: {analysis.get('resistance', '-')}")
            st.caption(f"**MA**: {ind.get('ma_status', '-')}")
            st.caption(f"**RSI**: {ind.get('rsi_status', '-')} | **BOLL**: {ind.get('boll_status', '-')}")
            st.caption(f"**量能**: {ind.get('vol_status', '-')}")
        with a2:
            rsn = analysis.get('assessment_reason', '')
            st.markdown(f"**{icon} {assessment}** — {rsn}")
            ref = analysis.get('reference_price', 0)
            if ref and ref > 0:
                st.caption(f"参考价位: {ref:.2f}")
            st.caption(f"⚠️ {analysis.get('risk', '')}")

        # Expandable full analysis
        full = analysis.get('full_analysis', '')
        if full:
            with st.expander(f"📝 {name} 完整分析"):
                st.markdown(full)
