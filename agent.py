#!/usr/bin/env python3
"""Kaggriculture agent — repo: Kaggriculture.

CERES strategy v2: carrot monoculture on a 3-tile plot PLUS one goose for
steady, price-resilient egg income.

Design choices (verified against kaggriculture.py):
  * The goose coop is placed on the SPAWN tile (4,4). The env resets the
    farmer to the spawn every day (_end_of_day -> _default_spawn), so the
    farmer starts each day standing on the coop and can feed/care/harvest the
    goose in the first few turns before tending carrots. This guarantees the
    goose is never starved (2 consecutive unfed days -> escape -> lost $300).
  * FEED consumes 1 WHEAT from the *farmer's own inventory*; the farmer must
    PICKUP wheat from the shed (shed-adjacent at spawn) before feeding.
  * Goose: BUY_ANIMAL $300 -> shed; PLACE on a COOP tile populates it. Produces
    1 egg/day from day 4 (interval 1). CARE banks +1 egg/prod-day (capped at
    max_held 4 on the tile). Eggs are collected via HARVEST -> inventory ->
    SELL. Egg price is resilient (above_target 0.20), unlike carrots which
    crash on a glut.
  * Crops still need same-day watering after planting (a fresh seed starts at
    consecutive_unwatered = 1).
  * One farmer action per turn. Stateless across turns.

Strategy (per turn, highest priority first):
  1. If on the coop: build it / place the goose / PICKUP-feed / CARE / HARVEST
     eggs as needed (keeps the goose alive and productive).
  2. If the goose is unfed and we are NOT on the coop: walk to the coop.
  3. If standing on a carrot tile: harvest / water / plant as needed.
  4. Otherwise: walk toward the nearest unserved carrot tile.

Observation schema (default config, boardSize=10):
  obs = {"player","day","hour","step","farms":[farm,farm],
         "market":{"inventory","prices"}, "town":{"unlocked_shops"},
         "private":{"shed","seeds","inventories":[farmer_inv,...]}}
  farm = {"money","tiles":[[tile]],"farmer":[x,y],"hands":[[x,y]...],
          "unlocked_quadrants","hires_today"}
"""

from typing import Any, Dict, List, Optional, Tuple

CROP = "CARROT"
# Coop on the spawn tile so the farmer begins each day on it.
COOP: Tuple[int, int] = (4, 4)
# Three carrot tiles (all in the starting NW quadrant, always unlocked).
CARROT_TILES: List[Tuple[int, int]] = [(3, 4), (4, 3), (3, 3)]

