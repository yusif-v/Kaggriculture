#!/usr/bin/env bash
# Package and submit the Kaggriculture agent to Kaggle.
#
# Usage:
#   ./submit.sh "CERES v4.1: hands + animals + fertilizer"        # gated
#   ./submit.sh "CERES v4.1: hands + animals + fertilizer" --force  # skip $25k gate
#
# What it does:
#   1. Gate A: validate.py --short must PASS (survives the validation episode).
#   2. Gate B: local 720-turn self-play mean must be >= 25000 coins (user's floor),
#      unless --force is given. This prevents shipping a bot that regressed below
#      the agreed local bar.
#   3. Package main.py + agent.py (+ README.md) into submission.tar.gz.
#   4. Submit via `kaggle competitions submit`.
#   5. Print the status-check command.
set -euo pipefail

cd "$(dirname "$0")"

MESSAGE="${1:-CERES v4.1: hands + animals + fertilizer}"
FORCE=0
[[ "${2:-}" == "--force" ]] && FORCE=1

. .venv/bin/activate

# 1) Gate A — short smoke test.
echo ">> gate: validate.py --short"
if ! python validate.py --short >/dev/null 2>&1; then
  echo "GATE FAILED: short smoke test" >&2
  exit 1
fi

# 2) Gate B — local self-play floor (>= 25k unless --force).
echo ">> gate: local 720-turn self-play mean >= 25000"
if [[ "$FORCE" -eq 0 ]]; then
  MEAN=$(python - <<'PY'
from kaggle_environments import make
from agent import agent
env=make("kaggriculture",configuration={"episodeSteps":720}); env.run([agent,agent])
a=env.steps[-1][0].observation.farms[0]["money"]; b=env.steps[-1][1].observation.farms[1]["money"]
print(round((a+b)/2))
PY
)
  if (( MEAN < 25000 )); then
    echo "GATE FAILED: local self-play mean ${MEAN} < 25000 (use --force to override)" >&2
    exit 1
  fi
  echo ">> local self-play mean: ${MEAN}  (ok)"
else
  echo ">> --force given: skipping 25k local gate"
fi

# 3) Package.
echo ">> packaging submission.tar.gz"
rm -f submission.tar.gz
tar -czf submission.tar.gz main.py agent.py README.md

# 4) Submit.
echo ">> submitting: ${MESSAGE}"
kaggle competitions submit kaggriculture -f submission.tar.gz -m "${MESSAGE}"

# 5) Status.
echo ">> submitted. Poll status with:"
echo "   kaggle competitions submissions kaggriculture"
