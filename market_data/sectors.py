"""Fetch sector/industry ranking data."""

import time
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


def get_sector_ranking(top_n: int = 10) -> dict:
    """Get industry board ranking by涨跌幅. Returns top and bottom sectors."""
    result = {
        'leading_sectors': [],
        'lagging_sectors': [],
    }

    try:
        df = _retry(ak.stock_board_industry_name_em)
        if df is None or df.empty:
            return result

        # Determine column names
        pct_col = None
        for col in ['涨跌幅', '板块涨跌幅']:
            if col in df.columns:
                pct_col = col
                break

        name_col = None
        for col in ['板块名称', '行业名称', '名称']:
            if col in df.columns:
                name_col = col
                break

        if pct_col is None or name_col is None:
            return result

        df[pct_col] = pd.to_numeric(df[pct_col], errors='coerce')
        df_sorted = df.sort_values(pct_col, ascending=False)

        # Leading sectors
        leading = df_sorted.head(top_n)
        for _, row in leading.iterrows():
            result['leading_sectors'].append({
                'name': str(row.get(name_col, '')),
                'pct': round(float(row[pct_col]), 2),
            })

        # Lagging sectors
        lagging = df_sorted.tail(top_n).sort_values(pct_col, ascending=True)
        for _, row in lagging.iterrows():
            result['lagging_sectors'].append({
                'name': str(row.get(name_col, '')),
                'pct': round(float(row[pct_col]), 2),
            })

    except Exception as e:
        print(f"[sectors] Error: {e}")

    return result


def get_concept_board_ranking(top_n: int = 10) -> dict:
    """Get concept board (概念板块) ranking."""
    result = {
        'leading_concepts': [],
        'lagging_concepts': [],
    }

    try:
        df = _retry(ak.stock_board_concept_name_em)
        if df is None or df.empty:
            return result

        pct_col = None
        for col in ['涨跌幅', '板块涨跌幅']:
            if col in df.columns:
                pct_col = col
                break

        name_col = None
        for col in ['板块名称', '概念名称', '名称']:
            if col in df.columns:
                name_col = col
                break

        if pct_col is None or name_col is None:
            return result

        df[pct_col] = pd.to_numeric(df[pct_col], errors='coerce')
        df_sorted = df.sort_values(pct_col, ascending=False)

        leading = df_sorted.head(top_n)
        for _, row in leading.iterrows():
            result['leading_concepts'].append({
                'name': str(row.get(name_col, '')),
                'pct': round(float(row[pct_col]), 2),
            })

        lagging = df_sorted.tail(top_n).sort_values(pct_col, ascending=True)
        for _, row in lagging.iterrows():
            result['lagging_concepts'].append({
                'name': str(row.get(name_col, '')),
                'pct': round(float(row[pct_col]), 2),
            })

    except Exception as e:
        print(f"[sectors] Error fetching concepts: {e}")

    return result
