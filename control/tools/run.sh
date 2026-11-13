#!/bin/bash
# usage: run.sh <bsg> <controller.py> <experiment> <timeout> [hold]
cd "/c/For Claude/buildarena-runs/s02-run3/workspace/control"
export PYTHONIOENCODING=utf-8
uv run python -m besiege_cli run --bsg "$1" --controller "$2" --sandbox "LONE ORB" --controller-timeout "${4:-300}" --post-completion-hold "${5:-1}" --experiment "$3" $EXTRA 2>&1 | grep -v "VIRTUAL_ENV" | grep -E "controller:|Run complete|rror|Traceback|failed|timeout" | tail -${TAILN:-40}
