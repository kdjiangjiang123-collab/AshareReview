"""Fetch A-share index data.
Uses Ashare (Sina/Tencent K-line) for daily data + Tencent realtime API for spot.
Both are free and require no API key.
"""

from datetime import datetime
from typing import Optional
import pandas as pd

from market_data.Ashare import get_price
from market_data.tencent_api import fetch_indices_realtime

# Ashare index codes (format: sh000001, sz399001)
INDEX_SYMBOLS = {
    "上证指数": "sh000001",
    "深证成指": "sz399001",
    "创业板指": "sz399006",
    "科创50":  "sh000688",
}


def get_index_daily(name: str, count: int = 20) -> Optional[dict]:
    """Get daily OHLCV for a single index using Ashare (Sina/Tencent).
    Returns dict with close, open, high, low, volume, amount, pct_change.
    """
    symbol = INDEX_SYMBOLS.get(name)
    if not symbol:
        return None

    try:
        df = get_price(symbol, frequency='1d', count=count)
        if df is None or df.empty:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        pct = 0.0
        if prev['close'] and prev['close'] != 0:
            pct = round((latest['close'] - prev['close']) / prev['close'] * 100, 2)

        recent_5 = []
        for idx, row in df.tail(5).iterrows():
            recent_5.append({
                'date': idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)[:10],
                'close': float(row['close']),
            })

        return {
            'name': name,
            'date': df.index[-1].strftime('%Y-%m-%d') if hasattr(df.index[-1], 'strftime') else str(df.index[-1])[:10],
            'open': float(latest['open']),
            'high': float(latest['high']),
            'low': float(latest['low']),
            'close': float(latest['close']),
            'volume': int(latest['volume']),
            'amount': float(latest['volume']) * float(latest['close']) / 1e8,  # 估算成交额(亿)
            'pct': pct,
            'recent_5': recent_5,
        }
    except Exception as e:
        print(f"[indices] Error fetching {name}: {e}")
        return None


def get_all_indices_daily(date: str = None) -> dict:
    """Get daily data for all 4 major indices."""
    result = {}
    for name in INDEX_SYMBOLS:
        data = get_index_daily(name)
        if data:
            result[name] = data
    return result


def get_index_realtime() -> dict:
    """Get real-time index data using Tencent API.
    Works during trading hours with ~3s delay.
    """
    return fetch_indices_realtime()
