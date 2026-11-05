#!/usr/bin/env bash
# Records one approval of a model version, as a Git commit that you push.
#   bash scripts/approve.sh <revision> <role> "<your name>"
# The roles that must approve are in model/approvals.yaml. Each approval is one line in
# model/approvals/<revision>.yaml: the role, who approved, and when. Git also keeps who made the
# commit. Approve only after you checked what your role checks (05-model-pipeline).
# Run from the repository's main folder.
set -euo pipefail

[ -f model/approvals.yaml ] || { echo "Run from the repository's main folder."; exit 1; }
rev=${1:-}; role=${2:-}; who=${3:-}
if [ ${#rev} != 40 ] || [ -z "$role" ] || [ -z "$who" ]; then sed -n '3p' "$0"; exit 1; fi

roles=$(sed -n 's/^  - \([a-z0-9-]*\).*/\1/p' model/approvals.yaml)
echo "$roles" | grep -qx -- "$role" || { echo "Unknown role '$role'. The roles in model/approvals.yaml:"; echo "$roles"; exit 1; }

file=model/approvals/$rev.yaml
if grep -q "^$role:" "$file" 2>/dev/null; then
  echo "$role has already approved $rev:"; grep "^$role:" "$file"; exit 1
fi
mkdir -p model/approvals
[ -f "$file" ] || echo "# Approvals of the model revision $rev (scripts/approve.sh)" > "$file"
echo "$role: $who, $(date -u +%Y-%m-%dT%H:%MZ)" >> "$file"
git add "$file"
git commit -q -m "approve $rev: $role ($who)" -- "$file"
echo "Committed: $role approved $rev. Push it: git push"
echo
bash scripts/check-approval.sh "$rev" || true
