# Review — env-file-credentials

Design: `.agent-rfc/designs/env-file-credentials.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 3

Found while building, each verified before it was changed.

1. **The worker's startup note would have printed the secret** (P12). It writes each shadowed value
   with `repr`; recording a credential there as-is would put the key on screen on every start. The
   formatting moved into `runtime.config.shadowed_notes()`, which names a credential and shows a
   setting, and a test plants a key and asserts it appears nowhere.
2. **`doctor`'s `.env` parsing was a third copy** of the loaders' line rules (`no-copy-paste`). The
   standalone loader and `doctor` share `_shared._dotenv_pairs`; the runtime's loader stays its own,
   by the module boundary `_shared.py` documents.
3. **The design named a lever that does not exist** (`secrets-never-on-screen`); so did yesterday's
   `evals-dataset-shapes` records (`test-with-real-data`). Replaced with levers from
   `docs/review-levers.md` — `provenance-and-precedence`, `channel-precedence`; `test-the-contract`
   — in all three records.

## Pass 2 — findings: 0

Every loader of `.env` (`runtime.config.load_env_file`, `_shared._load_dotenv_standalone`) and every
caller (`runtime/worker.py`, `scripts/evals_port.py`, the script entry points through
`_shared._load_dotenv`) checked: each now gives a declared credential precedence and says so by
name. Credential readers (`llm_gateway`, `provider_dispatch`, `cost_router`, the judge) still read
`os.environ`, which now holds the declared value. An empty declaration and a matching shell value
change nothing; non-credential variables keep the old mirror. AgentSmith's own `.env` declares
credentials, and no test that sets a fake key loads it — they run in temporary repositories.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one credential rule per loader, the standalone one pinned to the runtime's by a test; the standalone loader and `doctor` share one `.env` parser; the startup note's wording lives beside the record it reads.
Group 2 · Quality / safety — [x] checked — 17 runtime tests (a stale export loses, said once, `env_overrides` wins, an empty declaration and a matching value change nothing, the note never shows a key) and 7 script tests (standalone with and without YAML, the pin, `doctor`'s two checks); `env_file_credentials` mutations 6/6.
Group 3 · Architecture / hygiene — [x] checked — no dependency; non-credential variables keep the old mirror; CI and deployments, with no `.env`, are untouched.
Group 4 · Process — [x] checked — design before code; CHANGELOG; User Manual (where keys go, `doctor`); DESIGN's config row.
Group 5 · Intuitive UI — [x] checked — one line per overridden key says which file won and how to let the shell win; `doctor` names the file and line.
Group 6 · Signal integrity — [x] checked — a stale exported key no longer reads as a judge that did not answer; the override is reported, never silent.
Group 7 · Auth & session integrity — [x] checked — the declared credential wins over an ambient one, and no credential value is printed, logged or recorded anywhere this change touches.

Tests added: `scripts/test/test_env_file_credentials.py` (7); credential cases in `runtime/test/test_config.py`.
Mutation-checked: `env_file_credentials` 6/6.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` rebuilt.
Gates run: full `pytest` on the staged tree (2327 passed, 10 skipped — on this machine, whose own `.env` declares credentials); `ruff check .`; `mypy` (1.14.1); the self-test's tree and knowledge-graph gates; `agentsmith doctor`'s new section run here (clean).

Levers reviewed: `declared-vs-enforced`, `provenance-and-precedence`, `channel-precedence`, `pin-unremovable-duplicates`, `no-copy-paste`.

KG query: kg:272816049cf7
