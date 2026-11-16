"""GP-owned module graph traversal with host-only filesystem boundary.

The host discovers and securely reads module files. GP decides dependency order,
cycle detection and alias validation; Python only maps ordered node IDs back to
already-validated source buffers and performs syntax-preserving namespace edits.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
from pathlib import Path


def resolve_order_gp(
    origins: list[str],
    destinations: list[str],
    aliases: list[str],
    roots: list[str],
    native_vm_path: str | Path | None = None,
    prefer_native: bool = True,
) -> list[str]:
    """Execute the production GP graph resolver and return its topological order."""
    if not (len(origins) == len(destinations) == len(aliases)):
        raise ValueError("Grafo de módulos GP inconsistente")
    resolver_path = Path(__file__).resolve().parents[1] / "linguagem" / "resolver_modulos_gp.gp"
    resolver_source = resolver_path.read_text(encoding="utf-8")
    literals = lambda values: "[" + ", ".join(json.dumps(v, ensure_ascii=False) for v in values) + "]"
    probe = (
        "\nlista texto __gp_graph_origins = " + literals(origins) + "\n"
        "lista texto __gp_graph_destinations = " + literals(destinations) + "\n"
        "lista texto __gp_graph_aliases = " + literals(aliases) + "\n"
        "lista texto __gp_graph_roots = " + literals(roots) + "\n"
        "lista texto __gp_graph_order = resolver_modulos_gp("
        "__gp_graph_origins, __gp_graph_destinations, __gp_graph_aliases, __gp_graph_roots)\n"
        "numero __gp_graph_i = 0\n"
        "enquanto (__gp_graph_i < tamanho(__gp_graph_order)) {\n"
        "    mostrar(\"GP_MODULE_ORDER:\", __gp_graph_order[__gp_graph_i])\n"
        "    __gp_graph_i = __gp_graph_i + 1\n"
        "}\n"
    )
    # Prefer the already-built, hash-checked GP frontend runner. This keeps
    # module graph decisions inside GP and avoids recompiling the resolver with
    # Python on every native project build. Python remains only the filesystem
    # boundary (reading source files and applying safe source edits).
    project_root = resolver_path.parents[1]
    configured_vm = os.environ.get("GP_NATIVE_VM")
    explicit_vm = prefer_native and (native_vm_path is not None or bool(configured_vm))
    selected_vm = native_vm_path if native_vm_path is not None else configured_vm
    native_vm = (
        Path(selected_vm).resolve() if selected_vm else (
            project_root / "build" / "gpvm-native"
        )
    ) if prefer_native else None
    if prefer_native and explicit_vm and not (
        native_vm is not None and native_vm.is_file() and native_vm.stat().st_mode & 0o111
    ):
        raise ValueError(f"VM C configurada não é executável: {native_vm}")

    if native_vm is not None and native_vm.is_file() and native_vm.stat().st_mode & 0o111:
        from gp_compile import load_selfhosted_runner_artifact

        runner_bytecode = load_selfhosted_runner_artifact()
        max_steps_text = os.environ.get("GP_MODULE_RESOLVER_MAX_STEPS", "5000000")
        if not max_steps_text.isdigit() or not (1 <= int(max_steps_text) <= 100_000_000):
            raise ValueError("GP_MODULE_RESOLVER_MAX_STEPS precisa estar entre 1 e 100000000")
        with tempfile.TemporaryDirectory(prefix="gp-module-order-") as directory:
            temporary = Path(directory)
            runner_path = temporary / "gp_frontend_runner.gbc"
            ir_path = temporary / "module-order.gp-ir.json"
            bytecode_path = temporary / "module-order.gbc"
            runner_path.write_bytes(runner_bytecode)
            try:
                frontend = subprocess.run(
                    [
                        str(native_vm), str(runner_path),
                        "--max-steps", str(int(max_steps_text)),
                        "--source-input", "-",
                    ],
                    input=resolver_source + probe,
                    text=True, encoding="utf-8", errors="strict",
                    capture_output=True, timeout=60, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise ValueError("Timeout ao executar frontend GP para resolver módulos") from exc
            if frontend.returncode != 0:
                detail = frontend.stderr.strip() or f"exit={frontend.returncode}"
                raise ValueError("VM C falhou no frontend GP do resolvedor: " + detail)

            status_lines = [
                line for line in frontend.stdout.splitlines()
                if line.startswith("GP-SELFHOSTED-STATUS:")
            ]
            if len(status_lines) != 1:
                raise ValueError("Runner GP não retornou status único ao resolver módulos")
            status = status_lines[0].split(":", 1)[1].split()
            if len(status) != 3 or any(
                item.lower() not in {"true", "false", "verdadeiro", "falso"}
                for item in status
            ) or not all(item.lower() in {"true", "verdadeiro"} for item in status):
                errors = [
                    line.split(":", 1)[1].strip()
                    for line in frontend.stdout.splitlines()
                    if line.startswith("GP-SELFHOSTED-ERROR:")
                ]
                detail = errors[-1] if errors else status_lines[0]
                raise ValueError("Frontend GP rejeitou o resolvedor de módulos: " + detail)

            canonical_lines = [
                line.split(":", 1)[1].lstrip()
                for line in frontend.stdout.splitlines()
                if line.startswith("GP-SELFHOSTED-IR-CANONICAL:")
            ]
            if len(canonical_lines) != 1 or not canonical_lines[0]:
                raise ValueError("Frontend GP não emitiu um único GP-IR canônico para módulos")
            ir_path.write_text(canonical_lines[0], encoding="utf-8")

            try:
                encoded = subprocess.run(
                    [str(native_vm), "--encode-ir", str(ir_path), str(bytecode_path)],
                    text=True, encoding="utf-8", errors="strict",
                    capture_output=True, timeout=60, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise ValueError("Timeout no encoder C do resolvedor de módulos GP") from exc
            if encoded.returncode != 0:
                detail = encoded.stderr.strip() or f"exit={encoded.returncode}"
                raise ValueError("Encoder C rejeitou o GP-IR do resolvedor de módulos: " + detail)

            try:
                execution = subprocess.run(
                    [str(native_vm), str(bytecode_path)],
                    text=True, encoding="utf-8", errors="strict",
                    capture_output=True, timeout=60, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise ValueError("Timeout ao executar resolvedor de módulos GP na VM C") from exc
            if execution.returncode != 0:
                detail = execution.stderr.strip() or f"exit={execution.returncode}"
                raise ValueError("VM C falhou ao executar resolvedor de módulos GP: " + detail)
            rendered_output = execution.stdout
    else:
        # Portable reference fallback for environments without the C runtime.
        # It is deliberately not used by the native project compiler.
        from gp_compile import compile_source
        from gpcompiler.vm import GPVirtualMachine

        _, _, bytecode = compile_source(resolver_source + probe, source_path=resolver_path)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine(max_steps=5_000_000).run_bytes(bytecode)
        rendered_output = output.getvalue()
    order: list[str] = []
    for line in rendered_output.splitlines():
        if line.startswith("GP_MODULE_ORDER:"):
            value = line.split(":", 1)[1].strip()
            if not value.isdigit():
                raise ValueError("O resolvedor GP retornou um identificador inválido")
            order.append(value)
    expected_nodes = set(roots) | set(origins) | set(destinations)
    if len(order) != len(expected_nodes) or set(order) != expected_nodes:
        raise ValueError(
            "Ciclo de importação GP detectado ou grafo inválido pelo resolvedor GP"
        )
    return order


def expand_source_modules_gp(
    source: str,
    source_path: str | Path | None,
    native_vm: str | Path | None = None,
    prefer_native: bool = True,
    *,
    ast_only: bool = False,
) -> str:
    """Validate a safe module graph with GP; optionally leave source untouched.

    In AST mode this function is a graph-validation boundary only. It must not
    delete import declarations or rewrite aliases in source text; the compiler
    links module declarations after parsing, using typed AST nodes.
    """
    from gp import Parser, lex
    from gpcompiler.ast import from_parser_tree
    from gpcompiler.modules import read_module_source, resolve_module_path
    from gp_compile import _apply_source_edits, _rename_module_calls

    root_tree = from_parser_tree(Parser(lex(source)).parse())
    root_items = root_tree.args[0]
    root_imports = [item for item in root_items if item.kind == "import"]
    lines = source.splitlines(keepends=True)
    source_tokens = lex(source)
    root_edits: list[tuple[int, int, str]] = []

    def line_offsets(text: str) -> tuple[list[str], list[int]]:
        local_lines = text.splitlines(keepends=True)
        offsets: list[int] = []
        cursor = 0
        for line in local_lines:
            offsets.append(cursor)
            cursor += len(line)
        return local_lines, offsets

    def import_edit(text: str, statement) -> tuple[int, int, str]:
        local_lines, offsets = line_offsets(text)
        if not statement.line or statement.line > len(local_lines):
            raise ValueError("Importação GP precisa ocupar uma linha própria")
        index = statement.line - 1
        tokens = [token for token in lex(local_lines[index]) if token.kind != "EOF"]
        kinds = [token.kind for token in tokens]
        expected = ["usar", "STRING", "como", "IDENT"]
        if kinds not in (expected, expected + [";"]):
            raise ValueError("Cada declaração usar deve ocupar uma linha própria")
        module_path, alias = statement.args
        if tokens[1].value != module_path or tokens[3].value != alias:
            raise ValueError("Declaração usar inconsistente durante expansão")
        return offsets[index], offsets[index] + len(local_lines[index]), ""

    def alias_edits(text: str, aliases_by_name: dict[str, str]) -> list[tuple[int, int, str]]:
        if not aliases_by_name:
            return []
        tokens = lex(text)
        edits: list[tuple[int, int, str]] = []
        for index, token in enumerate(tokens[:-3]):
            if token.kind != "IDENT" or token.value not in aliases_by_name:
                continue
            dot, member, opening = tokens[index + 1:index + 4]
            if dot.kind == "." and member.kind == "IDENT" and opening.kind == "(":
                edits.append((
                    token.pos,
                    member.pos + len(member.value),
                    aliases_by_name[token.value] + "__" + member.value,
                ))
        return edits

    if source_tokens and source_tokens[0].kind == "programa":
        header_line = source_tokens[0].line
        header_tokens = [
            token for token in lex(lines[header_line - 1]) if token.kind != "EOF"
        ]
        if len(header_tokens) not in (1, 2) or any(
            token.kind not in ("programa", "STRING") for token in header_tokens
        ):
            raise ValueError("Cabeçalho programa deve ocupar uma linha própria")
        start = sum(len(line) for line in lines[:header_line - 1])
        root_edits.append((start, start + len(lines[header_line - 1]), ""))

    if not root_imports:
        if ast_only:
            return source
        return _apply_source_edits(source, root_edits) if root_edits else source
    if source_path is None:
        raise ValueError("Importação de módulo exige caminho do arquivo principal")

    base = Path(source_path).resolve().parent
    records: dict[str, dict] = {}
    origins: list[str] = []
    destinations: list[str] = []
    edge_aliases: list[str] = []
    root_aliases: dict[str, str] = {}
    next_id = 1
    total_bytes = 0
    max_modules, max_depth = 128, 32
    max_module_bytes, max_total_bytes = 4 * 1024 * 1024, 16 * 1024 * 1024

    # Root node 0 represents the entry source. Each import instance receives
    # a distinct node so that importing one file under two namespaces remains
    # deterministic and does not collapse exported function names.
    queue: list[tuple[str, Path, str, int, dict[Path, str]]] = []
    root_path = resolve_module_path(source_path)
    root_ancestors = {root_path: "0"}
    for statement in root_imports:
        module_path, alias = statement.args
        if alias in root_aliases:
            raise ValueError(f"Alias de módulo duplicado: {alias}")
        child_prefix = "__gp_namespace_" + alias
        child_path = resolve_module_path(base / module_path)
        if next_id > max_modules:
            raise ValueError(f"Quantidade de módulos GP excede {max_modules}")
        child_id = str(next_id)
        next_id += 1
        root_aliases[alias] = child_prefix
        origins.append("0")
        destinations.append(child_id)
        edge_aliases.append(alias)
        queue.append((child_id, child_path, child_prefix, 1, root_ancestors))
        root_edits.append(import_edit(source, statement))
    root_edits.extend(alias_edits(source, root_aliases))

    while queue:
        node_id, resolved, prefix, depth, ancestors = queue.pop(0)
        if depth > max_depth:
            raise ValueError(f"Profundidade de módulos GP excede {max_depth}")
        module_source, actual_size = read_module_source(resolved, max_module_bytes)
        total_bytes += actual_size
        if total_bytes > max_total_bytes:
            raise ValueError("Grafo de módulos GP excede o limite total de 16 MiB")
        module_tree = from_parser_tree(Parser(lex(module_source)).parse())
        items = module_tree.args[0]
        imports = [item for item in items if item.kind == "import"]
        functions = [item for item in items if item.kind == "function"]
        unsupported = [
            item.kind for item in items
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
        if node_id in records:
            raise ValueError("Identificador duplicado no grafo de módulos GP")
        records[node_id] = {
            "path": resolved,
            "prefix": prefix,
            "source": module_source,
            "imports": imports,
            "functions": set(names),
            "nested_aliases": {},
        }
        module_ancestors = dict(ancestors)
        module_ancestors[resolved] = node_id
        nested_aliases: dict[str, str] = records[node_id]["nested_aliases"]
        for statement in imports:
            nested_path, alias = statement.args
            if alias in nested_aliases:
                raise ValueError(f"Alias de módulo duplicado: {alias} em {resolved}")
            child_path = resolve_module_path(resolved.parent / nested_path)
            if child_path in module_ancestors:
                child_id = module_ancestors[child_path]
                child_prefix = records[child_id]["prefix"] if child_id in records else (
                    "__gp_namespace_" + alias
                )
                origins.append(node_id)
                destinations.append(child_id)
                edge_aliases.append(alias)
                nested_aliases[alias] = child_prefix
                continue
            if next_id > max_modules:
                raise ValueError(f"Quantidade de módulos GP excede {max_modules}")
            child_id = str(next_id)
            next_id += 1
            child_prefix = prefix + "__" + alias
            nested_aliases[alias] = child_prefix
            origins.append(node_id)
            destinations.append(child_id)
            edge_aliases.append(alias)
            queue.append((child_id, child_path, child_prefix, depth + 1, module_ancestors))

    order = resolve_order_gp(origins, destinations, edge_aliases, ["0"], native_vm_path=native_vm, prefer_native=prefer_native)
    if not order or order[-1] != "0":
        raise ValueError("Ciclo de importação GP detectado pelo resolvedor da linguagem")

    # The reference compiler keeps the original import nodes and delegates
    # namespace linking to the AST module pass. The GP resolver still validates
    # the complete dependency graph, but no source text is expanded here.
    if ast_only:
        return source

    expanded_sources: list[str] = []
    for node_id in order:
        if node_id == "0":
            continue
        record = records[node_id]
        module_source = record["source"]
        module_edits = [
            import_edit(module_source, statement)
            for statement in record["imports"]
        ]
        module_edits.extend(alias_edits(module_source, record["nested_aliases"]))
        expanded_source = _apply_source_edits(module_source, module_edits)
        expanded_source = _rename_module_calls(
            expanded_source, record["functions"], record["prefix"]
        )
        if expanded_source.strip():
            expanded_sources.append(expanded_source.rstrip())

    main_source = _apply_source_edits(source, root_edits)
    return "\n".join(expanded_sources + [main_source])
