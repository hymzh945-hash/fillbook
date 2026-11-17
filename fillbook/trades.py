"""FIFO round-trip reconstruction: fills in, closed trades out."""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

EPS = 1e-9


def match(fills: pd.DataFrame) -> pd.DataFrame:
    """Match fills FIFO per symbol, supporting both long and short positions.

    Every exit produces one closed-trade row, so a single entry split across
    several exits shows up as several round trips — which is what actually
    happened on the exchange.
    """
    queues: Dict[str, List[Dict]] = {}
    trades: List[Dict] = []

    for _, fill in fills.sort_values("ts", kind="stable").iterrows():
        symbol = fill["symbol"]
        side = fill["side"]
        qty = float(fill["qty"])
        price = float(fill["price"])
        fee = float(fill.get("fee", 0.0))
        fee_per_unit = fee / qty if qty else 0.0
        book = queues.setdefault(symbol, [])

        # does this fill reduce an existing exposure or open a new one?
        if book:
            direction = book[0]["direction"]
            reduces = (direction == "long" and side == "sell") or \
                      (direction == "short" and side == "buy")
        else:
            reduces = False

        if not reduces:
            book.append({"direction": "long" if side == "buy" else "short",
                         "qty": qty, "price": price, "ts": fill["ts"], "fee_per_unit": fee_per_unit})
            continue

        remaining = qty
        while remaining > EPS and book:
            lot = book[0]
            take = min(remaining, lot["qty"])
            sign = 1.0 if lot["direction"] == "long" else -1.0
            gross = (price - lot["price"]) * take * sign
            fees = lot["fee_per_unit"] * take + fee_per_unit * take
            net = gross - fees
            notional = lot["price"] * take
            trades.append({
                "symbol": symbol,
                "direction": lot["direction"],
                "entry_ts": lot["ts"],
                "exit_ts": fill["ts"],
                "qty": round(take, 8),
                "entry": round(lot["price"], 8),
                "exit": round(price, 8),
                "gross": round(gross, 8),
                "fees": round(fees, 8),
                "net": round(net, 8),
                "return_pct": round(net / notional, 8) if notional else 0.0,
                "hold_minutes": round((fill["ts"] - lot["ts"]).total_seconds() / 60, 1),
            })
            lot["qty"] -= take
            remaining -= take
            if lot["qty"] <= EPS:
                book.pop(0)

        # an exit larger than the position flips direction for the excess
        if remaining > EPS:
            book.append({"direction": "long" if side == "buy" else "short",
                         "qty": remaining, "price": price, "ts": fill["ts"],
                         "fee_per_unit": fee_per_unit})

    if not trades:
        return pd.DataFrame(columns=["symbol", "direction", "entry_ts", "exit_ts", "qty",
                                     "entry", "exit", "gross", "fees", "net",
                                     "return_pct", "hold_minutes"])

    frame = pd.DataFrame(trades).sort_values("exit_ts", kind="stable").reset_index(drop=True)
    return frame


def open_exposure(fills: pd.DataFrame) -> pd.DataFrame:
    """What is still open at the end of the file — so the summary can flag it."""
    queues: Dict[str, List[Dict]] = {}
    for _, fill in fills.sort_values("ts", kind="stable").iterrows():
        symbol = fill["symbol"]
        side = fill["side"]
        qty = float(fill["qty"])
        book = queues.setdefault(symbol, [])
        if book:
            direction = book[0]["direction"]
            reduces = (direction == "long" and side == "sell") or \
                      (direction == "short" and side == "buy")
        else:
            reduces = False
        if not reduces:
            book.append({"direction": "long" if side == "buy" else "short",
                         "qty": qty, "price": float(fill["price"])})
            continue
        remaining = qty
        while remaining > EPS and book:
            lot = book[0]
            take = min(remaining, lot["qty"])
            lot["qty"] -= take
            remaining -= take
            if lot["qty"] <= EPS:
                book.pop(0)
        if remaining > EPS:
            book.append({"direction": "long" if side == "buy" else "short",
                         "qty": remaining, "price": float(fill["price"])})

    rows = [{"symbol": s, "direction": lot["direction"], "qty": round(lot["qty"], 8),
             "entry": lot["price"]} for s, book in queues.items() for lot in book]
    return pd.DataFrame(rows)
