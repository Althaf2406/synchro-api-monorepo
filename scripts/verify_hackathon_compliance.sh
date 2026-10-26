#!/usr/bin/env bash
set -euo pipefail

echo "====================================================================="
echo "  SYNCHRO-API: META GLOBAL AI HACKATHON COMPLIANCE AUDITOR           "
echo "  Allowed Coding Window: 2026-10-27T00:00:00 to 2026-11-04T23:59:59  "
echo "====================================================================="

PRE_HACKATHON_COMMITS=$(git log --until="2026-10-26T23:59:59" --oneline -- hackathon_core_engine/ | wc -l | tr -d ' ')

if [ "$PRE_HACKATHON_COMMITS" -ne 0 ]; then
  echo "[FAIL] Found $PRE_HACKATHON_COMMITS commits in hackathon_core_engine/ prior to Oct 27, 2026!"
  exit 1
fi

echo "[PASS] Zero commits in hackathon_core_engine/ prior to Oct 27, 2026."
echo ""
echo "--- Commit Timeline in hackathon_core_engine/ (Oct 27 - Nov 4, 2026) ---"
git log --since="2026-10-27T00:00:00" --pretty=format:"%h | %ad | %s" --date=iso -- hackathon_core_engine/
echo ""
echo ""
echo "--- Lines of Pure Hackathon Code Written ---"
git log --since="2026-10-27T00:00:00" --numstat --pretty="" -- hackathon_core_engine/ | \
  awk '{added+=$1; deleted+=$2} END {printf "Total Lines Added: %d | Deleted: %d\n", added, deleted}'
echo "====================================================================="
