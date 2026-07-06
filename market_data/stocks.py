"""Fetch individual stock data.
Uses Ashare (Sina/Tencent K-line) + Tencent realtime API.
"""

from typing import Optional
import pandas as pd
from market_data.Ashare import get_price
from market_data.tencent_api import fetch_stocks_realtime, search_stock_tencent, prefix


def normalize_code(raw: str) -> str:
    """统一规范化股票代码为6位纯数字。

    处理腾讯搜索返回的 sz/sh/bj 前缀，以及用户手动输入的各种格式。
    返回6位纯数字代码；无效格式返回空字符串。
    """
    if not raw:
        return ""
    code = raw.strip()
    # 去掉交易所前缀
    if len(code) >= 8 and code[:2] in ('sh', 'sz', 'bj', 'SH', 'SZ', 'BJ'):
        code = code[2:]
    # 再去一次（防止 szsh600519 这种双重前缀）
    if len(code) >= 8 and code[:2] in ('sh', 'sz', 'bj', 'SH', 'SZ', 'BJ'):
        code = code[2:]
    # 校验：必须是6位数字
    if code.isdigit() and len(code) == 6:
        return code
    return ""


def get_stock_daily(stock_code: str, count: int = 20) -> Optional[dict]:
    """Get daily K-line data for a stock using Ashare."""
    try:
        full_code = prefix(stock_code)
        df = get_price(full_code, frequency='1d', count=count)
        if df is None or df.empty:
            return None

        latest = df.iloc[-1]
        closes = df['close'].tolist()

        return {
            'code': stock_code,
            'date': df.index[-1].strftime('%Y-%m-%d') if hasattr(df.index[-1], 'strftime') else str(df.index[-1])[:10],
            'open': float(latest['open']),
            'high': float(latest['high']),
            'low': float(latest['low']),
            'close': float(latest['close']),
            'volume': int(latest['volume']),
            'pct': round((closes[-1] - closes[-2]) / closes[-2] * 100, 2) if len(closes) > 1 and closes[-2] else 0,
            'recent_closes': [float(c) for c in closes],
        }
    except Exception as e:
        print(f"[stocks] Error fetching daily {stock_code}: {e}")
        return None


def get_stock_realtime(stock_code: str) -> Optional[dict]:
    """Get real-time quote for a single stock from Tencent."""
    data = fetch_stocks_realtime([stock_code])
    if stock_code in data:
        d = data[stock_code]
        return {
            'code': stock_code,
            'name': d['name'],
            'price': d['price'],
            'pct': d['pct'],
            'high': d['high'],
            'low': d['low'],
            'open': d['open'],
            'volume': d['volume'],
            'amount': d['amount'],
            'prev_close': d['prev_close'],
        }
    return None


def get_holdings_realtime(holdings: list[dict]) -> list[dict]:
    """Update holdings with real-time prices from Tencent."""
    if not holdings:
        return []

    codes = [h['stock_code'] for h in holdings]
    realtime = fetch_stocks_realtime(codes)

    for h in holdings:
        code = h['stock_code']
        if code in realtime:
            r = realtime[code]
            current_price = r['price']
            cost = h.get('cost_price', 0)
            h['current_price'] = current_price
            h['today_pct'] = r['pct']
            if cost and cost > 0:
                h['pnl_pct'] = round((current_price - cost) / cost * 100, 2)

    return holdings


def search_stock(keyword: str) -> list[dict]:
    """Search stock by keyword (code or name) using Tencent smartbox.
    Returns codes already normalized (6-digit)."""
    results = search_stock_tencent(keyword)
    # Normalize codes in results
    cleaned = []
    for r in results:
        normalized = normalize_code(r['code'])
        if normalized:
            r['code'] = normalized
            cleaned.append(r)
    return cleaned  # only return results with valid 6-digit codes


def get_stock_kline_data(stock_code: str, count: int = 30) -> Optional[pd.DataFrame]:
    """Get daily K-line DataFrame for candlestick charting.

    Args:
        stock_code: 6-digit code like '000001'
        count: number of trading days to fetch

    Returns:
        DataFrame with columns [open, high, low, close, volume]
        indexed by date, or None on failure.
    """
    try:
        full_code = prefix(stock_code)
        df = get_price(full_code, frequency='1d', count=count)
        if df is None or df.empty:
            return None
        # Ensure standard columns
        df = df[['open', 'high', 'low', 'close', 'volume']].copy()
        df[['open', 'high', 'low', 'close', 'volume']] = \
            df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        return df
    except Exception as e:
        print(f"[stocks] Error fetching kline {stock_code}: {e}")
        return None
