# Review — an installed machine has what `tenant init` and `tenant adopt` need

Design: `.agent-rfc/designs/installed-architectures.md`. Every finding here came from one run:
adopting a real scratch tenant with the installed `agentsmith`, 2026-09-23, which is the first
time either command ran outside a checkout.

**Built evidence (2026-09-23):**

- **Three defects, each invisible to the test suite**, because every test and rehearsal set
  `AGENTSMITH_DIR` to the checkout:
  1. `templates/architectures.yaml` is not installed, so `--architecture` fails on an installed
     machine — for `tenant init` as much as for `adopt` — and failed as a traceback;
  2. **`.githooks/` is not installed either, and the release does not carry it.** The adopted
     tenant's `.githooks/` was empty, `core.hooksPath` pointed at it, and the next commit to
     gated code went in unchecked. A hooks path overrides `.git/hooks`, so such a tenant has
     neither the gates nor the machine's hooks. True for every installed machine since G7;
  3. `adopt` gated `scripts/**` in a vendored tenant, which is AgentSmith's own code — the next
     re-vendoring would have needed a design and a review of framework code.
- **Failing tests first** for each: `scripts/test/test_installer_templates.py` (5),
  `runtime/test/test_cli.py` (+3), `scripts/test/test_tenant_adopt.py` (+1),
  `scripts/test/test_release_artifact_contract.py` (githooks.tar.gz).
- **The journey, twice, with the installed CLI**, after re-running the installer: a TypeScript
  scratch tenant and a Go one, each built by `.github/scratch-tenants/build.sh` and committed as
  the workflow does. Both: the plan gates only the tenant's own code and names the vendored
  directories it left out; the adoption commit goes in with
  `ℹ️ Review: n/a: generated scaffold — 9 gated file(s) match …`; the next change to `src/` and
  to `calc/` is refused for a missing `Design:`; `docs/DESIGN.md` carries the chosen style with
  the repository's own source root (`calc/domain/`, not `internal/domain/`).

## Pass 1 — findings: 1

- `environment-parity` — **finding:** the suite could not have caught any of the three, because
  `AGENTSMITH_DIR` pointed at a checkout everywhere. The two new installer tests read
  `install-ai-stack.sh` and `release.yml` as text, so they hold regardless of the machine they
  run on, and `test_an_empty_framework_never_arms_an_empty_hooks_directory` builds a framework
  directory with nothing in it. The gap that remains — a test that installs to a temp HOME and
  provisions a tenant from it — exists already in `test_scratch_tenants.py`'s `install` fixture,
  which builds the machine layout by hand; it would have missed these too, because it copies what
  the fixture author knew about rather than what the installer copies. Recorded as a stated limit.

## Pass 2 — findings: 0

The diff, the installer's two new blocks, the release step, and both journeys. Considered and
declined:

- Having `install_gate_hooks` fall back to copying from the checkout when the install lacks the
  hooks. That is the silent path that hid this for weeks; refusing, and naming the fix, is what
  makes a broken install visible.
- Gating a vendored directory when the tenant has edited it. A tenant that edits vendored
  framework code has a problem the gates cannot fix, and `hooks/post-checkout` already warns.

**Stated limits:**

- no test installs to a temporary HOME and provisions from it, so a fourth missing piece would
  surface the same way these did — by running it. The two text-reading tests cover the two
  directories the commands need today;
- `tenant adopt` has still never run its gates workflow on GitHub: that needs a repository with
  the `AGENTSMITH_READ_TOKEN` secret, which is the owner's to set.

## Pass 3 — findings: 2

From the mutation runs over the new guards.

- `test-that-cannot-fail` — **finding:** two installer mutations survived: the tests asserted the
  path appeared *anywhere* in `install-ai-stack.sh`, which the comment above each copy satisfies.
  They now look for a `cp` line naming it, and both mutations are caught.
- `test-that-pins-a-defect` — **finding:** `adopt`'s plan-time refusal had no test — only
  `install_gate_hooks`'s did — so "adopt writes over a repository even when the gates cannot be
  armed" survived. `test_adopt_refuses_when_the_install_cannot_arm_the_gates` covers it, and the
  mutation applied by hand against that test is caught.

**Mutation runs:** `installed_machine` 4/4 caught after the test fix; `tenant_adopt` 20 mutations,
19 caught on the run, the survivor above fixed and re-checked by hand against its new test.

## Pass 4 — findings: 0

The two test fixes, the new refusal test, and the catalogue entries that pin them.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — command-line output, read in each case
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      scripts/test/test_installer_templates.py (5), runtime/test/test_cli.py (+3),
                          scripts/test/test_tenant_adopt.py (+2),
                          scripts/test/test_release_artifact_contract.py (githooks.tar.gz)
Mutation-checked:          yes — installed_machine (4, all caught) and tenant_adopt (20; one survivor
                          fixed and re-checked)
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:797f774a4bb1
Gates run locally:         ruff, the suites above, the full pytest run, and both journeys with the
                          installed CLI after re-running install-ai-stack.sh
Declared gaps:             (1) no test provisions from a temp-HOME install; (2) the gates workflow has
                              not yet run on GitHub
```
