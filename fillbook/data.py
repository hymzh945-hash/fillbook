"""Normalise exchange fill exports (OKX / Binance / generic CSV) into one schema."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

TIME = {"ts", "time", "timestamp", "trade_time", "fill_time", "created_at", "date",
        "成交时间", "时间", "交易时间"}
SIDE = {"side", "direction", "bs", "buy_sell", "买卖", "方向", "交易方向"}
QTY = {"qty", "size", "amount", "quantity", "filled", "executed_qty", "base_volume",
       "成交量", "数量", "成交数量"}
PRICE = {"price", "avg_price", "fill_price", "trade_price", "成交均价", "价格", "成交价格"}
FEE = {"fee", "fees", "commission", "fee_amount", "手续费", "手续费金额"}
SYMBOL = {"symbol", "instrument", "pair", "market", "contract", "币种", "交易对", "合约"}
TOTAL = {"total", "notional", "quote_volume", "成交额", "成交金额"}

BUY = {"buy", "b", "long", "买", "买入", "做多", "bid"}
SELL = {"sell", "s", "short", "卖", "卖出", "做空", "ask"}


def _pick(columns, aliases) -> str | None:
    lowered = {str(c).strip().lower(): c for c in columns}
    for alias in aliases:
        if alias in lowered:
            return lowered[alias]
    return None


def _side(value) -> str:
    text = str(value).strip().lower()
    if text in BUY or text.startswith("buy"):
        return "buy"
    if text in SELL or text.startswith("sell"):
        return "sell"
    return ""


def load_fills(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in {".json", ".jsonl"}:
        raw = pd.read_json(path, lines=path.suffix.lower() == ".jsonl")
    else:
        raw = pd.read_csv(path, sep=None, engine="python")
    raw.columns = [str(c).strip() for c in raw.columns]

    time_col = _pick(raw.columns, TIME)
    side_col = _pick(raw.columns, SIDE)
    qty_col = _pick(raw.columns, QTY)
    price_col = _pick(raw.columns, PRICE)
    if not side_col or not qty_col:
        raise ValueError("could not find side/qty columns — expected an exchange fill export")

    missing = [n for n, col in (("timestamp", time_col), ("price", price_col)) if col is None]
    if missing:
        raise ValueError(f"missing columns: {', '.join(missing)}")

    frame = pd.DataFrame({
        "ts": pd.to_datetime(raw[time_col], errors="coerce", utc=True),
        "side": raw[side_col].map(_side),
        "qty": pd.to_numeric(raw[qty_col], errors="coerce").abs(),
        "price": pd.to_numeric(raw[price_col], errors="coerce").abs(),
    })
    fee_col = _pick(raw.columns, FEE)
    frame["fee"] = pd.to_numeric(raw[fee_col], errors="coerce").abs() if fee_col else 0.0
    symbol_col = _pick(raw.columns, SYMBOL)
    frame["symbol"] = raw[symbol_col].astype(str).str.upper().str.replace("-", "/", regex=False) \
        if symbol_col else "UNKNOWN"
    total_col = _pick(raw.columns, TOTAL)
    if total_col:
        notional = pd.to_numeric(raw[total_col], errors="coerce").abs()
        frame["notional"] = notional.where(notional > 0, frame["qty"] * frame["price"])
    else:
        frame["notional"] = frame["qty"] * frame["price"]

    frame = frame.dropna(subset=["ts", "qty", "price"])
    frame = frame[(frame["qty"] > 0) & (frame["price"] > 0) & (frame["side"] != "")]
    frame = frame.sort_values("ts", kind="stable").reset_index(drop=True)
    frame["fee"] = frame["fee"].fillna(0.0)
    return frame[["ts", "symbol", "side", "qty", "price", "notional", "fee"]]


def synthetic_fills(round_trips: int = 40, seed: int = 5) -> pd.DataFrame:
    """Deterministic OKX-style fills: mostly small wins, a few big losses."""
    import numpy as np

    rng = np.random.default_rng(seed)
    rows = []
    ts = pd.Timestamp("2026-01-05 01:00:00", tz="UTC")
    price = 42000.0
    for i in range(round_trips):
        symbol = "BTC/USDT" if i % 3 else "ETH/USDT"
        base = 42000.0 if symbol == "BTC/USDT" else 2300.0
        qty = round((0.01 if symbol == "BTC/USDT" else 0.2) * rng.uniform(0.6, 1.4), 4)
        side = "buy" if rng.random() < 0.7 else "sell"   # mostly longs
        entry = base * rng.uniform(0.97, 1.03)
        hold = int(rng.integers(20, 600))
        drift = rng.normal(0.0018 if side == "buy" else 0.0006, 0.006)
        exit_price = entry * (1 + drift)
        fee_rate = 0.0005
        rows.append({"ts": ts, "symbol": symbol, "side": side, "qty": qty,
                     "price": round(entry, 2), "fee": round(entry * qty * fee_rate, 4)})
        ts = ts + pd.Timedelta(minutes=hold)
        rows.append({"ts": ts, "symbol": symbol, "side": "sell" if side == "buy" else "buy",
                     "qty": qty, "price": round(exit_price, 2),
                     "fee": round(exit_price * qty * fee_rate, 4)})
        ts = ts + pd.Timedelta(minutes=int(rng.integers(30, 2000)))
        price = exit_price
    frame = pd.DataFrame(rows)
    frame["notional"] = frame["qty"] * frame["price"]
    frame["symbol"] = frame["symbol"]
    return frame[["ts", "symbol", "side", "qty", "price", "notional", "fee"]]
