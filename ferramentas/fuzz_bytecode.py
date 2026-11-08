#!/usr/bin/env python3
"""Deterministic, resource-bounded differential smoke fuzzer for GP bytecode v2."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import random
import resource
import struct
import zlib
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gpcompiler.bytecode import decode
from gpcompiler.vm import GPVirtualMachine


MAX_ITERATIONS = 512
MAX_FIXTURE_BYTES = 2 * 1024 * 1024
NATIVE_MEMORY_LIMIT = 512 * 1024 * 1024
NATIVE_CPU_LIMIT = 3
DEFAULT_SEED = 0x47505632


def repack_json(data: bytes, payload: dict, *, pretty: bool = False) -> bytes:
    """Rebuild a valid v2 envelope while preserving its outer version."""
    magic, version, _raw_size, _crc = struct.unpack(">4sHII", data[:14])
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    ).encode("utf-8")
    header = struct.pack(
        ">4sHII", magic, version, len(raw), zlib.crc32(raw) & 0xFFFFFFFF
    )
    return header + zlib.compress(raw, level=9)


def mutate(data: bytes, rng: random.Random) -> tuple[bytes, str]:
    """Apply one bounded mutation to a golden input, valid or invalid."""
    kind = rng.choice(
        (
            "bitflip", "truncate", "append", "header", "zlib_bitflip",
            "crc_bitflip", "valid_reorder", "valid_whitespace", "valid_extension",
        )
    )
    if kind.startswith("valid_"):
        payload = json.loads(zlib.decompress(data[14:]).decode("utf-8"))
        if kind == "valid_extension":
            payload["x-fuzz-extension"] = {
                "seed": rng.randrange(2**31),
                "note": "unknown-field-preservation",
            }
        return repack_json(data, payload, pretty=kind == "valid_whitespace"), kind
    if kind == "bitflip":
        offset = rng.randrange(len(data))
        changed = bytearray(data)
        changed[offset] ^= 1 << rng.randrange(8)
        return bytes(changed), f"bitflip@{offset}"

    if kind == "truncate":
        size = rng.randrange(len(data))
        return data[:size], f"truncate@{size}"

    if kind == "append":
        suffix = rng.randbytes(rng.randint(1, 8))
        return data + suffix, f"append-{len(suffix)}"

    if kind == "header":
        offset = rng.randrange(min(14, len(data)))
        changed = bytearray(data)
        changed[offset] ^= 1 << rng.randrange(8)
        return bytes(changed), f"header-bitflip@{offset}"

    if kind == "zlib_bitflip":
        if len(data) <= 14:
            return data[:-1], "zlib-empty-truncate"
        offset = rng.randrange(14, len(data))
        changed = bytearray(data)
        changed[offset] ^= 1 << rng.randrange(8)
        return bytes(changed), f"zlib-bitflip@{offset}"

    if len(data) < 14:
        return data[:-1], "crc-short-file"
    offset = rng.randrange(10, 14)
    changed = bytearray(data)
    changed[offset] ^= 1 << rng.randrange(8)
    return bytes(changed), f"crc-bitflip@{offset}"


def run_python(data: bytes) -> tuple[bool, bool, str]:
    """Return (decoder_accepted, execution_succeeded, stdout)."""
    try:
        decode(data)
    except Exception:
        return False, False, ""

    output = io.StringIO()
    succeeded = True
    with contextlib.redirect_stdout(output):
        try:
            GPVirtualMachine(max_steps=1_000_000).run_bytes(data)
        except Exception:
            succeeded = False
    return True, succeeded, output.getvalue()


def _limit_native_resources() -> None:
    # RLIMIT_AS breaks Android/Bionic's linker CFI shadow mappings. RLIMIT_DATA
    # constrains heap/data allocations while leaving those virtual mappings intact.
    resource.setrlimit(resource.RLIMIT_DATA, (NATIVE_MEMORY_LIMIT, NATIVE_MEMORY_LIMIT))
    resource.setrlimit(resource.RLIMIT_CPU, (NATIVE_CPU_LIMIT, NATIVE_CPU_LIMIT))


def run_native(vm: Path, data: bytes, timeout: float) -> tuple[bool, str, str]:
    """Return (process_succeeded, stdout, stderr), with child CPU/RAM caps."""
    with tempfile.NamedTemporaryFile(prefix="gp-fuzz-", suffix=".gbc") as handle:
        handle.write(data)
        handle.flush()
        try:
            result = subprocess.run(
                [str(vm), handle.name],
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout,
                preexec_fn=_limit_native_resources,
            )
        except subprocess.TimeoutExpired:
            return False, "", "timeout"
        except OSError as exc:
            return False, "", f"spawn-error: {exc}"
    return result.returncode == 0, result.stdout, result.stderr


def main(argv: list[str] | None = None) -> int:
    project = PROJECT_ROOT
    parser = argparse.ArgumentParser(
        description="Executa mutações determinísticas e compara loaders/VMs Python e C."
    )
    parser.add_argument("--fixtures", type=Path, default=project / "tests/fixtures/bytecode_v2")
    parser.add_argument("--native-vm", type=Path, default=project / "build/gpvm-native-final")
    parser.add_argument("--iterations", type=int, default=64)
    parser.add_argument("--seed", type=lambda value: int(value, 0), default=DEFAULT_SEED)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--report", type=Path, default=project / "build/fuzz-reports/latest.json")
    args = parser.parse_args(argv)

    if not 1 <= args.iterations <= MAX_ITERATIONS:
        parser.error(f"--iterations deve estar entre 1 e {MAX_ITERATIONS}")
    if not 0.1 <= args.timeout <= 5.0:
        parser.error("--timeout deve estar entre 0.1 e 5 segundos")
    vm = args.native_vm.resolve()
    if not vm.is_file():
        parser.error(f"VM nativa não encontrada: {vm}")

    fixtures = sorted(args.fixtures.glob("*.gbc"))
    if not fixtures:
        parser.error(f"Nenhuma fixture .gbc em {args.fixtures}")

    seeds: list[tuple[str, bytes]] = []
    for fixture in fixtures:
        data = fixture.read_bytes()
        if len(data) > MAX_FIXTURE_BYTES:
            parser.error(f"Fixture excede {MAX_FIXTURE_BYTES} bytes: {fixture}")
        seeds.append((fixture.name, data))

    rng = random.Random(args.seed)
    divergences: list[dict[str, object]] = []
    divergence_cases: list[tuple[int, bytes]] = []
    rejected = 0
    executed = 0
    for iteration in range(args.iterations):
        fixture_name, original = rng.choice(seeds)
        damaged, mutation_name = mutate(original, rng)
        py_accepted, py_succeeded, py_stdout = run_python(damaged)
        c_succeeded, c_stdout, c_stderr = run_native(vm, damaged, args.timeout)

        # A CLI C combines loading and execution. A Python decoder rejection
        # paired with a successful C execution is a definite loader divergence.
        mismatch = False
        reason = ""
        if not py_accepted:
            rejected += 1
            mismatch = c_succeeded
            reason = "Python recusou; VM C executou" if mismatch else ""
        else:
            executed += 1
            mismatch = py_succeeded != c_succeeded or (
                py_succeeded and c_succeeded and py_stdout != c_stdout
            )
            reason = "resultado/saída divergente entre VMs" if mismatch else ""

        if mismatch:
            divergence_cases.append((iteration, damaged))
            divergences.append(
                {
                    "iteration": iteration,
                    "fixture": fixture_name,
                    "mutation": mutation_name,
                    "python_accepted": py_accepted,
                    "python_succeeded": py_succeeded,
                    "native_succeeded": c_succeeded,
                    "python_stdout": py_stdout[:500],
                    "native_stdout": c_stdout[:500],
                    "native_stderr": c_stderr[:500],
                    "reason": reason,
                }
            )

    report = {
        "seed": args.seed,
        "resource_limits": {
            "native_data_segment_bytes": NATIVE_MEMORY_LIMIT,
            "native_cpu_seconds": NATIVE_CPU_LIMIT,
            "native_wall_timeout_seconds": args.timeout,
            "python_vm_max_steps": 1_000_000,
            "max_fixture_bytes": MAX_FIXTURE_BYTES,
        },
        "iterations": args.iterations,
        "fixtures": len(fixtures),
        "decoder_rejections": rejected,
        "accepted_and_executed": executed,
        "divergences": divergences,
        "native_vm": str(vm),
    }
    report_path = args.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report["report_path"] = str(report_path)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for iteration, case_data in divergence_cases:
        (report_path.parent / f"divergence-{iteration:04d}.gbc").write_bytes(case_data)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if divergences else 0


if __name__ == "__main__":
    raise SystemExit(main())
