# Kaggriculture v3 Plan — from rival analysis

Derived from watching the 10 public episodes our bot played (v1 baseline) and
the public leaderboard (we rank ~2814 / rating 300.4; top teams ~3100+).

## What the rivals actually do (replay forensics)

Every replay contains BOTH farms, so we can read the opponent. Three archetypes
emerged across our 10 games:

1. **Expander (Adrián Flores, beat us 7191 vs 5088).** Unlocks all 4
   quadrants, scales to ~16 plants, **hires up to 5 hands/day**, diversifies into
   melon / tomato / strawberry / carrot. No animals. Ended $7,411. This is the
   reliable winning template — wins against the $5k pack consistently.
2. **Animal + hire monster (Mason R. Brito, 79979 vs our 4586).** Hired up to
   **12 hands/day**, ran 16 animals (sheep→wool, cow→milk), melon+strawberry
   crops, collected+used fertilizer (4–9 units). The 79,979 is inflated by a
   *market monopoly*: we only had 4 carrots and barely sold, so Mason sold into
   a near-empty market at full price. Against a strong seller the price would
   crash — but the *shape* (hands + animals + high-value crops + fertilizer) is
   the dominant strategy.
3. **Do-nothings / inefficient (Akash Babu 3385, Mahad Kakooza 3528).** 1 wheat
   plant or over-hired with 0 plants. We beat both. They confirm that
   expansion+hiring is necessary but must be paired with actual planting.

## The single biggest lever

**Hired farm hands.** v1/v2 use 0 hands. Every rival that beats us hires 5–12.
Cost is fib: 1,1,2,3,5,8,13… per hand/day. A few hands (3–4 = $7/day) is cheap
and multiplies tile actions by 4–5x. This is what v3 must add — the action
schema already supports it (`"hands": [[op,...], ...]`).

## v3 target design (ordered, each behind the gate)

Keep v2's goose (it's free steady income once placed) and build on it:

1. **Land expansion.** BUY_LAND NE ($1k) → SW ($2k) → SE ($4k) as cashflow
   allows. More tiles = more production surface. Gate: only buy when money >
   cost + buffer.
2. **Hire hands (the core change).** Hire 3–4 hands/day once land is expanding.
   Each hand gets its own action computed from the same per-tile priority logic
   (plant/water/harvest/move). Cost stays bounded by a daily hire cap.
3. **High-value crop mix.** Shift off pure carrot. Strawberry (base $120,
   ongoing) and melon (base $250, one-time) dominate rival output. Keep carrot
   only where quick turnover helps. Respect same-day watering for new plantings.
4. **Fertilizer.** Collect from animals (COLLECT_FERTILIZER) and apply to
   high-value crops during their bonus window (doubles per-day yield bonus).
5. **Scale animals.** Add cow (milk $160) / sheep (wool $200) past the goose,
   each on its own pasture, fed + cared daily. Each hand can own a sub-route.

## Risk controls (keep the gate green)

- Every change re-runs `validate.py --short` + full 720 before submit.
- Hiring is gated on `money > daily_hire_cost + planting_budget` so we never
  bankrupt the farm.
- Animals are only placed after a coop/pasture exists AND we can afford feed
  wheat — starve = lost animal.
- Never exceed 10 market orders/turn.

## Success metric

v2 self-play ≈ $5,100. v3 target: beat the $7,411 expander archetype in
self-play (aim >$8k) and climb the leaderboard rating above ~1500 (clear the
bottom third). Coins are the local proxy; the ladder rating is the real score.
