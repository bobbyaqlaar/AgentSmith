// portal/lib/environment.ts — the portal's copy of runtime/environment.py.
//
// A DELIBERATE mirror, not a second opinion. `environment` is a pillar-3 span
// attribute, and the redaction profile the Python side applies is chosen from
// the same value — so if the worker calls a deployment "production" and the
// portal calls it "development", one trace carries two answers to the same
// question and the more permissive one wins wherever it is read.
//
// It cannot be imported: that module is Python. It CAN be pinned, and
// test/tracing.test.ts fails if the two alias tables drift apart — the same
// treatment scripts/_shared.py's `_dotenv_value` mirror gets.
//
// Fail-closed to "production" for the reason the Python header gives: an unset
// or misspelled ENVIRONMENT must never resolve to the least restrictive
// profile.

const ALIASES: Record<string, string> = {
  development: "development",
  dev: "development",
  testing: "development",
  test: "development",
  staging: "staging",
  stage: "staging",
  production: "production",
  prod: "production",
};

export type Environment = "development" | "staging" | "production";

export function getEnvironment(env: NodeJS.ProcessEnv = process.env): Environment {
  // The parameter is a seam for callers that already hold an env (and for the
  // tests). Without it `resourceAttributes(env)` read ENVIRONMENT from
  // process.env while reading everything else from its argument — one function
  // answering from two sources, which is how a mirror stops being one.
  const raw = (env.ENVIRONMENT ?? "").trim().toLowerCase();
  return (ALIASES[raw] ?? "production") as Environment;
}

/** The alias table itself, for the drift test. Not for runtime use. */
export const ENVIRONMENT_ALIASES = ALIASES;
