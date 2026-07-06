"""CRUD operations for holdings table."""

from typing import Optional
from db.schema import get_connection


def add_holding(stock_code: str, stock_name: str, cost_price: float,
                quantity: int, buy_date: str, notes: str = "") -> int:
    """Add a holding. Returns the new holding ID."""
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO holdings (stock_code, stock_name, cost_price, quantity,
           buy_date, notes) VALUES (?, ?, ?, ?, ?, ?)""",
        (stock_code, stock_name, cost_price, quantity, buy_date, notes)
    )
    conn.commit()
    hid = cursor.lastrowid
    conn.close()
    return hid


def update_holding(holding_id: int, **kwargs) -> bool:
    """Update holding fields."""
    allowed = {'stock_code', 'stock_name', 'cost_price', 'quantity',
               'buy_date', 'current_price', 'pnl_pct', 'notes', 'is_active'}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [holding_id]

    conn = get_connection()
    conn.execute(f"UPDATE holdings SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return True


def delete_holding(holding_id: int) -> bool:
    """Delete a holding."""
    conn = get_connection()
    conn.execute("DELETE FROM holdings WHERE id = ?", (holding_id,))
    conn.commit()
    conn.close()
    return True


def get_holdings(active_only: bool = True) -> list[dict]:
    """Get holdings. By default returns only active positions."""
    conn = get_connection()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM holdings WHERE is_active = 1 ORDER BY buy_date DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM holdings ORDER BY buy_date DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_holding_by_id(holding_id: int) -> Optional[dict]:
    """Get a single holding."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM holdings WHERE id = ?", (holding_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def close_holding(holding_id: int) -> bool:
    """Mark a holding as closed."""
    return update_holding(holding_id, is_active=0)


def get_holding_by_code(stock_code: str) -> Optional[dict]:
    """Get active holding by stock code."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM holdings WHERE stock_code = ? AND is_active = 1",
        (stock_code,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def find_holding_by_code(stock_code: str) -> Optional[dict]:
    """Get any holding by stock code (active or inactive)."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM holdings WHERE stock_code = ? ORDER BY is_active DESC, id DESC LIMIT 1",
        (stock_code,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None
