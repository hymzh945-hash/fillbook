"""FillBook HTML report — score, KPIs, equity, buckets, insights, trade table."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from . import analytics, charts

CSS = """
:root{--bg:#0b0f18;--panel:#121a29;--panel2:#0f1624;--line:#22304a;--fg:#e8eef8;
--muted:#8b9ab1;--accent:#38bdf8;--good:#34d399;--warn:#fbbf24;--bad:#f87171}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1060px;margin:0 auto;padding:34px 24px 60px}
h1{font-size:26px;margin:0 0 6px;letter-spacing:-.02em}
h2{font-size:14px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:32px 0 10px}
.sub{color:var(--muted);font-size:13px}
.hero{display:flex;gap:18px;align-items:center;background:var(--panel);border:1px solid var(--line);
border-radius:14px;padding:20px 22px;margin-top:18px}
.hero .score{font-size:38px;font-weight:700;letter-spacing:-.03em;line-height:1}
.hero .vt{font-size:15px;font-weight:650}
.hero .vd{color:var(--muted);font-size:12.5px;margin-top:4px}
.meta{display:flex;flex-wrap:wrap;gap:8px 20px;font-size:12px;color:var(--muted);margin-top:12px}
.meta b{color:var(--fg)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(142px,1fr));gap:10px;margin-top:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:13px 15px}
.card .l{font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}
.card .v{font-size:20px;font-weight:650;margin-top:5px;letter-spacing:-.02em}
.card .f{font-size:10.5px;color:var(--muted);margin-top:2px}
.pos{color:var(--good)} .neg{color:var(--bad)}
img{width:100%;border-radius:12px;border:1px solid var(--line);display:block;margin-top:8px}
table{width:100%;border-collapse:collapse;margin-top:6px;font-size:12.5px;font-variant-numeric:tabular-nums}
th{text-align:left;color:var(--muted);font-weight:600;font-size:10.5px;text-transform:uppercase;
letter-spacing:.06em;border-bottom:1px solid var(--line);padding:7px 9px}
td{padding:7px 9px;border-bottom:1px solid #1a2436}
.ins{display:grid;gap:10px;margin-top:10px}
.ins .i{border-left:3px solid var(--line);background:var(--panel);border-radius:10px;padding:12px 16px}
.ins .i.bad{border-color:var(--bad)} .ins .i.warn{border-color:var(--warn)}
.ins .i.good{border-color:var(--good)}
.ins .t{font-weight:600;font-size:13.5px} .ins .d{color:var(--muted);font-size:12px;margin-top:3px}
.lock{background:linear-gradient(135deg,#131c2c,#0d1420);border:1px dashed var(--line);
border-radius:13px;padding:20px;text-align:center;margin-top:10px}
.lock .t{font-weight:650} .lock .d{color:var(--muted);font-size:12.5px;margin:6px auto 12px;max-width:520px}
.lock a{display:inline-block;background:var(--accent);color:#05121c;text-decoration:none;
font-weight:650;padding:9px 17px;border-radius:9px;font-size:13px}
.note{background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.3);border-radius:10px;
padding:12px 16px;font-size:12.5px;margin-top:12px;color:#fde68a}
footer{margin-top:40px;padding-top:14px;border-top:1px solid var(--line);color:var(--muted);
font-size:11.5px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
"""


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _img(b64: str, alt: str) -> str:
    return f'<img src="data:image/png;base64,{b64}" alt="{html.escape(alt)}">'


def _table(frame: pd.DataFrame) -> str:
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in frame.columns)
    rows = "".join("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in row) + "</tr>"
                   for _, row in frame.iterrows())
    return f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"


def build(
    trades: pd.DataFrame,
    stats: Dict,
    verdict: Dict,
    open_rows: Optional[pd.DataFrame] = None,
    source: str = "",
    pro: bool = False,
    version: str = "0.1.0",
) -> str:
    equity = analytics.equity_curve(trades)
    by_hour = analytics.buckets(trades, "hour")
    by_symbol = analytics.buckets(trades, "symbol")
    by_dir = analytics.buckets(trades, "direction")
    found = analytics.insights(trades, stats, pro=pro)

    cards = "".join([
        f'<div class="card"><div class="l">Net PnL</div><div class="v {"pos" if stats["net"] > 0 else "neg"}">'
        f'{_money(stats["net"])}</div><div class="f">{stats["trades"]} closed trades</div></div>',
        f'<div class="card"><div class="l">Win rate</div><div class="v">{stats["win_rate"] * 100:.1f}%</div>'
        f'<div class="f">profit factor {stats["profit_factor"]:.2f}</div></div>',
        f'<div class="card"><div class="l">Expectancy</div><div class="v">{_money(stats["expectancy"])}</div>'
        f'<div class="f">per trade</div></div>',
        f'<div class="card"><div class="l">Fees paid</div><div class="v neg">{_money(stats["fees"])}</div>'
        f'<div class="f">{stats["fee_drag"] * 100:.0f}% of gross</div></div>',
        f'<div class="card"><div class="l">Payoff</div><div class="v">{stats["payoff"]:.2f}</div>'
        f'<div class="f">avg win / avg loss</div></div>',
        f'<div class="card"><div class="l">Worst streak</div><div class="v">{stats["max_consec_losses"]}</div>'
        f'<div class="f">losses in a row</div></div>',
        f'<div class="card"><div class="l">Worst trade</div><div class="v neg">{_money(stats["worst"])}</div>'
        f'<div class="f">best {_money(stats["best"])}</div></div>',
        f'<div class="card"><div class="l">Avg hold</div><div class="v">{stats["avg_hold_minutes"] / 60:.1f}h</div>'
        f'<div class="f">per round trip</div></div>',
    ])

    parts = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FillBook — trade audit</title><style>{CSS}</style></head><body><div class="wrap">
<h1>FillBook — trade audit</h1>
<div class="sub">Every fill matched FIFO into round trips · fees charged both sides</div>
<div class="hero"><div><div class="score" style="color:{verdict['color']}">{verdict['score']:.0f}</div>
<div class="sub">/ 100</div></div>
<div><div class="vt" style="color:{verdict['color']}">{html.escape(verdict['verdict'])}</div>
<div class="vd">{stats["trades"]} round trips · net {_money(stats["net"])} ·
{stats["win_rate"] * 100:.0f}% hit rate</div></div></div>
<div class="meta">
{f'<span>source <b>{html.escape(source)}</b></span>' if source else ''}
<span>first exit <b>{trades["exit_ts"].min():%Y-%m-%d}</b></span>
<span>last exit <b>{trades["exit_ts"].max():%Y-%m-%d}</b></span>
<span>generated <b>{datetime.now():%Y-%m-%d %H:%M}</b></span></div>
<div class="cards">{cards}</div>
"""]
    if open_rows is not None and len(open_rows):
        parts.append(f'<div class="note">Open exposure at end of file: '
                     + ", ".join(f'{r.symbol} {r.direction} {r.qty:g}' for _, r in open_rows.iterrows())
                     + ' — not included in the numbers above.</div>')

    parts.append("<h2>Cumulative PnL</h2>" + _img(charts.pnl_curve(equity), "pnl curve"))

    if pro:
        if len(by_symbol):
            parts.append("<h2>By symbol</h2>" + _img(
                charts.bar(by_symbol.set_index("symbol")["net"], "Net PnL per symbol", horizontal=True),
                "symbol bars"))
        if len(by_hour):
            parts.append("<h2>By exit hour (UTC)</h2>" + _img(charts.hour_bars(by_hour), "hour bars"))
        if len(by_dir):
            parts.append("<h2>Longs vs shorts</h2>" + _table(by_dir.rename(
                columns={"direction": "direction", "trades": "trades", "net": "net",
                         "avg": "avg per trade", "win_rate": "win rate"})))
        dist = analytics.r_distribution(trades)
        if len(dist):
            parts.append("<h2>R-multiple distribution</h2>" + _table(dist))
        if found:
            items = "".join(f'<div class="i {i["tone"]}"><div class="t">{html.escape(i["title"])}</div>'
                            f'<div class="d">{html.escape(i["detail"])}</div></div>' for i in found)
            parts.append(f'<h2>Findings</h2><div class="ins">{items}</div>')
    else:
        parts.append("""<h2>Findings</h2><div class="lock"><div class="t">The findings engine is Pro</div>
<div class="d">Pro reads your fills and names the leaks in dollars: fee drag, the hour that costs you
money, the symbol that never works, the direction carrying your whole equity, and the losing streaks
you keep repeating.</div><a href="https://fillbook.gumroad.com">Get FillBook Pro</a></div>""")

    table = trades.copy()
    table["entry_ts"] = table["entry_ts"].dt.strftime("%Y-%m-%d %H:%M")
    table["exit_ts"] = table["exit_ts"].dt.strftime("%Y-%m-%d %H:%M")
    table["net"] = table["net"].map(lambda v: _money(v))
    table["return_pct"] = (table["return_pct"] * 100).round(2).astype(str) + "%"
    table = table[["exit_ts", "symbol", "direction", "qty", "entry", "exit", "net", "return_pct",
                   "hold_minutes"]].head(40)
    parts.append(f"<h2>Round trips (latest {len(table)})</h2>{_table(table)}")
    parts.append(f"""<footer><span>FillBook {version} · FIFO matching, fees included</span>
<span>Not financial advice. Verify against your exchange statement.</span></footer></div></body></html>""")
    return "".join(parts)
