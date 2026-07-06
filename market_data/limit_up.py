"""Fetch limit-up / limit-down /炸板 pool data."""

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


def get_limit_up_pool(date: str = None) -> dict:
    """Get limit-up pool data for a specific date.
    Returns total count, structure by连板数, top stocks.
    """
    if date is None:
        date = _latest_trade_date()

    result = {
        'zt_count': 0,
        'dt_count': 0,
        'zb_count': 0,
        'zt_structure': {},
        'max_lianban': 0,
        'hot_concepts': [],
        'top_zt_stocks': [],
    }

    try:
        # Limit-up pool
        df_zt = _retry(ak.stock_zt_pool_em, date=date)
        if df_zt is not None and not df_zt.empty:
            result['zt_count'] = len(df_zt)

            # Analyze连板 structure
            if '连板数' in df_zt.columns:
                lb_counts = df_zt['连板数'].value_counts().to_dict()
                result['zt_structure'] = {str(k): int(v) for k, v in lb_counts.items()}
                result['max_lianban'] = int(df_zt['连板数'].max()) if not df_zt['连板数'].empty else 0

            # Top涨停 stocks (by封单金额 if available)
            top_cols = ['代码', '名称', '涨停时间', '连板数', '封单金额', '所属行业']
            available_cols = [c for c in top_cols if c in df_zt.columns]
            top = df_zt[available_cols].head(20).fillna('').to_dict('records')
            result['top_zt_stocks'] = top

            # Hot concepts from涨停 stocks
            if '所属行业' in df_zt.columns:
                concept_counts = df_zt['所属行业'].value_counts().head(8).to_dict()
                result['hot_concepts'] = [{'name': k, 'count': int(v)} for k, v in concept_counts.items()]

    except Exception as e:
        print(f"[limit_up] Error fetching涨停池: {e}")

    # Limit-down pool
    try:
        df_dt = _retry(ak.stock_zt_pool_dtgc_em, date=date)
        if df_dt is not None and not df_dt.empty:
            result['dt_count'] = len(df_dt)
    except Exception as e:
        print(f"[limit_up] Error fetching跌停池: {e}")

    # 炸板 pool
    try:
        df_zb = _retry(ak.stock_zt_pool_zbgc_em, date=date)
        if df_zb is not None and not df_zb.empty:
            result['zb_count'] = len(df_zb)
    except Exception as e:
        print(f"[limit_up] Error fetching炸板池: {e}")

    return result


def get_limit_up_realtime() -> dict:
    """Get real-time涨停 data using the strong stock pool."""
    result = {
        'zt_count': 0,
        'dt_count': 0,
        'hot_concepts': [],
    }
    try:
        df = _retry(ak.stock_zt_pool_strong_em, date=datetime.now().strftime('%Y%m%d'))
        if df is not None and not df.empty:
            result['zt_count'] = len(df)
            if '所属行业' in df.columns:
                concept_counts = df['所属行业'].value_counts().head(8).to_dict()
                result['hot_concepts'] = [{'name': k, 'count': int(v)} for k, v in concept_counts.items()]
    except Exception as e:
        print(f"[limit_up] Error fetching realtime: {e}")

    return result


def _latest_trade_date() -> str:
    """Get latest trading date."""
    now = datetime.now()
    if now.hour < 15 or (now.hour == 15 and now.minute < 30):
        # Before market close, use previous day
        return (now - pd.Timedelta(days=1)).strftime('%Y%m%d')
    return now.strftime('%Y%m%d')
