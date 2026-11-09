# Review: scratch-wait-survives-red-run

Found on `main` after `.agent-rfc/designs/scratch-profile-expects-ungraded.md` merged: `python-dubai-gov` still failed, with no message.

## Pass 1 — findings: 2

Against `docs/review-levers.md`, and the log of run 42578775473.

1. **The wait step aborted on a red tenant run.** The runner adds `-e`, so `gh run watch --exit-status` ended the step before `rc=$?`. `expect-ungraded.sh` never ran, and the step's own diagnostics have never printed on a red run. Fixed with `|| rc=$?`.
2. **The same line was in the `adopted` job.** Fixed there too.

The earlier review missed this because its tests ran the script alone. Nothing ran the step that calls it.

## Pass 2 — findings: 0

- New tests run the real step text from the workflow under `bash -e` against a fake `gh`: a red run reaches its report; a red run reaches the refusal check and passes on the expected refusal; and it stays red when the refusal is not the reason. Another holds every `gh run watch` line in the file.
- With the fix removed by hand, all four fail.
- Other commands in the step were read for the same fault: the `id=` lookup sits inside `if !`, and `[ -n "$id" ] && break` does not trip `-e`.
- `scripts/test/test_scratch_tenants.py` passes whole.

Not proven until this reaches `main`: the job runs there and not on a pull request.

## Sign-off

Group 1 · DRY & shared code — [x] checked — the same two-line form in both jobs that wait.
Group 2 · Quality / safety — [x] checked — `rc` starts at 0 and is set only by a failing watch.
Group 3 · Architecture / hygiene — [x] checked — no new file; one workflow and its test.
Group 4 · Process — [x] checked — design first; the tenant's run is the requirement.
Group 5 · Intuitive UI — [x] n/a — no screen changes.
Group 6 · Signal integrity — [x] checked — a red tenant run now reports why, and is still a failure unless the expected refusal is the reason.
Group 7 · Auth & session integrity — [x] n/a — no auth or session code.

Tests added: four in `scripts/test/test_scratch_tenants.py`.
Mutation-checked: yes, by hand; the fix removed, all four fail.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: `scripts/test/test_scratch_tenants.py`; ruff; YAML parse; the process gate and knowledge-graph check against the commit.

Levers reviewed: `implemented-not-invoked`, `grep-for-siblings`, `failure-is-not-a-result`.

KG query: kg:35c3f7a4ffa2
