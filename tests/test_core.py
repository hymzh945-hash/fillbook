"""FillBook tests — FIFO matching, analytics, parsing, report."""

from __future__ import annotations

import base64
import json

import pandas as pd
import pytest

from fillbook import analytics, data, licensing, report, trades as matching


def fills(rows):
    frame = pd.DataFrame(rows)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame["notional"] = frame["qty"] * frame["price"]
    frame["fee"] = frame.get("fee", 0.0)
    return frame[["ts", "symbol", "side", "qty", "price", "notional", "fee"]]


def test_long_round_trip_pnl():
    f = fills([
        {"ts": "2026-01-01 10:00", "symbol": "BTC/USDT", "side": "buy", "qty": 1, "price": 100.0},
        {"ts": "2026-01-01 12:00", "symbol": "BTC/USDT", "side": "sell", "qty": 1, "price": 110.0},
    ])
    trades = matching.match(f)
    assert len(trades) == 1
    assert trades.iloc[0]["net"] == pytest.approx(10.0)
    assert trades.iloc[0]["direction"] == "long"
    assert trades.iloc[0]["return_pct"] == pytest.approx(0.1)
    assert trades.iloc[0]["hold_minutes"] == pytest.approx(120.0)


def test_fees_are_charged_on_both_sides():
    f = fills([
        {"ts": "2026-01-01 10:00", "symbol": "BTC/USDT", "side": "buy", "qty": 1, "price": 100.0, "fee": 0.5},
        {"ts": "2026-01-01 12:00", "symbol": "BTC/USDT", "side": "sell", "qty": 1, "price": 110.0, "fee": 0.5},
    ])
    trade = matching.match(f).iloc[0]
    assert trade["gross"] == pytest.approx(10.0)
    assert trade["fees"] == pytest.approx(1.0)
    assert trade["net"] == pytest.approx(9.0)


def test_short_round_trip():
    f = fills([
        {"ts": "2026-01-01 10:00", "symbol": "ETH/USDT", "side": "sell", "qty": 2, "price": 100.0},
        {"ts": "2026-01-01 11:00", "symbol": "ETH/USDT", "side": "buy", "qty": 2, "price": 90.0},
    ])
    trade = matching.match(f).iloc[0]
    assert trade["direction"] == "short"
    assert trade["net"] == pytest.approx(20.0)


def test_partial_exits_produce_separate_round_trips():
    f = fills([
        {"ts": "2026-01-01 10:00", "symbol": "BTC/USDT", "side": "buy", "qty": 2, "price": 100.0},
        {"ts": "2026-01-01 11:00", "symbol": "BTC/USDT", "side": "sell", "qty": 1, "price": 105.0},
        {"ts": "2026-01-01 12:00", "symbol": "BTC/USDT", "side": "sell", "qty": 1, "price": 110.0},
    ])
    trades = matching.match(f)
    assert len(trades) == 2
    assert trades["net"].sum() == pytest.approx(15.0)
    assert trades["qty"].tolist() == [1.0, 1.0]


def test_oversized_exit_flips_position():
    f = fills([
        {"ts": "2026-01-01 10:00", "symbol": "BTC/USDT", "side": "buy", "qty": 1, "price": 100.0},
        {"ts": "2026-01-01 11:00", "symbol": "BTC/USDT", "side": "sell", "qty": 2, "price": 110.0},
    ])
    trades = matching.match(f)
    assert len(trades) == 1 and trades.iloc[0]["net"] == pytest.approx(10.0)
    opened = matching.open_exposure(f)
    assert len(opened) == 1
    assert opened.iloc[0]["direction"] == "short"
    assert opened.iloc[0]["qty"] == pytest.approx(1.0)


def test_summary_and_streaks():
    f = fills([
        {"ts": "2026-01-01 10:00", "symbol": "BTC/USDT", "side": "buy", "qty": 1, "price": 100},
        {"ts": "2026-01-01 11:00", "symbol": "BTC/USDT", "side": "sell", "qty": 1, "price": 90},   # -10
        {"ts": "2026-01-02 10:00", "symbol": "BTC/USDT", "side": "buy", "qty": 1, "price": 100},
        {"ts": "2026-01-02 11:00", "symbol": "BTC/USDT", "side": "sell", "qty": 1, "price": 95},   # -5
        {"ts": "2026-01-03 10:00", "symbol": "BTC/USDT", "side": "buy", "qty": 1, "price": 100},
        {"ts": "2026-01-03 11:00", "symbol": "BTC/USDT", "side": "sell", "qty": 1, "price": 120},  # +20
    ])
    stats = analytics.summary(matching.match(f))
    assert stats["trades"] == 3
    assert stats["net"] == pytest.approx(5.0)
    assert stats["win_rate"] == pytest.approx(1 / 3, abs=1e-3)  # summary rounds to 4dp
    assert stats["profit_factor"] == pytest.approx(20 / 15, abs=1e-3)
    assert stats["max_consec_losses"] == 2
    assert stats["worst"] == pytest.approx(-10.0)


