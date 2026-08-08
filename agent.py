#!/usr/bin/env python3
"""Kaggriculture agent — repo: Kaggriculture.

CERES strategy v3: hired farm hands + high-value diverse crops + land
expansion, on top of the v2 goose.

Why v3 looks like this (rival forensics from v1/v2 ladder games):
  * Opponents that beat us 4-5x did it with HIRED HANDS (5-12/day) and
    high-value crops (melon $250, strawberry $120, tomato $60) — often with
    NO land expansion (jps stayed in one quadrant and still won 4x). Hired
    hands are the single biggest lever, because watering is the binding
    constraint: every plant must be watered daily or it weeds, and one farmer
    can only water ~6 tiles/day. More units = more watered tiles = more yield.
  * So v3's core change is a MULTI-UNIT scheduler: the farmer + each hired
    hand is assigned the nearest unserved tile task each turn (water >
    harvest > plant > animal service). The action schema supports it:
    {"farmer": [...], "hands": [[...], ...], "market": [...]}.

Mechanics verified against kaggriculture.py:
  * HIRE is a market order; the hand appears NEXT turn at a shed-adjacent
    tile and persists for the rest of the day. Cost = fib(n) per hire that
    day (1,1,2,3,5,8,...). So hands_actions length must equal
    len(farm["hands"]) THIS turn, not the number we just hired.
  * BUY_LAND unlocks NE ($1k) -> SW ($2k) -> SE ($4k).
  * FEED/CARE/HARVEST on the goose need the unit standing on the coop; FEED
    needs WHEAT in that unit's inventory (PICKUP from the shed first). The
    coop sits on the spawn tile (4,4), which is shed-adjacent, so PICKUP works.
  * One farmer/hand action per turn. Stateless across turns.
"""

from typing import Any, Dict, List, Optional, Tuple

