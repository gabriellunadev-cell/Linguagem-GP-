"""GP source -> AST -> semantics -> IR -> binary bytecode."""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from gp import Parser, lex, GPError
from gpcompiler.ast import from_parser_tree, to_dict
from gpcompiler.semantic import SemanticAnalyzer
from gpcompiler.modules import expand_modules, read_module_source, resolve_module_path
from gpcompiler.lower import Lowerer, ir_to_dict
from gpcompiler.bytecode import encode, encode_canonical_ir
from gpcompiler.ir import validate_canonical_ir
from gpcompiler.vm import GPVirtualMachine, GPVMError



def write_bytecode_atomic(output_path: str | Path, bytecode: bytes) -> None:
    """Publish a complete GGPC artifact atomically in the destination directory."""
    destination = Path(output_path)
    if not isinstance(bytecode, bytes) or not bytecode:
        raise ValueError("bytecode precisa ser bytes não vazios")
    parent = destination.parent
    if not parent.is_dir():
        raise ValueError(f"diretório de saída não existe: {parent}")
    descriptor = -1
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=parent
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(bytecode)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, destination)
        temporary_path = None
        directory_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        raise ValueError(f"não foi possível publicar bytecode atomicamente em {destination}: {exc}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def _validate_native_encoder_timeout(timeout_seconds: int) -> None:
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 3600:
        raise ValueError("timeout_seconds deve estar entre 1 e 3.600")


def _encode_gp_ir_native_json(
    canonical_json: bytes,
    native_encoder: str | Path,
    *,
    timeout_seconds: int = 300,
) -> bytes:
    """Pass already-serialized GP-IR bytes to the native validating encoder."""
    _validate_native_encoder_timeout(timeout_seconds)
    if not isinstance(canonical_json, bytes) or not canonical_json:
        raise ValueError("GP-IR serializado precisa ser bytes UTF-8 não vazios")
    if len(canonical_json) > 64 * 1024 * 1024:
        raise ValueError("GP-IR serializado excede 64 MiB")
    executable = Path(native_encoder).resolve()
    if not executable.is_file():
        raise ValueError(f"Encoder nativo não encontrado: {executable}")
    with tempfile.TemporaryDirectory(prefix="gp-native-encoder-") as directory:
        output_path = Path(directory) / "output.gbc"
        try:
            result = subprocess.run(
                [str(executable), "--encode-ir", "-", str(output_path)],
                input=canonical_json, capture_output=True,
                timeout=timeout_seconds, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Timeout do encoder GGPC nativo") from exc
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            stdout = result.stdout.decode("utf-8", errors="replace").strip()
            detail = stderr or stdout or f"exit={result.returncode}"
            raise ValueError(f"Encoder GGPC nativo rejeitou GP-IR: {detail}")
        if not output_path.is_file():
            raise ValueError("Encoder GGPC nativo não produziu arquivo de saída")
        bytecode = output_path.read_bytes()
        if len(bytecode) < 14 or not bytecode.startswith(b"GGPC"):
            raise ValueError("Encoder GGPC nativo produziu contêiner inválido")
        return bytecode


def encode_canonical_ir_native_json(
    canonical_json: str,
    native_encoder: str | Path,
    *,
    timeout_seconds: int = 300,
) -> bytes:
    """Encode raw canonical GP-IR JSON without materializing a Python dict."""
    _validate_native_encoder_timeout(timeout_seconds)
    if not isinstance(canonical_json, str):
        raise ValueError("GP-IR canônico bruto precisa ser texto")
    try:
        raw = canonical_json.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError("GP-IR canônico bruto não é Unicode válido") from exc
    return _encode_gp_ir_native_json(raw, native_encoder, timeout_seconds=timeout_seconds)


def encode_canonical_ir_native(
    document: dict,
    native_encoder: str | Path,
    *,
    timeout_seconds: int = 300,
) -> bytes:
    """Validate a canonical GP-IR object and encode it with the native C backend."""
    _validate_native_encoder_timeout(timeout_seconds)
    validate_canonical_ir(document)
    canonical_json = json.dumps(
        document, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return _encode_gp_ir_native_json(
        canonical_json, native_encoder, timeout_seconds=timeout_seconds,
    )


def compile_source(source: str, source_path: str | Path | None = None):
    try:
        parser_tree = Parser(lex(source)).parse()
    except GPError as exc:
        if source_path is not None:
            raise GPError(f"{Path(source_path)}: {exc}") from exc
        raise
    ast = from_parser_tree(parser_tree)
    ast = expand_modules(ast, source_path=source_path)
    errors = SemanticAnalyzer().analyze(ast)
    if errors:
        prefix = f"{Path(source_path)}: " if source_path is not None else ""
        raise ValueError("\n".join(prefix + error for error in errors))
    ir = Lowerer().lower(ast)
    return ast, ir, encode(ir)



def _apply_source_edits(source: str, edits: list[tuple[int, int, str]]) -> str:
    """Apply non-overlapping source edits from right to left."""
    ordered = sorted(edits, key=lambda item: (item[0], item[1]), reverse=True)
    previous_start = len(source) + 1
    result = source
    for start, end, replacement in ordered:
        if start < 0 or end < start or end > len(source) or end > previous_start:
            raise ValueError("Sobreposição inválida ao expandir módulo GP")
        result = result[:start] + replacement + result[end:]
        previous_start = start
    return result


def _rename_module_calls(source: str, function_names: set[str], prefix: str) -> str:
    """Namespace direct calls to functions declared by one module."""
    tokens = lex(source)
    if tokens and tokens[0].kind == "programa":
        header_line = tokens[0].line
        lines = source.splitlines(keepends=True)
        header_tokens = [token for token in lex(lines[header_line - 1]) if token.kind != "EOF"]
        if len(header_tokens) not in (1, 2) or any(
            token.kind not in ("programa", "STRING") for token in header_tokens
        ):
            raise ValueError("Cabeçalho programa do módulo deve ocupar uma linha própria")
        start = sum(len(line) for line in lines[:header_line - 1])
        source = source[:start] + source[start + len(lines[header_line - 1]):]
        tokens = lex(source)
    edits: list[tuple[int, int, str]] = []
    for index, token in enumerate(tokens[:-1]):
        if token.kind != "IDENT" or token.value not in function_names:
            continue
        previous = tokens[index - 1] if index else None
        following = tokens[index + 1]
        if following.kind == "(" and (previous is None or previous.kind != "."):
            edits.append((token.pos, token.pos + len(token.value), prefix + "__" + token.value))
    return _apply_source_edits(source, edits)


def _expand_modules_for_selfhosted(
    source: str, source_path: str | Path | None,
) -> str:
    """Expand a bounded graph of function-only local modules for the GP frontend.

    Imports are expanded recursively and receive hierarchical namespaces. Cycles,
    duplicate aliases/functions, unsupported declarations and excessive module
    graphs fail closed before the GP-owned parser/analyzer sees the combined text.
    """
    try:
        root = from_parser_tree(Parser(lex(source)).parse())
    except GPError:
        raise
    imports = [item for item in root.args[0] if item.kind == "import"]
    source_tokens = lex(source)
    source_lines = source.splitlines(keepends=True)
    removal_edits: list[tuple[int, int, str]] = []
    if source_tokens and source_tokens[0].kind == "programa":
        header_line = source_tokens[0].line
        header_tokens = [
            token for token in lex(source_lines[header_line - 1])
            if token.kind != "EOF"
        ]
        if len(header_tokens) not in (1, 2) or any(
            token.kind not in ("programa", "STRING") for token in header_tokens
        ):
            raise ValueError("Cabeçalho programa deve ocupar uma linha própria")
        header_start = sum(len(line) for line in source_lines[:header_line - 1])
        removal_edits.append((
            header_start,
            header_start + len(source_lines[header_line - 1]),
            "",
        ))
    if not imports:
        return _apply_source_edits(source, removal_edits) if removal_edits else source
    if source_path is None:
        raise ValueError("Importação de módulo exige caminho do arquivo principal")

    limits = {"count": 0, "total_bytes": 0}
    max_modules = 128
    max_depth = 32
    max_module_bytes = 4 * 1024 * 1024
    max_total_module_bytes = 16 * 1024 * 1024

    def line_offsets_for(text: str) -> tuple[list[str], list[int]]:
        lines = text.splitlines(keepends=True)
        offsets: list[int] = []
        offset = 0
        for line in lines:
            offsets.append(offset)
            offset += len(line)
        return lines, offsets

    def import_line_edit(
        text: str,
        lines: list[str],
        offsets: list[int],
        statement,
    ) -> tuple[int, int, str]:
        if not statement.line or statement.line > len(lines):
            raise ValueError("Importação GP precisa ocupar uma linha própria")
        line_index = statement.line - 1
        line_text = lines[line_index]
        line_tokens = [token for token in lex(line_text) if token.kind != "EOF"]
        expected_kinds = ["usar", "STRING", "como", "IDENT"]
        actual_kinds = [token.kind for token in line_tokens]
        if actual_kinds not in (expected_kinds, expected_kinds + [";"]):
            raise ValueError("Cada declaração usar deve ocupar uma linha própria")
        module_path, alias = statement.args
        if line_tokens[1].value != module_path or line_tokens[3].value != alias:
            raise ValueError("Declaração usar inconsistente durante expansão")
        start_offset = offsets[line_index]
        return start_offset, start_offset + len(line_text), ""

    def alias_call_edits(
        text: str, aliases: dict[str, str],
    ) -> list[tuple[int, int, str]]:
        if not aliases:
            return []
        tokens = lex(text)
        edits: list[tuple[int, int, str]] = []
        for index, token in enumerate(tokens[:-3]):
            if token.kind != "IDENT" or token.value not in aliases:
                continue
            dot, member, opening = tokens[index + 1:index + 4]
            if dot.kind == "." and member.kind == "IDENT" and opening.kind == "(":
                edits.append((
                    token.pos,
                    member.pos + len(member.value),
                    aliases[token.value] + "__" + member.value,
                ))
        return edits

    def expand_module(
        module_file: Path,
        namespace: str,
        stack: tuple[Path, ...],
    ) -> str:
        resolved = resolve_module_path(module_file)
        if resolved in stack:
            cycle = " -> ".join(str(item) for item in (*stack, resolved))
            raise ValueError(f"Ciclo de importação GP detectado: {cycle}")
        if len(stack) >= max_depth:
            raise ValueError(f"Profundidade de módulos GP excede {max_depth}")
        if limits["count"] >= max_modules:
            raise ValueError(f"Quantidade de módulos GP excede {max_modules}")
        module_source, actual_size = read_module_source(resolved, max_module_bytes)
        limits["total_bytes"] += actual_size
        if limits["total_bytes"] > max_total_module_bytes:
            raise ValueError("Grafo de módulos GP excede o limite total de 16 MiB")
        limits["count"] += 1
        module_root = from_parser_tree(Parser(lex(module_source)).parse())
        module_items = module_root.args[0]
        module_imports = [item for item in module_items if item.kind == "import"]
        functions = [item for item in module_items if item.kind == "function"]
        unsupported = [
            item.kind for item in module_items
            if item.kind not in ("function", "import", "empty")
        ]
        if unsupported:
            raise ValueError(
                f"Módulo {resolved} contém declaração não suportada; "
                "módulos 0.4 devem exportar funções e importar outros módulos"
            )
        names = [item.args[0] for item in functions]
        if len(names) != len(set(names)):
            raise ValueError(f"Funções duplicadas no módulo: {resolved}")

        lines, offsets = line_offsets_for(module_source)
        module_edits: list[tuple[int, int, str]] = []
        nested_aliases: dict[str, str] = {}
        nested_sources: list[str] = []
        for statement in module_imports:
            nested_path, alias = statement.args
            if alias in nested_aliases:
                raise ValueError(f"Alias de módulo duplicado: {alias} em {resolved}")
            module_edits.append(import_line_edit(
                module_source, lines, offsets, statement,
            ))
            child_namespace = namespace + "__" + alias
            nested_aliases[alias] = child_namespace
            child_file = resolved.parent / nested_path
            nested_sources.append(expand_module(
                child_file, child_namespace, (*stack, resolved),
            ))
        module_edits.extend(alias_call_edits(module_source, nested_aliases))
        expanded_source = _apply_source_edits(module_source, module_edits)
        expanded_source = _rename_module_calls(expanded_source, set(names), namespace)
        parts = [*nested_sources, expanded_source]
        return "\n".join(part.rstrip() for part in parts if part.strip())

    base = Path(source_path).resolve().parent
    aliases: dict[str, str] = {}
    module_sources: list[str] = []
    lines, offsets = line_offsets_for(source)
    for statement in imports:
        module_path, alias = statement.args
        if alias in aliases:
            raise ValueError(f"Alias de módulo duplicado: {alias}")
        removal_edits.append(import_line_edit(source, lines, offsets, statement))
        namespace = "__gp_namespace_" + alias
        aliases[alias] = namespace
        module_sources.append(expand_module(
            (base / module_path).resolve(), namespace, (),
        ))

    removal_edits.extend(alias_call_edits(source, aliases))
    main_source = _apply_source_edits(source, removal_edits)
    expanded_modules = "\n".join(
        part.rstrip() for part in module_sources if part.strip()
    )
    return expanded_modules + "\n" + main_source



BOOTSTRAP_RUNNER_DIR = ROOT / "artifacts" / "bootstrap"
BOOTSTRAP_RUNNER_BYTECODE = BOOTSTRAP_RUNNER_DIR / "gp_frontend_runner.gbc"
BOOTSTRAP_RUNNER_MANIFEST = BOOTSTRAP_RUNNER_DIR / "manifest.json"
BOOTSTRAP_INPUTS = (
    "gp.py",
    "gp_compile.py",
    "gpcompiler/ast.py",
    "gpcompiler/semantic.py",
    "gpcompiler/modules.py",
    "gpcompiler/lower.py",
    "gpcompiler/bytecode.py",
    "gpcompiler/vm.py",
    "linguagem/parser_gp.gp",
)


_SELFHOSTED_GLOBALS = {
    "tokens_parser", "arvore_ast_gp", "cursor_parser", "ultimo_no_ast_gp",
    "raiz_ast_gp", "linha_parser", "coluna_parser", "profundidade_laco_parser",
    "profundidade_funcao_parser", "erro_parser", "mensagem_parser",
    "instrucoes_ir_gp", "secoes_funcoes_ir_gp", "secoes_estruturas_ir_gp",
    "erro_ir_gp", "diagnostico_ir_gp", "contador_rotulo_ir_gp",
    "nomes_rotulos_ir_gp", "enderecos_rotulos_ir_gp", "rotulos_fim_laco_ir_gp",
    "rotulos_continuar_laco_ir_gp", "profundidade_lacos_ir_gp",
    "nomes_estruturas_semanticas_gp", "chaves_campos_estruturas_semanticas_gp",
    "tipos_campos_estruturas_semanticas_gp",
    "nomes_semanticos_ast_gp", "tipos_semanticos_ast_gp",
    "escopos_semanticos_ast_gp", "pais_semanticos_ast_gp",
    "erro_semantico_ast_gp", "nomes_funcoes_semanticas_gp",
    "retornos_funcoes_semanticas_gp", "parametros_funcoes_semanticas_gp",
    "retorno_funcao_atual_semantica_gp", "dentro_funcao_semantica_gp",
    "profundidade_lacos_semantica_ast_gp",
}


def _gp_brace_delta(line: str) -> int:
    delta = 0
    in_string = False
    escaped = False
    index = 0
    while index < len(line):
        char = line[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        else:
            if char == "/" and index + 1 < len(line) and line[index + 1] == "/":
                break
            if char == '"':
                in_string = True
            elif char == "{":
                delta += 1
            elif char == "}":
                delta -= 1
        index += 1
    return delta


def _strip_gp_top_level_self_tests(source: str) -> str:
    """Keep executable definitions/state, excluding top-level dev probes."""
    lines = source.splitlines()
    retained: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            index += 1
            continue
        if stripped.startswith(("funcao ", "estrutura ")):
            depth = 0
            while index < len(lines):
                current = lines[index]
                retained.append(current)
                depth += _gp_brace_delta(current)
                index += 1
                if depth == 0:
                    break
            continue
        if stripped.startswith("usar "):
            index += 1
            continue
        if "=" in stripped:
            left = stripped.split("=", 1)[0].strip()
            parts = left.split()
            candidate = parts[-1] if parts else ""
            if candidate in _SELFHOSTED_GLOBALS:
                retained.append(line)
                index += 1
                continue
        # Drop one top-level probe/statement including its entire block.
        depth = _gp_brace_delta(line)
        index += 1
        while depth > 0 and index < len(lines):
            depth += _gp_brace_delta(lines[index])
            index += 1
    return "\n".join(retained) + "\n"


def _selfhosted_runner_source() -> str:
    parser_path = ROOT / "linguagem" / "parser_gp.gp"
    parser_source = parser_path.read_text(encoding="utf-8")
    expanded_frontend = _expand_modules_for_selfhosted(parser_source, parser_path)
    parser_source = _strip_gp_top_level_self_tests(expanded_frontend)
    runner_tail = f"""
    
// Entrada do compilador auto-hospedado: dados da compilacao atual.
texto gp_selfhosted_fonte = entrada_fonte()
logico gp_selfhosted_sintaxe = validar_sintaxe_gp(gp_selfhosted_fonte)
logico gp_selfhosted_semantica = falso
logico gp_selfhosted_geracao = falso
se (gp_selfhosted_sintaxe) {{
    gp_selfhosted_semantica = analisar_semantica_ast_gp(raiz_ast_gp)
}}
se (gp_selfhosted_semantica) {{
    gp_selfhosted_geracao = gerar_ir_ast_gp(raiz_ast_gp)
}}
mostrar("GP-SELFHOSTED-STATUS:", gp_selfhosted_sintaxe, gp_selfhosted_semantica, gp_selfhosted_geracao)
se (!gp_selfhosted_sintaxe) {{
    mostrar(
        "GP-SELFHOSTED-ERROR:", mensagem_parser,
        "linha:", linha_parser, "coluna:", coluna_parser,
        "cursor:", cursor_parser, "token:", atual_parser()
    )
}}
se (gp_selfhosted_sintaxe && !gp_selfhosted_semantica) {{
    mostrar("GP-SELFHOSTED-ERROR:", erro_semantico_ast_gp)
}}
se (gp_selfhosted_semantica && !gp_selfhosted_geracao) {{
    mostrar("GP-SELFHOSTED-ERROR:", diagnostico_ir_gp)
}}
se (gp_selfhosted_geracao) {{
    mostrar("GP-SELFHOSTED-IR-JSON:", serializar_ir_json_gp())
    mostrar("GP-SELFHOSTED-IR-CANONICAL:", serializar_gp_ir_canonico_gp())
}}
"""
    return parser_source + runner_tail


def _bootstrap_input_hashes() -> dict[str, str]:
    hashes = {}
    for relative in BOOTSTRAP_INPUTS:
        path = ROOT / relative
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def generate_selfhosted_runner_artifact(
    *, force: bool = False, allow_python_bootstrap: bool = True
) -> dict:
    """Load a verified runner seed, optionally allowing legacy Python generation."""
    current_inputs = _bootstrap_input_hashes()
    if not force and BOOTSTRAP_RUNNER_BYTECODE.is_file() and BOOTSTRAP_RUNNER_MANIFEST.is_file():
        try:
            existing = json.loads(BOOTSTRAP_RUNNER_MANIFEST.read_text(encoding="utf-8"))
            artifact = BOOTSTRAP_RUNNER_BYTECODE.read_bytes()
            if (
                existing.get("artifact_version") == 1
                and existing.get("inputs") == current_inputs
                and existing.get("bytecode_sha256") == hashlib.sha256(artifact).hexdigest()
            ):
                return existing
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    if not allow_python_bootstrap:
        raise ValueError(
            "Seed bootstrap GP ausente, corrompido ou desatualizado; "
            "regeneração pelo compilador Python está desabilitada neste fluxo"
        )

    runner_source = _selfhosted_runner_source()
    # Module imports embedded in parser_gp.gp resolve relative to linguagem/,
    # not to the artifact output directory.
    _, _, bytecode = compile_source(
        runner_source, source_path=ROOT / "linguagem" / "parser_gp.gp"
    )
    manifest = {
        "artifact": "gp_frontend_runner.gbc",
        "artifact_version": 1,
        "bytecode_format": "GGPC v2",
        "frontend_format": "GP-IR v1",
        "builder": "Python bootstrap compile_source",
        "runtime_input": "entrada_fonte()",
        "inputs": current_inputs,
        "bytecode_sha256": hashlib.sha256(bytecode).hexdigest(),
        "bytecode_size": len(bytecode),
    }
    BOOTSTRAP_RUNNER_DIR.mkdir(parents=True, exist_ok=True)
    temporary_bytecode = BOOTSTRAP_RUNNER_BYTECODE.with_suffix(".gbc.tmp")
    temporary_manifest = BOOTSTRAP_RUNNER_MANIFEST.with_suffix(".json.tmp")
    temporary_bytecode.write_bytes(bytecode)
    temporary_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary_bytecode.replace(BOOTSTRAP_RUNNER_BYTECODE)
    temporary_manifest.replace(BOOTSTRAP_RUNNER_MANIFEST)
    return manifest


def load_selfhosted_runner_artifact(*, require_existing: bool = False) -> bytes:
    """Load a verified runner; optionally forbid Python bootstrap regeneration."""
    manifest = generate_selfhosted_runner_artifact(
        allow_python_bootstrap=not require_existing
    )
    bytecode = BOOTSTRAP_RUNNER_BYTECODE.read_bytes()
    if hashlib.sha256(bytecode).hexdigest() != manifest["bytecode_sha256"]:
        raise ValueError("Hash do artefato bootstrap GP não confere")
    return bytecode


def _compile_source_selfhosted_document(
    source: str,
    source_path: str | Path | None = None,
    *,
    runner_backend: str = "python",
    native_vm: str | Path | None = None,
    runner_max_steps: int = 5_000_000,
    runner_timeout_seconds: int = 300,
    _raw_json_output: bool = False,
):
    """Run the GP-owned frontend and return either validated GP-IR or its raw JSON.

    Raw mode is reserved for the native encoder path: it avoids Python JSON
    parsing/materialization, leaving the complete schema validation to C.

    A hash-checked GGPC runner artifact is reused across compilations. The
    target source is supplied as explicit host data and parsed/lowered by the
    GP implementation, not by Python's Lowerer. The initial runner artifact is
    still built by the Python bootstrap; unsupported GP IR fails closed.
    """
    if runner_backend not in {"python", "native"}:
        raise ValueError(f"Backend de execução do runner inválido: {runner_backend}")
    if isinstance(runner_max_steps, bool) or not isinstance(runner_max_steps, int) or not (1 <= runner_max_steps <= 100_000_000):
        raise ValueError("runner_max_steps deve estar entre 1 e 100.000.000")
    if isinstance(runner_timeout_seconds, bool) or not isinstance(runner_timeout_seconds, int) or not (1 <= runner_timeout_seconds <= 3600):
        raise ValueError("runner_timeout_seconds deve estar entre 1 e 3.600")
    parser_path = ROOT / "linguagem" / "parser_gp.gp"
    source = _expand_modules_for_selfhosted(source, source_path)
    runner_bytecode = load_selfhosted_runner_artifact()
    if runner_backend == "python":
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            # This VM executes the compiler frontend itself, not the target
            # program. It receives the target source as explicit host data.
            GPVirtualMachine(max_steps=runner_max_steps).run_bytes(
                runner_bytecode, host_source=source
            )
        runner_output = output.getvalue()
    else:
        native_path = Path(native_vm) if native_vm else ROOT / "build" / "gpvm-native"
        native_path = native_path.resolve()
        if not native_path.is_file():
            raise ValueError(
                f"VM C não encontrada para executar o runner: {native_path}; "
                "compile com make native-vm"
            )
        with tempfile.TemporaryDirectory(
            prefix=".gp_selfhosted_native_runner_", dir=parser_path.parent
        ) as temporary:
            temporary_path = Path(temporary)
            bytecode_path = temporary_path / "frontend-runner.gbc"
            bytecode_path.write_bytes(runner_bytecode)
            try:
                result = subprocess.run(
                    [
                        str(native_path), str(bytecode_path),
                        "--max-steps", str(runner_max_steps),
                        "--source-input", "-",
                    ],
                    input=source, text=True, encoding="utf-8", errors="strict",
                    capture_output=True, timeout=runner_timeout_seconds, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise ValueError("Timeout ao executar frontend GP na VM C") from exc
            if result.returncode != 0:
                detail = result.stderr.strip() or f"exit={result.returncode}"
                raise ValueError(f"VM C falhou ao executar o frontend GP: {detail}")
            runner_output = result.stdout

    lines = runner_output.splitlines()
    status_lines = [
        line for line in lines
        if line.startswith("GP-SELFHOSTED-STATUS:")
    ]
    if len(status_lines) != 1:
        raise ValueError("O frontend auto-hospedado não retornou um status válido")
    status = status_lines[0].split(":", 1)[1].split()
    if len(status) != 3 or any(
        item.lower() not in {"true", "false", "verdadeiro", "falso"}
        for item in status
    ):
        raise ValueError("Status inválido do frontend auto-hospedado")
    ok_syntax, ok_semantic, ok_generation = [
        item.lower() in {"true", "verdadeiro"} for item in status
    ]
    if not (ok_syntax and ok_semantic and ok_generation):
        errors = [
            line.split(":", 1)[1].strip()
            for line in lines
            if line.startswith("GP-SELFHOSTED-ERROR:")
        ]
        detail = errors[-1] if errors else "sem diagnóstico adicional"
        label = (
            "sintaxe" if not ok_syntax
            else "semântica" if not ok_semantic
            else "geração de IR"
        )
        prefix = f"{Path(source_path)}: " if source_path else ""
        raise ValueError(
            f"{prefix}frontend GP auto-hospedado rejeitou a etapa de {label}: {detail}"
        )

    canonical_lines = [
        line.split(":", 1)[1].lstrip()
        for line in lines
        if line.startswith("GP-SELFHOSTED-IR-CANONICAL:")
    ]
    if len(canonical_lines) != 1:
        raise ValueError(
            f"O frontend GP não retornou exatamente um GP-IR canônico (canônicos={len(canonical_lines)}; saída={lines[-8:]})"
        )
    if _raw_json_output:
        # The C encoder parses UTF-8 and validates the entire GP-IR schema.
        # Keeping this as a string avoids json.loads + json.dumps in the native path.
        return canonical_lines[0]
    try:
        canonical = json.loads(canonical_lines[0])
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON de IR auto-hospedado inválido: {exc}") from exc
    if not isinstance(canonical, dict):
        raise ValueError("O frontend não emitiu um documento GP-IR canônico")
    try:
        validate_canonical_ir(canonical)
        return canonical
    except ValueError as exc:
        prefix = f"{Path(source_path)}: " if source_path else ""
        raise ValueError(f"{prefix}IR auto-hospedado inválido: {exc}") from exc

def compile_source_selfhosted(
    source: str,
    source_path: str | Path | None = None,
    *,
    runner_backend: str = "python",
    native_vm: str | Path | None = None,
    runner_max_steps: int = 5_000_000,
    runner_timeout_seconds: int = 300,
):
    """Compatibility API returning IRProgram for legacy callers."""
    from gpcompiler.selfhosted_ir import canonical_ir_to_program
    document = _compile_source_selfhosted_document(
        source, source_path, runner_backend=runner_backend, native_vm=native_vm,
        runner_max_steps=runner_max_steps,
        runner_timeout_seconds=runner_timeout_seconds,
    )
    return canonical_ir_to_program(document)


def compile_source_selfhosted_document(
    source: str,
    source_path: str | Path | None = None,
    *,
    runner_backend: str = "python",
    native_vm: str | Path | None = None,
    runner_max_steps: int = 5_000_000,
    runner_timeout_seconds: int = 300,
):
    """Compile with the GP frontend and return canonical JSON GP-IR v1."""
    return _compile_source_selfhosted_document(
        source, source_path, runner_backend=runner_backend, native_vm=native_vm,
        runner_max_steps=runner_max_steps,
        runner_timeout_seconds=runner_timeout_seconds,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="gpc", description="Compilador Gabriel Programming 0.4")
    parser.add_argument("source", help="Arquivo .gp")
    parser.add_argument("-o", "--output", help="Arquivo de bytecode .gbc")
    parser.add_argument("--run", action="store_true", help="Executar o bytecode após compilar")
    parser.add_argument(
        "--run-vm",
        choices=("python", "native"),
        default="python",
        help="VM usada para executar o bytecode alvo com --run (padrão: python)",
    )
    parser.add_argument(
        "--run-max-steps", type=int, default=1_000_000,
        help="limite de instruções da execução alvo (1..100 milhões)",
    )
    parser.add_argument(
        "--run-timeout-seconds", type=int, default=300,
        help="timeout da VM nativa ao executar o alvo (1..3600 segundos)",
    )
    parser.add_argument("--dump-ast", action="store_true")
    parser.add_argument("--dump-ir", action="store_true")
    parser.add_argument(
        "--self-hosted",
        action="store_true",
        help="usar o lexer, parser, análise semântica e gerador de IR escritos em GP",
    )
    parser.add_argument(
        "--runner-vm",
        choices=("python", "native"),
        default="python",
        help="VM que executa o runner do frontend GP (padrão: python)",
    )
    parser.add_argument("--native-vm", help="caminho da VM C usado com --runner-vm native ou --run-vm native")
    parser.add_argument(
        "--native-encoder",
        help="usar o encoder GGPC v2 nativo (padrão: VM C quando --runner-vm native)",
    )
    parser.add_argument(
        "--runner-max-steps", type=int, default=5_000_000,
        help="limite de instruções do runner GP (máximo 100 milhões)",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.run_max_steps <= 100_000_000:
        parser.error("--run-max-steps deve estar entre 1 e 100.000.000")
    if not 1 <= args.run_timeout_seconds <= 3600:
        parser.error("--run-timeout-seconds deve estar entre 1 e 3600")
    source_path = Path(args.source).resolve()
    try:
        source = source_path.read_text(encoding="utf-8")
        native_vm_path = args.native_vm or (
            ROOT / "build" / "gpvm-native"
            if args.runner_vm == "native" or args.run_vm == "native" else None
        )
        native_encoder = args.native_encoder or (
            native_vm_path if args.runner_vm == "native" else None
        )
        if args.self_hosted:
            if native_encoder:
                ir = _compile_source_selfhosted_document(
                    source, source_path=source_path,
                    runner_backend=args.runner_vm, native_vm=native_vm_path,
                    runner_max_steps=args.runner_max_steps,
                    _raw_json_output=True,
                )
                bytecode = encode_canonical_ir_native_json(ir, native_encoder)
                if args.dump_ir:
                    ir = json.loads(ir)
            else:
                ir = compile_source_selfhosted_document(
                    source, source_path=source_path,
                    runner_backend=args.runner_vm, native_vm=native_vm_path,
                    runner_max_steps=args.runner_max_steps,
                )
                bytecode = encode_canonical_ir(ir)
            ast = None
        else:
            ast, ir, bytecode = compile_source(source, source_path=source_path)
        output_path = Path(args.output) if args.output else source_path.with_suffix(".gbc")
        write_bytecode_atomic(output_path, bytecode)
        backend = (
            f"GP-IR direto (frontend GP; runner VM {args.runner_vm}; "
            f"encoder {'C nativo' if native_encoder else 'Python'})"
            if args.self_hosted else "bootstrap Python"
        )
        print(f"GP: bytecode binário v2 gerado pelo backend {backend} em {output_path} ({len(bytecode)} bytes)")
        if args.dump_ast and ast is not None:
            print(json.dumps(to_dict(ast), ensure_ascii=False, indent=2))
        if args.dump_ir:
            print(json.dumps(ir if isinstance(ir, dict) else ir_to_dict(ir), ensure_ascii=False, indent=2))
        if args.run:
            print(f"GP VM ({args.run_vm}): execução iniciada", flush=True)
            if args.run_vm == "python":
                GPVirtualMachine(max_steps=args.run_max_steps).run_bytes(bytecode)
            else:
                native_path = Path(native_vm_path).resolve()
                if not native_path.is_file():
                    raise ValueError(
                        f"VM C não encontrada para executar o bytecode: {native_path}; "
                        "compile com make native-vm ou informe --native-vm"
                    )
                try:
                    execution = subprocess.run(
                        [
                            str(native_path), str(output_path),
                            "--max-steps", str(args.run_max_steps),
                        ],
                        timeout=args.run_timeout_seconds,
                        check=False,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise ValueError("Timeout ao executar bytecode na VM C nativa") from exc
                if execution.returncode != 0:
                    return execution.returncode if execution.returncode > 0 else 1
        return 0
    except (OSError, ValueError, GPVMError, KeyError) as exc:
        print(f"Erro GP Compiler: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
