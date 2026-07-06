"""Fetch market breadth data: up/down/flat counts, limit-up/down counts."""

import time
from typing import Optional
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


def get_market_breadth() -> dict:
    """Get market breadth from A-share spot data.
    Returns up/down/flat counts, total stocks, up/down ratio.
    """
    try:
        df = _retry(ak.stock_zh_a_spot_em)
        if df is None or df.empty:
            return _empty_breadth()

        pct_col = None
        for col in ['涨跌幅', '涨跌额']:
            if col in df.columns:
                pct_col = col
                break

        if pct_col is None:
            # Try to find by pattern
            for col in df.columns:
                if '涨跌' in col:
                    pct_col = col
                    break

        if pct_col is None:
            return _empty_breadth()

        pct_series = pd.to_numeric(df[pct_col], errors='coerce')
        up_count = int((pct_series > 0).sum())
        down_count = int((pct_series < 0).sum())
        flat_count = int((pct_series == 0).sum())

        # Get amount column
        amount_col = None
        for col in ['成交额', '成交金额']:
            if col in df.columns:
                amount_col = col
                break

        total_amount = 0
        if amount_col:
            total_amount = pd.to_numeric(df[amount_col], errors='coerce').sum() / 1e8
            total_amount = round(total_amount, 2)

        return {
            'up_count': up_count,
            'down_count': down_count,
            'flat_count': flat_count,
            'total_stocks': up_count + down_count + flat_count,
            'up_pct': round(up_count / (up_count + down_count + flat_count) * 100, 1) if (up_count + down_count + flat_count) > 0 else 0,
            'down_pct': round(down_count / (up_count + down_count + flat_count) * 100, 1) if (up_count + down_count + flat_count) > 0 else 0,
            'total_amount_yi': total_amount,
        }
    except Exception as e:
        print(f"[breadth] Error: {e}")
        return _empty_breadth()


def _empty_breadth() -> dict:
    return {
        'up_count': 0, 'down_count': 0, 'flat_count': 0,
        'total_stocks': 0, 'up_pct': 0, 'down_pct': 0, 'total_amount_yi': 0
    }
