# examples/oil-price-agent/Dockerfile — container image for the oil-price-demo
# worker (Temporal poller + /healthz). Build context must be the AgentSmith
# repo ROOT (not this directory) so it can vendor runtime/ alongside the
# tenant app — matches the "runtime/ is never copied at dev time, only
# accessed via $AGENTSMITH_DIR" rule in OPERATIONS.md, except here it's
# baked into the image at build time instead, since there's no shared
# checkout inside a container.
#
# Build (from the AgentSmith repo root):
#   docker build -f examples/oil-price-agent/Dockerfile -t oil-price-worker .
#
# CI/CD: .github/actions/build-push-ghcr builds from the repo root
# automatically if a Dockerfile exists there — for a standalone tenant repo
# (oil-price-demo), this Dockerfile is copied to the tenant repo root, and
# runtime/ is vendored alongside it (see OPERATIONS.md §2.2 step 2 / §D.5b).

FROM python:3.12-slim

WORKDIR /app

# Only the runtime deps this worker actually needs at runtime — not the full
# framework requirements.txt (dev/CI tooling like pytest, langgraph, etc.
# doesn't belong in a production worker image).
COPY runtime/requirements-runtime.txt /app/requirements-runtime.txt
RUN pip install --no-cache-dir -r /app/requirements-runtime.txt

COPY runtime/ /app/runtime/
COPY examples/oil-price-agent/ /app/tenant/

ENV AGENTSMITH_DIR=/app
WORKDIR /app/tenant

EXPOSE 8080
CMD ["python3", "worker.py"]
