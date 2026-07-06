"""After-market review page with 3 tabs."""

import streamlit as st
import json
from datetime import datetime

from db.trade_repo import get_trades, get_trade_stats
from db.holding_repo import get_holdings
from db.analysis_repo import save_analysis, get_analyses, get_analysis_by_id, rate_analysis
from market_data.fetcher import fetch_aftermarket_data, save_aftermarket_snapshot
from analysis.analyzer import run_aftermarket_analysis
from analysis.portfolio_analyzer import analyze_portfolio
from ui.components import (
    render_index_cards, render_breadth_bar, render_sector_bars,
    render_pnl_curve, render_win_rate_pie, render_monthly_heatmap,
    status_badge, render_portfolio_card,
)


def render():
    st.title("📝 盘后复盘")

    # Check API key
    api_key = st.session_state.get('deepseek_api_key', '')
    if not api_key:
        st.warning("⚠️ 未配置 DeepSeek API Key，请在侧边栏 ⚙️ 设置 中配置")
        # Still allow trade entry and market data without API

    tab1, tab2, tab3 = st.tabs(["📊 市场数据", "🤖 AI分析", "📈 统计面板"])

    with tab1:
        _render_market_data()

    with tab2:
        _render_ai_analysis()

    with tab3:
        _render_statistics()


# ─── Tab 1: Market Data ────────────────────────────────────────

def _render_market_data():
    st.subheader("市场数据获取")

    col1, col2 = st.columns([2, 3])
    with col1:
        date = st.date_input("选择日期", value=datetime.now(), key="md_date")

    if st.button("📡 获取今日市场数据", type="primary"):
        with st.spinner("正在从 akshare 拉取数据..."):
            try:
                data = fetch_aftermarket_data(date.strftime('%Y-%m-%d'))
                st.session_state['market_data'] = data
                # Save snapshot
                save_aftermarket_snapshot(date.strftime('%Y-%m-%d'), data)
                st.success(f"✅ 已获取 {date.strftime('%Y-%m-%d')} 市场数据")
            except Exception as e:
                st.error(f"获取失败: {e}")

    data = st.session_state.get('market_data')
    if not data:
        st.info("点击按钮获取市场数据")
        return

    # Index cards
    st.subheader("📊 指数概览")
    indices = data.get('indices', {})
    if indices:
        render_index_cards(indices)
    else:
        st.info("指数数据不可用（可能是非交易日）")

    # Breadth
    breadth = data.get('breadth', {})
    if breadth:
        st.subheader("📈 市场宽度")
        render_breadth_bar(breadth)

    # Sectors
    sectors = data.get('sectors', {})
    if sectors:
        col_a, col_b = st.columns(2)
        with col_a:
            leading = sectors.get('leading_sectors', [])
            if leading:
                render_sector_bars(leading, "领涨行业板块", ascending=True)
        with col_b:
            lagging = sectors.get('lagging_sectors', [])
            if lagging:
                render_sector_bars(lagging, "领跌行业板块", ascending=False)

    # Limit-up data
    limit_up = data.get('limit_up', {})
    if limit_up:
        st.subheader("🔥 涨跌停数据")
        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            st.metric("涨停", limit_up.get('zt_count', 0))
        with col_b:
            st.metric("跌停", limit_up.get('dt_count', 0))
        with col_c:
            st.metric("炸板", limit_up.get('zb_count', 0))
        with col_d:
            st.metric("最高连板", f"{limit_up.get('max_lianban', 0)}板")

        hot = limit_up.get('hot_concepts', [])
        if hot:
            st.caption("热门涨停概念: " + ', '.join(
                f"{c['name']}({c['count']})" for c in hot[:6]
            ))

    # North bound
    # North bound — show available data post-2024 regulation
    nb = data.get('north_bound', {})
    if nb:
        st.subheader("💰 北向资金")
        if nb.get('note'):
            st.caption(nb['note'])
        leading = nb.get('leading_stocks', [])
        if leading:
            cols = st.columns(len(leading))
            for i, s in enumerate(leading):
                with cols[i]:
                    pct_color = "#ef5350" if s['pct'] >= 0 else "#4caf50"
                    st.markdown(
                        f"**{s['market']}领涨**  {s['name']}  "
                        f"<span style='color:{pct_color}'>{s['pct']:+.2f}%</span>",
                        unsafe_allow_html=True,
                    )
        b_cols = st.columns(3)
        up = nb.get('up_count')
        down = nb.get('down_count')
        flat = nb.get('flat_count')
        if up is not None:
            with b_cols[0]:
                st.metric("北向持仓上涨", f"{up} 家")
        if down is not None:
            with b_cols[1]:
                st.metric("北向持仓下跌", f"{down} 家")
        if nb.get('index_level'):
            with b_cols[2]:
                st.metric("参考指数", f"{nb['index_level']:.0f}",
                          delta=f"{nb.get('index_pct', 0):+.2f}%" if nb.get('index_pct') else None)
        if nb.get('is_trading'):
            st.caption("🟢 交易进行中（净买卖额受监管限制不披露）")


