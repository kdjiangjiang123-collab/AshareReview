"""Convert raw market data into structured text for LLM prompts."""

import json
from datetime import datetime
from typing import Optional


def format_market_data(data: dict, holdings: Optional[list] = None,
                       trades: Optional[list] = None) -> str:
    """Format all market data into a structured text for LLM consumption.
    Used for both intraday and aftermarket analysis.

    Args:
        data: The market data dict from fetcher.
        holdings: List of user's active holdings.
        trades: List of today's trades for aftermarket review.

    Returns:
        Formatted text ready to inject into the user message.
    """
    parts = []
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    parts.append(f"## 当前时间\n{now}")
    parts.append("")

    # ─── Indices ───
    indices = data.get('indices') or data.get('index_data', {})
    if indices:
        parts.append("## 主要指数")
        parts.append("| 指数 | 收盘/现价 | 涨跌幅 | 成交额(亿) | 开盘 | 最高 | 最低 |")
        parts.append("|------|-----------|--------|------------|------|------|------|")
        for name, idx in indices.items():
            close = _fmt(idx.get('close', 0))
            pct = _fmt_pct(idx.get('pct', 0))
            amount = _fmt_amount(idx.get('amount', 0))
            open_p = _fmt(idx.get('open', ''))
            high = _fmt(idx.get('high', ''))
            low = _fmt(idx.get('low', ''))
            parts.append(f"| {name} | {close} | {pct} | {amount} | {open_p} | {high} | {low} |")
        parts.append("")

        # Recent 5 days for trend context
        for name, idx in indices.items():
            recent = idx.get('recent_5', [])
            if recent:
                closes = [str(r.get('close', '')) for r in recent]
                dates = [str(r.get('date', ''))[-5:] for r in recent]
                parts.append(f"{name} 近5日收盘: {', '.join(closes)}")
                break  # One is enough for context
        parts.append("")

    # ─── Breadth ───
    breadth = data.get('breadth') or data.get('breadth_data', {})
    if breadth:
        parts.append("## 市场宽度")
        parts.append(f"- 上涨: {breadth.get('up_count', 0)} 家 ({breadth.get('up_pct', 0)}%)")
        parts.append(f"- 下跌: {breadth.get('down_count', 0)} 家 ({breadth.get('down_pct', 0)}%)")
        parts.append(f"- 平盘: {breadth.get('flat_count', 0)} 家")
        if breadth.get('total_amount_yi'):
            parts.append(f"- 两市成交额: {breadth['total_amount_yi']} 亿")
        parts.append("")

    # ─── Limit Up / Down ───
    lu = data.get('limit_up') or data.get('limit_up_data', {})
    if lu:
        parts.append("## 涨跌停数据")
        parts.append(f"- 涨停: {lu.get('zt_count', 0)} 家")
        parts.append(f"- 跌停: {lu.get('dt_count', 0)} 家")
        parts.append(f"- 炸板: {lu.get('zb_count', 0)} 家")
        if lu.get('max_lianban'):
            parts.append(f"- 最高连板: {lu['max_lianban']} 板")
        if lu.get('zt_structure'):
            parts.append(f"- 连板结构: {json.dumps(lu['zt_structure'], ensure_ascii=False)}")
        if lu.get('hot_concepts'):
            concepts_str = ', '.join(
                f"{c.get('name', c)}" + (f"({c.get('count', '')}只)" if isinstance(c, dict) else "")
                for c in lu['hot_concepts'][:8]
            )
            parts.append(f"- 涨停热门概念: {concepts_str}")
        parts.append("")

    # ─── Sectors ───
    sectors = data.get('sectors') or data.get('sector_data', {})
    if sectors:
        leading = sectors.get('leading_sectors', [])
        if leading:
            parts.append("## 领涨板块")
            for s in leading[:8]:
                parts.append(f"- {s['name']}: **+{s['pct']}%**")
            parts.append("")

        lagging = sectors.get('lagging_sectors', [])
        if lagging:
            parts.append("## 领跌板块")
            for s in lagging[:8]:
                parts.append(f"- {s['name']}: {s['pct']}%")
            parts.append("")

        # Concept boards
        leading_c = sectors.get('leading_concepts', [])
        if leading_c:
            parts.append("## 热门概念")
            for c in leading_c[:6]:
                parts.append(f"- {c['name']}: +{c['pct']}%")
            parts.append("")

    # ─── North Bound ───
    nb = data.get('north_bound') or data.get('north_flow', {})
    if nb:
        parts.append("## 北向资金")
        if nb.get('note'):
            parts.append(f"- {nb['note']}")
        leading = nb.get('leading_stocks', [])
        if leading:
            for s in leading:
                parts.append(f"- {s.get('market', '')}领涨: {s['name']} {s['pct']:+.2f}%")
        if nb.get('up_count') is not None:
            parts.append(f"- 北向持仓: 上涨{nb['up_count']}家 / 下跌{nb['down_count']}家 / 持平{nb.get('flat_count', 0)}家")
        if nb.get('index_level'):
            idx_pct = nb.get('index_pct')
            pct_str = f" ({idx_pct:+.2f}%)" if idx_pct else ""
            parts.append(f"- 参考指数: {nb['index_level']:.2f}{pct_str}")
        if nb.get('is_trading'):
            parts.append("- 交易进行中（净买卖额受监管限制不披露）")
        parts.append("")

    # ─── Holdings ───
    hlist = holdings or data.get('holdings_snapshot', [])
    if hlist:
        parts.append("## 用户持仓")
        parts.append("| 代码 | 名称 | 成本价 | 现价 | 今日涨跌 | 浮盈浮亏 |")
        parts.append("|------|------|--------|------|----------|----------|")
        for h in hlist:
            code = h.get('stock_code', '')
            name = h.get('stock_name', '')
            cost = _fmt(h.get('cost_price', 0))
            cur = _fmt(h.get('current_price', ''))
            today = _fmt_pct(h.get('today_pct', ''))
            pnl = _fmt_pct(h.get('pnl_pct', ''))
            parts.append(f"| {code} | {name} | {cost} | {cur} | {today} | {pnl} |")
        parts.append("")

    # ─── Today's Trades ───
    if trades:
        parts.append("## 今日交易记录")
        parts.append("| ID | 类型 | 代码 | 名称 | 价格 | 数量 | 理由 | 策略 | 盈亏 | 标签 |")
        parts.append("|----|------|------|------|------|------|------|------|------|------|")
        for t in trades:
            tid = t.get('id', '')
            ttype = '买入' if t.get('trade_type') == 'buy' else '卖出'
            code = t.get('stock_code', '')
            name = t.get('stock_name', '')
            price = _fmt(t.get('price', 0))
            qty = t.get('quantity', 0)
            reason = str(t.get('reason', ''))[:30]
            logic = str(t.get('logic', ''))[:20]
            pnl = _fmt(t.get('profit_loss', ''))
            tags = ', '.join(t.get('tags', [])) if isinstance(t.get('tags'), list) else str(t.get('tags', ''))[:20]
            parts.append(f"| {tid} | {ttype} | {code} | {name} | {price} | {qty} | {reason} | {logic} | {pnl} | {tags} |")
        parts.append("")

    parts.append("---")
    parts.append("请基于以上数据进行分析。")

    return "\n".join(parts)


def _fmt(val) -> str:
    """Format a numeric value for display."""
    if val is None or val == '':
        return '-'
    try:
        return f"{float(val):.2f}"
    except (ValueError, TypeError):
        return str(val)


def _fmt_pct(val) -> str:
    """Format a percentage value."""
    if val is None or val == '':
        return '-'
    try:
        v = float(val)
        return f"{v:+.2f}%"
    except (ValueError, TypeError):
        return str(val)


def _fmt_amount(val) -> str:
    """Format amount in 亿."""
    if val is None or val == '':
        return '-'
    try:
        v = float(val)
        if v > 1e8:
            return f"{v / 1e8:.2f}"
        return f"{v:.2f}"
    except (ValueError, TypeError):
        return str(val)
