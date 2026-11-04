# AgentSmith — Remaining To-Do Items

**Last reviewed:** 2026-11-03: every entry checked against the code and CI. What that closed is in
`docs/PRODUCT_ARCHIVE.md`.

> **Scope:** this document owns only *not-yet-done* work. Completed build history lives in
> `docs/PRODUCT_ARCHIVE.md`; the formal specification is `docs/DESIGN.md`; operator procedures are
> `docs/UserManual.md`; release notes are `CHANGELOG.md`.
>
> If an entry here says something is missing, check it still is. On 2026-11-03 this file said "the release
> install works for anyone", on the strength of a 200 and a checksum. Run from scratch, a stranger's first commit
> was refused.

## Current state (2026-11-04)

**v3.0.1 is the latest release**, and `release.yml` runs the Quick Start on its published URL. The governance
contracts C1–C9 are complete. **AgentSmith is public (AGPL-3.0)**; KYC Sentinel and AqlaarTeleologyStudio are
private. KYC is on 3.0.0 with green CI, and OTS on 3.0.0 with red CI, on 69 ruff errors in its frozen core and
two security controls awaiting its own content: do not use it as a showcase.

---

## The launch: two stages (owner, 2026-11-03)

**Target: Friday 6 November, end of day.** The owner's decisions: AGPL-3.0 stays; the package becomes `agentsmith`;
the repository stays `bobbyaqlaar/AgentSmith`, because `uses: Aqlaar/AgentSmith` would have to be a real repository
under that owner, and `aqlaar` on GitHub is an existing user account; launch in two stages.

### Stage 1: public preview, "governance for building with AI agents"

The claim: *an AI coding agent cannot merge code in a governed repository without a design, a review and a passing
gate, and every decision is on the record.* True today, tested on two tenants and six scratch tenants. Ops is
labelled preview.

| # | Step | Who | Day |
|---|---|---|---|
| 1 | ✅ Installing from a release works (`release-install-path`, merged; first released in 3.0.1) | Claude | Tue 3 |
| 2 | ✅ AGPL notices and community files (`agpl-compliance`, merged) | Claude | Tue 3 |
| 3 | ✅ Release 3.0.1; `release.yml`'s verify job green on the real URL | Claude | Tue 3 |
| 4 | ✅ Private vulnerability reporting on, which `SECURITY.md` relies on | Owner | Tue 3 |
| 5 | Rename `agentsmith` to `agentsmith`; release 4.0.0; move KYC. Distribution stays `agentsmith-runtime`: `agentsmith` on PyPI is an unrelated Neo4j tool, last released 2019 | Claude | Wed 4 |
| 6 | First run: a new repository's red security job says it is expected, and what to write to get green (fires the onboarding item below) | Claude | Wed 4 |
| 7 | Honest coverage: OWASP Agentic Top 10 and EU AI Act mapped in `docs/security-framework-map.md`, with gaps said (gaps 1 and 8) | Claude | Wed 4 |
| 8 | Small fixes with the release: `PROMPT_DENYLIST_PATH` in the evals port; DLQ **Discard** confirmation; pin `phoenix:latest`; delete `ai-compat.sh`; the widget's dead `cdn.agenticframework.io`; `oil-price-demo` in live docs | Claude | Thu 5 |
| 9 | Secret scan over **full history**, not only the tree (the pattern check so far covered the tree) | Claude | Thu 5 |
| 10 | README leads with the three audiences and states its limits: edit-time enforcement on Claude Code and Cursor only (rule files and CI elsewhere), Windows untested, yarn, bun and Poetry unsupported, Ops in preview | Claude | Thu 5 |
| 11 | Confirm with counsel: copyright holder in `NOTICE` (Aqlaar Tech FZE LLC, assigned?), `TRADEMARK.md` (names Bobby Rajagopal), and what AGPL means for a tenant importing the runtime. Say whether OTS, KYC and GCP project `agentsmith-500916` may stay named in a public repository | Owner | Thu 5 |
| 12 | Set the repository's description and topics (it still says "Universal agentic framework") | Owner, or say go | Thu 5 |
| 13 | Rehearsal: `check_release_install.sh` on the final release, then the README followed by hand on a clean machine or account | Claude and owner | Fri 6 |
| 14 | Publish the announcement. The honest story is the strongest: what building a real tenant found in the framework | Owner | Fri 6 |

### Stage 2: "the DevOps platform for AI-infused and agent apps"

The claim needs evidence a preview does not: a real app, on real traffic, traced back to the design that shaped it.
**6 November is possible only in the narrow form below, and only if the owner supplies step 15 by Wednesday noon.
Otherwise Stage 1 ships on the 6th and Stage 2 the following week.** Stage 1 does not depend on it.

