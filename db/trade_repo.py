"""CRUD operations for trades table."""

import json
from typing import Optional
from db.schema import get_connection


def add_trade(trade_date: str, trade_type: str, stock_code: str, stock_name: str,
              price: float, quantity: int, reason: str = "", logic: str = "",
              profit_loss: Optional[float] = None, profit_loss_pct: Optional[float] = None,
              tags: Optional[list] = None, review_notes: str = "") -> int:
    """Add a trade record. Returns the new trade ID."""
    amount = price * quantity
    tags_json = json.dumps(tags or [], ensure_ascii=False)

    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO trades (trade_date, trade_type, stock_code, stock_name,
           price, quantity, amount, reason, logic, profit_loss, profit_loss_pct,
           tags, review_notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (trade_date, trade_type, stock_code, stock_name, price, quantity,
         amount, reason, logic, profit_loss, profit_loss_pct, tags_json, review_notes)
    )
    conn.commit()
    trade_id = cursor.lastrowid
    conn.close()
    return trade_id


def update_trade(trade_id: int, **kwargs) -> bool:
    """Update trade fields by keyword arguments."""
    allowed = {'trade_date', 'trade_type', 'stock_code', 'stock_name', 'price',
               'quantity', 'amount', 'reason', 'logic', 'profit_loss',
               'profit_loss_pct', 'tags', 'review_notes'}
    updates = {k: v for k, v in kwargs.items() if k in allowed}

    if 'tags' in updates and isinstance(updates['tags'], list):
        updates['tags'] = json.dumps(updates['tags'], ensure_ascii=False)
    if 'quantity' in updates and 'price' in kwargs:
        updates['amount'] = kwargs['price'] * kwargs['quantity']

    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [trade_id]

    conn = get_connection()
    conn.execute(
        f"UPDATE trades SET {set_clause}, updated_at = datetime('now','localtime') WHERE id = ?",
        values
    )
    conn.commit()
    conn.close()
    return True


def delete_trade(trade_id: int) -> bool:
    """Delete a trade record."""
    conn = get_connection()
    conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    conn.commit()
    conn.close()
    return True


def get_trades(date: Optional[str] = None, trade_type: Optional[str] = None,
               stock_code: Optional[str] = None, limit: int = 200) -> list[dict]:
    """Query trades with optional filters."""
    conn = get_connection()
    conditions = []
    params = []

    if date:
        conditions.append("trade_date = ?")
        params.append(date)
    if trade_type:
        conditions.append("trade_type = ?")
        params.append(trade_type)
    if stock_code:
        conditions.append("stock_code = ?")
        params.append(stock_code)

    where = " AND ".join(conditions) if conditions else "1=1"
    rows = conn.execute(
        f"SELECT * FROM trades WHERE {where} ORDER BY trade_date DESC, id DESC LIMIT ?",
        params + [limit]
    ).fetchall()

    trades = [dict(r) for r in rows]
    for t in trades:
        if t.get('tags'):
            try:
                t['tags'] = json.loads(t['tags'])
            except json.JSONDecodeError:
                t['tags'] = []
    conn.close()
    return trades


def get_trade_by_id(trade_id: int) -> Optional[dict]:
    """Get a single trade by ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    conn.close()
    if row:
        trade = dict(row)
        if trade.get('tags'):
            try:
                trade['tags'] = json.loads(trade['tags'])
            except json.JSONDecodeError:
                trade['tags'] = []
        return trade
    return None


def get_trade_stats(start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """Get trading statistics for a date range."""
    conn = get_connection()
    conditions = []
    params = []

    if start_date:
        conditions.append("trade_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("trade_date <= ?")
        params.append(end_date)

    where = " AND ".join(conditions) if conditions else "1=1"

    # Overall stats
    total = conn.execute(
        f"SELECT COUNT(*) as cnt FROM trades WHERE {where}", params
    ).fetchone()['cnt']

    sells = conn.execute(
        f"SELECT profit_loss, profit_loss_pct FROM trades WHERE {where} AND trade_type='sell' AND profit_loss IS NOT NULL",
        params
    ).fetchall()

    wins = sum(1 for s in sells if s['profit_loss'] and s['profit_loss'] > 0)
    total_sells = len(sells)
    win_rate = (wins / total_sells * 100) if total_sells > 0 else 0
    total_pnl = sum(s['profit_loss'] for s in sells if s['profit_loss']) if sells else 0
    avg_pnl = (total_pnl / total_sells) if total_sells > 0 else 0

    # Monthly stats
    monthly = conn.execute(
        f"""SELECT substr(trade_date,1,7) as month,
                   COUNT(*) as trades,
                   SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins,
                   COUNT(CASE WHEN trade_type='sell' AND profit_loss IS NOT NULL THEN 1 END) as sell_count,
                   SUM(profit_loss) as total_pnl
            FROM trades WHERE {where}
            GROUP BY month ORDER BY month"""
        , params
    ).fetchall()

    conn.close()

    return {
        'total_trades': total,
        'total_sells': total_sells,
        'wins': wins,
        'win_rate': round(win_rate, 1),
        'total_pnl': round(total_pnl, 2) if total_pnl else 0,
        'avg_pnl': round(avg_pnl, 2),
        'monthly': [dict(m) for m in monthly]
    }
