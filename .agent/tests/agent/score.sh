#!/usr/bin/env bash
# Append one eval result to results.csv
# Usage: score.sh <setup> <case> <pass|fail> <retries> <interventions> [notes]
# setup examples: baseline | superpowers | +skills | +guardrails | full
set -euo pipefail
F="$(dirname "$0")/results.csv"
[[ -f "$F" ]] || echo "date,setup,case,result,retries,human_interventions,notes" > "$F"
echo "$(date +%F),$1,$2,$3,$4,$5,\"${6:-}\"" >> "$F"
echo "recorded -> $F"
