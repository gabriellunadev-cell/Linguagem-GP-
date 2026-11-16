"""AST-level module discovery and linking for GP Core.

The linker reads bounded local modules, records a typed GP-MODULE-GRAPH v1,
resolves aliases to module namespaces, and rewrites calls on AST nodes only.
GP-IR v1 remains a flat function table for backward compatibility.
"""
from __future__ import annotations

import errno
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .ast import ASTNode, from_parser_tree
from .module_graph import GPModuleGraph, GPModuleImport, GPModuleUnit
from gp import Parser, lex


MAX_MODULE_BYTES = 4 * 1024 * 1024
MAX_MODULE_COUNT = 128
MAX_MODULE_DEPTH = 32
MAX_MODULE_GRAPH_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class ModuleLinkPlan:
    """Validated module graph plus parsed AST units consumed by the AST linker."""

    graph: GPModuleGraph
    module_asts: dict[str, ASTNode]


def resolve_module_path(path: str | Path) -> Path:
    """Resolve module paths and convert symlink/path failures into GP diagnostics."""
    try:
        return Path(path).resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"Caminho de módulo GP inválido: {path}: {exc}") from exc


def read_module_source(
    path: str | Path,
    max_bytes: int = MAX_MODULE_BYTES,
) -> tuple[str, int]:
    """Read at most max_bytes + 1 bytes; enforce limits on the opened stream."""
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValueError("Limite de leitura de módulo GP inválido")
    module_path = Path(path)
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(module_path, flags)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError(f"Módulo GP deve ser arquivo regular: {module_path}")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            raw = stream.read(max_bytes + 1)
    except FileNotFoundError as exc:
        raise ValueError(f"Módulo GP não encontrado: {module_path}") from exc
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ValueError(
                f"Caminho de módulo GP inválido (ciclo de link simbólico): {module_path}"
            ) from exc
        raise ValueError(f"Não foi possível acessar módulo GP {module_path}: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if len(raw) > max_bytes:
        limit_mib = max_bytes / (1024 * 1024)
        raise ValueError(
            f"Módulo GP excede o limite de {limit_mib:g} MiB: {module_path}"
        )
    try:
        return raw.decode("utf-8"), len(raw)
    except UnicodeDecodeError as exc:
        raise ValueError(f"Módulo GP não contém UTF-8 válido: {module_path}") from exc


def _rewrite(value, aliases=None, local_functions=None, prefix=None):
    """Resolve module-qualified calls and local function calls recursively in the AST."""
    aliases = aliases or {}
    local_functions = local_functions or set()
    if isinstance(value, ASTNode):
        args = tuple(_rewrite(x, aliases, local_functions, prefix) for x in value.args)
        node = ASTNode(value.kind, args, value.line, value.column)
        if node.kind == "call":
            callee, call_args = node.args
            if callee.kind == "field" and callee.args[0].kind == "var":
                alias, member = callee.args[0].args[0], callee.args[1]
                if alias in aliases:
                    node = ASTNode(
                        "call",
                        (ASTNode("var", (aliases[alias] + "__" + member,)), call_args),
                        node.line,
                        node.column,
                    )
            elif callee.kind == "var" and prefix and callee.args[0] in local_functions:
                node = ASTNode(
                    "call",
                    (ASTNode("var", (prefix + "__" + callee.args[0],)), call_args),
                    node.line,
                    node.column,
                )
        return node
    if isinstance(value, dict):
        return {key: _rewrite(item, aliases, local_functions, prefix) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite(x, aliases, local_functions, prefix) for x in value]
    if isinstance(value, tuple):
        return tuple(_rewrite(x, aliases, local_functions, prefix) for x in value)
    return value


def build_module_link_plan(
    root: ASTNode,
    source_path: str | Path | None = None,
) -> ModuleLinkPlan:
    """Discover source units and return a strict, deterministic module-link graph."""
    if not isinstance(root, ASTNode) or root.kind != "block":
        raise ValueError("Raiz da AST GP inválida")

    root_items = root.args[0]
    root_imports = [item for item in root_items if item.kind == "import"]
    if root_imports and source_path is None:
        raise ValueError("Importação de módulo exige caminho do arquivo principal")

    units: list[GPModuleUnit] = [
        GPModuleUnit("0", "", None, None, ())
    ]
    imports: list[GPModuleImport] = []
    order: list[str] = []
    module_asts: dict[str, ASTNode] = {"0": root}
    namespaces = {""}
    next_id = 1
    total_bytes = 0
    root_path = resolve_module_path(source_path) if source_path is not None else None

    def visit(
        parent_id: str,
        module_file: Path,
        module_path: str,
        alias: str,
        namespace: str,
        depth: int,
        stack: tuple[Path, ...],
    ) -> str:
        nonlocal next_id, total_bytes
        if depth > MAX_MODULE_DEPTH:
            raise ValueError(f"Profundidade de módulos GP excede {MAX_MODULE_DEPTH}")
        resolved = resolve_module_path(module_file)
        if resolved in stack or (root_path is not None and resolved == root_path):
            cycle = " -> ".join(str(item) for item in (*stack, resolved))
            raise ValueError(f"Ciclo de importação GP detectado: {cycle}")
        if next_id > MAX_MODULE_COUNT:
            raise ValueError(f"Quantidade de módulos GP excede {MAX_MODULE_COUNT}")
        module_source, actual_size = read_module_source(resolved, MAX_MODULE_BYTES)
        total_bytes += actual_size
        if total_bytes > MAX_MODULE_GRAPH_BYTES:
            raise ValueError("Grafo de módulos GP excede o limite total de 16 MiB")
        module_tree = from_parser_tree(Parser(lex(module_source)).parse())
        if not isinstance(module_tree, ASTNode) or module_tree.kind != "block":
            raise ValueError(f"Raiz da AST inválida no módulo {resolved}")

        items = module_tree.args[0]
        functions = [item for item in items if item.kind == "function"]
        nested_imports = [item for item in items if item.kind == "import"]
        unsupported = [
            item.kind for item in items
            if item.kind not in ("function", "import", "empty")
        ]
        if unsupported:
            raise ValueError(
                f"Módulo {resolved} contém declaração não suportada; "
                "módulos GP atuais exportam funções e importam outros módulos"
            )
        exports = tuple(item.args[0] for item in functions)
        if len(exports) != len(set(exports)):
            raise ValueError(f"Funções duplicadas no módulo: {resolved}")
        if any(not isinstance(name, str) or not name for name in exports):
            raise ValueError(f"Símbolo exportado inválido no módulo: {resolved}")

        module_id = str(next_id)
        next_id += 1
        if namespace in namespaces:
            raise ValueError(f"Namespace GP duplicado: {namespace}")
        namespaces.add(namespace)
        units.append(GPModuleUnit(
            module_id, namespace, parent_id, alias, exports,
        ))
        imports.append(GPModuleImport(parent_id, module_id, alias, module_path))
        module_asts[module_id] = module_tree

        nested_aliases: set[str] = set()
        for statement in nested_imports:
            child_path, child_alias = statement.args
            if child_alias in nested_aliases:
                raise ValueError(f"Alias de módulo duplicado: {child_alias} em {resolved}")
            nested_aliases.add(child_alias)
            child_namespace = namespace + "__" + child_alias
            visit(
                module_id,
                resolved.parent / child_path,
                child_path,
                child_alias,
                child_namespace,
                depth + 1,
                (*stack, resolved),
            )
        order.append(module_id)
        return module_id

    root_aliases: set[str] = set()
    base = root_path.parent if root_path is not None else Path.cwd()
    for statement in root_imports:
        module_path, alias = statement.args
        if alias in root_aliases:
            raise ValueError(f"Alias de módulo duplicado: {alias}")
        root_aliases.add(alias)
        visit(
            "0", base / module_path, module_path, alias,
            "__gp_namespace_" + alias, 1, (),
        )
    order.append("0")

    graph = GPModuleGraph(
        entry_id="0",
        units=tuple(units),
        imports=tuple(imports),
        dependency_order=tuple(order),
    )
    graph.to_document()  # Validate graph invariants at the linker boundary.
    return ModuleLinkPlan(graph=graph, module_asts=module_asts)


def expand_modules(root: ASTNode, source_path: str | Path | None = None) -> ASTNode:
    """Link a bounded module graph and lower namespaces by rewriting typed AST calls."""
    if root.kind != "block":
        raise ValueError("Raiz da AST GP inválida")
    if not any(item.kind == "import" for item in root.args[0]):
        return root

    plan = build_module_link_plan(root, source_path)
    graph = plan.graph
    units = {unit.module_id: unit for unit in graph.units}
    aliases_by_source: dict[str, dict[str, str]] = {}
    for edge in graph.imports:
        aliases_by_source.setdefault(edge.source_id, {})[
            edge.alias
        ] = units[edge.target_id].namespace

    linked_functions: list[ASTNode] = []
    linked_symbols: set[str] = set()
    for module_id in graph.dependency_order:
        if module_id == graph.entry_id:
            continue
        unit = units[module_id]
        module_tree = plan.module_asts[module_id]
        items = module_tree.args[0]
        local_functions = {
            item.args[0] for item in items if item.kind == "function"
        }
        for function in items:
            if function.kind != "function":
                continue
            name, params, return_type, body = function.args
            symbol = unit.namespace + "__" + name
            if symbol in linked_symbols:
                raise ValueError(f"Símbolo de módulo duplicado após link: {symbol}")
            linked_symbols.add(symbol)
            rewritten_body = _rewrite(
                body,
                aliases=aliases_by_source.get(module_id, {}),
                local_functions=local_functions,
                prefix=unit.namespace,
            )
            linked_functions.append(ASTNode(
                "function",
                (symbol, params, return_type, rewritten_body),
                function.line,
                function.column,
            ))

    root_statements = [
        item for item in root.args[0] if item.kind != "import"
    ]
    root_symbols = {
        item.args[0] for item in root_statements if item.kind == "function"
    }
    collision = root_symbols & linked_symbols
    if collision:
        raise ValueError(
            "Função da aplicação colide com símbolo de módulo: "
            + ", ".join(sorted(collision))
        )
    rewritten_root = [
        _rewrite(
            item,
            aliases=aliases_by_source.get(graph.entry_id, {}),
        )
        for item in root_statements
    ]
    return ASTNode(
        "block",
        (linked_functions + rewritten_root,),
        root.line,
        root.column,
    )
