/**
 * AgenticFramework In-App Widget — <agent-status>
 *
 * Embeddable, read-only status component for tenant applications
 * (SPECS.md §15, §26). No framework dependency, no build step.
 *
 * Usage:
 *   <script src="https://cdn.agenticframework.io/widget.js"></script>
 *   <agent-status
 *     tenant-id="acme"
 *     token="<read-only-scoped-token>"
 *     portal-url="https://ops.example.com"
 *   ></agent-status>
 *
 * Security: `tenant-id` is a DISPLAY LABEL ONLY. Which tenant's data is
 * returned is determined entirely by `token`, which the portal resolves
 * server-side (see portal/app/api/widget/status/route.ts) — there is no way
 * to spoof another tenant's data by changing the tenant-id attribute.
 *
 * Mint a token via: POST {portal-url}/api/tenants/:id/widget-token
 * (requires the Ops Portal dashboard's basic auth credentials — do this
 * once from a trusted environment, not from the browser).
 */
(function () {
  "use strict";

  const STATUS_COLORS = {
    success: "#22c55e",
    degraded: "#f59e0b",
    failed: "#ef4444",
    unknown: "#6b7280",
  };

  const STATUS_LABELS = {
    success: "Operational",
    degraded: "Degraded",
    failed: "Failed",
    unknown: "Unknown",
  };

  const DEFAULT_POLL_INTERVAL_MS = 30000;

  class AgentStatus extends HTMLElement {
    constructor() {
      super();
      this._root = this.attachShadow({ mode: "open" });
      this._pollHandle = null;
    }

    static get observedAttributes() {
      return ["tenant-id", "token", "portal-url", "poll-interval-ms"];
    }

    connectedCallback() {
      this._render({ loading: true });
      this._fetchAndRender();
      const interval = parseInt(this.getAttribute("poll-interval-ms") || "", 10) || DEFAULT_POLL_INTERVAL_MS;
      this._pollHandle = setInterval(() => this._fetchAndRender(), interval);
    }

    disconnectedCallback() {
      if (this._pollHandle) clearInterval(this._pollHandle);
    }

    attributeChangedCallback() {
      if (this.isConnected) this._fetchAndRender();
    }

    async _fetchAndRender() {
      const token = this.getAttribute("token");
      const portalUrl = this.getAttribute("portal-url");

      if (!token || !portalUrl) {
        this._render({ error: "agent-status requires both 'token' and 'portal-url' attributes." });
        return;
      }

      try {
        const resp = await fetch(`${portalUrl.replace(/\/$/, "")}/api/widget/status?token=${encodeURIComponent(token)}`, {
          headers: { Accept: "application/json" },
        });
        if (!resp.ok) {
          const body = await resp.json().catch(() => ({}));
          this._render({ error: body.error || `Status unavailable (HTTP ${resp.status})` });
          return;
        }
        const data = await resp.json();
        this._render({ data });
      } catch (err) {
        this._render({ error: "Could not reach the status service." });
      }
    }

    _render({ loading, error, data }) {
      const tenantLabel = this.getAttribute("tenant-id") || "";
      const status = data?.status || "unknown";
      const color = STATUS_COLORS[status] || STATUS_COLORS.unknown;
      const label = STATUS_LABELS[status] || STATUS_LABELS.unknown;

      this._root.innerHTML = `
        <style>
          .af-widget {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-family: system-ui, -apple-system, sans-serif;
            font-size: 13px;
            color: #1f2937;
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            padding: 6px 10px;
            background: #fff;
          }
          .af-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
          }
          .af-link {
            color: inherit;
            text-decoration: none;
          }
          .af-error { color: #ef4444; }
          .af-muted { color: #6b7280; }
        </style>
        <div class="af-widget" role="status" aria-live="polite">
          ${
            error
              ? `<span class="af-dot" style="background:${STATUS_COLORS.unknown}"></span><span class="af-error">${this._escape(error)}</span>`
              : loading
              ? `<span class="af-dot" style="background:${STATUS_COLORS.unknown}"></span><span class="af-muted">Loading${tenantLabel ? " " + this._escape(tenantLabel) : ""}…</span>`
              : `
                <span class="af-dot" style="background:${color}"></span>
                <span>${tenantLabel ? this._escape(tenantLabel) + ": " : ""}${label}</span>
                ${data?.errorSummary ? `<span class="af-muted" title="${this._escapeAttr(data.errorSummary)}"> — ${this._escape(this._truncate(data.errorSummary, 40))}</span>` : ""}
                ${data?.traceUrl ? `<a class="af-link" href="${this._escapeAttr(data.traceUrl)}" target="_blank" rel="noopener noreferrer" style="text-decoration:underline">trace</a>` : ""}
              `
          }
        </div>
      `;
    }

    _truncate(text, max) {
      return text.length > max ? text.slice(0, max) + "…" : text;
    }

    _escape(text) {
      const div = document.createElement("div");
      div.textContent = String(text);
      return div.innerHTML;
    }

    // For values placed inside a double-quoted HTML attribute (title=, href=).
    // Must escape '&' first (so it doesn't double-escape the entities it just
    // introduced), then '"' to prevent breaking out of the attribute, plus
    // '<'/'>' defensively.
    _escapeAttr(text) {
      return String(text)
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    }
  }

  if (!customElements.get("agent-status")) {
    customElements.define("agent-status", AgentStatus);
  }
})();
