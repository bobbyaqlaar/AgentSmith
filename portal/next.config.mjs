/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone build: copies only the production deps a request actually
  // needs into .next/standalone, so the Docker image (Dockerfile) doesn't
  // need to ship the full node_modules tree.
  output: "standalone",
};

export default nextConfig;
