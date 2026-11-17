"""Charts for the FillBook report — matplotlib Agg, base64 data URIs."""

from __future__ import annotations

import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BG = "#0f1420"
PANEL = "#161d2e"
FG = "#e6edf7"
MUTED = "#8b98ad"
ACCENT = "#38bdf8"
GOOD = "#34d399"
BAD = "#f87171"

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": PANEL, "savefig.facecolor": BG,
    "axes.edgecolor": "#243046", "axes.labelcolor": FG, "text.color": FG,
    "xtick.color": MUTED, "ytick.color": MUTED, "font.size": 9,
    "axes.grid": True, "grid.color": "#1e2739", "grid.linewidth": 0.6,
})


def _save(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def pnl_curve(equity: pd.Series) -> str:
    fig, ax = plt.subplots(figsize=(10, 3.6))
    colour = ACCENT if equity.iloc[-1] >= 0 else BAD
    ax.plot(equity.index, equity.values, color=colour, lw=1.5)
    ax.fill_between(equity.index, equity.values, 0, color=colour, alpha=0.10)
    ax.axhline(0, color="#243046", lw=0.8)
    ax.set_title("Cumulative net PnL (fees included)", loc="left", color=FG, fontsize=11)
    ax.yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))
    locator = matplotlib.dates.AutoDateLocator(minticks=3, maxticks=8)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(matplotlib.dates.ConciseDateFormatter(locator))
    ax.spines[["top", "right"]].set_visible(False)
    return _save(fig)


def bar(values: pd.Series, title: str, horizontal: bool = False) -> str:
    fig, ax = plt.subplots(figsize=(8, 3.2))
    colours = [GOOD if v > 0 else BAD for v in values.to_numpy()]
    if horizontal:
        ax.barh(range(len(values)), values.values, color=colours, height=0.62)
        ax.set_yticks(range(len(values)))
        ax.set_yticklabels([str(i) for i in values.index])
        ax.invert_yaxis()
    else:
        ax.bar(range(len(values)), values.values, color=colours, width=0.7)
        ax.set_xticks(range(len(values)))
        ax.set_xticklabels([str(i) for i in values.index])
    ax.axvline(0) if horizontal else ax.axhline(0, color="#243046", lw=0.8)
    ax.set_title(title, loc="left", color=FG, fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    return _save(fig)


def hour_bars(by_hour: pd.DataFrame) -> str:
    series = pd.Series(0.0, index=[f"{h:02d}" for h in range(24)])
    for _, row in by_hour.iterrows():
        series[f"{int(row['hour']):02d}"] = float(row["net"])
    return bar(series, "Net PnL by exit hour (UTC)")