SELLABLE = {
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL", "FERTILIZER",
}
MAX_MARKET_ORDERS = 10
SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
GOOSE_COST = 300
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
    money = farm["money"]
    shed = priv["shed"]
    seeds = priv["seeds"]
    inv = priv["inventories"][0] if priv.get("inventories") else {}

    market_orders: List[List] = []

    # ---- sell everything harvestable sitting in the shed ----
    for item, qty in shed.items():
        if qty > 0 and item in SELLABLE and len(market_orders) < MAX_MARKET_ORDERS:
            market_orders.append(["SELL", item, int(qty)])

    # ---- carrot plot bookkeeping ----
    planted = 0
    need_water, need_harvest, need_plant = [], [], []
    for (x, y) in CARROT_TILES:
        if not (0 <= y < len(tiles) and 0 <= x < len(tiles[0])):
            continue
        t = tiles[y][x]
        if isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == CROP:
            planted += 1
            age = day - t.get("planted_day", day)
            if t.get("yield_units", 0) >= 1 and age >= HARVEST_AGE.get(CROP, 99):
                need_harvest.append((x, y))
            elif not t.get("watered_today", True) and t.get("consecutive_unwatered", 0) < 2:
                need_water.append((x, y))
        elif _is_empty(t) and seeds.get(CROP, 0) > 0 and planted < len(CARROT_TILES):
            need_plant.append((x, y))

    # ---- goose state (coop at spawn) ----
    g = tiles[COOP[1]][COOP[0]] if (0 <= COOP[1] < len(tiles) and 0 <= COOP[0] < len(tiles[0])) else None
    gdict: Optional[Dict[str, Any]] = g if isinstance(g, dict) else None
    goose = gdict is not None and gdict.get("animal") == "GOOSE"
    coop_built = gdict is not None and gdict.get("kind") == "COOP"
    on_coop = (fx, fy) == COOP

    # ---- procurement ----
    if (seeds.get(CROP, 0) == 0 and planted < len(CARROT_TILES)
            and money > SEED_COST.get(CROP, 20) and len(market_orders) < MAX_MARKET_ORDERS):
        market_orders.append(["BUY_SEED", CROP, len(CARROT_TILES) - planted])
    if (not goose and money > GOOSE_COST and shed.get("GOOSE", 0) == 0
            and len(market_orders) < MAX_MARKET_ORDERS):
        market_orders.append(["BUY_ANIMAL", "GOOSE", 1])
    # Keep a small wheat buffer for feeding (1/day; buffer avoids starve if a buy lags).
    if shed.get("WHEAT", 0) < 2 and money > 60 and len(market_orders) < MAX_MARKET_ORDERS:
        market_orders.append(["BUY_PRODUCT", "WHEAT", 2])

    # ---- farmer action (exactly one per turn) ----
    action: List[Any] = ["PASS"]

    # 1) On the coop: build / place / service the goose.
    if on_coop:
        if not goose and not coop_built:
            action = ["BUILD_COOP"]
        elif not goose and coop_built:
            # PLACE takes the animal from the FARMER's inventory, not the shed,
            # so we must PICKUP the goose from the shed first.
            if shed.get("GOOSE", 0) > 0 and inv.get("GOOSE", 0) == 0:
                action = ["PICKUP", "GOOSE", 1]
            elif inv.get("GOOSE", 0) > 0:
                action = ["PLACE", "GOOSE"]
        elif goose and gdict is not None:
            if (not gdict.get("fed_today", True)) and inv.get("WHEAT", 0) == 0 and shed.get("WHEAT", 0) > 0:
                action = ["PICKUP", "WHEAT", 1]
            elif (not gdict.get("fed_today", True)) and inv.get("WHEAT", 0) > 0:
                action = ["FEED"]
            elif not gdict.get("cared_today", True):
                action = ["CARE"]
            elif gdict.get("yield_units", 0) >= 2:
                action = ["HARVEST"]
            # else: fully serviced -> fall through to carrot work.

    # 2) Goose is unfed and we are NOT on the coop: go feed it (survival first).
    if action == ["PASS"] and goose and gdict is not None and (not gdict.get("fed_today", True)) and (not on_coop):
        action = [_move_toward(fx, fy, *COOP)]

    # 3) Standing on a carrot tile: harvest / water / plant.
    if action == ["PASS"] and (fx, fy) in CARROT_TILES:
        here = tiles[fy][fx]
        if isinstance(here, dict) and here.get("kind") == "PLANT" and here.get("crop") == CROP:
            age = day - here.get("planted_day", day)
            yu = here.get("yield_units", 0)
            if yu >= 1 and age >= HARVEST_AGE.get(CROP, 99):
                action = ["HARVEST"]
            elif not here.get("watered_today", True) and here.get("consecutive_unwatered", 0) < 2:
                action = ["WATER"]
        elif _is_empty(here) and seeds.get(CROP, 0) > 0 and planted < len(CARROT_TILES):
            action = ["PLANT", CROP]

    # 4) Otherwise: walk toward the nearest unserved carrot tile.
    if action == ["PASS"]:
        tgt = (_nearest(need_harvest, fx, fy)
               or _nearest(need_water, fx, fy)
               or _nearest(need_plant, fx, fy))
        if tgt is not None:
            action = [_move_toward(fx, fy, *tgt)]

    return {"farmer": action, "market": market_orders}