| # | Step | Who |
|---|---|---|
| 15 | Provide for KYC staging: Cloud SQL and Temporal (reuse or tear down what is billing in `agentsmith-500916`), `GEMINI_API_KEY` and `OPENROUTER_API_KEY` set on its environment, a deployed portal and its Ops token | Owner |
| 16 | KYC live on staging: the worker as a service, Phoenix and portal wired | Claude |
| 17 | One real HITL round trip through the portal, and one production case promoted, with screenshots | Claude and owner |
| 18 | **The accountability chain (gap 2):** a run carries its commit, so a production run links to its commit, design and approvals | Claude |
| 19 | **A kill switch (gap 4):** an app or agent stopped from the portal, the gateway refusing its calls | Claude |
| 20 | Publish the article, with the screenshots from step 17 | Owner |

### KYC Sentinel "Running live": what it needs

**Goal:** take the tenant from offline/smoke-job to serving real traffic, so
the observability, HITL and promotion loops are exercised end-to-end rather
than asserted.

**Trigger:** fired — everything upstream of it is done.

**Blocked on:** standing up infrastructure and providing credentials. Not a
code blocker; deliberately deferred when the deploy pipeline was proven.

**What it needs** (from `KYC_Sentinel/DEVLOG.md` 2026-07-22):

1. Cloud SQL (`BUDGET_BACKEND=postgres`, `IDEMPOTENCY_BACKEND=postgres`),
   a Temporal server, Ollama for the sovereign `intake` route, and Phoenix.
2. Real provider keys: whichever variable the tenant's `judge` role declares —
   `GEMINI_API_KEY` as of 2026-08-19, when the judge moved back to
   `gemini-3-flash-preview` after Groq decommissioned the whole Llama family
   and `llama-3.3-70b-versatile` began 404ing on every call. It is **not** a
   fixed name and has now changed three times, so read it off the merged
   registry rather than this list — this line itself was four days stale.
   Plus the actor routes' key, `OPENROUTER_API_KEY` (research and analyst).
   No actor route uses Groq — that is deliberate, so exhausting an actor's
   quota cannot also take out its reviewer.

   Setting the judge key no longer turns all three judge-backed gates on at
   once: golden runs on every push, fairness and hallucination on alternating
   crons, because the three together need 22 judge calls against a free tier
   that allows 20 a day (KYC `DEVLOG.md` 2026-08-08).

   **This contradicts the judge binding's own note** in KYC `models.yaml`, which
   says the quota constraint "no longer binds" after a full 22-call cycle
   completed on 2026-08-19, and tells you not to restore the split without
   re-measuring. Re-measured 2026-08-23: the limit is real and hard —

       429 RESOURCE_EXHAUSTED
       quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier
       quotaValue: 20   model: gemini-3-flash

   so the split stands. The daily budget resets at midnight America/Los_Angeles,
   which is the only thing that clears it; probing says nothing about how much of
   the day's 20 remain, only that the per-minute window is open.
3. Swap `cd-staging.yml`'s Cloud Run **Job** for a `gcloud run deploy` of
   `worker.py` as a long-running service (`--no-cpu-throttling
   --min-instances=1`, docs/UserManual.md › Deploy via GitHub CI/CD), pointed at the real
   `TEMPORAL_ADDRESS`.
4. Then, in order: Phoenix/Ops Portal wiring → widget embed → first HITL
   round-trip through the portal → shadow-eval sampling on → first production
   golden case promoted.

Append progress to `KYC_Sentinel/DEVLOG.md` as you go.


---

## Where the industry is, and how AgentSmith stands ahead

Researched 2026-11-03. Most sources are vendor write-ups, so market claims are directional. Check anything quoted
externally against the primary source.

**The market has split into camps, and none joins Dev to Ops:**

| Camp | Examples | What they do | What they do not |
|---|---|---|---|
| GRC suites | Credo AI, IBM watsonx.governance, ServiceNow AI Control Tower, OneTrust | Inventory, policy packs, reports for auditors | See how the code was built |
| Agent control planes | Microsoft Agent 365, Kore.ai | A registry and controls for agents in production | Govern the change that produced them |
| Runtime security | Zenity, Noma; **Microsoft Agent Governance Toolkit** (open source, maps all ten OWASP agentic risks) | Policy enforcement while agents run | Say why the agent is built this way |
| LLM observability and evals | Langfuse, LangSmith, Phoenix, Braintrust | Traces, scores | Stop a merge on a missing design |
| Coding-agent security | Pillar, Endor Labs, OX | Controls on Claude Code, Cursor, Codex | Follow the code into production |

**AgentSmith's position:** the one record from design to production run, in git, for any stack, under published
contracts someone else could implement. Its own history is the demonstration: every commit in a public repository
carries its design and review. To stand ahead: finish the chain (gap 2), sign what it records (gap 5), answer the checklist buyers now bring (gaps 1, 3, 8), and say it plainly.

