"""CRUD for ai_analyses, market_snapshots, intraday_snapshots."""

import json
from typing import Optional
from db.schema import get_connection


# ─── AI Analyses ───────────────────────────────────────────────

def save_analysis(analysis_date: str, analysis_type: str, model_used: str,
                  analysis_data: dict) -> int:
    """Save an AI analysis result. Returns the new analysis ID."""
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO ai_analyses (analysis_date, analysis_type, model_used, analysis_json)
           VALUES (?, ?, ?, ?)""",
        (analysis_date, analysis_type, model_used, json.dumps(analysis_data, ensure_ascii=False))
    )
    conn.commit()
    aid = cursor.lastrowid
    conn.close()
    return aid


def get_analyses(analysis_date: Optional[str] = None,
                 analysis_type: Optional[str] = None,
                 limit: int = 50) -> list[dict]:
    """Query analyses."""
    conn = get_connection()
    conditions = []
    params = []
    if analysis_date:
        conditions.append("analysis_date = ?")
        params.append(analysis_date)
    if analysis_type:
        conditions.append("analysis_type = ?")
        params.append(analysis_type)
    where = " AND ".join(conditions) if conditions else "1=1"

    rows = conn.execute(
        f"SELECT * FROM ai_analyses WHERE {where} ORDER BY created_at DESC LIMIT ?",
        params + [limit]
    ).fetchall()
    conn.close()

    results = []
    for r in rows:
        d = dict(r)
        try:
            d['analysis_json'] = json.loads(d['analysis_json'])
        except (json.JSONDecodeError, TypeError):
            pass
        results.append(d)
    return results


def get_analysis_by_id(analysis_id: int) -> Optional[dict]:
    """Get a single analysis by ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM ai_analyses WHERE id = ?", (analysis_id,)).fetchone()
    conn.close()
    if row:
        d = dict(row)
        try:
            d['analysis_json'] = json.loads(d['analysis_json'])
        except (json.JSONDecodeError, TypeError):
            pass
        return d
    return None


def rate_analysis(analysis_id: int, rating: int) -> bool:
    """Rate an analysis (1-5)."""
    conn = get_connection()
    conn.execute("UPDATE ai_analyses SET user_rating = ? WHERE id = ?",
                 (rating, analysis_id))
    conn.commit()
    conn.close()
    return True


# ─── Market Snapshots ──────────────────────────────────────────

def save_market_snapshot(snapshot_date: str, data: dict) -> bool:
    """Save or replace a market snapshot."""
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO market_snapshots
           (snapshot_date, indices, breadth, limit_up, north_bound, sectors, raw_data)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (snapshot_date,
         json.dumps(data.get('indices', {}), ensure_ascii=False),
         json.dumps(data.get('breadth', {}), ensure_ascii=False),
         json.dumps(data.get('limit_up', {}), ensure_ascii=False),
         json.dumps(data.get('north_bound', {}), ensure_ascii=False),
         json.dumps(data.get('sectors', {}), ensure_ascii=False),
         json.dumps(data.get('raw', {}), ensure_ascii=False))
    )
    conn.commit()
    conn.close()
    return True


def get_market_snapshot(snapshot_date: str) -> Optional[dict]:
    """Get a market snapshot by date."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM market_snapshots WHERE snapshot_date = ?", (snapshot_date,)
    ).fetchone()
    conn.close()
    if not row:
        return None

    d = dict(row)
    for key in ['indices', 'breadth', 'limit_up', 'north_bound', 'sectors', 'raw_data']:
        try:
            d[key] = json.loads(d[key]) if d.get(key) else {}
        except (json.JSONDecodeError, TypeError):
            d[key] = {}
    return d


def get_recent_snapshots(days: int = 5) -> list[dict]:
    """Get the most recent N market snapshots."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM market_snapshots ORDER BY snapshot_date DESC LIMIT ?", (days,)
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        for key in ['indices', 'breadth', 'limit_up', 'north_bound', 'sectors']:
            try:
                d[key] = json.loads(d[key]) if d.get(key) else {}
            except (json.JSONDecodeError, TypeError):
                d[key] = {}
        results.append(d)
    return results


# ─── Intraday Snapshots ────────────────────────────────────────

def save_intraday_snapshot(data: dict) -> int:
    """Save an intraday snapshot."""
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO intraday_snapshots
           (snapshot_time, index_data, breadth_data, sector_data, north_flow, holdings_snapshot)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (data.get('snapshot_time', ''),
         json.dumps(data.get('index_data', {}), ensure_ascii=False),
         json.dumps(data.get('breadth_data', {}), ensure_ascii=False),
         json.dumps(data.get('sector_data', {}), ensure_ascii=False),
         json.dumps(data.get('north_flow', {}), ensure_ascii=False),
         json.dumps(data.get('holdings_snapshot', {}), ensure_ascii=False))
    )
    conn.commit()
    sid = cursor.lastrowid
    conn.close()
    return sid