# ─── Tab 2: AI Analysis ────────────────────────────────────────

def _render_ai_analysis():
    st.subheader("AI复盘分析")

    col1, col2, col3 = st.columns(3)
    with col1:
        include_macro = st.checkbox("宏观大局分析", value=True)
    with col2:
        include_micro = st.checkbox("微观结构分析", value=True)
    with col3:
        include_scenario = st.checkbox("情景推演", value=True)

    analysis_date = st.date_input("分析日期", value=datetime.now(), key="analysis_date")

    if st.button("🚀 开始AI复盘分析", type="primary", use_container_width=True):
        if not any([include_macro, include_micro, include_scenario]):
            st.warning("请至少选择一个分析维度")
            return

        # Fetch market data first
        with st.spinner("📡 获取市场数据..."):
            try:
                data = fetch_aftermarket_data(analysis_date.strftime('%Y-%m-%d'))
                save_aftermarket_snapshot(analysis_date.strftime('%Y-%m-%d'), data)
                st.success("市场数据获取完成")
            except Exception as e:
                st.error(f"数据获取失败: {e}")
                return

        # Run analysis
        results = {}
        if include_macro:
            with st.spinner("🤖 正在进行宏观大局分析..."):
                try:
                    partial = run_aftermarket_analysis(
                        date=analysis_date.strftime('%Y-%m-%d'),
                        include_macro=True, include_micro=False, include_scenario=False
                    )
                    results['macro'] = partial.get('macro')
                    results['data'] = partial.get('data')
                    results['holdings'] = partial.get('holdings')
                    results['trades'] = partial.get('trades')
                except Exception as e:
                    st.error(f"宏观分析失败: {e}")

        if include_micro:
            with st.spinner("🤖 正在进行微观结构分析..."):
                try:
                    partial = run_aftermarket_analysis(
                        date=analysis_date.strftime('%Y-%m-%d'),
                        include_macro=False, include_micro=True, include_scenario=False
                    )
                    results['micro'] = partial.get('micro')
                except Exception as e:
                    st.error(f"微观分析失败: {e}")

        if include_scenario:
            with st.spinner("🤖 正在进行情景推演（使用DeepSeek Reasoner深度推理）..."):
                try:
                    partial = run_aftermarket_analysis(
                        date=analysis_date.strftime('%Y-%m-%d'),
                        include_macro=False, include_micro=False, include_scenario=True
                    )
                    results['scenario'] = partial.get('scenario')
                except Exception as e:
                    st.error(f"情景推演失败: {e}")

        st.session_state['aftermarket_results'] = results
        st.success("✅ AI分析完成")

    # Display results
    results = st.session_state.get('aftermarket_results')
    if not results:
        st.info("点击上方按钮开始AI复盘分析")
        return

    # ─── Macro Results ───
    macro = results.get('macro')
    if macro:
        st.divider()
        st.subheader("🏛️ 宏观大局分析")

        if isinstance(macro, dict) and 'error' not in macro:
            sentiment = macro.get('sentiment_position', {})
            phase = sentiment.get('phase', '')
            conf = sentiment.get('confidence', '')

            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"**{macro.get('market_summary', '')}**")
            with col_b:
                if phase:
                    st.metric("情绪周期", f"{status_badge(phase)} {phase}")

            with st.expander("📊 指数分析", expanded=True):
                idx_analysis = macro.get('index_analysis', {})
                for name, idx in idx_analysis.items():
                    st.markdown(f"**{name}**: {idx.get('close', '-')} ({idx.get('pct', '-')}) | "
                                f"趋势: {idx.get('trend', '-')} | {idx.get('key_levels', '')}")

            with st.expander("📈 量能分析"):
                st.markdown(macro.get('volume_analysis', ''))

            with st.expander("📊 市场宽度与情绪"):
                st.markdown(macro.get('breadth_analysis', ''))

            with st.expander("💰 北向资金分析"):
                st.markdown(macro.get('north_bound_analysis', ''))

            if sentiment:
                with st.expander(f"🔄 情绪周期定位: {phase}"):
                    st.markdown(f"**置信度**: {conf}")
                    st.markdown(sentiment.get('rationale', ''))

            risks = macro.get('risk_warnings', [])
            if risks:
                with st.expander("⚠️ 风险提示"):
                    for r in risks:
                        st.warning(r)
        else:
            st.error(f"宏观分析出错: {macro.get('error', str(macro))}")

    # ─── Micro Results ───
    micro = results.get('micro')
    if micro:
        st.divider()
        st.subheader("🔬 微观结构分析")

        if isinstance(micro, dict) and 'error' not in micro:
            sr = micro.get('sector_rotation', {})
            if sr:
                with st.expander("🔄 板块轮动", expanded=True):
                    st.markdown(f"**主线方向**: {sr.get('main_theme', '')}")
                    st.markdown(f"**轮动预判**: {sr.get('rotation_signal', '')}")

                    leading = sr.get('leading_sectors', [])
                    if leading:
                        st.caption("领涨板块:")
                        for s in leading:
                            st.markdown(f"- **{s['name']}** +{s['pct']}% | {s.get('drivers', '')} | 持续性: {s.get('sustainability', '')}")

            lu = micro.get('limit_up_analysis', {})
            if lu:
                with st.expander("🔥 涨停板结构"):
                    st.markdown(f"涨停 {lu.get('total_zt', 0)} 家 | 最高 {lu.get('max_lianban', 0)} 连板")
                    st.markdown(f"结构: {lu.get('structure', '')}")
                    st.markdown(f"情绪评分: {'🔥' * min(lu.get('sentiment_score', 5), 10)} {lu.get('sentiment_score', 5)}/10")
                    st.markdown(lu.get('interpretation', ''))

            holdings_analysis = micro.get('holdings_analysis', [])
            if holdings_analysis:
                with st.expander("💼 持仓评估", expanded=True):
                    for h in holdings_analysis:
                        assessment = h.get('assessment', '')
                        icon = {'持有': '✋', '减仓倾向': '👇', '加仓倾向': '👆', '清仓倾向': '🚪'}.get(assessment, '❓')
                        st.markdown(f"**{icon} {h.get('code', '')} {h.get('name', '')}** — {assessment}")
                        st.caption(f"成本 {h.get('cost', '-')} | 浮盈 {h.get('current_pnl_pct', '-')}% | 今日 {h.get('today_pct', '-')}%")
                        st.caption(h.get('rationale', ''))
                        st.markdown("---")

            trade_review = micro.get('trade_review', [])
            if trade_review:
                with st.expander("📝 今日交易回顾"):
                    for tr in trade_review:
                        st.markdown(f"**#{tr.get('trade_id', '')}** {tr.get('type', '')} {tr.get('code', '')} {tr.get('name', '')} — {tr.get('assessment', '')}")
                        st.caption(f"📖 {tr.get('lesson', '')}")

            opps = micro.get('opportunities', [])
            risks = micro.get('risks', [])
            if opps or risks:
                col_a, col_b = st.columns(2)
                with col_a:
                    if opps:
                        st.markdown("**🎯 关注方向**")
                        for o in opps:
                            st.success(o)
                with col_b:
                    if risks:
                        st.markdown("**⚠️ 风险提示**")
                        for r in risks:
                            st.warning(r)
        else:
            st.error(f"微观分析出错: {micro.get('error', str(micro))}")

    # ─── Scenario Results ───
    scenario = results.get('scenario')
    if scenario:
        st.divider()
        st.subheader("🔮 情景推演")

        if isinstance(scenario, dict) and 'error' not in scenario:
            scenarios = scenario.get('scenarios', {})

            bullish = scenarios.get('bullish', {})
            neutral = scenarios.get('neutral', {})
            bearish = scenarios.get('bearish', {})

            col_a, col_b, col_c = st.columns(3)

            with col_a:
                with st.container(border=True):
                    st.markdown(f"### 🟢 乐观 ({bullish.get('probability', '?')}%)")
                    st.caption(f"触发: {bullish.get('trigger', '')}")
                    st.caption(f"目标: {bullish.get('index_target', '')}")
                    st.markdown(f"**策略**: {bullish.get('strategy', '')}")

            with col_b:
                with st.container(border=True):
                    st.markdown(f"### 🟡 中性 ({neutral.get('probability', '?')}%)")
                    st.caption(f"区间: {neutral.get('range', '')}")
                    sigs = neutral.get('key_signals', [])
                    if sigs:
                        st.caption("观察信号: " + ', '.join(sigs))
                    st.markdown(f"**策略**: {neutral.get('strategy', '')}")

            with col_c:
                with st.container(border=True):
                    st.markdown(f"### 🔴 悲观 ({bearish.get('probability', '?')}%)")
                    st.caption(f"触发: {bearish.get('trigger', '')}")
                    st.caption(f"支撑: {bearish.get('support_levels', '')}")
                    st.markdown(f"**策略**: {bearish.get('strategy', '')}")

            # Short-term outlook
            st.markdown(f"**📅 短期预判**: {scenario.get('short_term_outlook', '')}")

            # Position advice
            st.info(f"**💡 仓位建议**: {scenario.get('position_advice', '')}")

            # Watch points
            watch = scenario.get('key_watch_tomorrow', [])
            if watch:
                st.markdown("**👀 明日关注**")
                for w in watch:
                    st.markdown(f"- {w}")

            # Pre-trade checklist
            checklist = scenario.get('pre_trade_checklist', [])
            if checklist:
                with st.expander("✅ 盘前检查清单"):
                    for i, item in enumerate(checklist, 1):
                        st.checkbox(f"{i}. {item}", key=f"check_{i}")

        else:
            st.error(f"情景推演出错: {scenario.get('error', str(scenario))}")

    # ─── Save Analysis ───
    if st.button("💾 保存完整分析结果"):
        try:
            analysis_payload = {
                'date': results.get('date', ''),
                'macro': results.get('macro'),
                'micro': results.get('micro'),
                'scenario': results.get('scenario'),
            }
            save_analysis(
                analysis_date=analysis_date.strftime('%Y-%m-%d'),
                analysis_type='aftermarket',
                model_used='deepseek-chat+reasoner',
                analysis_data=analysis_payload,
            )
            st.success("✅ 分析结果已保存到数据库")
        except Exception as e:
            st.error(f"保存失败: {e}")

    # ─── Portfolio Deep Analysis ───
    st.divider()
    st.subheader("🔬 持仓技术深度分析")
    st.caption("拉取每只持仓近30日K线 → 计算MA/MACD/KDJ/BOLL/RSI/量比 → DeepSeek逐只诊断")

    if st.button("🔬 深度分析所有持仓", type="primary", use_container_width=True):
        holdings_db = get_holdings(active_only=True)
        if not holdings_db:
            st.warning("当前没有持仓，请先在交易录入中添加持仓")
        else:
            with st.spinner("📊 拉取K线 + 计算技术指标 + AI深度分析中..."):
                try:
                    results = analyze_portfolio(holdings_db)
                    st.session_state['aftermarket_portfolio_results'] = results
                except Exception as e:
                    st.error(f"持仓分析失败: {e}")

    pf_results = st.session_state.get('aftermarket_portfolio_results')
    if pf_results:
        for r in pf_results:
            render_portfolio_card(r)


