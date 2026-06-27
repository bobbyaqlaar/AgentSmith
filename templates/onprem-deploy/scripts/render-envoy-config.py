#!/usr/bin/env python3
"""render-envoy-config.py — builds proxy/envoy/envoy.rendered.yaml, Envoy's
static bootstrap config, from .env. Same rationale as
render-traefik-config.py: built as a dict + yaml.safe_dump, not string
templating, so optional canary/shadow clusters can never produce invalid
YAML when omitted.

Uses Envoy's native `weighted_clusters` (canary split) and
`request_mirror_policies` (shadow mirroring) route fields — no Lua/WASM
filter needed, both are core HTTP connection manager route fields.
"""
import os
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent.parent


def load_env(env_path: Path) -> dict:
    env = dict(os.environ)
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip())
    return env


def cluster(name: str, address: str, port: int) -> dict:
    return {
        "name": name,
        "connect_timeout": "1s",
        "type": "STRICT_DNS",
        "lb_policy": "ROUND_ROBIN",
        "load_assignment": {
            "cluster_name": name,
            "endpoints": [
                {"lb_endpoints": [{"endpoint": {"address": {"socket_address": {"address": address, "port_value": port}}}}]}
            ],
        },
    }


def main() -> int:
    env = load_env(HERE / ".env")
    app_port = int(env.get("APP_PORT", "8080") or "8080")
    listen_port = int(env.get("PROXY_LISTEN_PORT", "80") or "80")
    canary_image = env.get("APP_IMAGE_CANARY", "").strip()
    shadow_image = env.get("APP_IMAGE_SHADOW", "").strip()
    canary_weight = int(env.get("CANARY_WEIGHT_PERCENT", "10") or "10")
    shadow_percent = int(env.get("SHADOW_MIRROR_PERCENT", "100") or "100")

    for name, value in (("CANARY_WEIGHT_PERCENT", canary_weight), ("SHADOW_MIRROR_PERCENT", shadow_percent)):
        if not 0 <= value <= 100:
            print(f"❌ {name} must be 0-100, got {value}", file=sys.stderr)
            return 1

    clusters = [cluster("app_prod", "app-prod", app_port)]

    route_action: dict = {"cluster": "app_prod"}
    if canary_image:
        clusters.append(cluster("app_canary", "app-canary", app_port))
        route_action = {
            "weighted_clusters": {
                "clusters": [
                    {"name": "app_prod", "weight": max(0, 100 - canary_weight)},
                    {"name": "app_canary", "weight": canary_weight},
                ],
                "total_weight": 100,
            }
        }

    if shadow_image:
        clusters.append(cluster("app_shadow", "app-shadow", app_port))
        route_action["request_mirror_policies"] = [
            {
                "cluster": "app_shadow",
                "runtime_fraction": {
                    "default_value": {"numerator": shadow_percent, "denominator": "HUNDRED"}
                },
            }
        ]

    config = {
        "static_resources": {
            "listeners": [
                {
                    "name": "ingress",
                    "address": {"socket_address": {"address": "0.0.0.0", "port_value": listen_port}},
                    "filter_chains": [
                        {
                            "filters": [
                                {
                                    "name": "envoy.filters.network.http_connection_manager",
                                    "typed_config": {
                                        "@type": "type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager",
                                        "stat_prefix": "ingress_http",
                                        "access_log": [
                                            {
                                                "name": "envoy.access_loggers.stdout",
                                                "typed_config": {
                                                    "@type": "type.googleapis.com/envoy.extensions.access_loggers.stream.v3.StdoutAccessLog"
                                                },
                                            }
                                        ],
                                        "route_config": {
                                            "name": "local_route",
                                            "virtual_hosts": [
                                                {
                                                    "name": "app",
                                                    "domains": ["*"],
                                                    "routes": [{"match": {"prefix": "/"}, "route": route_action}],
                                                }
                                            ],
                                        },
                                        "http_filters": [
                                            {
                                                "name": "envoy.filters.http.router",
                                                "typed_config": {
                                                    "@type": "type.googleapis.com/envoy.extensions.filters.http.router.v3.Router"
                                                },
                                            }
                                        ],
                                    },
                                }
                            ]
                        }
                    ],
                }
            ],
            "clusters": clusters,
        },
        "admin": {"address": {"socket_address": {"address": "127.0.0.1", "port_value": 9901}}},
    }

    out_path = HERE / "proxy" / "envoy" / "envoy.rendered.yaml"
    # proxy/envoy/ may be an empty dir that git doesn't track (absent on a
    # clean checkout / in CI) — create it before writing.
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(config, sort_keys=False))
    print(f"✅ Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
