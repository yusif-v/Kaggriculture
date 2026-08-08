# CERES Roadmap — path to the 25k local gate

Status: v4.1 submitted (ref 55354736, PENDING). Local self-play mean ~$19k
(~2.6x v3). The user gate is >= $25k local before the NEXT push.

## What the v4.x experiments proved (all measured, 10 self-play runs each)

The agent architecture (greedy assignment + farmer animal state machine + 8
hired hands + 3 animals) has a HARD CEILING near ~$19-21k. Every parameter is
exhausted:

| Lever tried                | Result        | Verdict |
|---------------------------|---------------|---------|
| 5 / 8 / 10 / 12 hands     | 7k / 19k / 16k / 1.6k | 8 hands is the cap; fib hire cost bleeds cash above it |
| nearest vs urgency assign | 19k / 18.5k   | no gain |
| seed-buy fix (fill headroom) | 4.7k-15k  | competes with animal/hand cash; net loss |
| dense (NW+NE) + 12 hands  | 9.6k          | hire cost dominates |
| melon-lean / ongoing crops| 9.8k / 2.7k   | slow first-yield starves early game |
| drop goose (cow+sheep)    | 7.4k          | goose funds everything early |
| drop all animals          | 0.4k          | animals are the load-bearing income |

KEY FINDING: v4.1 only ever plants ~8 of 54 capacity tiles. The seed-buy guard
`seeds[crop]==0` stops buying after the first batch. Yet it scores ~$19k because
the 3 ANIMALS (goose/cow/sheep) carry almost the entire farm. Crops are a minor
add-on. Fixing seeds to plant 50+ tiles drains the cash that funds animals, so
total income DROPS. Animals and a large crop farm are mutually cash-starved at
this hand count.

## The real path to 25k: per-quadrant sub-farms (rewrite, not a tweak)

The top ladder bots (Daniel Wu $100k, Mason $80k, JTHEFROG $12k) run 12-16
hands profitably because they farm DENSE — each quadrant is a compact sub-farm
with its own local hands + 1 animal, so 12-16 hands stay productive instead of
walking a thin 100-tile spread that weeds out. Our capacity = units*6 spread
across all land = thin = weeds.

Concrete v5 design to attempt:
1. Divide the board into 4 quadrant sub-farms. Each gets ceil(hands/4) units.
2. Per sub-farm: dense plant block (melon/strawberry led), local watering,
   local fertilize, 1 animal (cow/sheep) tended by that sub-farm's units.
3. Farmer = roaming supervisor (fills gaps, handles wheat logistics).
4. Hire toward 12-16 hands ONLY once sub-farms are dense enough that each hand
   tends ~4-6 tiles (so watering coverage holds).
5. Shop/animal-product price resilience (wool/milk) keeps income stable under
   crop glut.

This is a from-scratch scheduler rewrite. Risk: high (the v4 animal-feed
logistics took 4 attempts to get right). Reward: the only known route past 25k.

## Secondary unexplored angle: shop demand

Discovered SHOPS (Bakery, Pizza, Yarn, IceCream, Smoothie, Brunch) that consume
products from the GLOBAL market inventory every 4 steps — this is a supply/
demand price lever, NOT a direct sales channel. Aligning production to shop
needs (e.g. MILK+TOMATO+WHEAT for Pizza, WOOL for Yarn) could lift prices/
volume, but it is a refinement, not the 25k unlock. Lower priority than the
per-quadrant rewrite.

## Decision needed from user

Approve the v5 per-quadrant rewrite (multi-hour, may regress before it
improves), or accept v4.1 (~$19k, 2.6x v3) as the shipped baseline and stop
pursuing 25k.
