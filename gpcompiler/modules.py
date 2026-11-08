"""Compile-time module expansion for GP Core 0.4.

This first module system imports function-only modules into a namespace.
The module file is resolved relative to the importing source file.
"""
from __future__ import annotations
import errno
import os
import stat
from pathlib import Path
from .ast import ASTNode, from_parser_tree
from gp import GPError, Parser, lex



MAX_MODULE_BYTES = 4 * 1024 * 1024


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
                    node = ASTNode("call", (ASTNode("var", (aliases[alias] + "__" + member,)), call_args))
            elif callee.kind == "var" and prefix and callee.args[0] in local_functions:
                node = ASTNode("call", (ASTNode("var", (prefix + "__" + callee.args[0],)), call_args))
        return node
    if isinstance(value, dict):
        return {key: _rewrite(item, aliases, local_functions, prefix) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite(x, aliases, local_functions, prefix) for x in value]
    if isinstance(value, tuple):
        return tuple(_rewrite(x, aliases, local_functions, prefix) for x in value)
    return value


def expand_modules(root: ASTNode, source_path: str | Path | None = None) -> ASTNode:
    """Expand a bounded local module graph and rewrite hierarchical namespaces."""
    if root.kind != "block":
        raise ValueError("Raiz da AST GP inválida")
    base = Path(source_path).resolve().parent if source_path else Path.cwd()
    aliases: dict[str, str] = {}
    imported: list[ASTNode] = []
    statements: list[ASTNode] = []
    limits = {"count": 0, "total_bytes": 0}
    max_modules = 128
    max_depth = 32
    max_module_bytes = 4 * 1024 * 1024
    max_total_module_bytes = 16 * 1024 * 1024

    def expand_module(
        module_file: Path,
        prefix: str,
        stack: tuple[Path, ...],
    ) -> list[ASTNode]:
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
        module_tree = from_parser_tree(Parser(lex(module_source)).parse())
        module_items = module_tree.args[0]
        module_functions = [item for item in module_items if item.kind == "function"]
        module_imports = [item for item in module_items if item.kind == "import"]
        unsupported = [
            item.kind for item in module_items
            if item.kind not in ("function", "import", "empty")
        ]
        if unsupported:
            raise ValueError(
                f"Módulo {resolved} contém declaração não suportada; "
                "módulos 0.4 devem exportar funções e importar outros módulos"
            )
        names = [item.args[0] for item in module_functions]
        if len(names) != len(set(names)):
            raise ValueError(f"Funções duplicadas no módulo: {resolved}")

        nested_aliases: dict[str, str] = {}
        expanded: list[ASTNode] = []
        for statement in module_imports:
            module_path, alias = statement.args
            if alias in nested_aliases:
                raise ValueError(f"Alias de módulo duplicado: {alias} em {resolved}")
            child_prefix = prefix + "__" + alias
            nested_aliases[alias] = child_prefix
            expanded.extend(expand_module(
                resolved.parent / module_path,
                child_prefix,
                (*stack, resolved),
            ))

        for function in module_functions:
            name, params, return_type, body = function.args
            rewritten_body = _rewrite(
                body,
                aliases=nested_aliases,
                local_functions=set(names),
                prefix=prefix,
            )
            expanded.append(ASTNode(
                "function",
                (prefix + "__" + name, params, return_type, rewritten_body),
                function.line,
                function.column,
            ))
        return expanded

    for statement in root.args[0]:
        if statement.kind != "import":
            statements.append(statement)
            continue
        module_path, alias = statement.args
        if alias in aliases:
            raise ValueError(f"Alias de módulo duplicado: {alias}")
        prefix = "__gp_namespace_" + alias
        aliases[alias] = prefix
        imported.extend(expand_module(base / module_path, prefix, ()))

    rewritten = [_rewrite(item, aliases=aliases) for item in statements]
    return ASTNode("block", (imported + rewritten,), root.line, root.column)
