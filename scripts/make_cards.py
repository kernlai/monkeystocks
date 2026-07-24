"""Generate daily social cards (1200x675) from the live arena data.

Outputs to cards/latest/:
  - leaderboard.png
  - trade_<monkey>.png  (each monkey's most recent trade, thesis included)

Run after build_arena_data.py. Same brand language as the site.
"""
import json
import math
import pathlib
import re

import matplotlib.pyplot as plt
import matplotlib.patches as mp
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import numpy as np

HERE = pathlib.Path(__file__).parent
OUT = HERE.parent / "cards" / "latest"
OUT.mkdir(parents=True, exist_ok=True)

INK = "#20180a"; INK2 = "#6b5f42"; CREAM = "#faf4e6"; PAPER = "#fffdf6"
BAN = "#ffce33"; BAND = "#e0a800"; GREEN = "#1a9e55"; RED = "#e0472e"
SANS = "Helvetica Neue"; MONO = "Courier New"

MONKEYS = [
    ("ChimpGPT", "OpenApe", "Sam Apeman", "#e0472e"),
    ("Grokilla", "xApe", "E-lemur Musk", "#2a78d6"),
    ("Clawed Anthropoid", "Opusable Thumbs Capital", "Dario Ape-modei", "#1a9e55"),
    ("Gibbonini", "Alphabanana Inc.", "Demis Hassa-bananas", "#b3529e"),
    ("Orang-1", "Chain-of-Monkey-Thought LP", "Ilya Nutskever", "#e08a00"),
    ("Llemur", "Meta Primate Platforms", "Yann LeMur", "#12a5a5"),
    ("DeepShriek", "High-Swinger Quant", "Liang Swingfeng", "#7a5ce0"),
    ("Qwenzee", "Alibanana Cloud", "Jack Macaque", "#8b7355"),
]

raw = (HERE.parent / "site" / "prices.js").read_text()
MARKET = json.loads(re.search(r"const MARKET=(\{.*\});", raw, re.S).group(1))
DATES, PX, META = MARKET["dates"], MARKET["px"], MARKET["meta"]
TKS = [t for t in PX if t != "SPY"]
T = len(DATES)
SPY_RET = PX["SPY"][-1] / PX["SPY"][0] * 100 - 100


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


MENUS = MARKET["menus"]

def replay(seed):
    rng = mulberry32(seed)
    cash, hold, trades = 100000.0, {}, []
    navs = [0.0]
    for t in range(1, T):
        j_any = math.floor(rng() * len(TKS))
        f = rng()
        if f < 1/3:
            menu = MENUS[t]
            tk = TKS[menu[math.floor(rng() * len(menu))]]
            frac = 0.05 + rng() * 0.07
            nav = cash + sum(sh * PX[s][t] for s, sh in hold.items())
            spend = min(frac * nav, cash)
            if spend > 1:
                hold[tk] = hold.get(tk, 0) + spend / PX[tk][t]
                cash -= spend
                trades.append((t, "BUY", tk, PX[tk][t], spend))
        elif f < 2/3:
            tk = TKS[j_any]
            if tk in hold:
                usd = hold.pop(tk) * PX[tk][t]
                cash += usd
                trades.append((t, "SELL", tk, PX[tk][t], usd))
        navs.append((cash + sum(sh * PX[s][t] for s, sh in hold.items())) / 1000 - 100)
    ret = navs[-1]
    return trades, ret, navs


def canvas():
    fig, ax = plt.subplots(figsize=(12, 6.75), dpi=100)
    ax.set_xlim(0, 1200); ax.set_ylim(0, 675); ax.axis("off")
    fig.subplots_adjust(0, 0, 1, 1)
    ax.add_patch(mp.Rectangle((0, 0), 1200, 675, color=CREAM))
    xs, ys = np.meshgrid(np.arange(0, 1220, 26), np.arange(0, 695, 26))
    ax.scatter(xs, ys, s=2, color="#eadfc0", zorder=1)
    return fig, ax