**What to lean on, because it is true and rare:** the gates fail closed, where hook-based tools are commonly reported
to fail open; guardrails are mutation-tested, so they are shown to be able to fail; "this suite proved nothing"
is reported as such; CI re-checks what the IDE hook checked; self-hosted, with sovereign routing.

### Glaring gaps, in order

Each was checked absent from the code on 2026-11-03.

1. **No OWASP Top 10 for Agentic Applications mapping** (published December 2025). `docs/security-framework-map.md`
   maps the LLM Top 10 only, and the first thing a buyer of agent governance asks is now this list. Microsoft's open-source
   toolkit claims all ten. **Fix:** map the `SEC-*` controls, and name what is uncovered. *Stage 1.*
2. **The accountability chain stops at the commit.** A production run carries no commit (`app_commit` appears nowhere;
   portal phase 4), so "why does this agent do that?" cannot be answered from a trace. This is the differentiator no
   camp above has. *Stage 2.*
3. **MCP and tool supply chain ungoverned.** Tool poisoning, rug-pulled definitions and shadow MCP are the concerns of
   2026. Pinning a tool definition and blocking on drift is reported missing from at least one gateway, and signing is not
   required by the protocol. AgentSmith checks nothing about a repository's `.mcp.json`. **Fix, without shipping a client:** the
   repository declares its MCP servers and tool-definition hashes, and the gate fails on an undeclared server or a drifted
   definition. Small, and ahead of most. *First after launch.*
4. **No kill switch**, listed "not covered" in `docs/agentic-42001-coverage.md` (F12, S10). `agentsmith mode off` meanwhile
   records a state nothing reads (below): give it this meaning. *Stage 2.*
5. **Evidence is not signed.** A gate record is a JSON file and a commit, which an auditor must take on trust. Microsoft's
   toolkit signs an attestation per deployment; no AI-provenance predicate is settled in SLSA or in-toto, so there is room to
   lead. **Fix:** an in-toto attestation of each gate verdict, signed keylessly in CI. *After launch.*
6. **A record does not say who wrote the change, or who judged it.** `contract/record/v1` has no agent or model, and no gate
   version, so a backfill judges old commits by today's rules. Attribution by `Co-authored-by` is known to be weak. **Fix:**
   the IDE hook knows the agent: record it, and the gate's version. *After launch.*
7. **No `gen_ai.*` telemetry.** `contract/telemetry/v1` defines its own attributes. OpenTelemetry's GenAI conventions, with
   agent and MCP spans, are still in Development but are what every observability tool reads. **Fix:** emit both, and
   pin the conventions' version. *After launch.*
8. **No EU AI Act mapping.** The coverage docs lead with UAE and ISO themes. The Digital Omnibus (in force 27 July 2026, per
   law-firm summaries; confirm against the Official Journal) moved Annex III high-risk duties to 2 December 2027 and Annex I
   to 2 August 2028; Article 50 transparency applied from 2 August 2026. **Fix:** map it, with those dates. *Stage 1.*
9. **Agent evals stop at the answer.** Suites judge an output. Agents fail in the path: wrong tool, wrong order, a skipped
   approval. **Fix:** a `trajectory` suite in the evals contract, graded from traces, plus the rubric digest below.
   *After launch.*
10. **Prompt injection into the coding agent itself is unchecked in CI.** In April 2026 researchers hijacked Claude Code,
    Gemini CLI and Copilot through malicious pull-request titles. **Fix:** a gate check that fails a workflow passing untrusted
    event text to an agent. Small, and a strong demonstration. *After launch.*
11. **Edit-time enforcement on two of six IDEs.** Copilot, Codex and Gemini CLI now have hook and managed-policy surfaces.
    Confirm each schema from a real session, then generate its config; Copilot first, for reach. *After launch.*

