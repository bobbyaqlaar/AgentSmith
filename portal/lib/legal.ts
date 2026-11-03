// The notice AGPL-3.0 section 5(d) asks an interactive interface to show, and the
// source offer section 13 asks of a network service (NOTICE). Someone running a
// modified portal sets AGENTSMITH_SOURCE_URL to where their source is published.
export const COPYRIGHT = "© 2026 Aqlaar Tech FZE LLC";
export const LICENSE_URL = "https://www.gnu.org/licenses/agpl-3.0.html";
const UPSTREAM_SOURCE = "https://github.com/bobbyaqlaar/AgentSmith";

// An http(s) URL only: this value becomes a link, and a `javascript:` one would run.
export function sourceUrl(configured: string | undefined): string {
  if (!configured) return UPSTREAM_SOURCE;
  try {
    const { protocol } = new URL(configured);
    return protocol === "http:" || protocol === "https:" ? configured : UPSTREAM_SOURCE;
  } catch {
    return UPSTREAM_SOURCE;
  }
}