def logo_chip(ax, x=72, y=610):
    ax.add_patch(mp.FancyBboxPatch((x, y - 20), 268, 44, boxstyle="round,pad=6",
                 facecolor=BAN, edgecolor=INK, lw=3.5, zorder=8))
    ax.text(x + 12, y - 7, "MONKEYSTOCKS", fontsize=21, fontweight="bold",
            color=INK, family=SANS, zorder=9)


def banana(ax, cx, cy, s=1.0, z=9):
    t = np.linspace(np.pi * 1.15, np.pi * 1.85, 60)
    bx, by = cx + np.cos(t) * 26 * s, cy + np.sin(t) * 26 * s + 10 * s
    ax.plot(bx, by, color=INK, lw=10 * s, solid_capstyle="round", zorder=z)
    ax.plot(bx, by, color="#8a5f00", lw=6.5 * s, solid_capstyle="round", zorder=z + 1)


def coin(ax, cx, cy, r, z=3):
    c = mp.Circle((cx, cy), r, facecolor=BAN, edgecolor=INK, lw=7, zorder=z)
    ax.add_patch(c)
    hl = mp.Circle((cx - r*0.2, cy + r*0.25), r * .75, facecolor="#ffe488", alpha=.5, zorder=z + 1)
    hl.set_clip_path(c); ax.add_patch(hl)
    t = np.linspace(np.pi * 1.15, np.pi * 1.85, 60)
    bx, by = cx + np.cos(t) * r * .48, cy + np.sin(t) * r * .48 + r * .18
    ax.plot(bx, by, color=INK, lw=r * .16, solid_capstyle="round", zorder=z + 2)
    ax.plot(bx, by, color="#8a5f00", lw=r * .11, solid_capstyle="round", zorder=z + 3)


def fmt(r):
    return ("+" if r >= 0 else "") + f"{r:.1f}%"


BANANA_IMG = plt.imread(HERE / "assets" / "banana.png")
def banana_emoji(ax, x, y, px=48, z=9):
    ab = AnnotationBbox(OffsetImage(BANANA_IMG, zoom=px / BANANA_IMG.shape[0]), (x, y),
                        frameon=False, zorder=z)
    ax.add_artist(ab)

results = {}
for name, lab, mgr, col in MONKEYS:
    seed = META["house_seeds"][[m[0] for m in MONKEYS].index(name)]
    trades, ret, navs = replay(seed)
    results[name] = dict(trades=trades, ret=ret, navs=navs, lab=lab, mgr=mgr, col=col)

# ---------------- trade cards ----------------
for name, r in results.items():
    t, side, tk, px_, usd = r["trades"][-1]
    date = DATES[t]
    fig, ax = canvas()
    logo_chip(ax)
    coin(ax, 1050, 520, 110)
    ax.text(72, 520, "TRADE CONFIRMATION", fontsize=17, color=INK2, family=MONO, fontweight="bold", zorder=8)
    ax.text(72, 448, name, fontsize=46, fontweight="bold", color=INK, family=SANS, zorder=8)
    ax.text(74, 408, f"{r['lab']}  ·  YTD {fmt(r['ret'])}", fontsize=19, color=INK2, family=SANS, fontweight="bold", zorder=8)
    sc = GREEN if side == "BUY" else RED
    ax.text(72, 318, f"{side} {tk}", fontsize=64, fontweight="bold", color=sc, family=SANS, zorder=8)
    ax.text(74, 272, f"\\${px_:,.2f}  ·  \\${usd:,.0f}  ·  {date}", fontsize=20, color=INK2, family=MONO, fontweight="bold", zorder=8)
    # thesis slip
    box = mp.FancyBboxPatch((66, 96), 700, 118, boxstyle="round,pad=10",
                            facecolor=PAPER, edgecolor=INK, lw=3.5, zorder=8)
    box.set_transform(ax.transData)
    ax.add_patch(box)
    ax.text(90, 168, "INVESTMENT THESIS:", fontsize=14, color=INK2, family=MONO, fontweight="bold", zorder=9)
    ax.text(90, 124, '"bananas"', fontsize=34, fontweight="bold", color=INK, family=SANS, zorder=9)
    banana_emoji(ax, 400, 154, 44)
    ax.text(756, 106, f"— {r['mgr']}, CIO, {r['lab']}", fontsize=12.5, color=INK2, family=MONO,
            fontweight="bold", zorder=9, ha="right")
    ax.text(72, 42, "MONKEYSTOCKS.AI", fontsize=13,
            color=INK2, family=MONO, fontweight="bold", zorder=8)
    slug = name.lower().replace(" ", "-")
    fig.savefig(OUT / f"trade_{slug}.png"); plt.close(fig)

