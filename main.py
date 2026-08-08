#!/usr/bin/env python3
"""Kaggriculture submission entry point.

Kaggle imports `main` and calls `agent(obs)` each turn. The actual strategy
lives in `agent.py` (the single source of truth); we re-export it here so the
submission is a clean multi-file package (main.py + agent.py) without
duplicating logic.

Caveats enforced by the harness (do not break these):
  * `agent` must be import-safe and stateless across turns — the harness may
    re-import the module per episode.
  * Only stdlib imports at module scope (kaggle_environments is provided server-side).
"""
from agent import agent

__all__ = ["agent"]
