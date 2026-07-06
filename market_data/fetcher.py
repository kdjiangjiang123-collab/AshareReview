"""Unified market data fetcher — data from Ashare + Tencent + akshare."""

from datetime import datetime
from typing import Optional

from market_data import indices, breadth, limit_up, north_bound, sectors, stocks
from db.holding_repo import get_holdings
from db.analysis_repo import save_market_snapshot, save_intraday_snapshot


def fetch_intraday_data() -> dict:
    """Fetch all data needed for intraday analysis.
    Real-time data primarily from Tencent API (fast & reliable).
    Falls back gracefully if akshare is unavailable.
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    data = {
        'snapshot_time': now,
        'index_data': {},
        'breadth_data': {},
        'sector_data': {},
        'north_flow': {},
        'holdings_snapshot': [],
    }

    # Index realtime (Tencent - reliable)
    try:
        data['index_data'] = indices.get_index_realtime()
    except Exception as e:
        print(f"[fetcher] Index realtime failed: {e}")

    # Breadth (akshare - may fail)
    try:
        data['breadth_data'] = breadth.get_market_breadth()
    except Exception as e:
        print(f"[fetcher] Breadth failed: {e}")
        data['breadth_data'] = breadth._empty_breadth()

    # Sectors (akshare - may fail)
    try:
        data['sector_data'] = sectors.get_sector_ranking(top_n=10)
        data['sector_data'].update(sectors.get_concept_board_ranking(top_n=6))
    except Exception as e:
        print(f"[fetcher] Sectors failed: {e}")

    # North bound
    try:
        data['north_flow'] = north_bound.get_north_bound_realtime()
    except Exception as e:
        print(f"[fetcher] North bound failed: {e}")

    # Limit up realtime
    try:
        lu_data = limit_up.get_limit_up_realtime()
        data['breadth_data']['zt_count_realtime'] = lu_data.get('zt_count', 0)
        data['breadth_data']['hot_concepts_rt'] = lu_data.get('hot_concepts', [])
    except Exception as e:
        print(f"[fetcher] Limit-up realtime failed: {e}")

    # Holdings realtime (Tencent - reliable)
    try:
        holdings_list = get_holdings(active_only=True)
        if holdings_list:
            data['holdings_snapshot'] = stocks.get_holdings_realtime(holdings_list)
    except Exception as e:
        print(f"[fetcher] Holdings realtime failed: {e}")

    return data


def fetch_aftermarket_data(date: Optional[str] = None) -> dict:
    """Fetch complete after-market data for daily review.
    Index daily from Ashare, others from akshare with fallback.
    """
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    data = {
        'date': date,
        'indices': {},
        'breadth': {},
        'limit_up': {},
        'north_bound': {},
        'sectors': {},
    }

    # Index daily data (Ashare - reliable)
    try:
        data['indices'] = indices.get_all_indices_daily(date)
    except Exception as e:
        print(f"[fetcher] Index daily failed: {e}")
        # Fallback to realtime
        try:
            rt = indices.get_index_realtime()
            if rt:
                data['indices'] = rt
        except Exception:
            pass

    # Market breadth (akshare)
    try:
        data['breadth'] = breadth.get_market_breadth()
    except Exception as e:
        print(f"[fetcher] Breadth failed: {e}")

    # Limit-up/down pools (akshare)
    try:
        date_compact = date.replace('-', '')
        data['limit_up'] = limit_up.get_limit_up_pool(date_compact)
    except Exception as e:
        print(f"[fetcher] Limit-up failed: {e}")

    # North-bound daily
    try:
        data['north_bound'] = north_bound.get_north_bound_daily()
    except Exception as e:
        print(f"[fetcher] North bound failed: {e}")

    # Sector rankings (akshare)
    try:
        data['sectors'] = sectors.get_sector_ranking(top_n=10)
        data['sectors'].update(sectors.get_concept_board_ranking(top_n=6))
    except Exception as e:
        print(f"[fetcher] Sectors failed: {e}")

    return data


def save_aftermarket_snapshot(date: str, data: dict) -> bool:
    """Persist after-market data to DB."""
    return save_market_snapshot(date, data)


def save_intraday_snapshot_to_db(data: dict) -> int:
    """Persist intraday data to DB."""
    return save_intraday_snapshot(data)
