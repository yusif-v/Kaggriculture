#!/usr/bin/env python3
"""Kaggriculture agent — repo: Kaggriculture.

CERES strategy v4: v3's 5-hand crop engine PLUS a 3-animal herd (goose + cow +
sheep) handled by an explicit FARMER state machine. Target: >= $25,000 local
self-play (user's gate).

Why animals are the only path to a big jump (rival forensics, all 17 ladder
games): every bot that crushed us ran 12-16 hands AND animals (Daniel Wu
100,093, Mason 79,979, JTHEFROG 12,590). v3 had 5 hands + 1 goose only. Raw
hand-count alone is saturated (v3's 5 hands ~= 8 hands; 12 hands bled cash on
fib hire cost ~$376/day and collapsed to ~$1.6k). Animal products are
price-resilient (WOOL above_target 3.20 / $200 base, MILK 1.60 / $160, EGG
0.20 / $50) vs crops that glut.

The v4 failure mode in earlier attempts: feeding needs a unit WITH WHEAT
standing on the animal tile, but a shared greedy scheduler split "PICKUP wheat
at coop" from "FEED at animal" across different units, so neither completed and
animals starved. Fix = the FARMER runs a deterministic per-turn state machine
for all 3 animals (it spawns on the coop (4,4) daily, adjacent to every animal
tile), and only falls back to crop work when no animal needs it. Hands never
touch animals, so there is no task conflict.

Mechanics (verified against kaggriculture.py):
  * HIRE -> hand appears NEXT turn; hands_actions length == len(farm["hands"]).
  * Shed-access tiles = (4,4),(5,4),(4,5),(5,5); only (4,4) is NW (unlocked day
    1). PICKUP works only there. Pastures on NW-adjacent (3,4)/(4,3).
  * FEED consumes 1 WHEAT from the UNIT's inventory. Escape after 2 consecutive
    unfed days => lost animal, so feeding is the top priority every turn.
  * HARVEST on an animal tile collects product (egg/milk/wool) to inventory;
    end-of-day it lands in the shed and is sold. WHEAT is feed stock only.
"""

from typing import Any, Dict, List, Optional, Tuple

CROP_PRIORITY = ["MELON", "STRAWBERRY", "TOMATO", "CARROT"]
SELLABLE = {"CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"}
MAX_MARKET_ORDERS = 10
SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
COOP: Tuple[int, int] = (4, 4)
ANIMAL_TILES = {"GOOSE": (4, 4), "COW": (3, 4), "SHEEP": (4, 3)}
# Crop yield windows (mirrors kaggriculture.py CROPS). The watering bonus window
# for one-time crops is ceil(max_yield_day/2) .. max_yield_day; fertilizing there
# doubles the per-day yield bonus.
CROP_DATA = {
    "WHEAT":      {"max_yield_day": 4,  "ongoing": False},
    "CARROT":     {"max_yield_day": 3,  "ongoing": False},
    "TOMATO":     {"max_yield_day": 8,  "ongoing": True},
    "STRAWBERRY": {"max_yield_day": 10, "ongoing": True},
    "MELON":      {"max_yield_day": 12, "ongoing": False},
}

MAX_HANDS = 8
SAFE_PER_UNIT = 6
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


def _manhattan(fx: int, fy: int, tx: int, ty: int) -> int:
    return abs(fx - tx) + abs(fy - ty)


# v4.1: each hired hand is pinned to a HOME QUADRANT so plants stay local and
# watering/harvest walks shrink (the top bots' effective play). Farmer stays NW.
def _quad_of(x: int, y: int) -> str:
    if x < 5 and y < 5:
        return "NW"
    if x >= 5 and y < 5:
        return "NE"
    if x < 5 and y >= 5:
        return "SW"
    return "SE"


HOME_QUADS = ["NW", "NE", "SW", "SE"]


