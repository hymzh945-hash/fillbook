# FillBook Pro — quick start

1. `pip install "fillbook[license]"`
2. Save your key to `~/fillbook-license.json` (or `export FILLBOOK_LICENSE=/path/to/key.json`)
3. `fillbook license` → prints your email and expiry
4. Export fills from your exchange (OKX: Trade history → Export; Binance: Order history → Export)
5. `fillbook audit -i fills.csv --report audit.html --csv trades.csv`
6. `fillbook serve` → drop-zone UI at http://127.0.0.1:8766

## What to look at first

- **Fee drag** above 25% of gross: you are trading too often or taking liquidity when you could post.
- **Score** below 55 with a positive net: the edge is real but thin — one bad week erases it.
- **Worst hour**: if a single session is net negative across 3+ trades, stop trading it.
- **Long vs short split**: one direction usually carries the whole book.

## Caveats

- Funding fees, transfers and unrealised positions are not in a fills export; FillBook reports
  only realised round trips it can match.
- If your export is a *positions* file (one row per closed position), matching still works — but
  check the round-trip count against the exchange.

Questions: reply to your Gumroad receipt.
