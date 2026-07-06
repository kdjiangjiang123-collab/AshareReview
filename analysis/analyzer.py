"""Analysis orchestrator — ties together data fetching, formatting, and LLM calls."""

from datetime import datetime
from typing import Optional

from analysis.llm_client import get_llm_client
from analysis.data_formatter import format_market_data
from analysis.prompts_intraday import INTRODAY_SYSTEM_PROMPT
from analysis.prompts_aftermarket import (
    MACRO_SYSTEM_PROMPT,
    MICRO_SYSTEM_PROMPT,
    SCENARIO_SYSTEM_PROMPT,
)
from market_data.fetcher import fetch_intraday_data, fetch_aftermarket_data
from db.holding_repo import get_holdings
from db.trade_repo import get_trades
from config.settings import (
    INTRODAY_MODEL, AFTERMARKET_MACRO_MODEL,
    AFTERMARKET_MICRO_MODEL, AFTERMARKET_SCENARIO_MODEL,
)


def run_intraday_analysis() -> dict:
    """Run a complete intraday analysis.
    1. Fetch real-time market data
    2. Format data for LLM
    3. Send to DeepSeek for quick analysis
    4. Return results

    Returns:
        dict with keys: snapshot_time, index_data, market_text, analysis_text
    """
    llm = get_llm_client()

    # Fetch data (includes fresh realtime prices for holdings)
    data = fetch_intraday_data()

    # Use holdings snapshot with realtime prices from fetcher (already populated by fetch_intraday_data)
    holdings = data.get('holdings_snapshot', [])

    # Format for LLM
    user_message = format_market_data(data, holdings=holdings)

    # Quick analysis (returns natural language, not JSON)
    analysis_text = llm.quick_analysis(INTRODAY_SYSTEM_PROMPT, user_message)

    return {
        'snapshot_time': data.get('snapshot_time', ''),
        'index_data': data.get('index_data', {}),
        'breadth_data': data.get('breadth_data', {}),
        'sector_data': data.get('sector_data', {}),
        'holdings_snapshot': data.get('holdings_snapshot', []),
        'market_text': user_message,
        'analysis_text': analysis_text,
    }


def run_aftermarket_analysis(date: Optional[str] = None,
                              include_macro: bool = True,
                              include_micro: bool = True,
                              include_scenario: bool = True) -> dict:
    """Run complete after-market analysis.
    1. Fetch daily market data
    2. Get user's trades and holdings
    3. Run selected analysis layers sequentially
    4. Return combined results

    Args:
        date: Trade date (YYYY-MM-DD). Defaults to today.
        include_macro: Run macro layer.
        include_micro: Run micro layer.
        include_scenario: Run scenario layer.

    Returns:
        dict with keys: date, data, holdings, trades, macro, micro, scenario
    """
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    llm = get_llm_client()

    # Fetch data
    data = fetch_aftermarket_data(date)
    holdings = get_holdings(active_only=True)
    trades = get_trades(date=date)

    # Format for LLM
    user_message = format_market_data(data, holdings=holdings, trades=trades)

    # Get today's trades for trade review in micro analysis
    # Already included in user_message formatting

    results = {
        'date': date,
        'data': data,
        'holdings': holdings,
        'trades': trades,
        'macro': None,
        'micro': None,
        'scenario': None,
    }

    # Layer 1: Macro
    if include_macro:
        try:
            results['macro'] = llm.deep_analysis(
                MACRO_SYSTEM_PROMPT, user_message, use_reasoner=False
            )
        except Exception as e:
            results['macro'] = {'error': str(e)}

    # Layer 2: Micro
    if include_micro:
        try:
            results['micro'] = llm.deep_analysis(
                MICRO_SYSTEM_PROMPT, user_message, use_reasoner=False
            )
        except Exception as e:
            results['micro'] = {'error': str(e)}

    # Layer 3: Scenario (uses reasoner model for depth)
    if include_scenario:
        try:
            results['scenario'] = llm.deep_analysis(
                SCENARIO_SYSTEM_PROMPT, user_message, use_reasoner=True
            )
        except Exception as e:
            results['scenario'] = {'error': str(e)}

    return results