# ─── Tab 3: Statistics ─────────────────────────────────────────

def _render_statistics():
    st.subheader("交易统计")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("开始日期", value=datetime(2024, 1, 1), key="stats_start")
    with col2:
        end_date = st.date_input("结束日期", value=datetime.now(), key="stats_end")

    stats = get_trade_stats(
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d')
    )

    # KPI cards
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        st.metric("总交易次数", stats.get('total_trades', 0))
    with col_b:
        st.metric("卖出次数", stats.get('total_sells', 0))
    with col_c:
        st.metric("胜率", f"{stats.get('win_rate', 0)}%")
    with col_d:
        st.metric("累计盈亏", f"¥{stats.get('total_pnl', 0):.2f}")

    col_e, col_f = st.columns(2)
    with col_e:
        st.metric("平均盈亏", f"¥{stats.get('avg_pnl', 0):.2f}")

    # Charts
    trades = get_trades(limit=500)
    if trades:
        col_a, col_b = st.columns(2)
        with col_a:
            render_pnl_curve(trades)
        with col_b:
            render_win_rate_pie(stats.get('wins', 0), stats.get('total_sells', 0))

        monthly = stats.get('monthly', [])
        if monthly:
            render_monthly_heatmap(monthly)
    else:
        st.info("还没有交易记录，开始录入交易后这里会有统计图表")

    # Historical analyses
    _render_history_analyses()


