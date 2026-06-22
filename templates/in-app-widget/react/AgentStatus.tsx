// templates/in-app-widget/react/AgentStatus.tsx — optional React wrapper
// around the vanilla <agent-status> web component (../widget.js).
//
// This component does NOT reimplement the widget's logic — it loads
// widget.js once and renders the custom element, so behaviour (polling,
// rendering, escaping) stays identical to the vanilla embed. If you don't
// use React, skip this file and use the <script> + <agent-status> tags
// directly per README.md.
//
// Usage:
//   <AgentStatus tenantId="acme" token={token} portalUrl="https://ops.example.com" />

import { useEffect, useRef } from "react";

export interface AgentStatusProps {
  tenantId?: string;
  token: string;
  portalUrl: string;
  pollIntervalMs?: number;
  widgetScriptUrl?: string; // defaults to the AgenticFramework CDN build
}

let widgetScriptPromise: Promise<void> | null = null;

function loadWidgetScript(src: string): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (customElements.get("agent-status")) return Promise.resolve();
  if (!widgetScriptPromise) {
    widgetScriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = src;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error(`Failed to load ${src}`));
      document.head.appendChild(script);
    });
  }
  return widgetScriptPromise;
}

export function AgentStatus({
  tenantId,
  token,
  portalUrl,
  pollIntervalMs,
  widgetScriptUrl = "https://cdn.agenticframework.io/widget.js",
}: AgentStatusProps) {
  const ref = useRef<HTMLElement | null>(null);

  useEffect(() => {
    loadWidgetScript(widgetScriptUrl).catch((err) => console.error("[AgentStatus]", err));
  }, [widgetScriptUrl]);

  return (
    <agent-status
      ref={ref as never}
      tenant-id={tenantId}
      token={token}
      portal-url={portalUrl}
      poll-interval-ms={pollIntervalMs ? String(pollIntervalMs) : undefined}
    />
  );
}

declare global {
  namespace JSX {
    interface IntrinsicElements {
      "agent-status": React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        "tenant-id"?: string;
        token?: string;
        "portal-url"?: string;
        "poll-interval-ms"?: string;
      };
    }
  }
}
