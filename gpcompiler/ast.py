"""Formal GP AST nodes and conversion from the bootstrap parser tree."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any


NODE_KINDS = {
    "block", "empty", "declare", "assign", "print", "if", "while",
    "for", "function", "struct", "return", "break", "continue",
    "expression", "lit", "var", "array", "unary", "binary", "call",
    "index", "field", "construct", "import",
}


@dataclass(frozen=True)
class ASTNode:
    kind: str
    args: tuple[Any, ...]
    line: int | None = None
    column: int | None = None


def from_parser_tree(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: from_parser_tree(item) for key, item in value.items()}
    if isinstance(value, tuple):
        if value and isinstance(value[0], str) and value[0] in NODE_KINDS:
            return ASTNode(value[0], tuple(from_parser_tree(x) for x in value[1:]), getattr(value, 'line', None), getattr(value, 'column', None))
        return tuple(from_parser_tree(x) for x in value)
    if isinstance(value, list):
        return [from_parser_tree(x) for x in value]
    return value


def to_dict(value: Any) -> Any:
    if isinstance(value, ASTNode):
        return {"node": value.kind, "args": [to_dict(x) for x in value.args], "line": value.line, "column": value.column}
    if isinstance(value, dict):
        return {str(key): to_dict(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_dict(x) for x in value]
    if isinstance(value, tuple):
        return [to_dict(x) for x in value]
    return value


def walk(node: ASTNode):
    yield node
    for arg in node.args:
        if isinstance(arg, ASTNode):
            yield from walk(arg)
        elif isinstance(arg, dict):
            for item in arg.values():
                if isinstance(item, ASTNode):
                    yield from walk(item)
        elif isinstance(arg, (list, tuple)):
            for item in arg:
                if isinstance(item, ASTNode):
                    yield from walk(item)
