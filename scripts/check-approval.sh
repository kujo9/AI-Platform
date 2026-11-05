#!/usr/bin/env bash
# Checks that every role in model/approvals.yaml has approved a model version, in a commit.
#   bash scripts/check-approval.sh <revision>
# Exit 0: approved. Exit 1: an approval is missing. canary.sh start runs it before a canary.
# Run from the repository's main folder.
set -euo pipefail

[ -f model/approvals.yaml ] || { echo "Run from the repository's main folder."; exit 1; }
rev=${1:-}
[ ${#rev} = 40 ] || { echo "Usage: bash scripts/check-approval.sh <40-character revision>"; exit 1; }

file=model/approvals/$rev.yaml
# Only committed approvals count: a line someone typed into the file is not an approval.
if [ -f "$file" ] && ! git diff --quiet HEAD -- "$file" 2>/dev/null; then
  echo "$file has changes that are not committed. Use scripts/approve.sh."; exit 1
fi

missing=0
for role in $(sed -n 's/^  - \([a-z0-9-]*\).*/\1/p' model/approvals.yaml); do
  line=$(git show "HEAD:$file" 2>/dev/null | grep "^$role:" || true)
  if [ -n "$line" ]; then echo "ok       $line"; else echo "MISSING  $role"; missing=1; fi
done
if [ "$missing" = 0 ]; then
  echo "Approved: $rev"
else
  echo "Not approved yet: $rev. Each missing role runs: bash scripts/approve.sh $rev <role> \"<name>\""
fi
exit "$missing"
