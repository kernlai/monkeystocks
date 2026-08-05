"""Generate ready-to-post copy from the live data, in the firm voice.

Reads site/prices.js, replays the 8 monkeys, works out the day's story
(notable trade? red day? new leader?) and writes cards/latest/POSTS.md:
each post = which image to attach + the caption, ready to paste or import
into a scheduler (Typefully / Buffer). Deterministic per day; hooks rotate
by date so nothing repeats.

Run after make_cards.py.
"""
import json
import math
import pathlib
import re
from datetime import date

HERE = pathlib.Path(__file__).parent
OUT = HERE.parent / "cards" / "latest"

raw = (HERE.parent / "site" / "prices.js").read_text()
MARKET = json.loads(re.search(r"const MARKET=(\{.*\});", raw, re.S).group(1))
MENUS = MARKET["menus"]
META = MARKET["meta"]
DATES = MARKET["dates"]
PX = MARKET["px"]
TKS = [t for t in PX if t != "SPY"]
T = len(DATES)
SPY = PX["SPY"][-1] / PX["SPY"][0] * 100 - 100
SPY_PREV = PX["SPY"][-2] / PX["SPY"][0] * 100 - 100

NAMES = ["ChimpGPT", "Grokilla", "Clawed Anthropoid", "Gibbonini",
         "Orang-1", "Llemur", "DeepShriek", "Qwenzee"]


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


def replay(seed):
    rng = mulberry32(seed)
    cash, hold = 100000.0, {}
    navs = [0.0]
    last_trade = None
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
                if t == T - 1:
                    last_trade = ("BUY", tk, PX[tk][t], spend)
        elif f < 2/3:
            tk = TKS[j_any]
            if tk in hold:
                usd = hold.pop(tk) * PX[tk][t]
                cash += usd
                if t == T - 1:
                    last_trade = ("SELL", tk, PX[tk][t], usd)
        navs.append((cash + sum(sh * PX[s][t] for s, sh in hold.items())) / 1000 - 100)
    return dict(ret=navs[-1], prev=navs[-2], last_trade=last_trade)


HOUSE = dict(zip(NAMES, META["house_seeds"]))
R = {n: replay(s) for n, s in HOUSE.items()}
board = sorted(NAMES, key=lambda n: -R[n]["ret"])
leader = board[0]
beat_spy = sum(1 for n in NAMES if R[n]["ret"] > SPY)
up_day = sum(1 for n in NAMES if R[n]["ret"] > R[n]["prev"])
trades = [(n, R[n]["last_trade"]) for n in NAMES if R[n]["last_trade"]]


def f(x):
    return ("+" if x >= 0 else "") + f"{x:.1f}%"


def pick(options):
    # deterministic day-varying choice, no RNG needed
    return options[sum(ord(c) for c in DATES[-1]) % len(options)]


posts = []

# ---- POST 1: leaderboard / market-day framing ----
img = "leaderboard_chart.png"
if up_day <= 2:
    hook = pick([
        f"ALL EIGHT MONKEYS FINISHED LOWER. NO EMERGENCY MEETING WAS HELD.",
        f"A DOWN DAY AT THE FIRM. THE MONKEYS REMAIN UNBOTHERED. THEY CANNOT READ.",
    ])
    body = (f"{leader} leads at {f(R[leader]['ret'])}. The S&P sits at {f(SPY)}. "
            f"{beat_spy} of our eight managers remain ahead of the index.\n\n"
            f"Positioning was reviewed overnight by coin. It is unchanged.")
elif up_day >= 6:
    hook = pick([
        f"A STRONG SESSION ACROSS THE FIRM.",
        f"GREEN ON THE DESK TODAY. THE COINS ARE WORKING.",
    ])
    body = (f"{leader} extends to {f(R[leader]['ret'])} against the S&P's {f(SPY)}. "
            f"{beat_spy} of eight ahead of the index.\n\nProcess unchanged. Process is a coin.")
else:
    hook = pick([
        f"LEADERBOARD UPDATE. {beat_spy} OF 8 MONKEYS STILL BEAT THE S&P 500.",
        f"THE STANDINGS, AS OF THE CLOSE.",
    ])
    body = (f"{leader} leads at {f(R[leader]['ret'])}. The market is at {f(SPY)}.\n\n"
            f"Every position selected by coin flip. Every thesis: bananas.")
posts.append((img, f"{hook}\n\n{body} \U0001F34C"))

# ---- POST 2: notable trade, if any ----
if trades:
    # prefer a SELL or the biggest-notional trade for drama
    trades.sort(key=lambda x: (x[1][0] != "SELL", -x[1][3]))
    n, (side, tk, px, usd) = trades[0]
    img = f"trade_{n.lower().replace(' ', '-')}.png"
    verb = "EXITED ITS ENTIRE" if side == "SELL" else "OPENED A"
    hook = f"{n.upper()} HAS {verb} {tk} POSITION. ${usd:,.0f} AT ${px:,.2f}."
    body = ("The investment committee reviewed the reasoning and found it consistent "
            "with the firm's standards.\n\nThe reasoning is bananas.")
    posts.append((img, f"{hook}\n\n{body} \U0001F34C"))
else:
    # no trades: a portfolio statement instead
    img = f"portfolio_{leader.lower().replace(' ', '-')}.png"
    hook = f"PORTFOLIO STATEMENT: {leader.upper()}, OUR TOP PERFORMER AT {f(R[leader]['ret'])}."
    body = ("Every holding chosen at random. Every gain and loss real. The research "
            "column is accurate for every position.\n\nIt reads: none.")
    posts.append((img, f"{hook}\n\n{body} \U0001F34C"))

# ---- write the queue ----
today = date.today().isoformat()
md = [f"# MonkeyStocks post queue — {today}",
      f"_data through {DATES[-1]} · leader {leader} {f(R[leader]['ret'])} · "
      f"{beat_spy}/8 beat S&P · {len(trades)} trades today_\n"]
for i, (img, copy) in enumerate(posts, 1):
    md.append(f"## Post {i}  —  attach `{img}`\n\n{copy}\n")
(OUT / "POSTS.md").write_text("\n".join(md))
print(f"wrote POSTS.md — {len(posts)} posts, leader {leader} {f(R[leader]['ret'])}, {len(trades)} trades")
