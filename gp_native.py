"""Compile a GP source file to a native Android/ARM64 executable using Clang."""
from __future__ import annotations
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from gp import Parser, lex
from gpcompiler.ast import from_parser_tree
from gpcompiler.modules import expand_modules
from gpcompiler.semantic import SemanticAnalyzer
from gpcompiler.native_c import CBackend, NativeBackendError


def main(argv=None):
    parser = argparse.ArgumentParser(prog="gpn", description="Compilador nativo experimental GP -> C -> Clang")
    parser.add_argument("source", help="Arquivo .gp")
    parser.add_argument("-o", "--output", help="Executável de saída")
    parser.add_argument("--emit-c", help="Salvar código C neste caminho")
    parser.add_argument("--clang", default="clang", help="Compilador C (padrão: clang)")
    parser.add_argument("--run", action="store_true", help="Executar o binário após compilar")
    args = parser.parse_args(argv)
    source_path = Path(args.source).resolve()
    output_path = Path(args.output) if args.output else source_path.with_suffix("")
    c_path = Path(args.emit_c) if args.emit_c else output_path.with_suffix(".native.c")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        c_path.parent.mkdir(parents=True, exist_ok=True)
        source = source_path.read_text(encoding="utf-8")
        root = from_parser_tree(Parser(lex(source)).parse())
        root = expand_modules(root, source_path=source_path)
        errors = SemanticAnalyzer().analyze(root)
        if errors: raise ValueError("\n".join(errors))
        c_source = CBackend().lower(root)
        c_path.write_text(c_source, encoding="utf-8")
        compiler = shutil.which(args.clang)
        if not compiler: raise NativeBackendError(f"Clang não encontrado: {args.clang}")
        result = subprocess.run(
            [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", str(c_path), "-lm", "-o", str(output_path)],
            text=True, capture_output=True, check=False,
        )
        if result.returncode:
            raise NativeBackendError(result.stderr.strip() or "Clang falhou sem diagnóstico")
        print(f"GP Native: executável gerado em {output_path}")
        print(f"C intermediário: {c_path}")
        if args.run:
            run = subprocess.run([str(output_path.resolve())], text=True, check=False)
            return run.returncode
        return 0
    except (OSError, ValueError, NativeBackendError) as exc:
        print(f"Erro GP Native: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