# Plant priority: highest-value first. Diversifying avoids a single-product
# price glut (carrot crashes hardest; melon/strawberry hold value better).
CROP_PRIORITY = ["MELON", "STRAWBERRY", "TOMATO", "CARROT"]
SELLABLE = {
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL", "FERTILIZER",
}
MAX_MARKET_ORDERS = 10
SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
GOOSE_COST = 300
MAX_HANDS = 5            # cap daily hires (fib: 1+1+2+3+5 = 12/day at 5 hands)
HARVEST_AGE = {"WHEAT": 4, "CARROT": 3, "MELON": 10}
COOP: Tuple[int, int] = (4, 4)   # coop on spawn so the farmer starts each day on it


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

    # Current living plant count (used by capacity-driven hiring/land/seed logic).
    planted = 0
    for _row in tiles:
        for _t in _row:
            if isinstance(_t, dict) and _t.get("kind") == "PLANT":
                planted += 1

    market_orders: List[List] = []

    # ---- sell everything harvestable in the shed ----
    for item, qty in shed.items():
        if qty > 0 and item in SELLABLE and len(market_orders) < MAX_MARKET_ORDERS:
            market_orders.append(["SELL", item, int(qty)])

    # ---- capacity: how many tiles our units can keep watered ----
    # A unit tending a DENSE cluster waters ~6 tiles/day (short walks). Planting
    # beyond capacity just creates weeds.
    units = 1 + len(hands)
    SAFE_PER_UNIT = 6
    capacity = units * SAFE_PER_UNIT

    # ---- hire hands (primary lever): build the workforce early ----
    # Rivals that win run 5-12 hands. Cost is fib (1,1,2,3,5 = 12/day at 5); cheap
    # vs the yield. Hire every day up to MAX_HANDS while we can still afford seeds.
    if (hires_today < MAX_HANDS and money > 400
            and len(market_orders) < MAX_MARKET_ORDERS):
        market_orders.append(["HIRE"])

    # ---- land expansion, only when the current land is basically full ----
    land_order = ["NE", "SW", "SE"]
    land_prices = [1000, 2000, 4000]
    n_extra = len(unlocked) - 1
    if (n_extra < len(land_order) and planted >= capacity - 3
            and money > land_prices[n_extra] + 800
            and len(market_orders) < MAX_MARKET_ORDERS):
        market_orders.append(["BUY_LAND"])

    # ---- seed procurement, only up to planting headroom ----
    # Headroom = capacity - planted (tiles we could responsibly plant). Buy a few
    # seeds per priority crop, but never stockpile beyond what we can plant.
    headroom = max(0, capacity - planted)
    for crop in CROP_PRIORITY:
        if (seeds.get(crop, 0) == 0 and headroom > 0 and money > SEED_COST[crop] + 100
                and len(market_orders) < MAX_MARKET_ORDERS):
            market_orders.append(["BUY_SEED", crop, min(3, headroom)])

    # ---- goose coop + a small wheat buffer for feeding ----
    g = tiles[COOP[1]][COOP[0]] if (0 <= COOP[1] < board and 0 <= COOP[0] < board) else None
    goose = isinstance(g, dict) and g.get("animal") == "GOOSE"
    coop_built = isinstance(g, dict) and g.get("kind") == "COOP"
    if not goose and money > GOOSE_COST and shed.get("GOOSE", 0) == 0 and len(market_orders) < MAX_MARKET_ORDERS:
        market_orders.append(["BUY_ANIMAL", "GOOSE", 1])
    if shed.get("WHEAT", 0) < 2 and money > 120 and len(market_orders) < MAX_MARKET_ORDERS:
        market_orders.append(["BUY_PRODUCT", "WHEAT", 2])

    # ---- build the task list across all tiles ----
    # task = dict(kind, x, y, crop?, needs_inv?)
    tasks = []
    for y in range(board):
        for x in range(board):
            t = tiles[y][x]
            if isinstance(t, dict) and t.get("animal") == "GOOSE" and (x, y) == COOP:
                if not t.get("fed_today", True) and farmer_inv.get("WHEAT", 0) == 0 and shed.get("WHEAT", 0) > 0:
                    tasks.append({"kind": "PICKUP_WHEAT", "x": x, "y": y})
                elif not t.get("fed_today", True) and (farmer_inv.get("WHEAT", 0) > 0 or shed.get("WHEAT", 0) > 0):
                    tasks.append({"kind": "FEED", "x": x, "y": y})
                elif not t.get("cared_today", True):
                    tasks.append({"kind": "CARE", "x": x, "y": y})
                elif t.get("yield_units", 0) >= 2:
                    tasks.append({"kind": "HARVEST_EGG", "x": x, "y": y})
            elif isinstance(t, dict) and t.get("kind") == "PLANT":
                planted += 1
                age = day - t.get("planted_day", day)
                if t.get("yield_units", 0) >= 1 and age >= HARVEST_AGE.get(t.get("crop"), 99):
                    tasks.append({"kind": "HARVEST", "x": x, "y": y})
                elif not t.get("watered_today", True) and t.get("consecutive_unwatered", 0) < 2:
                    tasks.append({"kind": "WATER", "x": x, "y": y})
            elif _is_empty(t):
                # plant the highest-value crop we have a seed for, but only up to
                # capacity (don't create weeds we can't water).
                if planted < capacity and (x, y) != COOP:
                    for crop in CROP_PRIORITY:
                        if seeds.get(crop, 0) > 0:
                            tasks.append({"kind": "PLANT", "x": x, "y": y, "crop": crop})
                            planted += 1
                            break

    # Build/place goose coop counts as a task on the coop tile.
    if not goose and not coop_built and (fx, fy) == COOP:
        tasks.append({"kind": "BUILD_COOP", "x": COOP[0], "y": COOP[1]})
    elif not goose and coop_built:
        if shed.get("GOOSE", 0) > 0 and farmer_inv.get("GOOSE", 0) == 0:
            tasks.append({"kind": "PICKUP_GOOSE", "x": COOP[0], "y": COOP[1]})
        elif farmer_inv.get("GOOSE", 0) > 0:
            tasks.append({"kind": "PLACE_GOOSE", "x": COOP[0], "y": COOP[1]})

    claimed = set()  # (x,y) claimed by a task already

    def _assign_unit(ux: int, uy: int, uinv: Dict[str, int]) -> List[str]:
        """Greedy: act on the tile we're standing on, else walk to nearest task."""
        # 1) Act in place.
        here_task = None
        for tk in tasks:
            if (tk["x"], tk["y"]) == (ux, uy) and (tk["x"], tk["y"]) not in claimed:
                here_task = tk
                break
        if here_task is not None:
            claimed.add((ux, uy))
            return _task_action(here_task, uinv)
        # 2) Nearest unclaimed task.
        best, best_d = None, 10 ** 9
        for tk in tasks:
            if (tk["x"], tk["y"]) in claimed:
                continue
            d = _manhattan(ux, uy, tk["x"], tk["y"])
            if d < best_d:
                best_d, best = d, tk
        if best is None:
            return ["PASS"]
        claimed.add((best["x"], best["y"]))
        if best_d == 0:
            return _task_action(best, uinv)
        return [_move_toward(ux, uy, best["x"], best["y"])]

    def _task_action(tk: Dict[str, Any], uinv: Dict[str, int]) -> List[str]:
        k = tk["kind"]
        if k == "WATER":
            return ["WATER"]
        if k == "HARVEST":
            return ["HARVEST"]
        if k == "PLANT":
            return ["PLANT", tk["crop"]]
        if k == "BUILD_COOP":
            return ["BUILD_COOP"]
        if k == "PICKUP_GOOSE":
            return ["PICKUP", "GOOSE", 1]
        if k == "PLACE_GOOSE":
            return ["PLACE", "GOOSE"]
        if k == "PICKUP_WHEAT":
            return ["PICKUP", "WHEAT", 1]
        if k == "FEED":
            return ["FEED"]
        if k == "CARE":
            return ["CARE"]
        if k == "HARVEST_EGG":
            return ["HARVEST"]
        return ["PASS"]

    # ---- assign farmer + each hand ----
    farmer_action = _assign_unit(fx, fy, farmer_inv)
    hands_actions: List[List[str]] = []
    for hidx, hp in enumerate(hands):
        hinv = inventories[hidx + 1] if hidx + 1 < len(inventories) else {}
        hands_actions.append(_assign_unit(hp[0], hp[1], hinv))

    return {"farmer": farmer_action, "hands": hands_actions, "market": market_orders}