# ---------------- leaderboard card ----------------
fig, ax = canvas()
logo_chip(ax, 72, 628)
ax.text(72, 545, "THE LEADERBOARD", fontsize=34, fontweight="bold", color=INK, family=SANS, zorder=8)
ax.text(1140, 545, "8 momentum monkeys · one coin flip a day", fontsize=14,
        color=INK2, family=MONO, fontweight="bold", ha="right", zorder=8)

PL, PR, PT, PB = 60, 1140, 522, 38
ax.add_patch(mp.FancyBboxPatch((PL+6, PB-6), PR-PL, PT-PB, boxstyle="round,pad=0,rounding_size=14",
             facecolor=INK, edgecolor="none", zorder=6))
ax.add_patch(mp.FancyBboxPatch((PL, PB), PR-PL, PT-PB, boxstyle="round,pad=0,rounding_size=14",
             facecolor=PAPER, edgecolor=INK, lw=3.5, zorder=7))

HDR_H = 46
ax.add_patch(mp.FancyBboxPatch((PL, PT-HDR_H), PR-PL, HDR_H, boxstyle="round,pad=0,rounding_size=14",
             facecolor=BAN, edgecolor=INK, lw=3.5, zorder=8))
ax.add_patch(mp.Rectangle((PL+2, PT-HDR_H), PR-PL-4, HDR_H//2, facecolor=BAN, edgecolor="none", zorder=8))
ax.plot([PL, PR], [PT-HDR_H, PT-HDR_H], color=INK, lw=3.5, zorder=9)
C_NAME, C_LAB, C_RET, C_VS = 118, 480, 950, 1108
ax.text(C_NAME-22, PT-HDR_H+15, "MONKEY", fontsize=13, family=MONO, fontweight="bold", color=INK, zorder=10)
ax.text(C_LAB, PT-HDR_H+15, "LAB", fontsize=13, family=MONO, fontweight="bold", color=INK, zorder=10)
ax.text(C_RET, PT-HDR_H+15, "RETURN", fontsize=13, family=MONO, fontweight="bold", color=INK, ha="right", zorder=10)
ax.text(C_VS, PT-HDR_H+15, "VS S&P", fontsize=13, family=MONO, fontweight="bold", color=INK, ha="right", zorder=10)

rows = sorted([(n, r["ret"]) for n, r in results.items()], key=lambda x: -x[1])
entries = [(n, ret, False) for n, ret in rows] + [("S&P 500", SPY_RET, True)]
entries.sort(key=lambda x: -x[1])
n_rows = len(entries)
ROW_H = (PT - HDR_H - PB - 10) / n_rows
y_top = PT - HDR_H
for idx, (n, ret, is_spx) in enumerate(entries):
    ry = y_top - (idx + 1) * ROW_H
    cy = ry + ROW_H / 2 - 7
    if idx < n_rows - 1:
        ax.plot([PL+14, PR-14], [ry, ry], color="#e5d9b8", lw=1.6, zorder=9)
    if is_spx:
        ax.add_patch(mp.Rectangle((PL+4, ry+2), PR-PL-8, ROW_H-4, facecolor="#f6efdd", edgecolor="none", zorder=8))
        ax.text(C_NAME-22, cy, "S&P 500", fontsize=19, color=INK2, family=SANS, fontweight="bold", zorder=10)
        ax.text(C_RET, cy, fmt(ret), fontsize=19, family=MONO, fontweight="bold", color=INK2, ha="right", zorder=10)
        ax.text(C_VS, cy, "—", fontsize=19, family=MONO, fontweight="bold", color=INK2, ha="right", zorder=10)
        continue
    d = ret - SPY_RET
    ax.add_patch(mp.Circle((C_NAME-8, cy+7), 8, facecolor=results[n]["col"], edgecolor=INK, lw=2, zorder=10))
    ax.text(C_NAME+8, cy, n, fontsize=19, color=INK, family=SANS, fontweight="bold", zorder=10)
    ax.text(C_LAB, cy, results[n]["lab"], fontsize=14.5, color=INK2, family=SANS, zorder=10)
    ax.text(C_RET, cy, fmt(ret), fontsize=19, family=MONO, fontweight="bold",
            color=GREEN if ret >= 0 else RED, ha="right", zorder=10)
    ax.text(C_VS, cy, fmt(d), fontsize=19, family=MONO, fontweight="bold",
            color=GREEN if d >= 0 else RED, ha="right", zorder=10)

ax.text(72, 16, "MONKEYSTOCKS.AI", fontsize=13, color=INK2, family=MONO, fontweight="bold", zorder=8)
fig.savefig(OUT / "leaderboard.png"); plt.close(fig)

# ---------------- leaderboard + chart combo ----------------
fig, ax = canvas()
logo_chip(ax, 72, 628)
ax.text(72, 545, "THE LEADERBOARD", fontsize=34, fontweight="bold", color=INK, family=SANS, zorder=8)
ax.text(1140, 545, "8 momentum monkeys · one coin flip a day", fontsize=14,
        color=INK2, family=MONO, fontweight="bold", ha="right", zorder=8)

def panel(x0, y0, x1, y1):
    ax.add_patch(mp.FancyBboxPatch((x0+6, y0-6), x1-x0, y1-y0, boxstyle="round,pad=0,rounding_size=14",
                 facecolor=INK, edgecolor="none", zorder=6))
    ax.add_patch(mp.FancyBboxPatch((x0, y0), x1-x0, y1-y0, boxstyle="round,pad=0,rounding_size=14",
                 facecolor=PAPER, edgecolor=INK, lw=3.5, zorder=7))

panel(60, 38, 730, 522)
spy_pct = [PX["SPY"][t] / PX["SPY"][0] * 100 - 100 for t in range(T)]
all_series = [r["navs"] for r in results.values()] + [spy_pct]
lo = min(min(sv) for sv in all_series) - 4
hi = max(max(sv) for sv in all_series) + 4
CX0, CX1, CY0, CY1 = 128, 700, 88, 490
def gx(i): return CX0 + i / (T - 1) * (CX1 - CX0)
def gy(v): return CY0 + (v - lo) / (hi - lo) * (CY1 - CY0)
import numpy as _np
step = 20 if hi - lo > 60 else 10
for gl in range(int(_np.ceil(lo / step)) * step, int(hi) + 1, step):
    ax.plot([CX0, CX1], [gy(gl), gy(gl)], color="#e5d9b8", lw=1.4, zorder=8)
    ax.text(CX0 - 10, gy(gl) - 5, f"{'+' if gl > 0 else ''}{gl}%", fontsize=11, family=MONO,
            fontweight="bold", color=INK2, ha="right", zorder=9)
ax.plot([CX0, CX1], [gy(0), gy(0)], color=INK, lw=1.6, alpha=.4, zorder=8)
MMM = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
for i in [0, T // 2, T - 1]:
    d = DATES[i]
    lbl = MMM[int(d[5:7]) - 1] + "-" + d[2:4]
    ax.text(gx(i), CY0 - 26, lbl, fontsize=11, family=MONO, fontweight="bold", color=INK2,
            ha="left" if i == 0 else ("right" if i == T - 1 else "center"), zorder=9)
xs = [gx(i) for i in range(T)]
for n, r in results.items():
    ax.plot(xs, [gy(v) for v in r["navs"]], color=r["col"], lw=2.2, zorder=9,
            solid_joinstyle="round", solid_capstyle="round")
ax.plot(xs, [gy(v) for v in spy_pct], color=INK, lw=1.8, ls=(0, (4, 3)), zorder=9)

TPL, TPR, TPT, TPB = 750, 1140, 522, 38
panel(TPL, TPB, TPR, TPT)
HDR_H = 46
ax.add_patch(mp.FancyBboxPatch((TPL, TPT - HDR_H), TPR - TPL, HDR_H, boxstyle="round,pad=0,rounding_size=14",
             facecolor=BAN, edgecolor=INK, lw=3.5, zorder=8))
ax.add_patch(mp.Rectangle((TPL + 2, TPT - HDR_H), TPR - TPL - 4, HDR_H // 2, facecolor=BAN, edgecolor="none", zorder=8))
ax.plot([TPL, TPR], [TPT - HDR_H, TPT - HDR_H], color=INK, lw=3.5, zorder=9)
ax.text(TPL + 34, TPT - HDR_H + 15, "MONKEY", fontsize=13, family=MONO, fontweight="bold", color=INK, zorder=10)
ax.text(TPR - 26, TPT - HDR_H + 15, "RETURN", fontsize=13, family=MONO, fontweight="bold", color=INK, ha="right", zorder=10)
rows2 = sorted([(n, r["ret"]) for n, r in results.items()], key=lambda x: -x[1])
entries2 = [(n, ret, False) for n, ret in rows2] + [("S&P 500", spy_pct[-1], True)]
entries2.sort(key=lambda x: -x[1])
ROW_H2 = (TPT - HDR_H - TPB - 10) / len(entries2)
for idx, (n, ret, is_spx) in enumerate(entries2):
    ry = TPT - HDR_H - (idx + 1) * ROW_H2
    cy = ry + ROW_H2 / 2 - 6
    if idx < len(entries2) - 1:
        ax.plot([TPL + 14, TPR - 14], [ry, ry], color="#e5d9b8", lw=1.6, zorder=9)
    if is_spx:
        ax.add_patch(mp.Rectangle((TPL + 4, ry + 2), TPR - TPL - 8, ROW_H2 - 4, facecolor="#f6efdd", edgecolor="none", zorder=8))
        ax.text(TPL + 34, cy, "S&P 500", fontsize=16, color=INK2, family=SANS, fontweight="bold", zorder=10)
        ax.text(TPR - 26, cy, fmt(ret), fontsize=16, family=MONO, fontweight="bold", color=INK2, ha="right", zorder=10)
        continue
    ax.add_patch(mp.Circle((TPL + 42, cy + 6), 7, facecolor=results[n]["col"], edgecolor=INK, lw=2, zorder=10))
    ax.text(TPL + 56, cy, n, fontsize=16, color=INK, family=SANS, fontweight="bold", zorder=10)
    ax.text(TPR - 26, cy, fmt(ret), fontsize=16, family=MONO, fontweight="bold",
            color=GREEN if ret >= 0 else RED, ha="right", zorder=10)

ax.text(72, 16, "MONKEYSTOCKS.AI", fontsize=13, color=INK2, family=MONO, fontweight="bold", zorder=8)
fig.savefig(OUT / "leaderboard_chart.png"); plt.close(fig)

print("cards written:", sorted(p.name for p in OUT.glob("*.png")))
