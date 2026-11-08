#!/usr/bin/env python3
"""Execute a previously compiled GP bytecode file."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from gpcompiler.vm import GPVirtualMachine, GPVMError, GP_MAX_HOST_SOURCE_BYTES


def main(argv=None):
    parser = argparse.ArgumentParser(prog="gp-vm", description="Máquina virtual GP")
    parser.add_argument("bytecode", help="Arquivo .gbc")
    parser.add_argument("--max-steps", type=int, default=1_000_000)
    parser.add_argument(
        "--source-input",
        help="Arquivo de texto fornecido ao programa pela função entrada_fonte()",
    )
    args = parser.parse_args(argv)
    try:
        data = Path(args.bytecode).read_bytes()
        host_source = None
        if args.source_input:
            host_path = Path(args.source_input)
            if host_path.stat().st_size > GP_MAX_HOST_SOURCE_BYTES:
                raise GPVMError("entrada_fonte excede o limite de 16 MiB")
            host_source = host_path.read_text(encoding="utf-8")
        GPVirtualMachine(max_steps=args.max_steps).run_bytes(
            data, host_source=host_source
        )
        return 0
    except (OSError, ValueError, GPVMError) as exc:
        print(f"Erro GP VM: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
