"""Trade entry and holdings management — standalone page with tight coupling."""

import streamlit as st
from datetime import datetime

from db.trade_repo import add_trade, get_trades, delete_trade, get_trade_by_id
from db.holding_repo import (
    add_holding, get_holdings, close_holding, get_holding_by_code, find_holding_by_code,
    update_holding, delete_holding as del_holding,
)
from market_data.stocks import search_stock, normalize_code, get_stock_kline_data
from market_data.tencent_api import fetch_stocks_realtime
from analysis.portfolio_analyzer import analyze_portfolio
from ui.components import render_portfolio_card


def render():
    st.title("💼 交易与持仓")

    tab1, tab2 = st.tabs(["✏️ 录入交易 + 持仓概览", "🔬 深度分析"])

    with tab1:
        _trade_and_holdings()

    with tab2:
        _portfolio_analysis_tab()


# ═════════════════════════════════════════════════════════════════
# Tab 1: Trade Entry + Holdings Overview (merged)
# ═════════════════════════════════════════════════════════════════

def _trade_and_holdings():
    _trade_form()
    st.divider()
    _holdings_with_realtime()
    st.divider()
    _kline_viewer()
    st.divider()
    _recent_trades()


def _trade_form():
    """搜股 → 自动填价 → 录入交易。同步到持仓。"""
    st.subheader("✏️ 录入交易")

    # ═══ 搜索区：输入即搜，自动匹配 ═══
    keyword = st.text_input(
        "🔍 搜索股票", placeholder="代码 / 名称 / 拼音首字母 ，如 000001、平安银行、payh",
        key="trade_search"
    )
    search_results = search_stock(keyword) if len(keyword) >= 1 else []

    stock_code = ""
    stock_name = ""
    current_price = 0.0

    if search_results:
        num_results = len(search_results)
        # 单选 → 无需下拉；多选 → 紧凑 radio
        if num_results == 1:
            r = search_results[0]
            stock_code = r['code']
            stock_name = r['name']
        else:
            options = [f"{r['code']} {r['name']}" for r in search_results]
            sel = st.radio("匹配结果", options, index=0,
                           horizontal=True, key="trade_stock_sel",
                           label_visibility="collapsed")
            if sel:
                parts = sel.split(' ', 1)
                stock_code = parts[0]
                stock_name = parts[1] if len(parts) > 1 else ""

        # 实时价格
        if stock_code:
            cache_key = f"_rtprice_{stock_code}"
            if cache_key not in st.session_state:
                rt = fetch_stocks_realtime([stock_code])
                if stock_code in rt:
                    st.session_state[cache_key] = rt[stock_code]['price']
            current_price = st.session_state.get(cache_key, 0)

        # 匹配确认
        price_str = f"  |  💰 现价 **{current_price:.2f}**" if current_price > 0 else "  |  ⚠️ 未获取到实时价"
        st.success(f"✅ **{stock_code}**  {stock_name}{price_str}")

    else:
        # 没搜到 → 手输
        c1, c2 = st.columns(2)
        with c1:
            raw_code = st.text_input("代码", placeholder="000001", key="trade_code")
            stock_code = normalize_code(raw_code) if raw_code else ""
            if raw_code and not stock_code:
                st.caption("⚠️ 格式不对，请输入6位数字代码")
        with c2:
            stock_name = st.text_input("名称", placeholder="平安银行", key="trade_name")

    # ═══ 录入表单 ═══
    with st.form("trade_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            trade_date = st.date_input("日期", value=datetime.now())
            side = st.radio("类型", ["买入", "卖出"], horizontal=True)
            price = st.number_input(
                "成交价", min_value=0.01, format="%.2f",
                value=current_price if current_price > 0 else 0.01,
                help="有实时价自动填入，可手动改"
            )
            qty = st.number_input("数量(股)", min_value=100, step=100, value=100)

        with c2:
            reason = st.text_area("交易理由", height=80, placeholder="为什么买/卖？")
            logic = st.text_input("策略标签", placeholder="龙头追涨 / 回调低吸 / 止损…")
            sync = st.checkbox("📌 同步到持仓", value=True,
                               help="买入→自动加仓；卖出→自动扣除")

        btn_col, _ = st.columns([1, 3])
        with btn_col:
            ok = st.form_submit_button("✅ 记录", type="primary", use_container_width=True)

        if ok and stock_code and stock_name and price > 0 and qty > 0:
            # 最后一道防线：再次规范化
            if not stock_code.isdigit() or len(stock_code) != 6:
                stock_code = normalize_code(stock_code)
            if not stock_code.isdigit() or len(stock_code) != 6:
                st.error(f"股票代码格式不对: '{stock_code}'，应为6位数字")
            else:
                if side == '卖出':
                    profit = None
                    pct = None
                    h = get_holding_by_code(stock_code)
                    if h and h.get('cost_price'):
                        profit = round((price - h['cost_price']) * qty, 2)
                        pct = round((price - h['cost_price']) / h['cost_price'] * 100, 2)

                    add_trade(trade_date.strftime('%Y-%m-%d'), 'sell',
                              stock_code, stock_name, price, qty,
                              reason=reason, logic=logic, profit_loss=profit,
                              profit_loss_pct=pct, tags=[])
                    if sync and h:
                        remain = h['quantity'] - qty
                        if remain <= 0:
                            close_holding(h['id'])
                        else:
                            update_holding(h['id'], quantity=remain)
                        st.success(f"已记录卖出，持仓已更新 (剩余 {max(remain,0)} 股)")
                    else:
                        st.success("卖出已记录（未同步持仓）")
                else:  # buy
                    add_trade(trade_date.strftime('%Y-%m-%d'), 'buy',
                              stock_code, stock_name, price, qty,
                              reason=reason, logic=logic, tags=[])
                    if sync:
                        # Use find_holding_by_code (includes closed) so
                        # sell-all-then-rebuy reuses the same holding row
                        existing = get_holding_by_code(stock_code)      # active
                        if not existing:
                            existing = find_holding_by_code(stock_code)  # closed
                        if existing:
                            if existing.get('is_active', 1):
                                # Active holding — add to it (weighted avg cost)
                                old_total = existing['cost_price'] * existing['quantity']
                                new_total = price * qty
                                total_qty = existing['quantity'] + qty
                                new_cost = round((old_total + new_total) / total_qty, 3)
                                update_holding(existing['id'], cost_price=new_cost, quantity=total_qty)
                                st.success(f"已加仓 {stock_name}，均价更新为 {new_cost:.2f}")
                            else:
                                # Was fully sold — reactivate with new cost basis
                                update_holding(existing['id'], cost_price=price, quantity=qty,
                                               is_active=1, buy_date=trade_date.strftime('%Y-%m-%d'))
                                st.success(f"已重建持仓 {stock_name}，成本重置为 {price:.2f}")
                        else:
                            add_holding(stock_code, stock_name, price, qty,
                                        trade_date.strftime('%Y-%m-%d'), notes=reason)
                            st.success(f"已买入并加入持仓: {stock_name}")
                    else:
                        st.success("买入已记录（未同步持仓）")


def _holdings_with_realtime():
    """Show holdings with live auto-refreshing prices from Tencent."""
    holdings = get_holdings(active_only=True)

    if not holdings:
        st.info("暂无持仓。录入买入交易时勾选「同步到持仓」即可自动添加。")
        with st.expander("手动添加持仓"):
            with st.form("quick_add", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1: code_raw = st.text_input("代码", placeholder="000001")
                with c2: name = st.text_input("名称", placeholder="平安银行")
                with c3: cost = st.number_input("成本价", min_value=0.01, format="%.3f")
                c4, c5 = st.columns(2)
                with c4: qty = st.number_input("数量", min_value=100, step=100, value=100)
                with c5: d = st.date_input("买入日期", value=datetime.now())
                if st.form_submit_button("✅ 添加"):
                    code = normalize_code(code_raw) if code_raw else ""
                    if not code:
                        st.error("代码格式不对，应为6位数字")
                    elif not name:
                        st.error("请输入股票名称")
                    elif cost > 0:
                        add_holding(code, name, cost, qty, d.strftime('%Y-%m-%d'))
                        st.success(f"已添加 {name} ({code})")
                        st.rerun()
        return

    # ── Auto-refresh toggle ──
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        st.subheader("💼 当前持仓")
    with c2:
        auto = st.checkbox("🔄 自动刷新", value=st.session_state.get('holdings_auto', False),
                           key="holdings_auto_toggle")
    with c3:
        interval = st.selectbox("间隔(秒)", [3, 5, 10, 30], index=1,
                                key="holdings_interval", label_visibility="collapsed")

    st.session_state['holdings_auto'] = auto

    # ── Fetch and display ──
    _render_holdings_table(holdings)

    if auto:
        import time
        time.sleep(interval)
        st.rerun()


def _render_holdings_table(holdings):
    """Render the holdings table with realtime prices and color coding."""
    codes = [h['stock_code'] for h in holdings]
    rt = fetch_stocks_realtime(codes)
    now_str = datetime.now().strftime('%H:%M:%S')

    rows = []
    total_market = 0
    total_cost = 0
    for h in holdings:
        code = h['stock_code']
        r = rt.get(code, {})
        cur = r.get('price', 0) or 0
        today_pct = r.get('pct', 0) or 0
        cp = h['cost_price']
        qty = h['quantity']
        mv = cur * qty
        cv = cp * qty
        pnl = mv - cv
        pnl_pct = ((cur - cp) / cp * 100) if cp else 0
        total_market += mv
        total_cost += cv
        rows.append({
            '代码': code, '名称': h['stock_name'],
            '成本': cp, '现价': cur, '涨幅': today_pct,
            '数量': qty, '市值': mv, '浮盈': pnl, '浮盈%': pnl_pct,
            '买入日': h['buy_date'],
        })

    # Summary bar
    total_pnl = total_market - total_cost
    pc = "#ef5350" if total_pnl >= 0 else "#4caf50"
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("持仓市值", f"¥{total_market:,.0f}")
    with c2:
        st.metric("持仓成本", f"¥{total_cost:,.0f}")
    with c3:
        st.markdown(
            f"**浮盈浮亏** <span style='color:{pc};font-size:1.1em'>¥{total_pnl:+,.0f}</span>",
            unsafe_allow_html=True,
        )
    with c4:
        st.caption(f"🕐 {now_str}")

    # Table
    st.dataframe(
        rows,
        column_config={
            '代码': st.column_config.TextColumn(width='small'),
            '名称': st.column_config.TextColumn(width='medium'),
            '成本': st.column_config.NumberColumn(format='%.3f'),
            '现价': st.column_config.NumberColumn(format='%.2f'),
            '涨幅': st.column_config.NumberColumn(format='%+.2f%%'),
            '数量': st.column_config.NumberColumn(format='%d'),
            '市值': st.column_config.NumberColumn(format='¥%.0f'),
            '浮盈': st.column_config.NumberColumn(format='¥%+.0f'),
            '浮盈%': st.column_config.NumberColumn(format='%+.2f%%'),
            '买入日': st.column_config.TextColumn(width='small'),
        },
        use_container_width=True, hide_index=True,
    )

    # Manage
    with st.expander("管理持仓（平仓/删除）"):
        mgmt_keyword = st.text_input(
            "🔍 搜索持仓", placeholder="代码 / 名称",
            key="hold_mgmt_search"
        )
        mgmt_holdings = get_holdings(active_only=True)
        mgmt_matches = []
        if mgmt_keyword and len(mgmt_keyword) >= 1:
            kw = mgmt_keyword.lower()
            for h in mgmt_holdings:
                code = h['stock_code']
                name = h.get('stock_name', '')
                if kw in code or kw in name.lower():
                    mgmt_matches.append(h)

        if mgmt_matches:
            mgmt_opts = [f"{h['stock_code']} {h['stock_name']} | 成本{h['cost_price']:.2f} | {h['quantity']}股" for h in mgmt_matches]
            sel = st.radio("匹配持仓", mgmt_opts, key="mgmt_sel", horizontal=True, label_visibility="collapsed")
            sel_idx = mgmt_opts.index(sel) if sel in mgmt_opts else -1
            if sel_idx >= 0:
                target = mgmt_matches[sel_idx]
                st.caption(f"选中持仓 #{target['id']}: {target['stock_code']} {target['stock_name']}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("📌 平仓", use_container_width=True, key="btn_close"):
                        close_holding(int(target['id']))
                        st.success(f"{target['stock_name']} 已平仓")
                        st.rerun()
                with c2:
                    if st.button("🗑️ 删除", use_container_width=True, key="btn_del"):
                        del_holding(int(target['id']))
                        st.success(f"{target['stock_name']} 已删除")
                        st.rerun()
        elif mgmt_keyword:
            st.caption("未匹配到持仓")


def _kline_viewer():
    """Interactive K-line chart viewer for any stock."""
    st.subheader("📊 K线图")

    holdings = get_holdings(active_only=True)
    c1, c2 = st.columns([1, 3])
    with c1:
        # Pre-populate choices: holdings first, then a custom input
        choice_labels = []
        choice_codes = []
        if holdings:
            choice_labels.append("--- 我的持仓 ---")
            choice_codes.append("")
            for h in holdings:
                choice_labels.append(f"{h['stock_code']} {h['stock_name']}")
                choice_codes.append(h['stock_code'])
        choice_labels.append("--- 手动输入 ---")
        choice_codes.append("__custom__")

        sel = st.selectbox("选择股票", choice_labels, key="kline_sel")
        sel_idx = choice_labels.index(sel) if sel in choice_labels else -1
        sel_code = choice_codes[sel_idx] if sel_idx >= 0 else ""

        if sel_code == "__custom__":
            raw = st.text_input("输入代码", placeholder="000001", key="kline_custom")
            sel_code = normalize_code(raw) if raw else ""
            sel_name = ""
        elif sel_code:
            # Find name from holdings
            sel_name = next((h['stock_name'] for h in holdings if h['stock_code'] == sel_code), "")
        else:
            sel_code = ""
            sel_name = ""

    with c2:
        days = st.slider("K线天数", 10, 120, 60, 10, key="kline_days")

    if sel_code:
        with st.spinner(f"加载 {sel_code} K线数据..."):
            df = get_stock_kline_data(sel_code, count=days)
            from ui.components import render_kline_chart
            render_kline_chart(df, stock_name=sel_name, stock_code=sel_code)
    else:
        st.info("👆 选择一只股票查看K线图")


def _recent_trades():
    """Recent trades with delete that restores holdings."""
    trades = get_trades(limit=30)
    if not trades:
        return

    st.subheader("📋 近期交易记录")
    rows = []
    for t in trades:
        rows.append({
            'ID': t['id'], '日期': t['trade_date'],
            '类型': '买' if t['trade_type'] == 'buy' else '卖',
            '代码': t['stock_code'], '名称': t['stock_name'],
            '价格': f"{t['price']:.2f}", '数量': t['quantity'],
            '理由': (t.get('reason') or '')[:20],
            '策略': (t.get('logic') or '')[:10],
            '盈亏': f"{t.get('profit_loss', 0):.2f}" if t.get('profit_loss') else '-',
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("删除交易（自动恢复持仓）"):
        del_id = st.number_input("交易ID", min_value=1, step=1, key="del_trade")
        if st.button("🗑️ 删除此交易"):
            trade = get_trade_by_id(int(del_id))
            if trade:
                # Reverse holding effect
                code = trade['stock_code']
                name = trade['stock_name']
                price = trade['price']
                qty = trade['quantity']
                h = get_holding_by_code(code)        # active only
                h_any = find_holding_by_code(code)   # active or inactive

                if trade['trade_type'] == 'buy':
                    # Undo buy: deduct from holding
                    if h and h.get('is_active', 1):
                        remain = h['quantity'] - qty
                        if remain <= 0:
                            close_holding(h['id'])
                            st.caption(f"已清空 {name} 持仓")
                        else:
                            old_total = h['cost_price'] * h['quantity']
                            new_cost = round((old_total - price * qty) / remain, 3)
                            update_holding(h['id'], quantity=remain, cost_price=new_cost)
                            st.caption(f"已从持仓扣除 {name}，均价更新为 {new_cost:.3f}")
                else:
                    # Undo sell: restore quantity (cost basis unchanged)
                    target = h or h_any
                    if target:
                        if target.get('is_active', 1):
                            update_holding(target['id'], quantity=target['quantity'] + qty)
                        else:
                            # Holding was closed — reactivate
                            update_holding(target['id'], quantity=qty, is_active=1)
                        st.caption(f"已恢复持仓 {name}")
                    else:
                        add_holding(code, name, price, qty, trade['trade_date'],
                                    notes='恢复自删除交易')
                        st.caption(f"已恢复持仓 {name}（新建）")

                delete_trade(int(del_id))
                st.success(f"交易 #{del_id} 已删除")
                st.rerun()
            else:
                st.error("交易不存在")


# ═════════════════════════════════════════════════════════════════
# Tab 2: Portfolio Deep Analysis
# ═════════════════════════════════════════════════════════════════

def _portfolio_analysis_tab():
    st.subheader("🔬 持仓技术深度分析")
    st.caption("30日K线 → MA5/10/20 + MACD + KDJ + BOLL + RSI6/14/24 + 量比 → DeepSeek逐只诊断")

    holdings = get_holdings(active_only=True)
    if not holdings:
        st.info("暂无持仓")
        return

    st.caption(f"{len(holdings)} 只持仓")

    if st.button("🔬 开始深度分析", type="primary", use_container_width=True):
        with st.spinner("并发拉取K线 + 计算7项指标 + DeepSeek分析中..."):
            try:
                results = analyze_portfolio(holdings)
                st.session_state['trade_analysis'] = results
                st.session_state['trade_analysis_time'] = datetime.now().strftime('%H:%M')
            except Exception as e:
                st.error(f"分析失败: {e}")

    results = st.session_state.get('trade_analysis')
    if results:
        st.caption(f"分析时间: {st.session_state.get('trade_analysis_time', '')}")
        for r in results:
            render_portfolio_card(r)
        if st.button("🔄 重新分析"):
            del st.session_state['trade_analysis']
            st.rerun()
