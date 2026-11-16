#!/usr/bin/env python3
"""Run the GP WASI Native VM with an isolated preopened workspace using Wasmtime."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", type=Path)
    parser.add_argument("bytecode", type=Path)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        import wasmtime
    except ImportError:
        parser.error("Instale o runtime Python Wasmtime: python -m pip install wasmtime")

    module_path = args.module.resolve()
    workspace = args.workspace.resolve()
    bytecode = args.bytecode
    if bytecode.is_absolute():
        try:
            bytecode = bytecode.resolve().relative_to(workspace)
        except ValueError:
            parser.error("O bytecode precisa estar dentro do workspace pré-aberto")
    bytecode_host = (workspace / bytecode).resolve()
    try:
        bytecode_host.relative_to(workspace)
    except ValueError:
        parser.error("Caminho do bytecode fora do workspace")
    if not module_path.is_file() or not bytecode_host.is_file():
        parser.error("Módulo WASM ou bytecode GP não encontrado")

    with tempfile.TemporaryDirectory(prefix="gp-wasi-") as directory:
        stdout_path = Path(directory) / "stdout.txt"
        stderr_path = Path(directory) / "stderr.txt"
        engine = wasmtime.Engine()
        store = wasmtime.Store(engine)
        wasi = wasmtime.WasiConfig()
        wasi.argv = [module_path.name, bytecode.as_posix()]
        wasi.preopen_dir(str(workspace), ".")
        wasi.stdout_file = str(stdout_path)
        wasi.stderr_file = str(stderr_path)
        store.set_wasi(wasi)
        linker = wasmtime.Linker(engine)
        linker.define_wasi()
        module = wasmtime.Module.from_file(engine, str(module_path))
        instance = linker.instantiate(store, module)
        try:
            instance.exports(store)["_start"](store)
        except wasmtime.ExitTrap as exc:
            if exc.code != 0:
                sys.stderr.write(stderr_path.read_text(encoding="utf-8", errors="replace"))
                return int(exc.code)
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
        sys.stdout.write(stdout)
        sys.stderr.write(stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
