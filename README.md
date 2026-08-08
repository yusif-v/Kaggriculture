# Kaggriculture

Kaggle Featured Simulation Competition agent. Build an autonomous agent that
runs a virtual farm for a 30-day season (720 turns) and ends with the most
coins. Repo named `Kaggriculture`; internal strategy codename CERES.

- Competition: https://www.kaggle.com/competitions/kaggriculture
- Entry deadline: 2026-09-23 · Final submission: 2026-09-30
- $50,000 pool (top 10 × $5,000). Elo-style ladder: win/loss/tie only (coin
  margin ignored); newer bots get far more matchmaking episodes, so an early
  submission compounds an advantage over the season.

## Agent

`agent.py` — stateless greedy crop bot (carrot monoculture on a 2×2 plot):
buy seeds → plant → water daily → harvest at peak → sell everything. This is
the baseline that passes the Kaggle Validation Episode (a self-play game).
Later iterations add animals, fertilizer, land expansion, and market timing.

### Critical env gotcha (cost me an hour)
The farmer action must be a **token list**, e.g. `["PLANT", "CARROT"]`, NOT a
joined string `"PLANT CARROT"`. The env reads `op = action[0]`; a joined
string makes `op` the whole `"PLANT CARROT"` and silently no-ops the turn.
Also: a freshly planted seed starts with `consecutive_unwatered = 1`, so it
**must be watered the same day** or it weeds out overnight — water before you
walk away from a new planting.

## Setup

```bash
python3.13 -m venv .venv
. .venv/bin/activate
pip install kaggle_environments
```

## Run / validate locally

```bash
. .venv/bin/activate
python validate.py                 # self-play, full 720 turns (Kaggle gate)
python validate.py --short         # 200-turn smoke test
python validate.py --vs random     # vs built-in random agent
```

A clean `RESULT: PASS` (status DONE, no error) means the agent will survive the
Kaggle validation episode.

## Submit to Kaggle

The agent is a single `agent.py` exposing `agent(obs) -> {"farmer":[...],"market":[...]}`.
Upload via the competition Code tab (or `kaggle competitions submit` once the
submission channel is open). Keep the file minimal — Kaggle imports `agent` and
calls it each turn; do not rely on global state across turns (the harness may
re-import per episode).

## Roadmap (iteration order)

1. ✅ Baseline crop loop that turns a profit vs `pass`.
2. Animals: goose→egg (cheapest steady income), then cow/sheep.
3. Fertilizer + care-bonus banking for yield uplift.
4. Land expansion (BUY_LAND) once cashflow supports the $1k/$2k/$4k ramp.
5. Market price-timing heuristic (buy low/sell high vs the dynamic price fn).
6. Multi-farm-hand scheduling + HIRE when marginal yield > hire cost.
