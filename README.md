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

The competition wants a `main.py` at the root that exports an `agent`
function. Per the env AGENTS.md, a submission is a package tarball of
`main.py` + `agent.py`. We keep the strategy in `agent.py` (single source of
truth) and re-export it from `main.py`:

```bash
chmod +x submit.sh
./submit.sh "CERES baseline v1: carrot monoculture 2x2"
```

`submit.sh` will:
1. **Gate** on the local harness — `validate.py --short` and the full 720-turn
   self-play must both PASS, else it aborts (never submit a bot that can't
   survive the validation episode).
2. Package `main.py agent.py README.md` into `submission.tar.gz`.
3. Run `kaggle competitions submit kaggriculture -f submission.tar.gz -m "<msg>"`.

Poll status after submitting:

```bash
kaggle competitions submissions kaggriculture
```

You must have **joined the competition** on the Kaggle website first (rules
acceptance); the channel is open for the agent file (not a CSV). Kaggle imports
`agent` and calls it each turn — keep it stateless (the harness may re-import
per episode) and use stdlib-only imports at module scope.

## Roadmap (iteration order)

1. ✅ Baseline crop loop that turns a profit vs `pass`.
2. Animals: goose→egg (cheapest steady income), then cow/sheep.
3. Fertilizer + care-bonus banking for yield uplift.
4. Land expansion (BUY_LAND) once cashflow supports the $1k/$2k/$4k ramp.
5. Market price-timing heuristic (buy low/sell high vs the dynamic price fn).
6. Multi-farm-hand scheduling + HIRE when marginal yield > hire cost.
