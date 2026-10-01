"use client";

// Start a tenant: collect an intake, then show its token once
// (.agent-rfc/designs/intake-form.md). Like AppForm, this only collects and says
// what the server said — lib/intakes.parseIntakeInput is the control. Like
// IngestTokenPanel, the token appears once, here, and is held in this
// component's state only: never the URL, never storage.

import { useState } from "react";

import { Timestamp } from "@/components/ui/Timestamp";
import {
  INTAKE_ARCHITECTURES,
  INTAKE_IDES,
  INTAKE_LIMITS,
  INTAKE_STACKS,
  linesOf,
  type IntakeIde,
  type IntakeStack,
} from "@/lib/intakeCatalog";

const FIELD =
  "w-full text-sm rounded-md border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] px-2 py-1.5";
const PRIMARY = "px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50";
const SECONDARY =
  "px-3 py-1.5 text-sm rounded-md border border-black/10 dark:border-white/10 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-50";
const DANGER = "px-3 py-1.5 text-sm rounded-md bg-red-600 text-white hover:bg-red-700 disabled:opacity-50";
const HINT = "text-xs text-black/60 dark:text-white/60";

interface Values {
  tenantId: string;
  stack: IntakeStack;
  isolation: "shared" | "dedicated";
  architecture: string;
  agentic: boolean;
  ides: IntakeIde[];
  objective: string;
  criteria: string;
  files: string;
}

const EMPTY: Values = {
  tenantId: "",
  stack: "python-fastapi",
  isolation: "shared",
  architecture: "",
  agentic: false,
  ides: [],
  objective: "",
  criteria: "",
  files: "",
};

interface Issued {
  intake_id: string;
  token: string;
  expires_at: string;
  command: string;
}

// Three different failures, rendered three different ways
// (`failure-is-not-a-result`): the portal refused what was typed; the id is
// taken (with Replace only when the open intake is the author's own); or the
// portal could not be reached, when whether anything was created is unknown.
type Problem =
  | { kind: "refused"; text: string }
  | { kind: "taken"; text: string; open?: { id: string; mine: boolean } }
  | { kind: "unreachable"; text: string };

