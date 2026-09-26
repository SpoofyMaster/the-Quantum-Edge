"""Append-only trial registry: every evaluated strategy variant is counted (multiple-testing control)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .config import ROOT

REGISTRY = ROOT / "results" / "trial_registry.jsonl"


def register_trial(experiment: str, variant: dict, metrics: dict, data_kind: str) -> None:
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "experiment": experiment,
           "data_kind": data_kind, "variant": variant, "metrics": metrics}
    with open(REGISTRY, "a") as f:
        f.write(json.dumps(rec, default=float) + "\n")


def count_trials(data_kind: str | None = None) -> int:
    if not REGISTRY.exists():
        return 0
    n = 0
    with open(REGISTRY) as f:
        for line in f:
            if data_kind is None or json.loads(line)["data_kind"] == data_kind:
                n += 1
    return n
