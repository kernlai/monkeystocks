"""Rebuild MonkeyStocks data from live Yahoo prices.

MOMENTUM MONKEYS: once per trading day each monkey flips a fair three-sided
coin. A buy invests a random 5-12% of the portfolio in a stock drawn at random
from the top quarter of the universe by trailing 3-month return (the "recent
winners" menu). A sell closes the position in a uniformly random stock, if
held. A hold does nothing. Long only, real dividend-adjusted prices.

- Window: 2025-11-25 (arena start) -> today; extra history fetched for lookback
- Universe: the 89 tickers the AI models traded + SPY
- Daily momentum menus are precomputed and shipped in prices.js so the
  browser engine replays the exact same monkeys (seeded mulberry32 PRNG)
- Exactly 8 monkeys, fixed seeds 1-8. No pool, no selection.
"""
import json
import math
import pathlib
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf

HERE = pathlib.Path(__file__).parent
FETCH_START = "2025-08-12"      # ~70 trading days of lookback before arena start
ARENA_START = "2025-11-25"
LOOKBACK = 63                   # trailing 3 months
SEEDS = [1, 2, 3, 4, 5, 6, 7, 8]   # the whole zoo

tickers = json.loads((HERE.parent / "data" / "universe.json").read_text())["tickers"]

data = yf.download(tickers + ["SPY"], start=FETCH_START, auto_adjust=True, progress=False)
closes = data["Close"].ffill()
good = sorted(t for t in closes.columns if closes[t].notna().mean() > 0.9 and t != "SPY")
ext = closes[good + ["SPY"]].dropna(how="all")
s0 = int(np.searchsorted(ext.index, pd.Timestamp(ARENA_START)))
assert s0 > LOOKBACK, "not enough lookback history"

win = ext.iloc[s0:]
px = {t: [round(v, 2) for v in win[t]] for t in good}
px["SPY"] = [round(v, 2) for v in win["SPY"]]
dates = [d.strftime("%Y-%m-%d") for d in win.index]
T, K = len(dates), len(good)
N_TOP = max(1, K // 4)
print(f"{K} tickers x {T} days, menus top-{N_TOP}, {dates[0]} -> {dates[-1]}")

C_ext = ext[good].to_numpy()  # TE x K
MENUS = [[]]
for t in range(1, T):
    i = s0 + t
    mom = C_ext[i - 1] / C_ext[i - 1 - LOOKBACK] - 1
    MENUS.append(np.argsort(mom)[-N_TOP:].tolist())

P = np.array([px[t] for t in good])  # K x T


def mulberry32(seed):
    a = seed & 0xffffffff
    def rng():
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xffffffff
        t = a
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xffffffff
        t = (t ^ (t + (((t ^ (t >> 7)) * (t | 61)) & 0xffffffff))) & 0xffffffff
        return ((t ^ (t >> 14)) & 0xffffffff) / 4294967296
    return rng


def sim(seed):
    rng = mulberry32(seed)
    cash, hold = 100000.0, {}
    for t in range(1, T):
        j_any = math.floor(rng() * K)
        f = rng()
        if f < 1/3:
            menu = MENUS[t]
            pick = menu[math.floor(rng() * len(menu))]
            frac = 0.05 + rng() * 0.07
            nav = cash + sum(sh * P[s, t] for s, sh in hold.items())
            spend = min(frac * nav, cash)
            if spend > 1:
                hold[pick] = hold.get(pick, 0) + spend / P[pick, t]
                cash -= spend
        elif f < 2/3 and j_any in hold:
            cash += hold.pop(j_any) * P[j_any, t]
    return (cash + sum(sh * P[s, -1] for s, sh in hold.items())) / 1000 - 100


print("running the 8 momentum monkeys...")
rets = {s: sim(s) for s in SEEDS}
house = sorted(SEEDS, key=lambda s: -rets[s])  # names map best->worst
spy_ret = px["SPY"][-1] / px["SPY"][0] * 100 - 100

meta = {
    "updated": date.today().isoformat(),
    "arena_start": ARENA_START,
    "style": "momentum",
    "lookback_td": LOOKBACK,
    "menu_size": N_TOP,
    "house_seeds": house,
    "house_rets": [round(float(rets[s]), 2) for s in house],
    "spy_pct": round(spy_ret, 2),
}
print(json.dumps(meta, indent=2))

out = {"dates": dates, "px": px, "menus": MENUS, "meta": meta}
f = HERE.parent / "site" / "prices.js"
f.write_text("// Live-rebuilt daily. Momentum monkeys. Run build_arena_data.py to refresh.\nconst MARKET="
             + json.dumps(out, separators=(",", ":")) + ";\n")
print(f"wrote {f} ({f.stat().st_size:,} bytes)")
