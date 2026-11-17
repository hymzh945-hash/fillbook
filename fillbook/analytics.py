"""Turn closed trades into the numbers a trader actually argues with."""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


def summary(trades: pd.DataFrame) -> Dict:
    if trades.empty:
        return {"trades": 0, "net": 0.0, "win_rate": 0.0, "profit_factor": 0.0,
                "fees": 0.0, "gross": 0.0, "fee_drag": 0.0, "avg_win": 0.0,
                "avg_loss": 0.0, "payoff": 0.0, "expectancy": 0.0, "best": 0.0,
                "worst": 0.0, "max_consec_losses": 0, "avg_hold_minutes": 0.0,
                "turnover": 0.0}

    net = trades["net"]
    wins = net[net > 0]
    losses = net[net < 0]
    gross_win = float(wins.sum())
    gross_loss = float(abs(losses.sum()))

    consec = max(_consecutive_losses(net.tolist()), 0)
    gross = float(trades["gross"].sum())
    fees = float(trades["fees"].sum())

    return {
        "trades": int(len(trades)),
        "net": round(float(net.sum()), 4),
        "gross": round(gross, 4),
        "fees": round(fees, 4),
        "fee_drag": round(abs(fees) / abs(gross), 4) if gross else 0.0,
        "win_rate": round(float((net > 0).mean()), 4),
        "profit_factor": round(gross_win / gross_loss, 4) if gross_loss else float("inf"),
        "avg_win": round(float(wins.mean()), 4) if len(wins) else 0.0,
        "avg_loss": round(float(losses.mean()), 4) if len(losses) else 0.0,
        "payoff": round(float(wins.mean() / abs(losses.mean())), 4)
        if len(wins) and len(losses) else 0.0,
        "expectancy": round(float(net.mean()), 4),
        "best": round(float(net.max()), 4),
        "worst": round(float(net.min()), 4),
        "max_consec_losses": consec,
        "avg_hold_minutes": round(float(trades["hold_minutes"].mean()), 1),
        "turnover": round(float(trades["entry"].mul(trades["qty"]).sum()), 2),
    }


def _consecutive_losses(values: List[float]) -> int:
    longest = run = 0
    for value in values:
        if value < 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return longest


def r_multiples(trades: pd.DataFrame, unit: Optional[float] = None) -> pd.DataFrame:
    """Express each trade in units of your average loss — the only sizing metric that matters."""
    if trades.empty:
        return trades.assign(r=[])
    if unit:
        risk = float(unit)
    else:
        losers = trades.loc[trades["net"] < 0, "net"]
        risk = abs(float(losers.mean())) if len(losers) else 0.0
    if not risk:
        return trades.assign(r=np.nan)
    return trades.assign(r=(trades["net"] / risk).round(3))


def r_distribution(trades: pd.DataFrame) -> pd.DataFrame:
    r = r_multiples(trades)
    if r.empty or "r" not in r:
        return pd.DataFrame(columns=["bucket", "count", "net"])
    buckets = pd.cut(r["r"], bins=[-np.inf, -2, -1, 0, 1, 2, np.inf],
                     labels=["< -2R", "-2..-1R", "-1..0R", "0..1R", "+1..2R", "> +2R"])
    out = r.assign(bucket=buckets).groupby("bucket", observed=False).agg(
        count=("net", "size"), net=("net", "sum")).reset_index()
    return out


def buckets(trades: pd.DataFrame, by: str = "hour") -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=[by, "trades", "net", "win_rate"])
    frame = trades.copy()
    if by == "hour":
        frame["key"] = pd.to_datetime(frame["exit_ts"]).dt.hour
    elif by == "dow":
        frame["key"] = pd.to_datetime(frame["exit_ts"]).dt.day_name().str[:3]
    elif by == "symbol":
        frame["key"] = frame["symbol"]
    elif by == "direction":
        frame["key"] = frame["direction"]
    else:
        raise ValueError("by must be hour, dow, symbol or direction")

    out = frame.groupby("key", observed=False).agg(
        trades=("net", "size"), net=("net", "sum"), avg=("net", "mean")).reset_index()
    out["win_rate"] = frame.groupby("key", observed=False)["net"].apply(
        lambda s: float((s > 0).mean())).values
    out = out.rename(columns={"key": by})
    return out.sort_values("net", ascending=False).round(3).reset_index(drop=True)


