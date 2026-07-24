# 🍌 MonkeyStocks

**"My AI is amazing at trading stocks." So is a coin-flipping monkey.**

Live at [monkeystocks.ai](https://monkeystocks.ai). Eight simulated monkeys trade
$100k of paper money each: once per trading day, each picks one of 89 US
large-cap stocks at random and flips a fair three-sided coin (buy / sell / hold).
Real, dividend-adjusted daily prices since 25 Nov 2025. No research, no news,
no thoughts. Don't be fooled by randomness.

## How it works
- `site/` — the static site. `engine.js` runs the simulations in your browser
  from a seeded PRNG (mulberry32), so every monkey is reproducible.
- `scripts/build_arena_data.py` — fetches latest prices, re-runs all 10,000
  monkeys, and regenerates `site/prices.js`. A GitHub Action runs it after
  each US close; the host redeploys on push.
- `data/universe.json` — the 89-ticker universe.

Every trade every monkey has ever made is in the trade log on the site,
derivable from its seed. Past bananas are not indicative of future bananas.
Not investment advice. Not intelligence.