# ─── History Viewer (used by both Tab 3 and Tab 4) ─────────────

def _render_history_analyses():
    """Render historical AI analyses in a readable format."""
    st.divider()
    st.subheader("📚 历史AI分析记录")

    # Filter
    col1, col2 = st.columns([2, 3])
    with col1:
        filter_type = st.selectbox(
            "筛选类型", ["全部", "盘中研判", "盘后复盘"],
            key="history_filter"
        )

    atype_filter = None
    if filter_type == "盘中研判":
        atype_filter = "intraday"
    elif filter_type == "盘后复盘":
        atype_filter = "aftermarket"

    analyses = get_analyses(analysis_type=atype_filter, limit=30)

    if not analyses:
        st.info("暂无历史分析记录。在AI分析完成后点击「保存分析」即可存档。")
        return

    st.caption(f"共 {len(analyses)} 条记录")

    for a in analyses:
        atype_label = "📡 盘中" if a['analysis_type'] == 'intraday' else "📝 盘后"
        date = a['analysis_date']
        model = a.get('model_used', '')
        rating = a.get('user_rating', 0)
        stars = '⭐' * rating if rating else '未评分'
        analysis_id = a['id']

        with st.expander(
            f"{atype_label} | {date} | {model} | {stars}",
            expanded=False
        ):
            # Rating widget
            col_r1, col_r2 = st.columns([1, 4])
            with col_r1:
                new_rating = st.select_slider(
                    "评分", options=[1, 2, 3, 4, 5],
                    value=rating if rating else 3,
                    key=f"rate_{analysis_id}"
                )
                if new_rating != rating:
                    rate_analysis(analysis_id, new_rating)
                    st.rerun()

            analysis_json = a.get('analysis_json', {})
            if not isinstance(analysis_json, dict):
                st.text(str(analysis_json)[:500])
                continue

            # Intraday: plain text
            if a['analysis_type'] == 'intraday':
                text = analysis_json.get('analysis_text', '')
                if text:
                    st.markdown(text)
                else:
                    st.json(analysis_json, expanded=False)
                continue

            # Aftermarket: structured display
            macro = analysis_json.get('macro', {})
            micro = analysis_json.get('micro', {})
            scenario = analysis_json.get('scenario', {})

            if macro and isinstance(macro, dict) and 'error' not in macro:
                st.markdown("### 🏛️ 宏观大局")
                sentiment = macro.get('sentiment_position', {})
                phase = sentiment.get('phase', '')
                conf = sentiment.get('confidence', '')
                st.caption(f"**{macro.get('market_summary', '')}**  |  情绪周期: {status_badge(phase)} {phase} ({conf}置信度)")

                # Index analysis compact table
                idx_table = []
                for name, idx in macro.get('index_analysis', {}).items():
                    idx_table.append({
                        '指数': name, '收盘': idx.get('close', '-'),
                        '涨跌': idx.get('pct', '-'), '趋势': idx.get('trend', '-'),
                        '关键位': idx.get('key_levels', '')[:40]
                    })
                if idx_table:
                    st.dataframe(idx_table, use_container_width=True, hide_index=True)

                st.markdown(f"**量能**: {macro.get('volume_analysis', '')[:200]}")
                st.markdown(f"**情绪**: {macro.get('breadth_analysis', '')[:200]}")
                st.markdown(f"**北向**: {macro.get('north_bound_analysis', '')[:200]}")

                risks = macro.get('risk_warnings', [])
                if risks:
                    for r in risks:
                        st.warning(r)

            if micro and isinstance(micro, dict) and 'error' not in micro:
                st.markdown("### 🔬 微观结构")
                sr = micro.get('sector_rotation', {})
                if sr:
                    st.caption(f"**主线**: {sr.get('main_theme', '')}  |  **轮动预判**: {sr.get('rotation_signal', '')}")
                    for s in sr.get('leading_sectors', [])[:5]:
                        st.caption(f"🔥 {s['name']} +{s.get('pct','')}% | {s.get('drivers','')} | 持续性: {s.get('sustainability','')}")

                lu = micro.get('limit_up_analysis', {})
                if lu:
                    st.caption(
                        f"涨停{lu.get('total_zt','-')}家 | "
                        f"最高{lu.get('max_lianban','-')}板 | "
                        f"情绪{lu.get('sentiment_score','-')}/10 | "
                        f"{lu.get('interpretation','')[:100]}"
                    )

                for h in micro.get('holdings_analysis', []):
                    a_text = h.get('assessment', '')
                    icon = {'持有': '✋', '减仓倾向': '👇', '加仓倾向': '👆', '清仓倾向': '🚪'}.get(a_text, '❓')
                    st.caption(f"{icon} {h.get('code','')} {h.get('name','')} — {a_text}: {h.get('rationale','')[:100]}")

                for tr in micro.get('trade_review', []):
                    icon = '✅' if '符合' in tr.get('assessment', '') else '⚠️'
                    st.caption(f"{icon} #{tr.get('trade_id','')} {tr.get('type','')} {tr.get('name','')} — {tr.get('assessment','')}: {tr.get('lesson','')[:80]}")

            if scenario and isinstance(scenario, dict) and 'error' not in scenario:
                st.markdown("### 🔮 情景推演")
                sc = scenario.get('scenarios', {})
                bullish = sc.get('bullish', {})
                neutral = sc.get('neutral', {})
                bearish = sc.get('bearish', {})

                cols = st.columns(3)
                with cols[0]:
                    st.caption(f"🟢 乐观 {bullish.get('probability','?')}%: {bullish.get('strategy','')[:80]}")
                with cols[1]:
                    st.caption(f"🟡 中性 {neutral.get('probability','?')}%: {neutral.get('strategy','')[:80]}")
                with cols[2]:
                    st.caption(f"🔴 悲观 {bearish.get('probability','?')}%: {bearish.get('strategy','')[:80]}")

                st.caption(f"📅 **短期预判**: {scenario.get('short_term_outlook', '')[:200]}")
                st.caption(f"💡 **仓位建议**: {scenario.get('position_advice', '')}")

            # Raw JSON (checkbox, not expander — can't nest them)
            if st.checkbox("📋 显示原始JSON", key=f"raw_{analysis_id}"):
                st.json(analysis_json, expanded=False)
