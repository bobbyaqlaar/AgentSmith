#!/usr/bin/env bash
# A scratch tenant on a compliance profile has no eval data and no in-border
# judge, so the profile must refuse its suites as ungraded. This passes only
# when exactly the named suites were refused, and nothing failed for any other
# reason (.agent-rfc/designs/scratch-profile-expects-ungraded.md).
#
#   expect-ungraded.sh <repo> <run-id> <suite>...
set -uo pipefail

repo="$1"
run="$2"
shift 2
want="$(printf '%s\n' "$@" | sort -u)"

if ! jobs="$(gh run view "$run" -R "$repo" --json jobs --jq \
    '.jobs[] | select(.conclusion != "success" and .conclusion != "skipped") | "\(.databaseId)\t\(.name)"')"; then
  echo "::error::could not read the jobs of run $run on $repo"
  exit 1
fi

status=0
found=""
while IFS=$'\t' read -r job name; do
  [ -n "$job" ] || continue
  if ! log="$(gh run view "$run" -R "$repo" --job "$job" --log-failed)"; then
    echo "::error::could not read the log of \"$name\""
    status=1
    continue
  fi
  suite="$(printf '%s\n' "$log" | sed -n 's/.*not_gradable — no \([a-z_]*\) dataset at .*/\1/p' | head -n 1)"
  if [ -z "$suite" ]; then
    echo "::error::\"$name\" failed for a reason other than an ungraded suite"
    status=1
    continue
  fi
  found="$found$suite"$'\n'
done <<< "$jobs"

got="$(printf '%s' "$found" | sort -u)"
if [ "$got" != "$want" ]; then
  echo "::error::expected the profile to refuse: $(echo "$want" | xargs); it refused: $(echo "$got" | xargs)"
  status=1
fi
[ "$status" -eq 0 ] && echo "the profile refused, as it should: $(echo "$got" | xargs)"
exit "$status"
