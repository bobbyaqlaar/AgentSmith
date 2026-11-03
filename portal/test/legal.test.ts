// portal/test/legal.test.ts — the source offer AGPL-3.0 section 13 asks of the portal
// (.agent-rfc/designs/agpl-compliance.md). Someone running a modified copy points it
// at their own source; a value that is not an http(s) URL must never become a link.
import assert from "node:assert/strict";
import { sourceUrl } from "../lib/legal.ts";

const upstream = "https://github.com/bobbyaqlaar/AgentSmith";

assert.equal(sourceUrl(undefined), upstream);
assert.equal(sourceUrl(""), upstream);
assert.equal(sourceUrl("https://git.example.com/acme/agentsmith"), "https://git.example.com/acme/agentsmith");
assert.equal(sourceUrl("http://git.internal/acme"), "http://git.internal/acme");
assert.equal(sourceUrl("javascript:alert(1)"), upstream, "a script URL must not reach an href");
assert.equal(sourceUrl("not a url"), upstream);
console.log("ok - the portal's source offer");
