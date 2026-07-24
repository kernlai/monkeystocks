"""Rebuild MonkeyStocks data from live Yahoo prices.

- Window: 2025-11-25 (arena start) -> today, dividend-adjusted daily prices
- Universe: the 89 tickers the AI models traded (from feed_all.json) + SPY
- Runs 10,000 seeded monkeys (exact port of engine.js mulberry32 sim)
- House 8 = a FIXED random draw from the 10,000 (seeded, reproducible)
- Emits arena/coin/prices.js with MARKET = {dates, px, meta}

Re-run any time (cron/GH Action) to refresh the site with latest closes.
"""
import json
import math
import pathlib
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf

HERE = pathlib.Path(__file__).parent
START = "2025-11-20"          # few days' buffer before arena start
ARENA_START = "2025-11-25"
N_MONKEYS = 10_000
SELECT_SEED = 20251125        # fixed: which 8 of the 10,000 are "ours"

tickers = json.loads((HERE.parent / "data" / "universe.json").read_text())["tickers"]

data = yf.download(tickers + ["SPY"], start=START, auto_adjust=True, progress=False)
closes = data["Close"].ffill()
closes = closes[closes.index >= ARENA_START]
good = sorted(t for t in closes.columns if closes[t].notna().mean() > 0.9 and t != "SPY")
px = {t: [round(v, 2) for v in closes[t]] for t in good}
px["SPY"] = [round(v, 2) for v in closes["SPY"]]
dates = [d.strftime("%Y-%m-%d") for d in closes.index]
T, K = len(dates), len(good)
print(f"{K} tickers x {T} days, {dates[0]} -> {dates[-1]}")

# ---- exact port of engine.js mulberry32 + sim ----
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

P = np.array([px[t] for t in good])  # K x T

def sim(seed):
    rng = mulberry32(seed)
    cash, hold = 100000.0, {}
    for t in range(1, T):
        j = math.floor(rng() * K)
        f = rng()
        p = P[j, t]
        if f < 1/3:
            nav = cash + sum(sh * P[s, t] for s, sh in hold.items())
            frac = 0.05 + rng() * 0.07
            spend = min(frac * nav, cash)
            if spend > 1:
                hold[j] = hold.get(j, 0) + spend / p
                cash -= spend
        elif f < 2/3 and j in hold:
            cash += hold.pop(j) * p
    return (cash + sum(sh * P[s, -1] for s, sh in hold.items())) / 1000 - 100

print("running 10,000 monkeys...")
rets = np.array([sim(s) for s in range(1, N_MONKEYS + 1)])
sel = np.random.default_rng(SELECT_SEED)
# 6 seats are a pure random draw; 2 seats are reserved (disclosed on site):
# the monkeys closest to the famous +68% and to +35%.
PICKS = [67.9, 35.0]
reserved = []
for tgt in PICKS:
    cand = int(np.argmin(np.abs(rets - tgt))) + 1
    while cand in reserved:
        cand += 1
    reserved.append(cand)
    print(f"reserved seat ~{tgt}%: seed {cand} at {rets[cand-1]:+.2f}%")
pool = np.setdiff1d(np.arange(1, N_MONKEYS + 1), reserved)
house = sel.choice(pool, 6, replace=False).tolist() + reserved
house = sorted(house, key=lambda s: -rets[s - 1])  # names map best->worst
exhibit = reserved[0]
spy_ret = px["SPY"][-1] / px["SPY"][0] * 100 - 100

meta = {
    "updated": date.today().isoformat(),
    "arena_start": ARENA_START,
    "n_monkeys": N_MONKEYS,
    "house_seeds": house,
    "house_rets": [round(float(rets[s - 1]), 2) for s in house],
    "exhibit_seed": exhibit,
    "reserved_seeds": reserved,
    "median_pct": round(float(np.median(rets)), 2),
    "best_pct": round(float(rets.max()), 2),
    "worst_pct": round(float(rets.min()), 2),
    "pct_beat_spy": round(float((rets > spy_ret).mean() * 100), 1),
    "spy_pct": round(spy_ret, 2),
}
print(json.dumps(meta, indent=2))

out = {"dates": dates, "px": px, "meta": meta}
f = HERE.parent / "site" / "prices.js"
f.write_text("// Live-rebuilt daily. Run build_arena_data.py to refresh.\nconst MARKET="
             + json.dumps(out, separators=(",", ":")) + ";\n")
print(f"wrote {f} ({f.stat().st_size:,} bytes)")
