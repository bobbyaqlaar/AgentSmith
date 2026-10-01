// portal/lib/intakeCatalog.ts — what a tenant intake may say, in a module the
// browser can load (.agent-rfc/designs/intake-form.md). lib/intakes.ts imports
// node:crypto and the database pool, so the form cannot import it; these
// constants lived there and moved here, and lib/intakes.ts re-exports them.
//
// Each is a mirror of a set something else owns, pinned by test/catalogs.test.ts:
// the stacks to runtime/cli.py STACKS, the IDEs to scripts/gate_ides.py
// GENERATED, the architectures to templates/architectures.yaml. The CLI
// re-checks every value against its own copy.

export const INTAKE_STACKS = ["python-fastapi", "ts-react", "go"] as const;
export const INTAKE_IDES = ["claude", "cursor"] as const;
export type IntakeStack = (typeof INTAKE_STACKS)[number];
export type IntakeIde = (typeof INTAKE_IDES)[number];

/** The structural styles, by id, with the name templates/architectures.yaml gives each. */
export const INTAKE_ARCHITECTURES = [
  { id: "layered", name: "Layered (n-tier)" },
  { id: "modular-monolith", name: "Modular monolith" },
  { id: "hexagonal", name: "Hexagonal (clean architecture, ports and adapters)" },
  { id: "microservice", name: "Microservice" },
  { id: "event-driven", name: "Event-driven" },
] as const;

export const INTAKE_LIMITS = {
  objective: 4000,
  criteria: 20,
  files: 50,
  item: 500,
  ttlHours: 24,
} as const;

/** A textarea as a list: one item per line, trimmed, blank lines dropped. The one
 *  place this happens, so the form and its test agree on what a "line" is. */
export function linesOf(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}
