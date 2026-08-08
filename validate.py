#!/usr/bin/env python3
"""Self-play validation harness for the Kaggriculture agent.

The Kaggle competition runs a Validation Episode where your agent plays a
copy of itself; if the episode errors, the submission is marked "Error". So a
clean full-length self-play run here is the gating check before submitting.

Usage:
    .venv/bin/python validate.py            # agent vs. agent, full 720 turns
    .venv/bin/python validate.py --short    # quick 200-turn smoke test
    .venv/bin/python validate.py --vs random  # agent vs. built-in random
"""
import argparse
import sys

from kaggle_environments import make

from agent import agent


def run(opponent: str, steps: int):
    if opponent == "random":
        players = [agent, "random"]
    else:
        players = [agent, agent]
    env = make("kaggriculture", configuration={"episodeSteps": steps})
    env.run(players)
    final0 = env.steps[-1][0]
    final1 = env.steps[-1][1]
    status0, status1 = final0.status, final1.status
    rew0, rew1 = final0.reward, final1.reward
    print(f"players     : {players}")
    print(f"steps run   : {len(env.steps)} (configured {steps})")
    print(f"status      : p0={status0} p1={status1}")
    print(f"reward/coin : p0={rew0} p1={rew1}")
    ok = (status0 == "DONE" and status1 == "DONE") and isinstance(rew0, (int, float)) and isinstance(rew1, (int, float))
    print("RESULT      :", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vs", choices=["self", "random"], default="self")
    ap.add_argument("--short", action="store_true", help="run a 200-turn smoke test")
    args = ap.parse_args()
    steps = 200 if args.short else 720
    return run(args.vs, steps)


if __name__ == "__main__":
    sys.exit(main())