Sources: [Gartner AI governance platforms](https://www.gartner.com/reviews/market/ai-governance-platforms) ·
[Gartner agent management platforms](https://www.gartner.com/reviews/market/ai-agent-management-platforms) ·
[Microsoft Agent Governance Toolkit](https://opensource.microsoft.com/blog/2026/04/02/introducing-the-agent-governance-toolkit/) ·
[State of MCP security, Microsoft](https://techcommunity.microsoft.com/blog/microsoft-security-blog/the-state-of-mcp-security-in-2026/4531327) ·
[MCP tool poisoning, CSA](https://labs.cloudsecurityalliance.org/research/csa-research-note-mcp-tool-poisoning-auto-execution-20260701/) ·
[EU AI Act Omnibus, Gibson Dunn](https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/) ·
[Omnibus finalised, Orrick](https://www.orrick.com/en/Insights/2026/07/EU-AI-Act-Update-Digital-Omnibus-Finalizes-8-Compliance-Changes) ·
[OTel GenAI status](https://dev.to/azena-ai/opentelemetrys-genai-semantic-conventions-are-not-stable-yet-heres-what-actually-shipped-in-2026-3mke) ·
[AI provenance, TODO Group](https://todogroup.org/blog/2026-07-14-verifiable-provenance-ai-assisted-contributions/) ·
[Coding-agent controls, Endor Labs](https://www.endorlabs.com/learn/critical-controls-coding-agents)

---

## After Stage 2, in order

**First-run friction.** All 14 pillars for a one-line change is the most likely reason a newcomer gives up. *Scope-derived
pillar subset:* ask only the pillars a change's paths implicate, each still carrying evidence. Held until G4, which has
shipped, and its impact query is trusted.

**A day-one tenant's CI is red on every stack, by design.** Stage 1 step 6 explains it. Whether it should stay red for a new
repository is still worth asking once outsiders try it. Do not relax strict merely to get green.

**The gate's own loose ends:**

### The stop gate cannot tell a mutation harness's edit from an unreviewed change

**Update 2026-11-01:** the *other* half of that day's confusion — "the stop gate is
slow" — turned out to be `sys.stdin.read()` waiting for an EOF nobody sent, and is
fixed (`hook-answers-without-its-payload`). This item is unaffected: the harness
really does hold gated files mid-run, and the gate really does read that as
unreviewed work. Two separate defects that presented as one symptom.

Raised 2026-11-01, while `scripts/mutation_check.py` was running in the background
as a turn ended. The stop gate refused with

> `agentsmith/cli.py`: no complete active design note covers it

and it was right about the file and wrong about the cause: the harness had
`agentsmith/cli.py` mutated in place at that instant (`tenant_scaffold`, `quoted_id`
→ `tenant_id`) and would restore it a second later. The design that covers
`agentsmith/cli.py` is `done`, correctly, because nothing in the slice changes it.

So a long catalogue run and a turn boundary cannot coexist: the gate reads a
transient edit as unreviewed work and blocks. Worse than the noise is the habit it
teaches — the remedy that looks right is to re-open a finished design, or to stop
running the harness.

The harness already knows which files it is holding: it writes pristine copies to
a backup directory and keeps a journal, which is how it restores a file after a
killed run (`♻️ restored agentsmith/idempotency.py`).

**Fix:** have the harness publish the set of files it currently holds — the journal
it already keeps is enough — and have `scripts/process_gate.py` treat a file listed
there as held rather than unreviewed, naming it as such in the output rather than
staying silent. Both halves matter: a gate that silently ignores a path is worse
than one that blocks on it.

### Nine more unbounded `sys.stdin.read()` calls, same defect as the gate's

Raised 2026-11-01 in Pass 2 of `hook-answers-without-its-payload`, by sweeping the
data rather than the directory. The gate's three reads are fixed; these nine are
the same line, unfixed:

| file | lines |
|---|---|
| `scripts/rules_port.py` | 211 |
| `scripts/security_port.py` | 234 |
| `scripts/evals_port.py` | 235 |
| `agentsmith/cli.py` | 1025, 1075, 1094, 1154 |
| `.githooks/process-gate` | 221, 409 (inline `python3 -`) |

Each waits for an EOF its caller may never send. The three ports are contract
endpoints the launcher invokes with a pipe it closes, and the `agentsmith/cli.py`
paths are `conformance` and the CLI's own stdin readers — so none is known to hang
today. That is a statement about the callers in this repository, not about the
code, which is exactly the reasoning this slice had to retract for the gate's two
`--decision` paths.

**Why it is not fixed here:** `_payload_text` lives in `scripts/process_gate.py`,
and the gate deliberately does not import its own modules. Sharing it means
putting it in `scripts/_shared.py` (or beside it) and having four modules plus two
inline hook scripts take it from there — a different change from bounding the
gate's own read, with its own tests per caller. Doing it inside this slice would
have meant five more gated files under a design written for one.

**Fix:** move the helper to a shared module, point all nine at it, and give each
caller the held-open-pipe test the gate now has.

### "caught" does not say which test caught it

Raised 2026-11-01 while cataloguing the mutants for `kg_drift_gate`, `gate_steps`
and the three `agentsmith/cli.py` additions (`curated-mutations-for-todays-gates`).

`scripts/mutation_check.py` prints `caught` when **any** test in the suite fails.
A mutation that breaks the file outright — a bad parse, a missing import — reads
identically to one caught by the test that asserts the property, so a catalogue
entry can look like evidence while proving only that the file still has to
compile. It matters most for a multi-statement entry, which is the kind most
likely to break something unrelated.

For the 11 entries added on 2026-11-01 this was closed by hand: each was applied
on its own and the failing test names read off, and each failed the test named in
its own entry with the rest of the suite still passing. That check is not
re-runnable, which is the same shape of gap the 11 entries themselves closed.

**Fix:** record the expected failing test per `Mutation` (optional field) and have
the runner report `caught by an unexpected test` as its own verdict, distinct
from `caught` and from `survived`. Small and additive; the runner already parses
pytest's output.

### `MINUTES` is measured in CI and goes stale silently

Raised 2026-11-01, same slice. `scripts/mutation_check.py::MINUTES` holds per-suite
CI durations measured once, on Self-Test run 38470842052 (2026-10-14), and a suite
missing from it weighs one minute. `vendoring_retired` has since grown from 9
mutations to 12 — three of them full tenant scaffolds — while its entry still says
0.7, and `kg_drift_gate`, `gate_steps`, `knowledge_graph` and `scratch_build` are
absent. A local measurement cannot be mixed into a CI-measured table honestly, so
nothing was changed here.

Costs shard balance only, never a result — the module's own comment says so, and it
is right. **Fix:** refresh the whole table from one weekly full run rather than
patching single rows, and note the run id beside it as the current comment does.


**Evals credibility:**

### A score records its judge but not its rubric version

Raised 2026-09-03 by an outside critique of LLM-judge practice, and it lands.

`scripts/run-evals.py` stores `"criteria": criteria.get("name", "default")` — a
static NAME. Meanwhile `scripts/promote-learning.py` appends to
`historical_learnings`, and `scripts/eval_judge.py` injects those into every
judge prompt. **The rubric mutates and the score does not record which version
graded it.** Two runs both stamped `criteria: "default"` may have been graded
under materially different criteria, and nothing downstream can tell.

What makes this worth fixing rather than noting is that **this codebase already
makes the argument, for the judge**. `eval_judge.run_judge` records `judged_by`
AND `judged_by_route` on every row, with the reasoning written out: a score is
not portable across graders, so "who graded this belongs with the score, not in
a single run-level field a substitution would silently falsify." That is exactly
the rubric's situation. The principle was established and applied to one of the
two inputs.

**Fix:** hash the resolved criteria (instructions + historical_learnings, after
merge) and store the digest per row beside `judged_by`; surface it in the
scorecard; refuse to compare scores across differing digests. Small, additive,
and it closes the half of the argument that is already written down.

**Related gaps from the same critique, deliberately NOT scheduled** — recorded so
the boundary is explicit rather than accidental: no confidence interval per score
(variance informs where a bar sits, but is not reported per run); no coverage or
decay measurement of the golden set against production traffic; case selection is
failure-driven rather than uncertainty-driven (no active learning); no linkage
from eval scores to business outcomes. The first is cheap and worth doing; the
last needs holdouts and traffic volume this project does not have.

**Open — a judge that is not the one the bars were calibrated for is not flagged (found 2026-10-07,
KYC).** A tenant's bars are calibrated against one grader (KYC's 0.95 / 0.95 / 0.75 against
`gemini-3-flash-preview`), but the judge a run uses is whatever the machine's mode selects: on a
machine in `local` mode KYC's judge resolves to `falcon3:3b`, which its own `models.yaml` calls
uncalibrated, and the provider grades against the same bars without a word. The scorecard records
the judge that answered (`judge_models_used`) but not the judge the bars belong to. Fix: the judge
role in `models.yaml` names the grader its `fail_below` was calibrated on; when the answering judge
differs, the scorecard says so in its reason and the launcher warns — a pass against a borrowed bar
is not the pass the bar describes (`failure-is-not-a-result`). **Also from the same move:** an
over-quota contract run raises two warnings, the launcher's and `run-evals.py`'s own annotation
fired inside the provider — one verdict should speak once.

**Open — evals-port suites for live latency and shadow comparison (found 2026-10-13, C9).**
`eval-ttft-live.yml` and `shadow-eval.yml` left the templates in 3.0.0: they ran `verify_ttft.py` and
`shadow-eval.py` by path and had no port. OTS ran the TTFT one (opt-in). Fix: `ttft` and `shadow` suites
in the evals contract, so a tenant asks for them like the others.

**Open — human feedback into a tenant's own evaluation data (found 2026-10-11, C8).**
`sync-ui-feedback.py` promoted negative Phoenix annotations into the golden dataset from tenant CD
and opened a PR with them; C8 retired it from CD (it was not an Ops record, and wrote cases without
the `actual_output` the evals contract requires). It stays the first half of `agentsmith evals` on a
developer's machine. Fix: a feedback feed the tenant pulls — from its portal or its trace store — into
cases the evals contract can grade, as an evals-data feature.

**`sync` and declarations a tenant edited.** Found on every tenant move. `sync` leaves a hand-edited `providers.json` at its
old setup pin and `^N` range, and a gates workflow a tenant wrote; `ownership()` and the rules check disagree on whose
`.cursorrules` is; hooks a tenant already holds uncommitted stay out of its commit list. Fix: a file the declared provider
renders is the provider's for `sync`, and it names what it left and why.

**`agentsmith mode off` and the bypass policy have nothing left to mute** (found 2026-10-13). `mode off` records a state only
`status` and `check` read, and `DISABLE_AI_STACK` is read by nothing. Gap 4 gives it a meaning, or retire it.

**Open — `tenant init` offering the rule files' `.gitignore` in a public repository (found 2026-10-13, C9).**
The machine-wide `post-checkout` asked, for a repository it judged public, whether to gitignore the rule
files (system-prompt content). It retired in 3.0.0 and `tenant init` does not ask. Fix: a non-interactive
flag (`--public`) that writes the block, and a line in the plan when the remote looks public.

**Open — a signed bundle of the provider and the org policy (found 2026-10-13, C9).**
The Enterprise Pack's signed hook bundle retired with the machine-wide hooks. IT now distributes
`install-ai-stack.sh` and the policy by its own means. Fix: a signed, versioned bundle of both, verified
before install, as the hook bundle was.

**Smaller, each with its trigger:**

| Item | Trigger |
|---|---|
| A clone made before 3.0.0 keeps the machine hooks in `.git/hooks`; where it never adopted the gates, `post-commit` still tags and pushes. The CHANGELOG says how to remove them | A report of an unexpected tag; then `agentsmith doctor --fix` |
| husky's `prepare` points `core.hooksPath` back at `.husky`, disarming the gates; `tenant adopt` warns | The first adopted repository using husky |
| Portal: Ops answers 404 for an app outside a user's grants, Dev shows two screens. Align them | The next change to an Ops page |
| A pointer by heading name dies when the heading is renamed, and nothing reads it | The next dead pointer |
| `tenant.yaml` is outside the IDE-config gitignore block; it may hold real endpoint URLs | A public tenant carrying them |
| Rule files are gitignored here, so a clone's copies go stale when `agent-rules.yaml` changes | Agents in this repository read stale rules again |
| `mutation_check.py --list` runs the journal recovery, so listing suites during a live run restores the file under mutation, and that mutant can read as a false survivor (hit 2026-11-03). The journal should name its owner's pid, and `--list` should not recover | Do with the next change to the runner |
| Two agents in one checkout: a lock. It recurred 2026-10-17, and the mutation journal makes it small | Owner request, or the next collision |
| KYC Sentinel moves to `records: single` | KYC's next governance change |
| Self-Test's security job installs `requirements.txt` ranges, not the lock, through a tenant-facing action | A harness run that differs by dependency version |
| The framework environment assumes a POSIX venv layout; there is no Windows runner | The first native Windows install |
| npm and pnpm only; pip and uv only. Yarn and bun fail by name, Poetry and Pipenv get a warning | A tenant on one; add a scratch app first |
| `AGENT_SHARED_RFC_DIR`: specified once, never built, and now documented as such. Sharing stays within one organisation | A team asks for RFCs across repositories |

**Known gaps from the 1.1.0 review:**

- **`SEC-TOOL-001` verifies the mechanism, not your allowlist.** Its runner
  smoke-tests `ToolRegistry` deny-by-default against the shipped *template*,
  so a tenant's green SEC-TOOL-001 says the enforcement works — not that the
  tenant's own `tool_allowlist.yaml` is sane. **Trigger:** an auditor reads the
  evidence pack as a statement about the tenant's tools.
- **A tenant that removes its controls removes the gate with them.** Both
  detection gates are conditional on the control existing: the fairness parity
  floor applies only `if min_parity is not None`, and the hallucination
  detection-miss floor only `if hallucination_miss is not None`. Delete the
  `pair_id`s from a fairness fixture, or the planted case from a hallucination
  one, and the suite still passes on `avg_score` alone having measured no bias
  and no detection. Both report the absence honestly — "NOT MEASURED", "no
  positive control in this suite" — so this is a reporting-is-right,
  gate-is-silent split, not a false green.

  The framework's own fixtures are guarded by tests (`test_fairness_evals.py`
  asserts pairs exist, `test_hallucination_evals.py` asserts a positive control
  does), so this is reachable only through a tenant override. Left alone
  deliberately: making it hard-fail would red-build every tenant whose fixture
  predates the control, which is a release decision, not a fix.
  **Trigger:** a tenant's fairness or hallucination gate is green and someone
  asks what it measured. Found in the 2026-08-24 review pass.


---

## Later: confirmed gaps, each waiting on its trigger

### Compliance gap status boards (pointers, not copies)

Live status for the two compliance tracks is maintained in one place each — do
**not** duplicate their tables here:

- **UAE Regulatory:** [`docs/uae-regulatory.md`](uae-regulatory.md) +
  [`docs/iso-42001-control-map.md`](iso-42001-control-map.md). Still
  open there: live verification against a *named* UAE sovereign API (beyond the
  verified Ollama Falcon 3 pattern), and org-level certification work (never
  framework-owned).
  **Trigger:** a bid requires live sovereign-endpoint verification, or an
  auditor demands a licensed clause-ID matrix beyond the thematic pack.
- **Enterprise Delivery Model:**
  [`docs/delivery-model.md`](delivery-model.md). v1 soft pack shipped.
  Still open: hard-fail enterprise mode; auto-inject `delivery.*` defaults from
  `ai-tenant-init`; a CD step uploading the evidence pack as a release artifact.
  **Trigger:** an org wants promote blocked when a platform isn't approved.

### Tool Orchestration — provider function-calling wire-up

**Shipped:** `agentsmith/tool_registry.py` (`@tool` + YAML allowlist,
`SEC-TOOL-001`, tenant-attributed spans). MCP stays **bring-your-own**.

**Remaining gap:** `llm_gateway.complete()` still does not emit provider
function-calling request fields — the registry is allowlist/schema extraction,
not a tool-choice runtime.

**Trigger:** a tenant needs the LLM to choose among tools dynamically inside
the gateway request, not only fixed activity sequences.

### Perception & Input Parsing — prompt templating

**Shipped:** `agentsmith/structured_output.py` (`parse_llm_json`,
`SEC-OUTPUT-001`).

**Remaining gap:** no reusable prompt-template engine; prompts are inline
f-strings (KYC Sentinel has four such prompts across its agents).

**Trigger:** 2+ real call sites sharing the same prompt structure.

**Fix sketch:** `agentsmith/prompt_templates.py` — a minimal Jinja2 or
`string.Template` wrapper.

### Memory / RAG — remaining extensions (v1 shipped)

Shipped: `conversation_memory.py`, `embeddings.py`, `vector_store.py`
(memory / pgvector). See [`docs/rag-memory.md`](rag-memory.md).

**Remaining:** summarization eviction; auto-RAG in the gateway; ingest/chunk
CLI; a live pgvector CI job (the extension is often absent in bare Postgres).

**Trigger:** a tenant needs summarization or gateway-native retrieve.

### HITL self-correction — remaining extensions (v1 shipped)

**Remaining:** tenant-specific policies for which error classes opt in.
Multi-turn planner/tool-choice correction stays out of scope.

### Eval suites — remaining extensions (v1 shipped)

- **Hallucination:** expand golden cases beyond seed pairs; a human review UI
  for flagged cases.
- **Fairness:** domain-specific sets beyond seed pairs; statistical
  disparate-impact metrics beyond judge + pair parity.
- **TTFT:** portal chat UI streaming; TTFT on the non-stream path (not
  measurable without a fake first token). Not wired into KYC Sentinel's CI —
  it needs a live streaming provider.

### Input guardrail — remaining extensions (v1 shipped)

**Remaining:** tenant-specific PII vocabularies beyond the default patterns
(Emirates ID, email, phone, Luhn cards). Content moderation (toxicity) stays
out of framework scope — tenants declare a `moderation.hook`.

---

**Settled design decisions (do not re-open without a concrete reason):**
- MCP integration stays tenant-owned (BYO): the framework ships no MCP client or server. Rationale in
  docs/DESIGN.md › Architecture by Layer. **Governing a repository's MCP declarations is a different thing,
  and is proposed below (gap 3).**
- LLM self-correction is a separate opt-in method
  (`run_with_self_correction`), never inserted in front of the human DLQ path.
- The default model registry is local-only. Cloud tiers are a deliberate
  per-tenant opt-in, not something a budget breach can reach.

---

## Appendix — Lessons (do not repeat)

Operational lessons distilled from past phases; full incident context in
`docs/PRODUCT_ARCHIVE.md` and `CHANGELOG.md`.

- **Review the branch, not the diff — and run the CI job list before pushing.**
  On 2026-08-24 three review passes over `scripts/` reported clean, and the push
  found `main` had been red for three commits: the portal could not build
  (`node:crypto` reached the Edge bundle via `middleware → authz → constantTime`),
  `SEC-RBAC-001` failed on a missing loader, and docs/DESIGN.md was missing
  `agentsmith/security_paths.py`. None were in the reviewed diff; all three were in
  what the branch was about to ship.

  Two habits would have caught all of them, and both are cheap:

  1. **Scope the review by what CI checks, not by what you edited.**
     `.github/workflows/self-test.yml` is the repo's definitive statement of
     "done". Every one of the three failures is a job in it, and all three
     reproduce locally in about ninety seconds. Read it as a checklist BEFORE
     pushing, not as a debugging aid after.
  2. **When a fix lands at "both" call sites, grep for the third.** The archive
     entry recording the loader fix said it was "now on both scripts" — one
     `git grep experimental-strip-types` printed twelve lines with the missed
     Python call site four lines below the fixed one. This is the same lesson as
     `return 2` for graceful skip, which is already in this list. It recurs
     because the fix always *looks* complete from inside the file you fixed.

  Note which pillar the miss maps to: pillar 15 (Ambiguous Signals) was applied
  hard and found real defects; pillar 2's five-step check — *what does this
  affect, are there downstream consumers* — covers four of the five misses and
  was not run at all. Working one pillar is not working the list.

  **A local run is only equivalent to CI if the git state matches.** The guard
  written for lesson 2 above passed locally and failed on the first push,
  because it swept `git ls-files` — and it was itself still untracked, so it
  never examined itself. Anything that derives its input from git sees a
  different repo before and after the commit. Sweeps should use
  `git ls-files --cached --others --exclude-standard`, which is the set that is
  about to be committed rather than the set already committed.

  Guards added rather than resolutions: `scripts/test/test_ts_runner_invocations.py`
  fails when any invocation of `node --experimental-strip-types` omits the
  loader, and `portal/test/edgeSafety.test.ts` fails when anything reachable
  from `middleware.ts` imports a Node-only builtin — that one is only visible to
  `next build`, since `tsc --noEmit` and `npm test` both pass on it.

- **A verification step must not regenerate the thing it verifies.**
  `verify_system.py --check-kg` called `map_codebase.run_map()` and then
  asserted the graph was non-empty and held known nodes — every assertion about
  the file it had just written, so it could only fail if the mapper broke. The
  committed graph was 703 lines stale with the gate green throughout.

  Two things fell out of fixing it, both worth keeping:
  - **Compare shape, not bytes.** `actions/checkout` stamps working-tree mtimes
    at checkout time, and the mapper walks the FILESYSTEM, so a committed graph
    also carries build output (`portal/next-env.d.ts`) and Guardrail nodes with
    ABSOLUTE paths. Comparing all of it red-built every CI run, which is worse
    than the weak gate — a gate that always fails gets deleted. Compare only
    git-tracked, reproducible content.
  - **An incremental cache cannot repair what it never re-reads.** `run_map`
    skips files whose stored mtime matches, so a graph wrong for any reason
    other than a file edit — a hand edit, a bad merge, a truncated write —
    survives every subsequent run. A corrupted graph reached a public repo this
    way. `run_map(force=True)` / `map_codebase.py --force` exists now, and any
    caller that VERIFIES the graph forces; the post-commit hook keeps the fast
    path.

- **A test double must never be more capable than the real thing.** KYC
  Sentinel's original fake gateway aliased `complete_stream` to `complete`,
  hiding a production crash on the analyst's own route. `agentsmith/testing.py`'s
  shipped double now refuses to stream what the real gateway can't.
- **A guard assertion inside the `try` it guards is not a guard.** Two F-scenario
  drivers raised `AssertionError` inside a block caught by
  `except Exception`, so they reported their control proven while it was
  broken — through CI and a Cloud Run smoke job.
- **Config that is read from two places will disagree.** There were four
  copies of "which model is the architect tier", a judge id in a constant
  *and* in models.yaml, and a security pack that was a byte-copy of its own
  template. Every one had drifted. Read from one source; guard it with a test.
- **cwd-relative vs install-relative is a real distinction.** The security
  harness resolved the tenant pack from its install location, so every tenant
  graded the framework's pack. Two roots that coincide during self-test hide
  this completely.
- **"Skip gracefully" means exit 0.** `return 2` from `run_scorecard()` still
  failed the CI step, so every fresh tenant went red for not yet having a
  golden dataset. This lesson was recorded here and applied to only one of two
  call sites for months.
- **A CI callee must ship with its caller.** `ci-python-fastapi.yml`
  referenced `eval-security.yml`, which `ai-tenant-init` never copied — GitHub
  rejects the whole workflow as invalid, not just the missing job.
- **GitHub Actions rejects YAML anchors.** They parse fine locally and fail on
  the runner.
- **Groq 429 retry needs FULL JITTER** — `(2**attempt)*5 + random.uniform(0, 3)`.
  A bare `2**n * 5` gives concurrent CI jobs identical waits. Baked into
  `scripts/cost_router.py`.
- **Cloud SQL from Cloud Run** — use the Auth Proxy
  (`--add-cloudsql-instances`, Unix-socket `DATABASE_URL`), never
  `sslmode=no-verify`; grant the Compute SA `roles/cloudsql.client` and
  `roles/secretmanager.secretAccessor` per secret.
- **New GCP projects grant the default compute SA nothing.** Cloud Run
  `--source` deploys use it via Cloud Build; it needs
  `roles/storage.objectViewer`, `roles/artifactregistry.writer`,
  `roles/logging.logWriter` before a first deploy will work.
- **WIF attribute condition is one expression** — adding a repo means updating
  `==` to `in [...]`, or the new repo gets
  `unauthorized_client: rejected by attribute condition`.
