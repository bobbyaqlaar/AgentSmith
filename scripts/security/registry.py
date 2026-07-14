from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


CheckType = Literal["unit", "integration", "eval", "artifact", "static", "live"]
ControlStatus = Literal["met", "partial", "gap", "org-owned"]
Owner = Literal["framework", "tenant", "shared"]


@dataclass(frozen=True)
class FrameworkTags:
    owasp: list[str]
    nist: list[str]
    atlas: list[str]
    iso42001: list[int]


@dataclass(frozen=True)
class ControlSpec:
    id: str
    title: str
    status: ControlStatus
    owner: Owner
    frameworks: FrameworkTags
    runner: str
    check_type: CheckType
    mechanism: str


def load_control_registry(path: Path) -> list[ControlSpec]:
    raw = json.loads(path.read_text())
    seen: set[str] = set()
    out: list[ControlSpec] = []
    for row in raw:
        cid = row["id"]
        if cid in seen:
            raise ValueError(f"duplicate control id: {cid}")
        seen.add(cid)
        fw = row.get("frameworks", {})
        out.append(
            ControlSpec(
                id=cid,
                title=row["title"],
                status=row["status"],
                owner=row["owner"],
                frameworks=FrameworkTags(
                    owasp=list(fw.get("owasp", [])),
                    nist=list(fw.get("nist", [])),
                    atlas=list(fw.get("atlas", [])),
                    iso42001=[int(x) for x in fw.get("iso42001", [])],
                ),
                runner=row["runner"],
                check_type=row["check_type"],
                mechanism=row["mechanism"],
            )
        )
    return out
