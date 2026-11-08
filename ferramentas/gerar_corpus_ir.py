#!/usr/bin/env python3
"""Build a reproducible GP-IR direct-encoder differential corpus."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gp_compile import compile_source, compile_source_selfhosted_document, encode_canonical_ir_native
from gpcompiler.bytecode import decode, encode, encode_canonical_ir
from gpcompiler.selfhosted_ir import canonical_ir_to_program
from gpcompiler.vm import GPVirtualMachine


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def execute_python(bytecode: bytes) -> str:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        GPVirtualMachine(max_steps=1_000_000).run_bytes(bytecode)
    return output.getvalue()


def execute_native(binary: Path, bytecode: bytes, path: Path) -> str:
    path.write_bytes(bytecode)
    result = subprocess.run(
        [str(binary), str(path)], text=True, capture_output=True,
        timeout=10, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or f"exit={result.returncode}")
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-vm", default=str(ROOT / "build" / "gpvm-native"))
    parser.add_argument("--output", default=str(ROOT / "tests" / "fixtures" / "gp_ir_direct"))
    args = parser.parse_args()
    native_vm = Path(args.native_vm).resolve()
    output = Path(args.output).resolve()
    if not native_vm.is_file():
        parser.error(f"VM C nativa não encontrada: {native_vm}")
    sources = sorted((ROOT / "tests" / "fixtures" / "bytecode_v2").glob("*.gp"))
    if not sources:
        parser.error("Corpus fonte bytecode_v2 não encontrado")
    output.mkdir(parents=True, exist_ok=True)
    cases = []

    for source_path in sources:
        source = source_path.read_text(encoding="utf-8")
        frontend_supported = True
        frontend_error = None
        try:
            document = compile_source_selfhosted_document(source, source_path=source_path)
            ir_origin = "frontend_gp"
        except ValueError as exc:
            # Keep opcode coverage reproducible even for a syntax form not yet
            # implemented by the GP parser; use the previously validated v2 fixture.
            golden_path = source_path.with_suffix(".gbc")
            if not golden_path.is_file():
                raise
            frontend_supported = False
            frontend_error = str(exc)
            ir_origin = "checked_in_golden_bytecode"
            document = decode(golden_path.read_bytes())["program"]
            document.setdefault("ir_version", 1)  # accepted GGPC v2 fixtures predating explicit GP-IR version

        native_runner_document = None
        if frontend_supported:
            native_runner_document = compile_source_selfhosted_document(
                source, source_path=source_path,
                runner_backend="native", native_vm=native_vm,
            )
            if native_runner_document != document:
                raise SystemExit(
                    f"Divergência de GP-IR entre runner Python/C: {source_path.name}"
                )

        direct = encode_canonical_ir(document)
        native_encoded = encode_canonical_ir_native(document, native_vm)
        if native_encoded != direct:
            raise SystemExit(f"Divergência binária encoder Python/C: {source_path.name}")
        legacy_program = canonical_ir_to_program(document)
        legacy = encode(legacy_program)
        if direct != legacy:
            raise SystemExit(f"Divergência binária encoder direto/legado: {source_path.name}")

        _ast, _ir, bootstrap = compile_source(source, source_path=source_path)
        frontend_bootstrap_exact = frontend_supported and direct == bootstrap
        if frontend_supported and not frontend_bootstrap_exact:
            raise SystemExit(
                f"Divergência estrutural frontend GP/bootstrap: {source_path.name}"
            )
        direct_output = execute_python(direct)
        bootstrap_output = execute_python(bootstrap)
        if bootstrap_output != direct_output:
            raise SystemExit(f"Divergência semântica GP/bootstrap Python: {source_path.name}")

        direct_path = output / f"{source_path.stem}.direct.gbc"
        bootstrap_path = output / f"{source_path.stem}.bootstrap.gbc"
        native_direct = execute_native(native_vm, direct, direct_path)
        native_bootstrap = execute_native(native_vm, bootstrap, bootstrap_path)
        if native_direct != direct_output or native_bootstrap != bootstrap_output:
            raise SystemExit(f"Divergência de execução Python/C: {source_path.name}")

        artifacts = {
            f"{source_path.stem}.gp": source.encode("utf-8"),
            f"{source_path.stem}.gp-ir.json": (
                json.dumps(document, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8"),
            f"{source_path.stem}.legacy.gbc": legacy,
            f"{source_path.stem}.direct.gbc": direct,
            f"{source_path.stem}.bootstrap.gbc": bootstrap,
        }
        golden_path = source_path.with_suffix(".gbc")
        if golden_path.is_file():
            artifacts[f"{source_path.stem}.golden.gbc"] = golden_path.read_bytes()
        for filename, data in artifacts.items():
            (output / filename).write_bytes(data)

        cases.append({
            "fixture": source_path.name,
            "ir_origin": ir_origin,
            "source_frontend_supported": frontend_supported,
            "source_frontend_error": frontend_error,
            "source_sha256": sha256(source.encode("utf-8")),
            "canonical_ir_sha256": sha256(artifacts[f"{source_path.stem}.gp-ir.json"]),
            "legacy_bytecode_sha256": sha256(legacy),
            "direct_bytecode_sha256": sha256(direct),
            "native_encoder_bytecode_sha256": sha256(native_encoded),
            "native_encoder_byte_identical": native_encoded == direct,
            "bootstrap_bytecode_sha256": sha256(bootstrap),
            "direct_legacy_byte_identical": direct == legacy,
            "frontend_bootstrap_byte_identical": frontend_bootstrap_exact if frontend_supported else None,
            "native_runner_gp_ir_identical": native_runner_document == document if frontend_supported else None,
            "frontend_bootstrap_python_output_identical": True,
            "native_direct_python_output_identical": True,
            "native_bootstrap_python_output_identical": True,
            "bytecode_bytes": len(direct),
            "stdout": direct_output,
        })

    manifest = {
        "corpus": "GP-IR direct encoder differential corpus",
        "format": "GP-IR v1",
        "container": "GGPC v2",
        "cases": cases,
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (output / "manifest.json").write_bytes(manifest_bytes)
    files = sorted(item for item in output.iterdir() if item.is_file() and item.name != "SHA256SUMS")
    sums = "".join(f"{sha256(item.read_bytes())}  {item.name}\n" for item in files)
    (output / "SHA256SUMS").write_text(sums, encoding="utf-8")
    supported = sum(c["source_frontend_supported"] for c in cases)
    print(
        f"CORPUS_OK cases={len(cases)} frontend_supported={supported} "
        f"direct_legacy_exact={sum(c['direct_legacy_byte_identical'] for c in cases)} "
        f"frontend_bootstrap_exact={sum(c['frontend_bootstrap_byte_identical'] is True for c in cases)} "
        f"native_runner_exact={sum(c['native_runner_gp_ir_identical'] is True for c in cases)} "
        f"native_encoder_exact={sum(c['native_encoder_byte_identical'] for c in cases)} "
        f"python_c_semantic={sum(c['native_direct_python_output_identical'] and c['native_bootstrap_python_output_identical'] for c in cases)}"
    )
    print(f"OUTPUT={output}")
    print(f"MANIFEST_SHA256={sha256(manifest_bytes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
