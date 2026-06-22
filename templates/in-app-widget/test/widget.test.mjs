// templates/in-app-widget/test/widget.test.mjs — jsdom regression tests for
// <agent-status> (widget.js). Run: npm test (from templates/in-app-widget/).
//
// Includes a regression test for a real attribute-injection XSS that was
// found and fixed during initial implementation: a crafted errorSummary
// containing a `"` could break out of the `title="..."` attribute and
// inject arbitrary attributes/event handlers. See README.md "Auth & security".

import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";

function freshDom() {
  const dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "https://tenant-app.example.com",
  });
  global.window = dom.window;
  global.document = dom.window.document;
  global.customElements = dom.window.customElements;
  global.HTMLElement = dom.window.HTMLElement;
  return dom;
}

function loadWidget(dom) {
  const src = readFileSync(new URL("../widget.js", import.meta.url), "utf-8");
  new dom.window.Function(src)();
}

async function mountWidget(attrs) {
  const el = document.createElement("agent-status");
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  document.body.appendChild(el);
  await new Promise((r) => setTimeout(r, 50));
  return el;
}

let passed = 0;
function test(name, fn) {
  return (async () => {
    try {
      await fn();
      passed += 1;
      console.log(`ok - ${name}`);
    } catch (err) {
      console.error(`not ok - ${name}`);
      console.error(err);
      process.exitCode = 1;
    }
  })();
}

const dom = freshDom();
loadWidget(dom);

await test("renders status, tenant label, truncated error, and trace link", async () => {
  global.fetch = async () => ({
    ok: true,
    json: async () => ({
      tenantId: "acme",
      status: "degraded",
      errorSummary: "validator_failed_max_retries on revision 2 because of a timeout",
      traceUrl: "https://phoenix.acme.example.com/projects",
    }),
  });
  const el = await mountWidget({ "tenant-id": "acme", token: "good", "portal-url": "https://ops.example.com" });
  const html = el.shadowRoot.innerHTML;
  assert.match(html, /Degraded/);
  assert.match(html, /acme/);
  assert.match(html, /validator_failed_max_retries/);
  assert.match(html, /href="https:\/\/phoenix\.acme\.example\.com\/projects"/);
});

await test("invalid token shows an error, not a crash", async () => {
  global.fetch = async () => ({ ok: false, status: 401, json: async () => ({ error: "invalid or revoked token" }) });
  const el = await mountWidget({ token: "bad", "portal-url": "https://ops.example.com" });
  assert.match(el.shadowRoot.innerHTML, /invalid or revoked token/);
});

await test("missing required attributes shows a config error", async () => {
  const el = await mountWidget({ token: "x" }); // no portal-url
  assert.match(el.shadowRoot.innerHTML, /requires both/);
});

await test("SECURITY: errorSummary cannot break out of the title attribute", async () => {
  global.fetch = async () => ({
    ok: true,
    json: async () => ({
      tenantId: "acme",
      status: "failed",
      errorSummary: 'oops" onmouseover="alert(1)',
      traceUrl: null,
    }),
  });
  const el = await mountWidget({ token: "x", "portal-url": "https://ops.example.com" });
  const span = el.shadowRoot.querySelector(".af-muted");
  assert.equal(span.hasAttribute("onmouseover"), false, "attribute injection succeeded — XSS regression!");
  assert.deepEqual(
    Array.from(span.attributes).map((a) => a.name).sort(),
    ["class", "title"]
  );
});

await test("SECURITY: errorSummary with <img onerror> never becomes a live element", async () => {
  global.fetch = async () => ({
    ok: true,
    json: async () => ({ tenantId: "acme", status: "failed", errorSummary: "<img src=x onerror=alert(1)>", traceUrl: null }),
  });
  const el = await mountWidget({ token: "x", "portal-url": "https://ops.example.com" });
  assert.equal(el.shadowRoot.querySelectorAll("img").length, 0);
});

console.log(`\n${passed} passed`);
process.exit(process.exitCode || 0);
