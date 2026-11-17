"""`fillbook audit | demo | serve | license`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import analytics, data, licensing, report, trades as matching
from .version import __version__

FEATURES_URL = "https://fillbook.gumroad.com"


def _require_pro(feature: str) -> None:
    print(f"{feature} is part of FillBook Pro — {FEATURES_URL}")
    raise SystemExit(1)


def _analyse(path: str | None, rows: int = 40) -> tuple:
    if path:
        fills = data.load_fills(path)
        source = Path(path).name
    else:
        fills = data.synthetic_fills(round_trips=rows)
        source = "synthetic demo"
    closed = matching.match(fills)
    stats = analytics.summary(closed)
    verdict = analytics.score(stats)
    opened = matching.open_exposure(fills)
    return fills, closed, stats, verdict, opened, source


def cmd_audit(args: argparse.Namespace) -> int:
    pro = licensing.is_pro()
    fills, closed, stats, verdict, opened, source = _analyse(args.input, args.round_trips)

    print(f"\nFillBook {__version__} · {source} · {len(fills)} fills → {stats['trades']} round trips")
    if stats["trades"] == 0:
        print("no closed round trips found — is this a fills file, or a positions file?")
        return 1

    print(f"  net PnL        {stats['net']:>12,.2f}")
    print(f"  gross / fees   {stats['gross']:>12,.2f} / {stats['fees']:,.2f}")
    print(f"  win rate       {stats['win_rate'] * 100:>11.1f}%")
    print(f"  profit factor  {stats['profit_factor']:>12.2f}")
    print(f"  expectancy     {stats['expectancy']:>12,.2f} per trade")
    print(f"  score          {verdict['score']:>12.0f}/100  {verdict['verdict']}")

    if pro:
        by_dir = analytics.buckets(closed, "direction")
        print("\nby direction:\n" + by_dir.to_string(index=False))
        by_hour = analytics.buckets(closed, "hour").head(3)
        print("\nbest hours:\n" + by_hour.to_string(index=False))
        for item in analytics.insights(closed, stats, pro=True):
            print(f"  [{item['tone']}] {item['title']} — {item['detail']}")
    else:
        print("\n(full buckets, findings engine and HTML report are Pro)")

    if args.report:
        if not pro:
            _require_pro("HTML report")
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.build(closed, stats, verdict, opened, source=source,
                                    pro=pro, version=__version__), "utf-8")
        print(f"\nreport -> {out}")

    if args.csv:
        out = Path(args.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        closed.to_csv(out, index=False)
        print(f"trades -> {out}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fills, closed, stats, verdict, opened, source = _analyse(None, args.round_trips)
    fills.to_csv(out / "demo_fills.csv", index=False)
    closed.to_csv(out / "demo_trades.csv", index=False)
    html = report.build(closed, stats, verdict, opened, source=source,
                        pro=licensing.is_pro(), version=__version__)
    (out / "fillbook-report.html").write_text(html, "utf-8")
    print(f"{len(fills)} fills → {stats['trades']} round trips · score {verdict['score']:.0f} · "
          f"{verdict['verdict']}")
    print(f"report -> {out / 'fillbook-report.html'}"
          f" ({'Pro' if licensing.is_pro() else 'free tier'})")
    return 0


def cmd_license(args: argparse.Namespace) -> int:
    st = licensing.status()
    if st["valid"]:
        print(f"Pro license · {st['email']} · expires {st['expires'] or 'lifetime'}")
        print(f"source: {licensing.license_path()}")
    else:
        print(f"Free tier · {st['info']}")
        print(f"Pro: {FEATURES_URL}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .server import serve
    serve(host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fillbook", description="Turn exchange fills into an audited PnL book.")
    p.add_argument("--version", action="version", version=f"fillbook {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("audit", help="audit a fills export")
    a.add_argument("-i", "--input", help="CSV/JSON fill export (OKX, Binance, generic)")
    a.add_argument("--round-trips", type=int, default=40, help="synthetic trips when no --input")
    a.add_argument("--report", help="write an HTML report (Pro)")
    a.add_argument("--csv", help="write matched round trips to CSV")
    a.set_defaults(func=cmd_audit)

    d = sub.add_parser("demo", help="synthetic end-to-end run")
    d.add_argument("-o", "--out", default="fillbook-demo")
    d.add_argument("--round-trips", type=int, default=40)
    d.set_defaults(func=cmd_demo)

    s = sub.add_parser("serve", help="local web UI")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8766)
    s.set_defaults(func=cmd_serve)

    l = sub.add_parser("license", help="license status")
    l.set_defaults(func=cmd_license)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
