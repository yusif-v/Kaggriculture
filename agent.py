#!/usr/bin/env python3
"""Kaggriculture baseline agent — repo: Kaggriculture.

Stateless greedy crop bot (CERES strategy v1).

Key environment facts discovered by reading the env source
(kaggle_environments/envs/kaggriculture/kaggriculture.py):
  * Agent return shape: {"farmer": [<action>, ...], "market": [[op,item,n], ...]}.
    Each farmer action is a TOKEN LIST, e.g. ["PLANT", "CARROT"], NOT a joined
    string "PLANT CARROT" (that silently no-ops because op = action[0]).
  * A freshly planted seed starts with consecutive_unwatered = 1, so it MUST be
    watered the SAME day it is planted or it turns to a weed overnight.
  * Plants must be watered every day (one action/turn). Harvested produce only
    becomes money via SELL market orders; unsold inventory is worthless.
  * The Kaggle Validation Episode is exactly a self-play game; if it runs 720
    turns with status DONE it passes. See validate.py.

Strategy (baseline, deliberately simple — the foundation to iterate on):
  1. Keep a compact 2x2 plot in the starting NW quadrant (tiles reachable from
     the (4,4) spawn within a few moves).
  2. Maintain a carrot monoculture: buy seeds when low, plant on empty plot
     tiles, water every plant daily, harvest at max_yield_day, replant.
  3. Sell all harvested produce every turn.
  4. Move toward the highest-priority unserved tile when standing idle.

Later iterations add: animals (goose->egg steady income), fertilizer,
land expansion, market price-timing heuristics.

Observation schema (default config, boardSize=10):
  obs = {"player","day","hour","step","farms":[farm,farm],
         "market":{"inventory","prices"}, "town":{"unlocked_shops"},
         "private":{"shed","seeds","inventories":[farmer_inv,...]}}
  farm = {"money","tiles":[[tile]],"farmer":[x,y],"hands":[[x,y]...],
          "unlocked_quadrants","hires_today"}
"""

from typing import Any, Dict, List, Optional, Tuple

# Compact 2x2 plot hugging the (4,4) spawn in the NW quadrant. All four tiles
# are empty/unlocked at start and reachable within a couple of moves.
PLOT: List[Tuple[int, int]] = [(4, 4), (3, 4), (4, 3), (3, 3)]
CROP = "CARROT"
SELLABLE = {
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL", "FERTILIZER",
}
MAX_MARKET_ORDERS = 10
SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
# Carrot: one-time crop, max_yield_day=3 (harvest when age >= 3).
HARVEST_AGE = {"WHEAT": 4, "CARROT": 3, "MELON": 10}


def _is_empty(tile: Any) -> bool:
    return tile is None


def _move_toward(fx: int, fy: int, tx: int, ty: int) -> str:
    if tx > fx:
        return "EAST"
    if tx < fx:
        return "WEST"
    if ty > fy:
        return "SOUTH"
    if ty < fy:
        return "NORTH"
    return "PASS"


def _nearest(targets: List[Tuple[int, int]], fx: int, fy: int) -> Optional[Tuple[int, int]]:
    best, best_d = None, 10 ** 9
    for (x, y) in targets:
        d = abs(x - fx) + abs(y - fy)
        if d < best_d:
            best_d, best = d, (x, y)
    return best


def agent(obs: Dict[str, Any]) -> Dict[str, Any]:
    p = obs["player"]
    farm = obs["farms"][p]
    priv = obs["private"]
    tiles = farm["tiles"]
    fx, fy = farm["farmer"]
    day = obs["day"]
    hour = obs["hour"]
    money = farm["money"]

    market_orders: List[List] = []
    shed = priv["shed"]
    seeds = priv["seeds"]

    # ---- count plants on our plot + collect per-tile jobs ----
    planted = 0
    need_water, need_harvest, need_plant = [], [], []
    for (x, y) in PLOT:
        if not (0 <= y < len(tiles) and 0 <= x < len(tiles[0])):
            continue
        t = tiles[y][x]
        if isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == CROP:
            planted += 1
            age = day - t.get("planted_day", day)
            if (t.get("yield_units", 0) or 0) >= 1 and age >= HARVEST_AGE.get(CROP, 99):
                need_harvest.append((x, y))
            elif not t.get("watered_today", True) and t.get("consecutive_unwatered", 0) < 2:
                need_water.append((x, y))
        elif _is_empty(t) and seeds.get(CROP, 0) > 0 and planted < len(PLOT):
            need_plant.append((x, y))

    # ---- market: sell everything harvestable sitting in the shed ----
    for item, qty in shed.items():
        if qty > 0 and item in SELLABLE and len(market_orders) < MAX_MARKET_ORDERS:
            market_orders.append(["SELL", item, int(qty)])

    # ---- market: seed procurement ----
    if seeds.get(CROP, 0) == 0 and planted == 0 and day == 0 and hour == 0:
        market_orders.append(["BUY_SEED", CROP, len(PLOT)])
    elif seeds.get(CROP, 0) == 0 and planted < len(PLOT) and money > SEED_COST.get(CROP, 20):
        market_orders.append(["BUY_SEED", CROP, len(PLOT) - planted])

    # ---- farmer action (exactly one per turn) ----
    here = tiles[fy][fx] if (0 <= fy < len(tiles) and 0 <= fx < len(tiles[0])) else None
    farmer_action: List[str] = ["PASS"]

    if isinstance(here, dict) and here.get("kind") == "PLANT" and here.get("crop") == CROP:
        age = day - here.get("planted_day", day)
        yu = here.get("yield_units", 0) or 0
        if yu >= 1 and age >= HARVEST_AGE.get(CROP, 99):
            farmer_action = ["HARVEST"]
        elif not here.get("watered_today", True) and here.get("consecutive_unwatered", 0) < 2:
            farmer_action = ["WATER"]
    elif _is_empty(here) and (fx, fy) in PLOT and seeds.get(CROP, 0) > 0 and planted < len(PLOT):
        farmer_action = ["PLANT", CROP]

    if farmer_action == ["PASS"]:
        target = (
            _nearest(need_harvest, fx, fy)
            or _nearest(need_water, fx, fy)
            or _nearest(need_plant, fx, fy)
        )
        if target is not None:
            farmer_action = [_move_toward(fx, fy, *target)]

    return {"farmer": farmer_action, "market": market_orders}
