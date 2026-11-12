#!/usr/bin/env bash
# .github/scratch-tenants/date-fixtures.sh <agenticframework dir> — date a profile's
# evidence when the scratch tenant is built, so the fixture never ages
# (.agent-rfc/designs/scratch-dates-and-worktree-tokens.md).
#
# A drill counts only if it was run, so never from the future (the 4.1.0 release
# review, R18), and a recurring signature expires on the catalogue's period (R15), so
# one dated in the fixture lapses on its own (the second pass, P2-R24). Each drill's
# `at` and each attestation's `attested_at` become now; `expires_at` is left as
# written, so the catalogue's period decides.
set -euo pipefail

dir="${1:?usage: date-fixtures.sh <agenticframework dir>}"
python3 - "$dir" <<'PY'
import datetime, json, sys
from pathlib import Path

root = Path(sys.argv[1])
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
for drill in sorted((root / "drills").glob("*.json")):
    record = json.loads(drill.read_text(encoding="utf-8"))
    record["at"] = now
    drill.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
signatures = root / "attestations.jsonl"
if signatures.is_file():
    lines = [json.loads(line) for line in signatures.read_text(encoding="utf-8").splitlines() if line.strip()]
    for record in lines:
        record["attested_at"] = now
    signatures.write_text("".join(json.dumps(record) + "\n" for record in lines), encoding="utf-8")
PY
