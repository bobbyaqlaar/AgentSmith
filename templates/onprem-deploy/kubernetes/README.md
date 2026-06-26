# Kubernetes / Helm — enterprise on-premise deployment

For customers running their own managed Kubernetes cluster who won't
accept raw Docker Compose (see `../README.md`'s 80/20 split). Requires the
[Kubernetes Gateway API](https://gateway-api.sigs.k8s.io/) CRDs installed
in the cluster, plus one of:

- **Traefik** as the cluster's Gateway API controller (`proxyEngine: traefik`,
  the default) — Traefik's `GatewayClass` is named `traefik`.
- **Envoy Gateway** (`proxyEngine: envoy-gateway`) — its `GatewayClass` is
  named `eg`.

Both are real, open-source Gateway API implementations; this chart targets
the **standard** Gateway API resources (`Gateway`, `HTTPRoute`) rather than
either project's proprietary CRDs, so the same chart works under either —
override `gatewayClassName` directly if your cluster's installation uses a
non-default name.

## Install

```bash
helm install my-app . \
  --set image.prod=ghcr.io/your-org/your-app:abc1234 \
  --set host=agent.your-customer.example.com \
  --set envSecretName=my-app-secrets
```

## Canary

```bash
helm upgrade my-app . \
  --set image.prod=ghcr.io/your-org/your-app:abc1234 \
  --set canary.enabled=true \
  --set image.canary=ghcr.io/your-org/your-app:def5678 \
  --set canary.weightPercent=10
```

`backendRefs[].weight` is a **core** Gateway API field — the 90/10 split
works identically under Traefik's or Envoy Gateway's controller.

## Shadow

```bash
helm upgrade my-app . --set shadow.enabled=true --set image.shadow=ghcr.io/your-org/your-app:canary-build
```

**Limitation vs. the Docker Compose template:** core Gateway API's
`RequestMirror` route filter always mirrors 100% of traffic matched by the
rule — there's no percentage field in the standard spec (unlike
Traefik's/Envoy's native proxy config used directly in
`../docker-compose.traefik.yml`/`../docker-compose.envoy.yml`, which do
support a percent). Partial-percentage mirroring on Kubernetes requires a
vendor-specific extension (Istio's `VirtualService.httpMirrorPercentage`,
or an Envoy Gateway `BackendTrafficPolicy`) and isn't included here, to
keep this chart portable across both supported proxy engines using only
the Gateway API standard. If you need a percentage on K8s specifically,
add the vendor extension on top of this chart's `HTTPRoute` rather than
forking it.

## Air-gapped clusters

Same image-bundling approach as `../README.md`'s Compose path: build/save
images on a connected machine, load them into the cluster's own private
registry mirror (Harbor, a local registry, whatever the customer already
runs), then `helm install` with `image.prod` pointing at that internal
registry — this chart never references a public registry itself.

## State layer

Set `withDb.enabled=true` for a consolidated PostgreSQL+pgvector
StatefulSet (`pgvector/pgvector:pg16`), same rationale as the Compose
template — fewer dependencies for the customer to operate. Provide
`withDb.credentialsSecretName` pointing at a pre-created `Secret` with
`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` keys; this chart never
generates or stores credentials itself.
