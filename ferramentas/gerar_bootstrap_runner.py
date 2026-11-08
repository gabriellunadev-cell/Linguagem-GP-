#!/usr/bin/env python3
"""Generate and report the versioned GP frontend bootstrap runner artifact."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gp_compile import generate_selfhosted_runner_artifact


def main() -> int:
    manifest = generate_selfhosted_runner_artifact(force=True)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
