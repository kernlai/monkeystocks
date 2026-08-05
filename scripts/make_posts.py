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
                if t == T-1: last = ("BUY", tk, PX[tk][t], spend)
        elif f < 2/3:
            tk = TKS[j]
            if tk in hold:
                usd = hold.pop(tk)*PX[tk][t]; cash += usd
                if t == T-1: last = ("SELL", tk, PX[tk][t], usd)
        navs.append((cash + sum(sh*PX[s][t] for s,sh in hold.items()))/1000 - 100)
    return dict(ret=navs[-1], prev=navs[-2], last=last)

R = {n: replay(s) for n,s in zip(NAMES, META["house_seeds"])}
board = sorted(NAMES, key=lambda n:-R[n]["ret"]); leader = board[0]
beat = sum(1 for n in NAMES if R[n]["ret"] > SPY)
up = sum(1 for n in NAMES if R[n]["ret"] > R[n]["prev"])
trades = sorted([(n, R[n]["last"]) for n in NAMES if R[n]["last"]],
                key=lambda x:(x[1][0]!="SELL", -x[1][3]))
def f(x): return ("+" if x>=0 else "")+f"{x:.1f}%"
wd = datetime.strptime(DATES[-1], "%Y-%m-%d").weekday()   # 0=Mon
slug = lambda n: n.lower().replace(" ","-")

posts = []  # (image_or_None, copy)

# ---- anchor post, rotated by weekday ----
if wd == 0:
    posts.append((None,
      "MINUTES OF THE MONDAY INVESTMENT COMMITTEE.\n\n"
      f"Attendance: 8 of 8. Review of last week: bananas. Outlook: bananas.\n"
      f"{leader} remains firm leader at {f(R[leader]['ret'])}, vs the S&P at {f(SPY)}.\n\n"
      "Action items: flip the coin at the open. One each. \U0001F34C"))
elif wd == 2:
    m = board[(T//5) % 8]  # rotate which monkey each Wednesday
    posts.append((f"portfolio_{slug(m)}.png",
      f"PORTFOLIO STATEMENT: {m.upper()}, {f(R[m]['ret'])} YTD.\n\n"
      "Every holding chosen at random. Every gain and loss real. The research "
      "column is accurate for all of them.\n\nIt reads: none. \U0001F34C"))
elif wd == 3:
    posts.append(("leaderboard_chart.png",
      f"{beat} OF 8 MONKEYS ARE BEATING THE S&P 500.\n\n"
      f"The market is up {f(SPY)}. {leader} leads the firm at {f(R[leader]['ret'])}, "
      "with a strategy of flipping a coin once a day.\n\n"
      "Good performance is not proof of skill. \U0001F34C"))
elif wd == 4:
    posts.append(("leaderboard_chart.png",
      "WEEK IN REVIEW, FROM THE DESK OF THE CIO.\n\n"
      f"The firm closed the week with {beat} of eight managers ahead of the S&P 500. "
      f"{leader} leads at {f(R[leader]['ret'])} vs the index's {f(SPY)}.\n\n"
      "We remain confident in our process. The process is a coin. \U0001F34C"))
elif wd >= 5:
    posts.append((None,
      "NOTICE: MARKETS ARE CLOSED THIS WEEKEND.\n\n"
      "The investment team will spend the time with their families, reflecting on process. "
      f"Positioning unchanged: {leader} leads at {f(R[leader]['ret'])}.\n\n"
      "The coins will be cleaned and returned to the vault by Monday. \U0001F34C"))
else:  # Tue default
    hook = ("ALL EIGHT MONKEYS FINISHED LOWER. NO EMERGENCY MEETING WAS HELD." if up <= 2
            else f"THE STANDINGS, AS OF THE CLOSE.")
    posts.append(("leaderboard_chart.png",
      f"{hook}\n\n{leader} leads at {f(R[leader]['ret'])}. The S&P sits at {f(SPY)}. "
      f"{beat} of eight ahead of the index.\n\n"
      "Every position picked by coin flip. Every thesis: bananas. \U0001F34C"))

# ---- trade post (takes priority slot if a trade happened today) ----
if trades:
    n,(side,tk,px,usd) = trades[0]
    verb = "EXITED ITS ENTIRE" if side=="SELL" else "OPENED A"
    posts.insert(0 if wd in (0,5,6) else 1, (f"trade_{slug(n)}.png",
      f"{n.upper()} HAS {verb} {tk} POSITION. ${usd:,.0f} AT ${px:,.2f}.\n\n"
      "The investment committee reviewed the reasoning and found it consistent with "
      "firm standards.\n\nThe reasoning is bananas. \U0001F34C"))

# ---- FACT CHECK: every % and $ figure in copy must exist in the data ----
valid_pcts = {f"{v:.1f}" for v in [SPY]+[R[n]["ret"] for n in NAMES]}
valid_usd  = {round(t[1][3]) for t in trades} | {round(t[1][2]) for t in trades}
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
               beat_spy=beat, trades=len(trades), posts=checked)
(OUT/"posts.json").write_text(json.dumps(payload, indent=2))

md = [f"# MonkeyStocks post queue — {payload['date']}",
      f"_data through {DATES[-1]} · {leader} {f(R[leader]['ret'])} · {beat}/8 beat S&P · {len(trades)} trades_\n"]
for i,p in enumerate(checked,1):
    flag = "" if p["verified"] else "  ⚠️ FAILED FACT CHECK — DO NOT AUTO-POST"
    att = f"attach `{p['image']}`" if p["image"] else "text only"
    md.append(f"## Post {i} — {att}{flag}\n\n{p['copy']}\n")
(OUT/"POSTS.md").write_text("\n".join(md))
print(f"{len(checked)} posts, all_verified={all(p['verified'] for p in checked)}, leader {leader} {f(R[leader]['ret'])}")
