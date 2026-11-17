# FillBook

**Turn your exchange fills into an audited PnL book.**

Your exchange shows you a number. FillBook shows you what that number is made of: every fill
matched FIFO into round trips, fees charged on both sides, then the leaks named in dollars —
which hour costs you money, which symbol never works, whether your shorts are funding your longs.

```bash
fillbook audit -i okx_fills.csv --report audit.html
```

```
80 fills → 40 round trips
  net PnL               $4.13
  gross / fees     $21.99 / $17.91
  win rate              52.5%
  profit factor          1.11
  expectancy    $0.10 per trade
  score                 55/100  Marginal — one bad habit from breakeven
```

That output is the point: a strategy with a 1.11 profit factor and 81% fee drag is not a strategy,
it is a fee donation with a story attached.

## What it does

- **FIFO round-trip matching** per symbol, longs and shorts, partial fills, position flips.
- **Fees on both sides**, net PnL and per-trade return percentage.
- **Fee drag** — how much of your gross edge the exchange took.
- **Buckets**: by exit hour (UTC), day of week, symbol, long vs short.
- **R-multiples** — every trade in units of your average loss, plus the distribution.
- **Findings engine** — plain-English leaks ordered by how much money they explain.
- **Score 0-100** with a blunt verdict, because "profitable" and "durable" are different words.
- **HTML report** and round-trip CSV export.
- **Local web UI** — drop a file, read the audit.

Free tier: PnL, hit rate, profit factor, expectancy, score, equity curve.
Pro: findings engine, all buckets, R-multiples, CSV export, HTML report, full UI.

## Input

Any CSV/JSON fills export with side, quantity and price columns — OKX, Binance, or your own
spreadsheet. Column names are sniffed, including Chinese headers (`成交时间`, `方向`, `数量`,
`成交均价`, `手续费`).

```bash
fillbook audit -i fills.csv              # terminal summary
fillbook audit -i fills.csv --csv t.csv  # export matched trades
fillbook demo                            # synthetic run, no data needed
fillbook serve                           # UI on :8766
```

## Notes

- A round trip is one exit; a single entry split across three exits becomes three rows, which is
  what actually happened.
- Open positions at the end of the file are reported separately and never counted as realised PnL.
- Numbers are computed from your fills, not from your account balance — funding fees and
  transfers are not in a fills export.

MIT licensed. No network calls, no credentials. Not financial advice.
