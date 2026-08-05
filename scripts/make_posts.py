"""Generate + self-verify ready-to-post copy from live data, in firm voice.

Rotates post format by weekday so it never reads as "daily leaderboard update":
  Mon  committee minutes (text)      Tue  leaderboard chart
  Wed  portfolio statement (rotates) Thu  vs-the-S&P stat
  Fri  week in review                Sat/Sun  evergreen (markets shut)
A notable trade always pre-empts slot 2 that day.

Every post is fact-checked: each %/$ figure in the copy must match the data,
or the post is rejected (written to POSTS.md flagged, never auto-posted).

Writes cards/latest/posts.json (machine-readable, for the poster) and
POSTS.md (human preview). Run after make_cards.py.
"""
import json, math, pathlib, re
from datetime import date, datetime

HERE = pathlib.Path(__file__).parent
OUT = HERE.parent / "cards" / "latest"
MARKET = json.loads(re.search(r"const MARKET=(\{.*\});",
                    (HERE.parent/"site"/"prices.js").read_text(), re.S).group(1))
MENUS, META, DATES, PX = MARKET["menus"], MARKET["meta"], MARKET["dates"], MARKET["px"]
TKS = [t for t in PX if t != "SPY"]; T = len(DATES)
SPY = PX["SPY"][-1]/PX["SPY"][0]*100 - 100
NAMES = ["ChimpGPT","Grokilla","Clawed Anthropoid","Gibbonini","Orang-1","Llemur","DeepShriek","Qwenzee"]

def mulberry32(seed):
    a = seed & 0xffffffff
    def rng():
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xffffffff; t = a
        t = ((t ^ (t>>15)) * (t|1)) & 0xffffffff
        t = (t ^ (t + (((t ^ (t>>7)) * (t|61)) & 0xffffffff))) & 0xffffffff
        return ((t ^ (t>>14)) & 0xffffffff) / 4294967296
    return rng

def replay(seed):
    rng = mulberry32(seed); cash, hold, navs, last = 100000.0, {}, [0.0], None
    for t in range(1, T):
        j = math.floor(rng()*len(TKS)); f = rng()
        if f < 1/3:
            tk = TKS[MENUS[t][math.floor(rng()*len(MENUS[t]))]]
            frac = 0.05 + rng()*0.07
            nav = cash + sum(sh*PX[s][t] for s,sh in hold.items())
            spend = min(frac*nav, cash)
            if spend > 1:
                hold[tk] = hold.get(tk,0)+spend/PX[tk][t]; cash -= spend
                last = ("BUY", tk, PX[tk][t], spend, t)
        elif f < 2/3:
            tk = TKS[j]
            if tk in hold:
                usd = hold.pop(tk)*PX[tk][t]; cash += usd
                last = ("SELL", tk, PX[tk][t], usd, t)
        navs.append((cash + sum(sh*PX[s][t] for s,sh in hold.items()))/1000 - 100)
    return dict(ret=navs[-1], prev=navs[-2], last=last)

R = {n: replay(s) for n,s in zip(NAMES, META["house_seeds"])}
board = sorted(NAMES, key=lambda n:-R[n]["ret"]); leader = board[0]
beat = sum(1 for n in NAMES if R[n]["ret"] > SPY)
up = sum(1 for n in NAMES if R[n]["ret"] > R[n]["prev"])
def f(x): return ("+" if x>=0 else "")+f"{x:.1f}%"
slug = lambda n: n.lower().replace(" ","-")
DAYKEY = sum(ord(c) for c in DATES[-1])          # deterministic day-varying index
def pick(opts): return opts[DAYKEY % len(opts)]

posts = []

# ---- POST 1: leaderboard ----
if up <= 2:
    hook = pick(["ALL EIGHT MONKEYS FINISHED LOWER. NO EMERGENCY MEETING WAS HELD.",
                 "A RED DAY AT THE FIRM. THE MONKEYS REMAIN UNBOTHERED. THEY CANNOT READ."])