export function IntakeForm() {
  const [values, setValues] = useState<Values>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [issued, setIssued] = useState<Issued | null>(null);
  const [copied, setCopied] = useState<"token" | "commands" | null>(null);

  const set =
    <K extends keyof Values>(key: K) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setValues((v) => ({ ...v, [key]: e.target.value }));

  function toggleIde(ide: IntakeIde) {
    setValues((v) => ({ ...v, ides: v.ides.includes(ide) ? v.ides.filter((i) => i !== ide) : [...v.ides, ide] }));
  }

  async function send(replace?: string) {
    // `no-double-submit`: a second create would get 409 for the first one, and
    // could land after it and replace the panel showing the first one's token.
    if (busy) return;
    setBusy(true);
    setProblem(null);
    try {
      const resp = await fetch("/api/dev/intakes", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          tenant_id: values.tenantId.trim(),
          stack: values.stack,
          isolation: values.isolation,
          architecture: values.architecture || null,
          agentic: values.agentic,
          ides: values.ides,
          rfc: {
            objective: values.objective,
            acceptance_criteria: linesOf(values.criteria),
            files_to_modify: linesOf(values.files),
          },
          ...(replace ? { replace } : {}),
        }),
      });
      const data = await resp.json().catch(() => ({}));
      if (resp.status === 201) {
        setIssued(data as Issued);
        setCopied(null);
      } else if (resp.status === 409) {
        setProblem({ kind: "taken", text: data.error ?? "That tenant id is taken.", open: data.open_intake });
      } else if (resp.status >= 500) {
        // The portal answered, and its transaction rolled back.
        setProblem({ kind: "unreachable", text: `The portal failed (${resp.status}) — nothing was created. ${data.error ?? ""}`.trim() });
      } else {
        setProblem({ kind: "refused", text: data.error ?? `The portal refused it (${resp.status}).` });
      }
    } catch {
      // No answer at all: the request may or may not have reached the portal.
      setProblem({
        kind: "unreachable",
        text:
          "The portal could not be reached, so it is not known whether the intake was created. Try again — if it was, " +
          "the portal will say so and you can replace it.",
      });
    } finally {
      setBusy(false);
    }
  }

  function startAnother() {
    setIssued(null);
    setValues(EMPTY);
    setProblem(null);
    setCopied(null);
  }

  if (issued) {
    const origin = window.location.origin;
    const tenant = values.tenantId.trim();
    const commands = [
      `mkdir ${tenant} && cd ${tenant} && git init`,
      `export AGENTSMITH_PORTAL_URL=${origin}`,
      issued.command,
    ].join("\n");
    const copy = async (what: "token" | "commands") => {
      await navigator.clipboard.writeText(what === "token" ? issued.token : commands);
      setCopied(what);
    };
    return (
      <div className="space-y-4 max-w-xl text-sm">
        <div className="border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/30 rounded-lg p-3 space-y-2" role="status">
          <p className="font-medium">
            Intake {issued.intake_id} is ready. Copy its token now — it is not shown again.
          </p>
          <div className="flex items-center gap-2">
            <code className="font-mono text-xs break-all flex-1">{issued.token}</code>
            <button type="button" className={SECONDARY} onClick={() => copy("token")} aria-label="Copy the intake token">
              {copied === "token" ? "Copied" : "Copy"}
            </button>
          </div>
          <p>
            It works once, for this tenant only, until <Timestamp value={issued.expires_at} />.
          </p>
        </div>

        <div className="space-y-2">
          <p className="font-medium">On your own machine, in a terminal:</p>
          <div className="flex items-start gap-2">
            <pre className="font-mono text-xs flex-1 overflow-x-auto rounded-md border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] p-2">
              {commands}
            </pre>
            <button type="button" className={SECONDARY} onClick={() => copy("commands")} aria-label="Copy the commands">
              {copied === "commands" ? "Copied" : "Copy"}
            </button>
          </div>
          <p className={HINT}>
            The last command asks for the token: paste it there. Asked, it stays out of your shell history, which an
            <code> export</code> would not. It scaffolds the tenant, writes your RFC as its first, and prints the exact
            command for its first commit.
          </p>
        </div>

        <button type="button" className={SECONDARY} onClick={startAnother}>
          Start another tenant
        </button>
      </div>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void send();
      }}
      className="space-y-4 max-w-xl"
      aria-busy={busy}
    >
      <div className="space-y-1">
        <label htmlFor="intake-tenant" className="block text-sm">
          Tenant id
        </label>
        <input
          id="intake-tenant"
          className={FIELD}
          value={values.tenantId}
          onChange={set("tenantId")}
          required
          pattern="[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
          aria-describedby="intake-tenant-hint"
          autoComplete="off"
        />
        <p id="intake-tenant-hint" className={HINT}>
          Lower-case letters, digits and dashes — the id the app will be registered under. It must not already be
          an app.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <label htmlFor="intake-stack" className="block text-sm">
            Stack
          </label>
          <select id="intake-stack" className={FIELD} value={values.stack} onChange={set("stack")}>
            {INTAKE_STACKS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label htmlFor="intake-architecture" className="block text-sm">
            Architecture
          </label>
          <select
            id="intake-architecture"
            className={FIELD}
            value={values.architecture}
            onChange={set("architecture")}
            aria-describedby="intake-architecture-hint"
          >
            <option value="">Not decided yet</option>
            {INTAKE_ARCHITECTURES.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
          <p id="intake-architecture-hint" className={HINT}>
            The structure the scaffold lays out and the design records.
          </p>
        </div>
      </div>

      <fieldset className="space-y-1">
        <legend className="text-sm">Isolation</legend>
        <div className="flex gap-4 text-sm">
          {(["shared", "dedicated"] as const).map((iso) => (
            <label key={iso} className="flex items-center gap-1.5">
              <input type="radio" name="intake-isolation" value={iso} checked={values.isolation === iso} onChange={set("isolation")} />
              {iso === "shared" ? "Shared workers" : "Its own worker pool"}
            </label>
          ))}
        </div>
      </fieldset>

      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          className="mt-0.5"
          checked={values.agentic}
          onChange={(e) => setValues((v) => ({ ...v, agentic: e.target.checked }))}
        />
        <span>
          Agentic — add the agent layer: agents, allowlisted tools, the model gateway, durable workflows and evals
        </span>
      </label>

      <fieldset className="space-y-1" aria-describedby="intake-ides-hint">
        <legend className="text-sm">IDEs</legend>
        <div className="flex gap-4 text-sm">
          {INTAKE_IDES.map((ide) => (
            <label key={ide} className="flex items-center gap-1.5">
              <input type="checkbox" checked={values.ides.includes(ide)} onChange={() => toggleIde(ide)} />
              {ide === "claude" ? "Claude Code" : "Cursor"}
            </label>
          ))}
        </div>
        <p id="intake-ides-hint" className={HINT}>
          Which editors get a hook config. None ticked means every editor whose config can be written.
        </p>
      </fieldset>

      <div className="space-y-1">
        <label htmlFor="intake-objective" className="block text-sm">
          Objective
        </label>
        <textarea
          id="intake-objective"
          className={FIELD}
          rows={3}
          value={values.objective}
          onChange={set("objective")}
          required
          maxLength={INTAKE_LIMITS.objective}
          aria-describedby="intake-objective-hint"
        />
        <p id="intake-objective-hint" className={HINT}>
          What the first change is for, in the words of whoever asked for it. It becomes the RFC an agent works from.
        </p>
      </div>

      <div className="space-y-1">
        <label htmlFor="intake-criteria" className="block text-sm">
          Acceptance criteria
        </label>
        <textarea
          id="intake-criteria"
          className={FIELD}
          rows={4}
          value={values.criteria}
          onChange={set("criteria")}
          required
          aria-describedby="intake-criteria-hint"
        />
        <p id="intake-criteria-hint" className={HINT}>
          One per line, up to {INTAKE_LIMITS.criteria} — what someone can check, not the code that produces it.
        </p>
      </div>

      <div className="space-y-1">
        <label htmlFor="intake-files" className="block text-sm">
          Files to modify <span className="text-black/50 dark:text-white/50">(optional)</span>
        </label>
        <textarea
          id="intake-files"
          className={FIELD}
          rows={3}
          value={values.files}
          onChange={set("files")}
          aria-describedby="intake-files-hint"
        />
        <p id="intake-files-hint" className={HINT}>
          One per line, if you know them yet.
        </p>
      </div>

      <div className="space-y-3">
        <button type="submit" className={PRIMARY} disabled={busy}>
          {busy ? "Starting…" : "Start the tenant"}
        </button>

        {problem && (
          <div role="alert" className="text-sm space-y-2">
            <p className={problem.kind === "unreachable" ? "text-amber-700 dark:text-amber-400" : "text-red-700 dark:text-red-400"}>
              {problem.text}
            </p>
            {problem.kind === "taken" && problem.open?.mine && (
              <button type="button" className={DANGER} disabled={busy} onClick={() => void send(problem.open!.id)}>
                {busy ? "Replacing…" : `Replace intake ${problem.open.id} — its token stops working`}
              </button>
            )}
          </div>
        )}
      </div>
    </form>
  );
}
