# portal/Dockerfile — multi-stage build for the Ops Portal.
#
# Used by the repo's docker-compose.yml `portal` service (and the vendored
# copy under ~/.agent-framework/observability/ — see install-ai-stack.sh)
# as the standing, machine-wide Ops Portal. Relies on next.config.mjs's
# `output: "standalone"` so the runner stage only needs the trimmed
# .next/standalone tree, not the full node_modules.
#
# node:22, not node:20 — scripts/migrate.ts and the test runner both use
# `node --experimental-strip-types`, which requires Node 22.6+. Using a
# Node 20 base here would build/serve fine but silently break migration
# inside the container.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001

COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
# Not part of Next's own build trace (it's a standalone migration script,
# never imported by the app itself) — copied explicitly so `docker compose
# run portal npm run db:migrate` works against the running image without a
# separate build step.
COPY --from=build --chown=nextjs:nodejs /app/scripts ./scripts
COPY --from=build --chown=nextjs:nodejs /app/db ./db
COPY --from=build --chown=nextjs:nodejs /app/package.json ./package.json

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
