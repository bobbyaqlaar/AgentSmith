#!/usr/bin/env python3
"""render-traefik-config.py — builds proxy/traefik/dynamic.rendered.yml from
.env's APP_PORT/CANARY_WEIGHT_PERCENT/SHADOW_MIRROR_PERCENT and which
APP_IMAGE_* values are set, using Traefik's native `weighted` and
`mirroring` service kinds. Built as a real dict + yaml.safe_dump rather
than string templating, so it's never invalid YAML regardless of which
optional services are active.

Run by scripts/up.sh before `docker compose up`. Output is gitignored —
regenerated every run, never edited by hand.
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


def main() -> int:
    env = load_env(HERE / ".env")
    app_port = env.get("APP_PORT", "8080")
    canary_image = env.get("APP_IMAGE_CANARY", "").strip()
    shadow_image = env.get("APP_IMAGE_SHADOW", "").strip()
    canary_weight = int(env.get("CANARY_WEIGHT_PERCENT", "10") or "10")
    shadow_percent = int(env.get("SHADOW_MIRROR_PERCENT", "100") or "100")

    for name, value in (("CANARY_WEIGHT_PERCENT", canary_weight), ("SHADOW_MIRROR_PERCENT", shadow_percent)):
        if not 0 <= value <= 100:
            print(f"❌ {name} must be 0-100, got {value}", file=sys.stderr)
            return 1

    services: dict = {
        "app-prod-svc": {
            "loadBalancer": {
                "servers": [{"url": f"http://app-prod:{app_port}"}],
                "healthCheck": {"path": "/healthz", "interval": "15s", "timeout": "5s"},
            }
        }
    }

    root_service = "app-prod-svc"

    if canary_image:
        services["app-canary-svc"] = {
            "loadBalancer": {
                "servers": [{"url": f"http://app-canary:{app_port}"}],
                "healthCheck": {"path": "/healthz", "interval": "15s", "timeout": "5s"},
            }
        }
        services["app-weighted"] = {
            "weighted": {
                "services": [
                    {"name": "app-prod-svc", "weight": max(0, 100 - canary_weight)},
                    {"name": "app-canary-svc", "weight": canary_weight},
                ]
            }
        }
        root_service = "app-weighted"

    if shadow_image:
        services["app-shadow-svc"] = {
            "loadBalancer": {
                "servers": [{"url": f"http://app-shadow:{app_port}"}],
                "healthCheck": {"path": "/healthz", "interval": "15s", "timeout": "5s"},
            }
        }
        services["app-mirrored"] = {
            "mirroring": {
                "service": root_service,
                "mirrors": [{"name": "app-shadow-svc", "percent": shadow_percent}],
            }
        }
        root_service = "app-mirrored"

    config = {
        "http": {
            "routers": {
                "app": {"rule": "PathPrefix(`/`)", "entryPoints": ["web"], "service": root_service}
            },
            "services": services,
        }
    }

    out_path = HERE / "proxy" / "traefik" / "dynamic.rendered.yml"
    out_path.write_text(yaml.safe_dump(config, sort_keys=False))
    print(f"✅ Wrote {out_path} (root service: {root_service})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