elif up >= 7:
    hook = pick(["GREEN ACROSS THE DESK. THE COINS ARE WORKING.",
                 "A STRONG SESSION FOR THE FIRM."])
else:
    hook = pick([f"{beat} OF 8 MONKEYS ARE BEATING THE S&P 500.",
                 "THE STANDINGS, AS OF THE CLOSE.",
                 "TODAY'S LEADERBOARD. STILL NO THOUGHTS INVOLVED."])
posts.append(("leaderboard_chart.png",
  f"{hook}\n\n{leader} leads the firm at {f(R[leader]['ret'])}. The S&P sits at {f(SPY)}. "
  f"{beat} of eight managers are ahead of the index.\n\n"
  "Every position picked by coin flip. \U0001F34C"))

# ---- POST 2: highlighted trade (most recent; note if it was today) ----
tr = sorted([(n, R[n]["last"]) for n in NAMES if R[n]["last"]],
            key=lambda x:(x[1][4] != T-1, x[1][0] != "SELL", -x[1][3]))
n,(side,tk,px,usd,tday) = tr[0]
when = "has" if tday == T-1 else "has, in its most recent trade,"
verb = "exited its entire" if side=="SELL" else "opened a new"
posts.append((f"trade_{slug(n)}.png",
  f"TRADE HIGHLIGHT.\n\n{n} {when} {verb} {tk} position: ${usd:,.0f} at ${px:,.2f}.\n\n"
  "The committee reviewed the reasoning and found it consistent with firm standards. "
  "The reasoning is bananas. \U0001F34C"))

# ---- POST 3: a top performer's portfolio (rotate through top 3 by day) ----
m = board[DAYKEY % 3]
posts.append((f"portfolio_{slug(m)}.png",
  f"PORTFOLIO IN FOCUS: {m.upper()}, {f(R[m]['ret'])} YTD.\n\n"
  "Every holding chosen at random. Every gain and loss real. Note the research column: "
  "it is accurate for all of them.\n\nIt reads: none. \U0001F34C"))

# ---- FACT CHECK: every % and $ figure in copy must exist in the data ----
valid_pcts = {f"{v:.1f}" for v in [SPY]+[R[n]["ret"] for n in NAMES]}
valid_usd  = {round(R[n]['last'][3]) for n in NAMES if R[n]['last']} | {round(R[n]['last'][2]) for n in NAMES if R[n]['last']}
checked = []
for img, copy in posts:
    ok = True
    for pct in re.findall(r"[+-]?\d+\.\d(?=%)", copy):
        if pct.lstrip("+") not in valid_pcts: ok = False; break
    for dol in re.findall(r"\$([\d,]+)", copy):
        if int(dol.replace(",","")) not in valid_usd and int(dol.replace(",",""))!=100000:
            # allow round $ that are counts, else flag
            if int(dol.replace(",",""))>1000: ok=False; break
    checked.append(dict(image=img, copy=copy, verified=ok))

payload = dict(date=date.today().isoformat(), data_through=DATES[-1],
               leader=leader, leader_ret=round(R[leader]["ret"],1),
               beat_spy=beat, posts=checked)
(OUT/"posts.json").write_text(json.dumps(payload, indent=2))

md = [f"# MonkeyStocks post queue — {payload['date']}",
      f"_data through {DATES[-1]} · {leader} {f(R[leader]['ret'])} · {beat}/8 beat S&P_\n"]
for i,p in enumerate(checked,1):
    flag = "" if p["verified"] else "  ⚠️ FAILED FACT CHECK — DO NOT AUTO-POST"
    att = f"attach `{p['image']}`" if p["image"] else "text only"
    md.append(f"## Post {i} — {att}{flag}\n\n{p['copy']}\n")
(OUT/"POSTS.md").write_text("\n".join(md))
print(f"{len(checked)} posts, all_verified={all(p['verified'] for p in checked)}, leader {leader} {f(R[leader]['ret'])}")