def agent(obs: Dict[str, Any]) -> Dict[str, Any]:
    p = obs["player"]
    farm = obs["farms"][p]
    priv = obs["private"]
    tiles = farm["tiles"]
    board = len(tiles)
    fx, fy = farm["farmer"]
    day = obs["day"]
    money = farm["money"]
    shed = priv["shed"]
    seeds = priv["seeds"]
    inventories = priv.get("inventories") or [{}]
    farmer_inv = inventories[0] if inventories else {}
    hands = farm.get("hands", [])
    hires_today = farm.get("hires_today", 0)
    unlocked = set(farm.get("unlocked_quadrants", ["NW"]))

    planted = 0
    for _row in tiles:
        for _t in _row:
            if isinstance(_t, dict) and _t.get("kind") == "PLANT":
                planted += 1

    present = {}
    for kind, (ax, ay) in ANIMAL_TILES.items():
        if 0 <= ay < board and 0 <= ax < board:
            t = tiles[ay][ax]
            if isinstance(t, dict) and t.get("animal") == kind:
                present[kind] = t
    num_animals = len(present)

    market_orders: List[List] = []

    # ---- sell harvestable; RESERVE wheat as feed (never sell the buffer) ----
    wheat_buffer = num_animals * 2 + 4
    for item, qty in shed.items():
        if qty > 0 and item in SELLABLE and len(market_orders) < MAX_MARKET_ORDERS:
            market_orders.append(["SELL", item, int(qty)])
    if shed.get("WHEAT", 0) > wheat_buffer and len(market_orders) < MAX_MARKET_ORDERS:
        market_orders.append(["SELL", "WHEAT", int(shed["WHEAT"] - wheat_buffer)])

    # ---- capacity + hired hands ----
    units = 1 + len(hands)
    capacity = units * SAFE_PER_UNIT
    if (hires_today < MAX_HANDS and money > 400
            and len(market_orders) < MAX_MARKET_ORDERS):
        market_orders.append(["HIRE"])

    # ---- land expansion when full ----
    land_order = ["NE", "SW", "SE"]
    land_prices = [1000, 2000, 4000]
    n_extra = len(unlocked) - 1
    if (n_extra < len(land_order) and planted >= capacity - 3
            and money > land_prices[n_extra] + 800
            and len(market_orders) < MAX_MARKET_ORDERS):
        market_orders.append(["BUY_LAND"])

    # ---- seeds up to headroom ----
    headroom = max(0, capacity - planted)
    for crop in CROP_PRIORITY:
        if (seeds.get(crop, 0) == 0 and headroom > 0 and money > SEED_COST[crop] + 100
                and len(market_orders) < MAX_MARKET_ORDERS):
            market_orders.append(["BUY_SEED", crop, min(3, headroom)])

    # ---- animals: buy when affordable + not owned ----
    for kind, cost in ANIMAL_COST.items():
        if (kind not in present and money > cost + 200 and shed.get(kind, 0) == 0
                and len(market_orders) < MAX_MARKET_ORDERS):
            market_orders.append(["BUY_ANIMAL", kind, 1])

    # ---- wheat feed reserve ----
    if shed.get("WHEAT", 0) < wheat_buffer and money > 120 and len(market_orders) < MAX_MARKET_ORDERS:
        market_orders.append(["BUY_PRODUCT", "WHEAT", wheat_buffer - shed.get("WHEAT", 0)])

    # ---------- FARMER ANIMAL STATE MACHINE ----------
    # Returns an action if the farmer should do animal work this turn; else None.
    def farmer_animal() -> Optional[List[str]]:
        for kind, (ax, ay) in ANIMAL_TILES.items():
            if not (0 <= ay < board and 0 <= ax < board):
                continue
            t = tiles[ay][ax]
            if isinstance(t, dict) and t.get("animal") == kind:
                # 1) feed (needs wheat in farmer inventory)
                if not t.get("fed_today", True):
                    if farmer_inv.get("WHEAT", 0) > 0:
                        if (fx, fy) == (ax, ay):
                            return ["FEED"]
                        return [_move_toward(fx, fy, ax, ay)]
                    else:
                        if (fx, fy) == COOP:
                            return ["PICKUP", "WHEAT", 1]
                        return [_move_toward(fx, fy, COOP[0], COOP[1])]
                # 2) care
                if not t.get("cared_today", True):
                    if (fx, fy) == (ax, ay):
                        return ["CARE"]
                    return [_move_toward(fx, fy, ax, ay)]
                # 3) collect fertilizer when available (free yield later)
                if t.get("fertilizer_available", False):
                    if (fx, fy) == (ax, ay):
                        return ["COLLECT_FERTILIZER"]
                    return [_move_toward(fx, fy, ax, ay)]
                # 4) collect product
                if t.get("yield_units", 0) >= 1:
                    if (fx, fy) == (ax, ay):
                        return ["HARVEST"]
                    return [_move_toward(fx, fy, ax, ay)]
            elif isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE"):
                # structure exists, place the animal
                if shed.get(kind, 0) > 0 and farmer_inv.get(kind, 0) == 0:
                    if (fx, fy) == COOP:
                        return ["PICKUP", kind, 1]
                    return [_move_toward(fx, fy, COOP[0], COOP[1])]
                if farmer_inv.get(kind, 0) > 0:
                    if (fx, fy) == (ax, ay):
                        return ["PLACE", kind]
                    return [_move_toward(fx, fy, ax, ay)]
            elif _is_empty(t) and (fx, fy) == (ax, ay):
                struct = "COOP" if kind == "GOOSE" else "PASTURE"
                return ["BUILD_" + struct]
        return None

    # ---------- CROP TASKS (for farmer fallback + hands) ----------
    # v4.1: tag each plant task with its quadrant so hands only tend their home.
    crop_tasks: List[Dict[str, Any]] = []
    for y in range(board):
        for x in range(board):
            t = tiles[y][x]
            q = _quad_of(x, y)
            if isinstance(t, dict) and t.get("kind") == "PLANT":
                planted += 1
                crop = t.get("crop")
                age = day - t.get("planted_day", day)
                cd = CROP_DATA.get(crop, {})
                myd = cd.get("max_yield_day", 99)
                bonus_lo = (myd + 1) // 2
                in_bonus = not cd.get("ongoing", False) and bonus_lo <= age <= myd
                if t.get("yield_units", 0) >= 1 and age >= HARVEST_AGE.get(crop, 99):
                    crop_tasks.append({"x": x, "y": y, "q": q, "op": "HARVEST"})
                elif in_bonus and not t.get("fertilized_until_day", -1) >= day:
                    crop_tasks.append({"x": x, "y": y, "q": q, "op": "FERTILIZE"})
                elif not t.get("watered_today", True) and t.get("consecutive_unwatered", 0) < 2:
                    crop_tasks.append({"x": x, "y": y, "q": q, "op": "WATER"})
            elif _is_empty(t):
                if planted < capacity and (x, y) not in ANIMAL_TILES.values():
                    for crop in CROP_PRIORITY:
                        if seeds.get(crop, 0) > 0:
                            crop_tasks.append({"x": x, "y": y, "q": q, "op": "PLANT", "crop": crop})
                            planted += 1
                            break

    def _crop_act(tk: Dict[str, Any], inv: Dict[str, int]) -> List[str]:
        if tk["op"] == "HARVEST":
            return ["HARVEST"]
        if tk["op"] == "FERTILIZE":
            return ["FERTILIZE"]
        if tk["op"] == "PLANT":
            return ["PLANT", tk["crop"]]
        return ["WATER"]

    def _assign_crop(ux: int, uy: int, inv: Dict[str, int], home: str = "ANY") -> List[str]:
        def _nearest(home_filter: str) -> Optional[Dict[str, Any]]:
            best, best_d = None, 10 ** 9
            for tk in crop_tasks:
                if home_filter != "ANY" and tk["q"] != home_filter:
                    continue
                if tk["op"] == "FERTILIZE" and inv.get("FERTILIZER", 0) == 0:
                    continue
                d = _manhattan(ux, uy, tk["x"], tk["y"])
                if d < best_d:
                    best_d, best = d, tk
            return best

        # in-place (any quadrant)
        for tk in crop_tasks:
            if (tk["x"], tk["y"]) == (ux, uy):
                if tk["op"] == "FERTILIZE" and inv.get("FERTILIZER", 0) == 0:
                    continue
                return _crop_act(tk, inv)
        # nearest: prefer home quadrant, else fall back to any
        best = _nearest(home) if home != "ANY" else None
        if best is None:
            best = _nearest("ANY")
        if best is None:
            return ["PASS"]
        if _manhattan(ux, uy, best["x"], best["y"]) == 0:
            return _crop_act(best, inv)
        return [_move_toward(ux, uy, best["x"], best["y"])]

    # Farmer: animal work first, else crops (NW only).
    farmer_action = farmer_animal()
    if farmer_action is None:
        farmer_action = _assign_crop(fx, fy, farmer_inv, home="NW")

    hands_actions: List[List[str]] = []
    for hidx, hp in enumerate(hands):
        hinv = inventories[hidx + 1] if hidx + 1 < len(inventories) else {}
        home = HOME_QUADS[hidx % 4]
        hands_actions.append(_assign_crop(hp[0], hp[1], hinv, home=home))

    return {"farmer": farmer_action, "hands": hands_actions, "market": market_orders}
