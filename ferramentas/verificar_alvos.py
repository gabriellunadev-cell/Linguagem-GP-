#!/usr/bin/env python3
"""Report detected toolchains and evidence-backed GP native target status."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "targets" / "manifest.json"


def detect_compiler(target: dict) -> str | None:
    identifier = target["id"]
    if identifier == "android-arm64":
        env_path = os.environ.get("ANDROID_NDK_HOME", "")
        if not env_path:
            return None
        candidates = Path(env_path).glob(
            "toolchains/llvm/prebuilt/*/bin/aarch64-linux-android*-clang"
        )
        return next((str(item) for item in candidates if item.is_file()), None)
    if identifier == "wasm32-wasi":
        compiler = shutil.which(os.environ.get("GP_WASI_CC", "clang-18"))
        sysroot = Path(os.environ.get("GP_WASI_SYSROOT", "/usr"))
        zlib_prefix = Path(os.environ.get("GP_WASI_ZLIB_PREFIX", "/nonexistent"))
        wasi_headers = sysroot / "include" / "wasm32-wasi" / "unistd.h"
        wasi_zlib = zlib_prefix / "include" / "zlib.h"
        wasi_libz = zlib_prefix / "lib" / "libz.a"
        return compiler if compiler and wasi_headers.is_file() and wasi_zlib.is_file() and wasi_libz.is_file() else None
    compiler_names = {
        "linux-aarch64": "aarch64-linux-gnu-gcc",
        "windows-x64": "x86_64-w64-mingw32-gcc",
    }
    name = compiler_names.get(identifier)
    return shutil.which(name) if name else None


def runtime_available(target: dict) -> bool:
    identifier = target["id"]
    if identifier == "linux-aarch64":
        return bool(
            shutil.which("qemu-aarch64")
            and Path("/usr/aarch64-linux-gnu/lib/ld-linux-aarch64.so.1").is_file()
        )
    if identifier == "wasm32-wasi":
        python = os.environ.get("GP_WASMTIME_PYTHON", "python3")
        try:
            result = subprocess.run(
                [python, "-c", "import wasmtime"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0
    return False


def enrich(target: dict) -> dict:
    compiler = detect_compiler(target)
    artifact_path = target.get("artifact")
    artifact = (ROOT / artifact_path) if artifact_path else None
    runtime_state = runtime_available(target) if target.get("runtime_test") else None
    return {
        **target,
        "toolchain_available": bool(compiler),
        "compiler_path": compiler,
        "artifact_exists": bool(artifact and artifact.is_file()),
        **({"runtime_available": runtime_state} if runtime_state is not None else {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail unless runtime-verified and cross-compiled artifacts exist and every planned toolchain is ready",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    host_compiler = shutil.which("gcc") or shutil.which("clang")
    host = {
        "id": "linux-x86_64",
        "toolchain_available": bool(host_compiler),
        "compiler_path": host_compiler,
        "status": "host_verified" if host_compiler else "missing",
    }
    runtime_verified = [enrich(item) for item in manifest.get("runtime_verified_targets", [])]
    cross_compiled = [enrich(item) for item in manifest.get("cross_compiled_targets", [])]
    planned = [enrich(item) for item in manifest.get("planned_targets", [])]
    output = {
        "host": host,
        "runtime_verified_targets": runtime_verified,
        "cross_compiled_targets": cross_compiled,
        "planned_targets": planned,
    }
    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"HOST {host['id']}: {'available' if host['toolchain_available'] else 'missing'} ({host['compiler_path'] or 'none'})")
        for group_name, items in (
            ("RUNTIME VERIFIED", runtime_verified),
            ("CROSS COMPILED", cross_compiled),
            ("PLANNED", planned),
        ):
            for item in items:
                compiler_state = "toolchain available" if item["toolchain_available"] else "toolchain missing"
                artifact_state = "artifact present" if item["artifact_exists"] else "artifact absent"
                runtime_state = (
                    "; runtime available" if item.get("runtime_available") is True
                    else "; runtime unavailable" if item.get("runtime_available") is False
                    else ""
                )
                print(f"{group_name} {item['id']}: {item['status']}; {compiler_state}; {artifact_state}{runtime_state}")
    cross_artifacts_ready = all(
        item["toolchain_available"]
        and item["artifact_exists"]
        and item.get("runtime_available") is True
        for item in runtime_verified
    ) and all(
        item["toolchain_available"] and item["artifact_exists"]
        for item in cross_compiled
    )
    all_planned_ready = all(item["toolchain_available"] for item in planned)
    if args.strict and (not host["toolchain_available"] or not cross_artifacts_ready or not all_planned_ready):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
