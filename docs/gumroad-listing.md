# Gumroad listing — FillBook Pro

## Product name
FillBook Pro — turn your exchange fills into an audited PnL book

## Price
$29 (launch $19 for the first 100 copies)

## Short description
FIFO round-trip matching, fee drag, session edge and named leaks from your OKX/Binance fills export. Offline license, runs on your machine.

## Full description

**Your exchange shows you a PnL number. It never shows you what the number is made of.**

FillBook reads your fills export and rebuilds the book the way a risk desk would:

- Every fill matched **FIFO** into round trips — longs and shorts, partial fills, position flips
- **Fees on both sides**, so "net" means net
- **Fee drag**: how much of your gross edge the exchange took (often the single biggest leak)
- **Buckets** by exit hour (UTC), day of week, symbol, and long vs short
- **R-multiples**: every trade in units of your average loss, plus the distribution
- **Findings engine**: plain-English statements ordered by how much money they explain — "03:00 UTC is your worst session", "shorts lose $412 while longs earn $890", "6 losses in a row"
- **Score 0-100** with a blunt verdict
- **HTML report** and round-trip CSV export
- **Local drag-and-drop UI** — no upload, no account, nothing leaves your machine

What it looks like on a real book:

```
80 fills → 40 round trips
net PnL $4.13 · gross $21.99 · fees $17.91 · win rate 52.5% · profit factor 1.11
score 55/100 — Marginal, one bad habit from breakeven
```

That is a strategy donating 81% of its gross edge in fees. You cannot see that on an exchange dashboard.

Free tier: net PnL, hit rate, profit factor, expectancy, score, equity curve from the CLI.
Pro: findings engine, all buckets, R-multiples, CSV export, HTML report, full UI.

## Input formats
OKX and Binance exports out of the box; any CSV/JSON with side, quantity and price columns. Column names are sniffed, including Chinese headers (`成交时间`, `方向`, `数量`, `成交均价`, `手续费`).

## Files
- `fillbook-0.1.0-py3-none-any.whl`
- `quickstart.md`
- `sample-audit-report.html`
- `sample_fills.csv` + `sample_trades.csv`

## Refund
14 days, no questions.

## Tags
trade journal, pnl, fifo, okx, binance, trading analytics, python, crypto