def equity_curve(trades: pd.DataFrame) -> pd.Series:
    if trades.empty:
        return pd.Series(dtype=float)
    series = trades.set_index("exit_ts")["net"].sort_index().cumsum()
    return pd.concat([pd.Series([0.0], index=[series.index[0] - pd.Timedelta(seconds=1)]), series])


def insights(trades: pd.DataFrame, stats: Dict, pro: bool = True) -> List[Dict]:
    """Plain-English findings, ordered by how much money they explain."""
    out: List[Dict] = []
    if trades.empty:
        return out

    if stats["fee_drag"] and stats["fee_drag"] > 0.25:
        out.append({"tone": "bad", "title": f"Fees are {stats['fee_drag'] * 100:.0f}% of your gross edge",
                    "detail": f"${stats['fees']:,.2f} of fees against ${stats['gross']:,.2f} gross. "
                              "Cut trade count or use maker orders."})

    by_dir = buckets(trades, "direction")
    if len(by_dir) == 2:
        long_net = float(by_dir.loc[by_dir["direction"] == "long", "net"].sum())
        short_net = float(by_dir.loc[by_dir["direction"] == "short", "net"].sum())
        if short_net < 0 < long_net:
            out.append({"tone": "warn", "title": f"Shorts lose ${abs(short_net):,.2f} while longs earn ${long_net:,.2f}",
                        "detail": "Your equity is carried by one direction only."})

    if pro:
        by_hour = buckets(trades, "hour")
        bad_hours = by_hour[(by_hour["net"] < 0) & (by_hour["trades"] >= 3)]
        if len(bad_hours):
            worst = bad_hours.iloc[-1]
            out.append({"tone": "warn",
                        "title": f"{int(worst['hour']):02d}:00 UTC is your worst session",
                        "detail": f"{int(worst['trades'])} trades, ${worst['net']:,.2f} net. "
                                  "Consider not trading that hour at all."})

        by_symbol = buckets(trades, "symbol")
        if len(by_symbol) > 1 and by_symbol.iloc[-1]["net"] < 0:
            worst = by_symbol.iloc[-1]
            out.append({"tone": "warn", "title": f"{worst['symbol']} is a net loser",
                        "detail": f"${worst['net']:,.2f} across {int(worst['trades'])} trades."})

    if stats["max_consec_losses"] >= 5:
        out.append({"tone": "bad", "title": f"{stats['max_consec_losses']} losses in a row",
                    "detail": "A stop-after-N-losses rule would have kept you in the game."})

    if stats["payoff"] and stats["win_rate"] and stats["payoff"] < 1.1 and stats["win_rate"] < 0.55:
        out.append({"tone": "bad", "title": "Low payoff with a low hit rate",
                    "detail": f"Payoff {stats['payoff']:.2f}, hit rate {stats['win_rate'] * 100:.0f}%. "
                              "That combination needs ~55%+ accuracy to break even."})

    if stats["net"] > 0 and stats["profit_factor"] and stats["profit_factor"] > 1.5:
        out.append({"tone": "good", "title": "Positive expectancy confirmed",
                    "detail": f"Profit factor {stats['profit_factor']:.2f}, "
                              f"expectancy ${stats['expectancy']:,.2f} per trade."})
    return out[:6]


def score(stats: Dict) -> Dict:
    """A blunt 0-100 health score, so the report opens with an opinion."""
    if not stats.get("trades"):
        return {"score": 0, "verdict": "No closed trades found", "color": "#8b9ab1"}
    value = 50.0
    value += 18 if stats["net"] > 0 else -18
    pf = stats["profit_factor"]
    if pf and pf != float("inf"):
        value += min(15.0, max(-15.0, (pf - 1) * 12))
    value += (stats["win_rate"] - 0.5) * 20
    value -= min(15.0, stats["fee_drag"] * 20)
    value -= min(12.0, max(0, stats["max_consec_losses"] - 3) * 3)
    value = float(max(0, min(100, value)))

    if value >= 70:
        verdict, colour = "Profitable and consistent", "#34d399"
    elif value >= 55:
        verdict, colour = "Profitable but leaky", "#fbbf24"
    elif value >= 40:
        verdict, colour = "Marginal — one bad habit from breakeven", "#fbbf24"
    else:
        verdict, colour = "Losing money — stop and fix the process", "#f87171"
    return {"score": round(value, 1), "verdict": verdict, "color": colour}
