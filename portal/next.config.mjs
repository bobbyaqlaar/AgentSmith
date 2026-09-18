/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone build: copies only the production deps a request actually
  // needs into .next/standalone, so the Docker image (Dockerfile) doesn't
  // need to ship the full node_modules tree.
  output: "standalone",
  // Portal phase 1 moved the operations pages under /ops. Old links —
  // bookmarks, a runbook, an alert — still land where they meant.
  async redirects() {
    return [
      { source: "/tenants/:id", destination: "/ops/apps/:id", permanent: true },
      { source: "/dlq", destination: "/ops/dlq", permanent: true },
      { source: "/dlq/:tenantId", destination: "/ops/dlq/:tenantId", permanent: true },
      { source: "/audit", destination: "/ops/audit", permanent: true },
    ];
  },
  experimental: {
    // Enables instrumentation.ts, which registers the OTel provider before the
    // first request. Next 14 needs this flag; it is on by default from 15.
    instrumentationHook: true,
  },
};

export default nextConfig;