def test_r_multiples_use_the_average_loss():
    f = fills([
        {"ts": "2026-01-01 10:00", "symbol": "BTC/USDT", "side": "buy", "qty": 1, "price": 100},
        {"ts": "2026-01-01 11:00", "symbol": "BTC/USDT", "side": "sell", "qty": 1, "price": 90},
        {"ts": "2026-01-02 10:00", "symbol": "BTC/USDT", "side": "buy", "qty": 1, "price": 100},
        {"ts": "2026-01-02 11:00", "symbol": "BTC/USDT", "side": "sell", "qty": 1, "price": 130},
    ])
    trades = matching.match(f)
    r = analytics.r_multiples(trades)
    assert r["r"].tolist() == pytest.approx([-1.0, 3.0])
    dist = analytics.r_distribution(trades)
    assert set(dist["bucket"].astype(str)) <= {"< -2R", "-2..-1R", "-1..0R", "0..1R", "+1..2R", "> +2R"}


def test_buckets_add_up():
    f = data.synthetic_fills(round_trips=12, seed=9)
    trades = matching.match(f)
    by_symbol = analytics.buckets(trades, "symbol")
    assert by_symbol["trades"].sum() == len(trades)
    assert by_symbol["net"].sum() == pytest.approx(trades["net"].sum(), abs=1e-2)  # buckets round to 3dp
    by_hour = analytics.buckets(trades, "hour")
    assert by_hour["trades"].sum() == len(trades)


def test_insights_flag_fee_drag():
    f = fills([
        {"ts": "2026-01-01 10:00", "symbol": "BTC/USDT", "side": "buy", "qty": 1, "price": 100, "fee": 5},
        {"ts": "2026-01-01 11:00", "symbol": "BTC/USDT", "side": "sell", "qty": 1, "price": 110, "fee": 5},
    ])
    trades = matching.match(f)
    stats = analytics.summary(trades)
    assert stats["fee_drag"] > 0.25
    titles = [i["title"] for i in analytics.insights(trades, stats, pro=False)]
    assert any("Fees are" in t for t in titles)


def test_score_is_bounded():
    f = data.synthetic_fills(round_trips=10, seed=2)
    stats = analytics.summary(matching.match(f))
    verdict = analytics.score(stats)
    assert 0 <= verdict["score"] <= 100
    assert verdict["verdict"]
    assert analytics.score({"trades": 0})["score"] == 0


def test_loader_handles_chinese_headers(tmp_path):
    frame = pd.DataFrame({
        "成交时间": ["2026-01-01 10:00:00", "2026-01-01 11:00:00"],
        "交易对": ["BTC-USDT", "BTC-USDT"],
        "方向": ["买入", "卖出"],
        "数量": [1, 1],
        "成交均价": [100, 110],
        "手续费": [0.1, 0.1],
    })
    path = tmp_path / "okx.csv"
    frame.to_csv(path, index=False)
    loaded = data.load_fills(path)
    assert loaded["side"].tolist() == ["buy", "sell"]
    assert loaded["symbol"].tolist() == ["BTC/USDT", "BTC/USDT"]
    assert loaded["fee"].sum() == pytest.approx(0.2)


def test_loader_rejects_unrelated_csv(tmp_path):
    path = tmp_path / "random.csv"
    pd.DataFrame({"a": [1], "b": [2]}).to_csv(path, index=False)
    with pytest.raises(ValueError):
        data.load_fills(path)


def test_report_embeds_images_and_gates_pro():
    f = data.synthetic_fills(round_trips=8, seed=4)
    trades = matching.match(f)
    stats = analytics.summary(trades)
    verdict = analytics.score(stats)

    free_html = report.build(trades, stats, verdict, pro=False)
    assert '<img src="data:image/png;base64,' in free_html
    assert "The findings engine is Pro" in free_html

    pro_html = report.build(trades, stats, verdict, pro=True)
    assert "The findings engine is Pro" not in pro_html
    assert "R-multiple distribution" in pro_html


def test_bad_license_falls_back_to_free(tmp_path, monkeypatch):
    doc = {"payload": {"product": "fillbook", "email": "x@y.z"}, "sig": base64.b64encode(b"nope").decode()}
    path = tmp_path / "license.json"
    path.write_text(json.dumps(doc))
    monkeypatch.setenv("FILLBOOK_LICENSE", str(path))
    assert licensing.status()["valid"] is False
