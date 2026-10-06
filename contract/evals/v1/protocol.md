# The evals contract, version 1

An **evals provider** judges a repository's eval datasets — the cases the tenant wrote and the
outputs its application produced — and answers with a scorecard. AgentSmith is one provider. This
directory is what another platform implements instead, and the suite that proves it did.

## The protocol

```
<evals-command> run
```

- **cwd** is the repository, or the request's `cwd` names it.
- **stdin** is one request, `request.schema.json`: `suite`, and optionally `fail_below` and
  `fail_above`; unknown keys are ignored.
- **stdout** is one scorecard, `scorecard.schema.json`, and nothing else. The provider's own report
  for a person goes to stderr.
- **exit 0** whenever the provider answers — the verdict is in the scorecard, and the caller decides
  what it means for a build. **Exit 3**: this provider cannot run here. An answer is a scorecard on
  stdout; anything else, whatever the exit code, is no answer.

## What the tenant owns

**The datasets**, at the paths below, one schema per suite (`dataset.<suite>.schema.json`). A case
may carry keys of its own; the provider reads the ones its suite names.

| Suite | Path | What a case carries |
|---|---|---|
| `golden` | `.agent-rfc/fixtures/golden_evals.json` | `id`, `input`, `actual_output` |
| `fairness` | `.agent-rfc/fixtures/fairness_evals.json` | the golden fields, `pair_id`, `protected_attribute`, `attribute_value` |
| `hallucination` | `.agent-rfc/fixtures/hallucination_evals.json` | the golden fields; `retrieved_context`, `expect_hallucination` |
| `adversarial` | `.agent-rfc/security/adversarial_evals.json` | `id`, `input`, `expect`: `block` \| `flag` \| `safe` |
| `rag_poison` | `.agent-rfc/fixtures/rag_poison_evals.json` | `id`, `query`, `document`, `expect` |

**The outputs.** A judged suite — golden, fairness, hallucination — grades what the application
produced, so every case carries its `actual_output`. Producing them is the tenant's own step, before
the eval. A provider never fills one in. The adversarial and rag_poison suites score the provider's
guard on the input itself and need none.

**The bars**, per suite, in `.agenticframework/process-gates.json` `extends.evals`:

```json
{"extends": {"evals": {"golden": {"fail_below": 0.8}, "hallucination": {"fail_above": 0.05}}}}
```

`fail_below` is a floor on the average score (golden, fairness, hallucination); `fail_above` a
ceiling on a rate — flagged claims for hallucination, misses for the guard suites. A provider
applies the request's bar, else the declaration's, else its own default, and **never one from the
environment** of whoever runs it. The scorecard reports the bars it applied.

## The scorecard

| Field | Means |
|---|---|
| `schema` | `1` |
| `suite` | the suite asked about |
| `verdict` | `pass` \| `fail` \| `no_verdict` \| `not_gradable` |
| `reason` | why, in a sentence — required for anything but `pass` |
| `threshold`, `fail_above` | the bars applied, `null` where the suite has none |
| `cases_total`, `cases_graded` | cases in the dataset, and cases a verdict was reached on |

A provider adds keys of its own: AgentSmith's scorecard carries every field its result file always
had (per-case rows, the judge that answered, the averages), which its security harness, promotion
loop and evidence pack read.

| Verdict | When |
|---|---|
| `pass` | every case graded and every bar cleared |
| `fail` | a bar missed, on whatever did grade |
| `no_verdict` | the judge did not answer — unreachable, refused, out of quota — for every case, or for some on a run that would otherwise pass |
| `not_gradable` | no dataset, a case that does not match its schema (a judged case without its output), or fewer cases than the suite needs |

## Who asks

**A repository's CI**, through a step that resolves the declared provider — AgentSmith's launcher
answers `bash .githooks/process-gate evals run --suite <suite>`. Failure is **closed**: `fail`, no
answer, and — unless the declaration says otherwise — `no_verdict` and `not_gradable` fail the
step. Only `pass` passes.

## The declaration

`.agenticframework/providers.json` names the provider (`providers.schema.json`):

```json
{"providers": {"evals": {"command": "agentsmith evals", "version": "^2", "contract": 1,
                         "no_verdict": {"golden": "warn"}}}}
```

The command is split on whitespace, with no quoting, and run with the verb appended.
`no_verdict` and `not_gradable` name the suites where that verdict only warns — an exception to
closed-in-CI that a tenant states in an always-governed file, so it is reviewed and visible.
`"evals": "none"` — the repository declares no evals provider, and an eval step says so instead of
judging.

## Conformance

```bash
agentsmith conformance --port evals --provider "<command>"
```

Builds `fixture.json`'s repository fresh for each case of `cases.json`, with that case's dataset at
its suite's path, and stands up a **stub judge**: an OpenAI-compatible endpoint on loopback, at
`$EVALS_STUB_JUDGE_URL` with the key in `$EVALS_STUB_JUDGE_KEY` (the fixture's `models.yaml` points
AgentSmith's judge role there; another provider reads the two variables). It answers each call with
the score the case's fixed output carries — `SCORE=`, `HALLUCINATION=`, `FAIRNESS=` — and refuses a
call without its key, so no model is called and no run drifts. The cases: a suite that passes and
one that fails; the declared bar, a request's bar beating it, and the environment's ignored; a case
without its output, no dataset and too few cases, each not gradable; a judge that does not answer
and one called without its key, each no verdict; a fairness pair scored alike and one scored apart;
a hallucination suite clean and one over its ceiling; a guard that lets benign input through and
one that misses what it should stop; and no answer to an unknown verb.

## What is not in version 1

Generating outputs — running the tenant's application over its inputs — is the tenant's step, not a
verb here. Live measurements against a deployed service (latency, shadow traffic) are operational
records, not evals of a dataset.
