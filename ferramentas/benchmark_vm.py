#!/usr/bin/env python3
"""Benchmark reproduzivel da VM Python e da VM nativa ARM64 do GP.

Mede execucao completa (inclui inicializacao do processo nativo e carga do bytecode).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import platform
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from gp_compile import compile_source
from gpcompiler.vm import GPVirtualMachine

SOURCE = """
numero i = 0
numero soma = 0
enquanto (i < 12000) {
    soma = soma + i
    i = i + 1
}
mostrar(soma)
"""

def median_seconds(fn, warmups: int, repeats: int) -> float:
    for _ in range(warmups):
        fn()
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return statistics.median(samples)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--native", type=Path, default=ROOT / "build/gpvm-native")
    args = parser.parse_args()
    if args.warmups < 0 or args.repeats < 1:
        parser.error("warmups deve ser >= 0 e repeats >= 1")
    if not args.native.is_file():
        parser.error(f"VM nativa nao encontrada: {args.native}; execute make native-vm")

    _, _, bytecode = compile_source(SOURCE)
    with tempfile.TemporaryDirectory(prefix="gp-bench-") as tmp:
        artifact = Path(tmp) / "benchmark.gbc"
        artifact.write_bytes(bytecode)

        def run_python():
            with contextlib.redirect_stdout(io.StringIO()):
                GPVirtualMachine(max_steps=2_000_000).run_bytes(bytecode)

        def run_native():
            result = subprocess.run(
                [str(args.native), str(artifact)],
                capture_output=True, text=True, check=False,
            )
            if result.returncode:
                raise RuntimeError(result.stderr or result.stdout)

        py = median_seconds(run_python, args.warmups, args.repeats)
        native = median_seconds(run_native, args.warmups, args.repeats)
        report = {
            "project": "Gabriel Programming",
            "core": "0.4",
            "device": platform.platform(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "bytecode_bytes": len(bytecode),
            "warmups": args.warmups,
            "repeats": args.repeats,
            "python_vm_median_seconds": py,
            "native_vm_process_median_seconds": native,
            "speedup_native_vs_python": py / native if native else None,
            "measurement": "inclui inicializacao e carga do processo nativo",
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
