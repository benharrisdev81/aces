#!/usr/bin/env bash
# Harvest-back protocol — git plumbing (CLAUDE.md Responsibility #17).
#
# Builds run in per-build clones of the template repo, so cross-build memory
# (attack-library probes, playbook lessons, build-ledger rows) must flow back
# to the template explicitly. This script does the deterministic git work;
# the orchestrator does the content work (merging entries, dedup) between
# `begin` and `finish`.
#
# Usage (from anywhere inside a build clone, after RETROSPECTIVE.md exists):
#
#   harvest.sh begin
#       Fetch origin/main and create a harvest/<timestamp> branch in a
#       .harvest/ worktree. The build clone's own working tree is never
#       touched. Then merge this build's NEW entries into:
#         .harvest/pipeline-state/attack-library.md   (end of each shard)
#         .harvest/pipeline-state/playbook.md         (end of file)
#         .harvest/pipeline-state/build-ledger.md     (one new table row)
#       Dedup against the fetched versions — the template may have advanced
#       since this clone was cut.
#
#   harvest.sh finish "<one-line build summary>"
#       Verify only the three harvestable files changed, commit, push, and
#       open a PR against main. Any other file in the diff aborts the
#       harvest — build artifacts never flow back to the template.
#
#   harvest.sh abort
#       Remove the worktree and delete the local harvest branch.

set -euo pipefail

die() { echo "harvest.sh: $*" >&2; exit 1; }

REPO_ROOT="$(git rev-parse --show-toplevel)" || die "not inside a git repository"
WORKTREE="$REPO_ROOT/.harvest"
BRANCH_FILE="$WORKTREE/.harvest-branch"

ALLOWED_FILES=(
  "pipeline-state/attack-library.md"
  "pipeline-state/playbook.md"
  "pipeline-state/build-ledger.md"
)

cmd_begin() {
  [ -e "$WORKTREE" ] && die "a harvest is already in progress ($WORKTREE exists); finish or abort it first"
  git -C "$REPO_ROOT" fetch origin main
  local branch="harvest/$(date -u +%Y-%m-%dT%H%M%SZ)"
  git -C "$REPO_ROOT" worktree add "$WORKTREE" -b "$branch" origin/main
  echo "$branch" > "$BRANCH_FILE"
  cat <<EOF
Harvest worktree ready: $WORKTREE   (branch $branch, from origin/main)

Next: merge this build's NEW entries into the worktree's copies of
  ${ALLOWED_FILES[0]}
  ${ALLOWED_FILES[1]}
  ${ALLOWED_FILES[2]}
dedup-checking against those fetched versions (a duplicate increments the
existing entry's Seen: count instead of being re-added; append-only and
stable-first ordering apply). Then run:
  $0 finish "<one-line build summary>"
EOF
}

cmd_finish() {
  local summary="${1:-}"
  [ -n "$summary" ] || die "usage: harvest.sh finish \"<one-line build summary>\""
  [ -d "$WORKTREE" ] || die "no harvest in progress (run: harvest.sh begin)"
  local branch
  branch="$(cat "$BRANCH_FILE" 2>/dev/null)" || die "missing $BRANCH_FILE; aborting"

  # Everything changed in the worktree, tracked or not (minus our marker).
  local changed
  changed="$(git -C "$WORKTREE" status --porcelain | awk '{print $NF}' | grep -v '^\.harvest-branch$' || true)"
  [ -n "$changed" ] || die "nothing to harvest — no files changed in $WORKTREE"

  local offenders=""
  while IFS= read -r f; do
    case " ${ALLOWED_FILES[*]} " in
      *" $f "*) ;;
      *) offenders="$offenders  $f"$'\n' ;;
    esac
  done <<< "$changed"
  [ -z "$offenders" ] || die "non-harvestable files in the diff — build artifacts must not flow back to the template:
$offenders"

  git -C "$WORKTREE" add "${ALLOWED_FILES[@]}"
  git -C "$WORKTREE" commit -m "harvest: $summary"
  git -C "$WORKTREE" push -u origin "$branch"

  local stat
  stat="$(git -C "$WORKTREE" diff origin/main.."$branch" --stat | sed 's/^/    /')"
  if command -v gh >/dev/null 2>&1; then
    local body_file
    body_file="$(mktemp)"
    cat > "$body_file" <<EOF
## Build harvest

$summary

Deltas returned from a per-build clone via the harvest-back protocol
(CLAUDE.md Responsibility #17):

$stat

### Reviewer checklist (this merge is the dedup/quality backstop)
- [ ] New probes/lessons are genuinely novel — duplicates should increment \`Seen:\` on the existing entry instead
- [ ] Entries are appended at the end of their shard/file (stable-first ordering preserved; nothing reordered or rewritten)
- [ ] No probe was weakened or retired (retirement is template-author-only)
- [ ] Build-ledger row is consistent with the final eval report
EOF
    gh pr create --base main --head "$branch" \
      --title "Harvest: $summary" \
      --body-file "$body_file"
    rm -f "$body_file"
  else
    echo "gh not found — branch '$branch' is pushed; open the PR manually."
  fi

  git -C "$REPO_ROOT" worktree remove --force "$WORKTREE"
  echo "Harvest complete: branch $branch pushed; worktree removed."
}

cmd_abort() {
  [ -d "$WORKTREE" ] || die "no harvest in progress"
  local branch
  branch="$(cat "$BRANCH_FILE" 2>/dev/null || true)"
  git -C "$REPO_ROOT" worktree remove --force "$WORKTREE"
  [ -n "$branch" ] && git -C "$REPO_ROOT" branch -D "$branch" || true
  echo "Harvest aborted; worktree removed${branch:+ and branch $branch deleted}."
}

case "${1:-}" in
  begin)  cmd_begin ;;
  finish) shift; cmd_finish "${1:-}" ;;
  abort)  cmd_abort ;;
  *) die "usage: harvest.sh {begin|finish \"<summary>\"|abort}" ;;
esac
