/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone build: copies only the production deps a request actually
  // needs into .next/standalone, so the Docker image (Dockerfile) doesn't
  // need to ship the full node_modules tree.
  output: "standalone",
  experimental: {
    // Enables instrumentation.ts, which registers the OTel provider before the
    // first request. Next 14 needs this flag; it is on by default from 15.
    instrumentationHook: true,
  },
};

export default nextConfig;
