"""Fetch north-bound capital flow data.

2024.8.19 regulation change: China stopped real-time disclosure of net buy/sell
amounts. ALL providers (akshare, eastmoney, sina, tencent) show NaN or 0 for
flow data. The only data still published:
  - 领涨股 (leading stocks in north-bound portfolio)
  - 上涨/下跌家数 (breadth within north-bound holdings)
  - 交易状态 (market open/closed)
  - 额度 (daily quota — not actual flow, always 520/420 billion)
"""

import time
from datetime import datetime
import pandas as pd
import akshare as ak
from config.settings import AKSHARE_RETRY, AKSHARE_RETRY_DELAY


def _retry(func, *args, **kwargs):
    for attempt in range(AKSHARE_RETRY):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == AKSHARE_RETRY - 1:
                raise e
            time.sleep(AKSHARE_RETRY_DELAY * (attempt + 1))


def _is_trading_time() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 60 + now.minute
    return 9 * 60 + 25 <= t <= 15 * 60 + 5


def get_north_bound_daily() -> dict:
    """Get available north-bound data for the latest trading day.

    Since 2024.8.19, net flow amounts are no longer published.
    We extract what IS available: leading stocks, index context, and breadth.

    Returns a dict suitable for display in the UI.
    """
    result = {
        'leading_stocks': [],       # [{name, pct, code}] — 领涨股
        'index_level': None,        # 沪深300 or 上证指数 点位
        'index_pct': None,          # 指数涨跌幅
        'date': '',                 # 数据日期
        'note': '',                 # 说明文字
        # During trading hours, fund_flow_summary adds:
        'up_count': None,           # 北向持仓上涨家数
        'down_count': None,
        'flat_count': None,
        'is_trading': False,        # 是否交易时段
    }

    # ── Daily history — 领涨股 + 指数 ──
    try:
        df_sh = _retry(ak.stock_hsgt_hist_em, symbol="沪股通")
        df_sz = _retry(ak.stock_hsgt_hist_em, symbol="深股通")

        notes = []

        for name, df in [("沪股通", df_sh), ("深股通", df_sz)]:
            if df is None or df.empty:
                continue
            latest = df.iloc[-1]
            result['date'] = str(latest.get('日期', ''))

            # 领涨股
            ls = latest.get('领涨股')
            if ls and not (isinstance(ls, float) and pd.isna(ls)):
                ls_pct = latest.get('领涨股-涨跌幅')
                ls_code = latest.get('领涨股-代码', '')
                result['leading_stocks'].append({
                    'name': str(ls),
                    'pct': float(ls_pct) if ls_pct and not pd.isna(ls_pct) else 0,
                    'code': str(ls_code).replace('.SH', '').replace('.SZ', ''),
                    'market': name,
                })

            # Index level (use first available)
            if result['index_level'] is None:
                for col in ['沪深300', '上证指数', '深证指数']:
                    if col in df.columns:
                        val = latest.get(col)
                        if val and not (isinstance(val, float) and pd.isna(val)):
                            result['index_level'] = float(val)
                            pct_col = f'{col}-涨跌幅'
                            if pct_col in df.columns:
                                pct_val = latest.get(pct_col)
                                if pct_val and not (isinstance(pct_val, float) and pd.isna(pct_val)):
                                    result['index_pct'] = float(pct_val)
                            break

        if result['leading_stocks']:
            names = ', '.join(
                f"{s['name']}({s['pct']:+.1f}%)" for s in result['leading_stocks']
            )
            notes.append(f"北向领涨: {names}")
        notes.append("净买卖额自2024.8.19起监管限制不再披露")
        result['note'] = ' | '.join(notes)

    except Exception as e:
        print(f"[north_bound] daily error: {e}")
        result['note'] = f'获取失败: {e}'

    # ── Realtime breadth (during trading hours only) ──
    try:
        live = _retry(ak.stock_hsgt_fund_flow_summary_em)
        if live is not None and not live.empty:
            north_live = live[live['资金方向'] == '北向']
            if not north_live.empty:
                result['up_count'] = int(north_live['上涨数'].sum())
                result['down_count'] = int(north_live['下跌数'].sum())
                result['flat_count'] = int(north_live['持平数'].sum())
                status_codes = north_live['交易状态'].values
                result['is_trading'] = any(int(s) == 1 for s in status_codes if s)
    except Exception as e:
        print(f"[north_bound] realtime breadth error: {e}")

    return result


def get_north_bound_realtime() -> dict:
    """Alias — same function, both call paths return the same dict now."""
    return get_north_bound_daily()
