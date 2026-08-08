#!/usr/bin/env bash
# Package and submit the Kaggriculture agent to Kaggle.
#
# Usage:
#   ./submit.sh "CERES baseline v1: carrot monoculture 2x2"
#   ./submit.sh            # uses the default message below
#
# What it does:
#   1. Gate: local self-play (short + full 720-turn) must PASS, else abort.
#   2. Package main.py + agent.py (+ README.md) into submission.tar.gz.
#   3. Submit via `kaggle competitions submit`.
#   4. Print the status-check command.
set -euo pipefail

cd "$(dirname "$0")"

MESSAGE="${1:-CERES baseline v1: carrot monoculture 2x2}"

# 1) Gate — never submit a bot that can't survive the validation episode.
echo ">> gate: validate.py --short"
. .venv/bin/activate
if ! python validate.py --short >/dev/null 2>&1; then
  echo "GATE FAILED: short smoke test" >&2
  exit 1
fi
echo ">> gate: validate.py (full 720-turn self-play)"
if ! python validate.py >/dev/null 2>&1; then
  echo "GATE FAILED: full self-play" >&2
  exit 1
fi

# 2) Package.
echo ">> packaging submission.tar.gz"
rm -f submission.tar.gz
tar -czf submission.tar.gz main.py agent.py README.md

# 3) Submit.
echo ">> submitting: ${MESSAGE}"
kaggle competitions submit kaggriculture -f submission.tar.gz -m "${MESSAGE}"

# 4) Status.
echo ">> submitted. Poll status with:"
echo "   kaggle competitions submissions kaggriculture"
