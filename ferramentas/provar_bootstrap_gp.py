#!/usr/bin/env python3
"""Attempt the GP frontend N -> N+1 -> N+2 bootstrap proof."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gp_compile import (
    _selfhosted_runner_source,
    compile_source_selfhosted_document,
    generate_selfhosted_runner_artifact,
    load_selfhosted_runner_artifact,
)
from gpcompiler.bytecode import decode, encode_canonical_ir
from gp_compile import encode_canonical_ir_native


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-vm", default=str(ROOT / "build" / "gpvm-native"))
    parser.add_argument("--output", default=str(ROOT / "artifacts" / "bootstrap" / "proof"))
    parser.add_argument(
        "--runner-timeout-seconds", type=int, default=600,
        help="limite por estágio de execução nativa (1..3600 segundos)",
    )
    parser.add_argument(
        "--runner-max-steps", type=int, default=100_000_000,
        help="limite de instruções GP por estágio (1..100000000)",
    )
    args = parser.parse_args()
    if not 1 <= args.runner_timeout_seconds <= 3600:
        parser.error("--runner-timeout-seconds deve estar entre 1 e 3600")
    if not 1 <= args.runner_max_steps <= 100_000_000:
        parser.error("--runner-max-steps deve estar entre 1 e 100000000")

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    # Never let an earlier successful proof survive a failed new attempt.
    for stale_name in (
        "proof.json",
        "memory_n_to_n1.json",
        "memory_n1_to_n2.json",
        "gp_frontend_runner_n1.gbc",
        "gp_frontend_runner_n2.gbc",
    ):
        stale_path = output / stale_name
        if stale_path.exists():
            stale_path.unlink()
    source_path = ROOT / "linguagem" / "parser_gp.gp"
    source = _selfhosted_runner_source()

    # A proof must begin from the checked-in seed. Never repair or regenerate
    # the seed through the Python compiler while claiming a native bootstrap.
    manifest_n = generate_selfhosted_runner_artifact(allow_python_bootstrap=False)
    artifact_n = load_selfhosted_runner_artifact(require_existing=True)
    print("STAGE_N", digest(artifact_n), flush=True)

    # N executes the compiler source in the native C VM and emits N+1.
    memory_n1_path = output / "memory_n_to_n1.json"
    with patch.dict(os.environ, {"GPVM_MEMORY_REPORT": str(memory_n1_path)}):
        document_n1 = compile_source_selfhosted_document(
            source,
            source_path=source_path,
            runner_backend="native",
            native_vm=args.native_vm,
            runner_max_steps=args.runner_max_steps,
            runner_timeout_seconds=args.runner_timeout_seconds,
        )
    artifact_n1_reference = encode_canonical_ir(document_n1)
    artifact_n1 = encode_canonical_ir_native(
        document_n1, args.native_vm, timeout_seconds=args.runner_timeout_seconds,
    )
    if artifact_n1 != artifact_n1_reference:
        raise SystemExit("Divergência binária entre encoder Python e C em N+1")
    decode(artifact_n1)
    (output / "gp_frontend_runner_n1.gbc").write_bytes(artifact_n1)
    print("STAGE_N1", digest(artifact_n1), "bytes", len(artifact_n1), flush=True)

    # N+1 is then executed by the same native C VM. If its GP-IR differs,
    # the two-stage proof fails closed.
    memory_n2_path = output / "memory_n1_to_n2.json"
    with patch("gp_compile.load_selfhosted_runner_artifact", return_value=artifact_n1), patch.dict(
        os.environ, {"GPVM_MEMORY_REPORT": str(memory_n2_path)}
    ):
        document_n2 = compile_source_selfhosted_document(
            source,
            source_path=source_path,
            runner_backend="native",
            native_vm=args.native_vm,
            runner_max_steps=args.runner_max_steps,
            runner_timeout_seconds=args.runner_timeout_seconds,
        )
    artifact_n2_reference = encode_canonical_ir(document_n2)
    artifact_n2 = encode_canonical_ir_native(
        document_n2, args.native_vm, timeout_seconds=args.runner_timeout_seconds,
    )
    if artifact_n2 != artifact_n2_reference:
        raise SystemExit("Divergência binária entre encoder Python e C em N+2")
    decode(artifact_n2)
    (output / "gp_frontend_runner_n2.gbc").write_bytes(artifact_n2)
    print("STAGE_N2", digest(artifact_n2), "bytes", len(artifact_n2), flush=True)

    if document_n1 != document_n2 or artifact_n1 != artifact_n2:
        raise SystemExit("BOOTSTRAP_DIVERGENCE: N+1 != N+2")

    report = {
        "proof": "GP frontend bootstrap N -> N+1 -> N+2",
        "status": "passed",
        "artifact_n_sha256": digest(artifact_n),
        "artifact_n1_sha256": digest(artifact_n1),
        "artifact_n2_sha256": digest(artifact_n2),
        "n1_equals_n2": artifact_n1 == artifact_n2,
        "native_stages": ["N -> N+1", "N+1 -> N+2"],
        "builder_n": manifest_n,
        "memory": {
            "measurement": "native VM allocation pools; peak values are independent maxima",
            "n_to_n1": json.loads(memory_n1_path.read_text(encoding="utf-8")),
            "n1_to_n2": json.loads(memory_n2_path.read_text(encoding="utf-8")),
        },
    }
    temporary_report = output / "proof.json.tmp"
    temporary_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_report.replace(output / "proof.json")
    print("BOOTSTRAP_PROOF_OK", flush=True)
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except BaseException as exc:
        print(f"BOOTSTRAP_PROOF_FAILED: {type(exc).__name__}: {exc}", flush=True)
        raise
    raise SystemExit(exit_code)
