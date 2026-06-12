#!/usr/bin/env bash
# One-time evidence collector for backfilling the harvest-back protocol
# across builds that completed BEFORE the protocol existed.
#
# Usage:
#   .claude/scripts/backfill-harvest.sh <build-clone-dir> [<build-clone-dir>...]
#
# For each prior build clone, copies its harvestable evidence into
# .harvest-backfill/<clone-name>/ in this repo and prints what it found.
# This script only collects; it does not write to pipeline-state/. The
# orchestrator then reads the evidence, distills the NEW probes, lessons,
# and one build-ledger row per build, and returns everything through ONE
# combined harvest:
#
#   .claude/scripts/harvest.sh begin
#   ... merge distilled entries into .harvest/pipeline-state/*.md ...
#   .claude/scripts/harvest.sh finish "Backfill: <n> prior builds"
#
# .harvest-backfill/ is gitignored — evidence never lands in the template.

set -euo pipefail

die() { echo "backfill-harvest.sh: $*" >&2; exit 1; }

[ "$#" -ge 1 ] || die "usage: backfill-harvest.sh <build-clone-dir> [<build-clone-dir>...]"

REPO_ROOT="$(git rev-parse --show-toplevel)" || die "not inside a git repository"
DEST_ROOT="$REPO_ROOT/.harvest-backfill"
mkdir -p "$DEST_ROOT"

# Evidence worth distilling, in rough order of value.
EVIDENCE=(
  "pipeline-state/attack-library.md"
  "pipeline-state/playbook.md"
  "pipeline-state/score-history.md"
  "pipeline-state/scoreboard.md"
  "pipeline-state/cost.md"
  "RETROSPECTIVE.md"
  "EVAL_PASS.md"
  "EVAL_UNRECOVERABLE.md"
  "planner_output.md"
)

for clone in "$@"; do
  [ -d "$clone" ] || { echo "SKIP: $clone is not a directory" >&2; continue; }
  name="$(basename "$clone")"
  dest="$DEST_ROOT/$name"
  mkdir -p "$dest/pipeline-state"

  echo "== $name ($clone)"
  found=0
  for f in "${EVIDENCE[@]}"; do
    if [ -f "$clone/$f" ]; then
      cp "$clone/$f" "$dest/$f"
      echo "   collected: $f"
      found=$((found + 1))
    fi
  done
  # Eval reports are per-round; glob them separately.
  for f in "$clone"/eval_report_round_*.md; do
    [ -f "$f" ] || continue
    cp "$f" "$dest/$(basename "$f")"
    echo "   collected: $(basename "$f")"
    found=$((found + 1))
  done
  if [ "$found" -eq 0 ]; then
    echo "   nothing harvestable found — is this a build clone?"
    rmdir "$dest/pipeline-state" "$dest" 2>/dev/null || true
  fi
done

echo
echo "Evidence staged under $DEST_ROOT/."
echo "Next: distill NEW probes/lessons + one build-ledger row per build,"
echo "then return them via harvest.sh begin / finish (one combined PR)."
