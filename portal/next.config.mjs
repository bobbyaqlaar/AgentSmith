/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone build: copies only the production deps a request actually
  // needs into .next/standalone, so the Docker image (Dockerfile) doesn't
  // need to ship the full node_modules tree.
  output: "standalone",
  // Portal phase 1 moved the operations pages under /ops. Old links —
  // bookmarks, a runbook, an alert — still land where they meant.
  async headers() {
    const script = process.env.NODE_ENV === "production" ? "script-src 'self' 'unsafe-inline'" : "script-src 'self' 'unsafe-inline' 'unsafe-eval'";
    const common = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "same-origin" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Content-Security-Policy", value: `default-src 'self'; ${script}; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'` },
      ...(process.env.COMPLIANCE_PROFILE ? [{ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" }] : []),
    ];
    // The widget's routes are called from other sites, so they keep their own rules.
    return [{ source: "/((?!api/widget).*)", headers: common }];
  },
  async redirects() {
    return [
      { source: "/tenants/:id", destination: "/ops/apps/:id", permanent: true },
      { source: "/dlq", destination: "/ops/dlq", permanent: true },
      { source: "/dlq/:tenantId", destination: "/ops/dlq/:tenantId", permanent: true },
      { source: "/audit", destination: "/ops/audit", permanent: true },
    ];
  },
};

export default nextConfig;
