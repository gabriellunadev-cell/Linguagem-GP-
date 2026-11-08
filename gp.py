#!/usr/bin/env python3
"""GP (Gabriel Programming) bootstrap interpreter, version 0.2.0.

This Python implementation is a temporary bootstrap for validating GP semantics.
It is not the final native runtime.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


GP_MAX_TEXT_JOIN_BYTES = 64 * 1024 * 1024


TOKEN_RE = re.compile(
    r"""(?P<SPACE>\s+)|(?P<COMMENT>//[^\n]*)|"""
    r"""(?P<STRING>"(?:\\.|[^"\\])*")|(?P<NUMBER>\d+(?:\.\d+)?)|"""
    r"""(?P<IDENT>[\wÀ-ÿ]+)|"""
    r"""(?P<OP>->|==|!=|>=|<=|&&|\|\||[+\-*/%<>=!(),{}\[\];.:])""",
    re.UNICODE,
)

KEYWORDS = {
    "programa", "numero", "texto", "logico", "lista", "mostrar",
    "se", "senao", "verdadeiro", "falso", "funcao", "retornar",
    "enquanto", "para", "estrutura", "quebrar", "continuar",
    "usar", "como",
}


class GPError(Exception):
    """A source-level GP error."""


class LocatedTuple(tuple):
    def __new__(cls, values, line, column):
        obj = super().__new__(cls, values)
        obj.line = line
        obj.column = column
        return obj


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    pos: int
    line: int = 1
    column: int = 1


@dataclass
class GPFunction:
    name: str
    params: list[tuple[str, str]]
    return_type: str | None
    body: tuple
    closure: "Environment"


@dataclass
class GPStructDef:
    name: str
    fields: list[tuple[str, str]]


@dataclass
class GPStructValue:
    definition: GPStructDef
    values: dict[str, Any]


class GPArray(list):
    """Runtime array retaining its declared element type."""
    def __init__(self, values=(), element_type: str | None = None):
        super().__init__(values)
        self.element_type = element_type


class GPModule:
    def __init__(self, path: Path, env: "Environment"):
        self.path = path
        self.env = env


class GPBuiltin:
    def __init__(self, name: str, implementation: Callable[[list[Any]], Any]):
        self.name = name
        self.implementation = implementation


class ReturnSignal(Exception):
    def __init__(self, value: Any = None):
        self.value = value


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


class Environment:
    def __init__(
        self, parent: "Environment | None" = None, base_dir: Path | None = None,
    ):
        self.values: dict[str, Any] = {}
        self.types: dict[str, tuple[str | None, str | None]] = {}
        self.parent = parent
        self.base_dir = base_dir or (parent.base_dir if parent else Path.cwd())
        self.module_cache = parent.module_cache if parent else {}
        self.loop_depth = parent.loop_depth if parent else 0

    def define(
        self, name: str, value: Any, type_name: str | None = None,
        element_type: str | None = None,
    ) -> None:
        if name in self.values:
            raise GPError(f"Identificador já declarado neste escopo: {name}")
        self.values[name] = value
        self.types[name] = (type_name, element_type)

    def get(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise GPError(f"Identificador não definido: {name}")

    def assign(self, name: str, value: Any) -> None:
        if name in self.values:
            type_name, element_type = self.types.get(name, (None, None))
            if type_name is not None and not type_matches(type_name, value, element_type):
                raise GPError(f"Tipo incompatível na atribuição de {name}: esperado {type_name}")
            self.values[name] = value
            return
        if self.parent is not None:
            self.parent.assign(name, value)
            return
        raise GPError(f"Variável não definida: {name}")


def _source_location(source: str, pos: int) -> tuple[int, int]:
    line = source.count("\n", 0, pos) + 1
    previous = source.rfind("\n", 0, pos)
    return line, pos - previous


def lex(source: str) -> list[Token]:
    tokens: list[Token] = []
    pos = 0
    while pos < len(source):
        match = TOKEN_RE.match(source, pos)
        if not match:
            if source[pos:].strip() == "":
                break
            line, column = _source_location(source, pos)
            raise GPError(f"linha {line}, coluna {column}: caractere inesperado {source[pos]!r}")
        kind = match.lastgroup
        value = match.group()
        start = pos
        pos = match.end()
        if kind in ("SPACE", "COMMENT"):
            continue
        line, column = _source_location(source, start)
        if kind == "STRING":
            tokens.append(Token("STRING", json.loads(value), start, line, column))
        elif kind == "NUMBER":
            tokens.append(Token("NUMBER", value, start, line, column))
        elif kind == "IDENT":
            tokens.append(Token(value if value in KEYWORDS else "IDENT", value, start, line, column))
        else:
            tokens.append(Token(value, value, start, line, column))
    line, column = _source_location(source, len(source))
    tokens.append(Token("EOF", "", len(source), line, column))
    return tokens


class Parser:
    PRECEDENCE = {
        "||": 1, "&&": 2, "==": 3, "!=": 3,
        ">": 4, "<": 4, ">=": 4, "<=": 4,
        "+": 5, "-": 5, "*": 6, "/": 6, "%": 6,
    }
    VALUE_TYPES = {"numero", "texto", "logico"}

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0

    def cur(self) -> Token:
        return self.tokens[self.index]

    def take(self, kind: str | None = None) -> Token:
        token = self.cur()
        if kind is not None and token.kind != kind:
            found = token.value or token.kind
            raise GPError(f"linha {token.line}, coluna {token.column}: esperado {kind}, encontrado {found}")
        self.index += 1
        return token

    def accept(self, *kinds: str) -> Token | None:
        if self.cur().kind in kinds:
            return self.take()
        return None

    def parse(self) -> tuple:
        self.accept("programa")
        if self.cur().kind == "STRING":
            self.take()
        statements = []
        while self.cur().kind != "EOF":
            statements.append(self.statement())
        return ("block", statements)

    def type_spec(self) -> tuple[str, str | None]:
        if self.accept("lista"):
            element = self.take()
            if element.kind not in self.VALUE_TYPES and element.kind != "IDENT":
                raise GPError(f"Tipo de elemento inválido para lista: {element.value}")
            return ("lista", element.value)
        token = self.take()
        if token.kind not in self.VALUE_TYPES and token.kind != "IDENT":
            raise GPError(f"Tipo inválido: {token.value or token.kind}")
        return (token.value, None)

    def looks_like_custom_declaration(self) -> bool:
        return (self.cur().kind == "IDENT" and self.index + 2 < len(self.tokens)
                and self.tokens[self.index + 1].kind == "IDENT"
                and self.tokens[self.index + 2].kind == "=")

    def variable_declaration(self, semicolon: bool = False) -> tuple:
        type_name, element_type = self.type_spec()
        name = self.take("IDENT").value
        self.take("=")
        value = self.expression()
        if semicolon:
            self.take(";")
        return ("declare", type_name, element_type, name, value)

    def simple_statement(self, semicolon: bool = False) -> tuple:
        if (self.cur().kind in self.VALUE_TYPES or self.cur().kind == "lista"
                or self.looks_like_custom_declaration()):
            return self.variable_declaration(semicolon)
        left = self.expression()
        if self.accept("="):
            node = ("assign", left, self.expression())
        else:
            node = ("expression", left)
        if semicolon:
            self.take(";")
        return node

    def statement(self) -> tuple:
        token = self.cur()
        node = self._statement()
        return LocatedTuple(node, token.line, token.column)

    def _statement(self) -> tuple:
        if self.accept(";"):
            return ("empty",)
        if self.accept("usar"):
            module_path = self.take("STRING").value
            self.take("como")
            alias = self.take("IDENT").value
            self.accept(";")
            return ("import", module_path, alias)
        if self.accept("funcao"):
            name = self.take("IDENT").value
            self.take("(")
            params = []
            if self.cur().kind != ")":
                while True:
                    param_type, _ = self.type_spec()
                    param_name = self.take("IDENT").value
                    params.append((param_type, param_name))
                    if not self.accept(","):
                        break
            self.take(")")
            return_type = None
            if self.accept("->"):
                return_type, _ = self.type_spec()
            return ("function", name, params, return_type, self.block())
        if self.accept("estrutura"):
            name = self.take("IDENT").value
            self.take("{")
            fields = []
            while self.cur().kind != "}":
                field_type, _ = self.type_spec()
                field_name = self.take("IDENT").value
                self.take(";")
                if any(existing == field_name for _, existing in fields):
                    raise GPError(f"Campo duplicado em {name}: {field_name}")
                fields.append((field_type, field_name))
            self.take("}")
            return ("struct", name, fields)
        if (self.cur().kind in self.VALUE_TYPES or self.cur().kind == "lista"
                or self.looks_like_custom_declaration()):
            return self.variable_declaration()
        if self.accept("mostrar"):
            self.take("(")
            values = []
            if self.cur().kind != ")":
                values.append(self.expression())
                while self.accept(","):
                    values.append(self.expression())
            self.take(")")
            self.accept(";")
            return ("print", values)
        if self.accept("se"):
            self.take("(")
            condition = self.expression()
            self.take(")")
            yes = self.block()
            no = self.block() if self.accept("senao") else None
            return ("if", condition, yes, no)
        if self.accept("enquanto"):
            self.take("(")
            condition = self.expression()
            self.take(")")
            return ("while", condition, self.block())
        if self.accept("para"):
            self.take("(")
            init = ("empty",) if self.cur().kind == ";" else self.simple_statement(semicolon=True)
            condition = ("lit", True) if self.cur().kind == ";" else self.expression()
            self.take(";")
            update = ("empty",) if self.cur().kind == ")" else self.simple_statement(semicolon=False)
            self.take(")")
            return ("for", init, condition, update, self.block())
        if self.accept("retornar"):
            value = None if self.cur().kind in (";", "}") else self.expression()
            self.accept(";")
            return ("return", value)
        if self.accept("quebrar"):
            self.accept(";")
            return ("break",)
        if self.accept("continuar"):
            self.accept(";")
            return ("continue",)
        return self.simple_statement()

    def block(self) -> tuple:
        self.take("{")
        statements = []
        while self.cur().kind not in ("}", "EOF"):
            statements.append(self.statement())
        self.take("}")
        return ("block", statements)

    def expression(self, min_precedence: int = 0) -> tuple:
        token = self.cur()
        node = self._expression(min_precedence)
        return LocatedTuple(node, token.line, token.column)

    def _expression(self, min_precedence: int = 0) -> tuple:
        token = self.take()
        if token.kind == "NUMBER":
            left = ("lit", float(token.value) if "." in token.value else int(token.value))
        elif token.kind == "STRING":
            left = ("lit", token.value)
        elif token.kind in ("verdadeiro", "falso"):
            left = ("lit", token.kind == "verdadeiro")
        elif token.kind in ("!", "-"):
            left = ("unary", token.kind, self.expression(7))
        elif token.kind == "(":
            left = self.expression()
            self.take(")")
        elif token.kind == "[":
            items = []
            if self.cur().kind != "]":
                items.append(self.expression())
                while self.accept(","):
                    items.append(self.expression())
            self.take("]")
            left = ("array", items)
        elif token.kind == "IDENT":
            left = ("var", token.value)
        else:
            raise GPError(f"linha {token.line}, coluna {token.column}: expressão inválida")

        while True:
            if self.cur().kind == "(":
                self.take("(")
                args = []
                if self.cur().kind != ")":
                    args.append(self.expression())
                    while self.accept(","):
                        args.append(self.expression())
                self.take(")")
                left = ("call", left, args)
                continue
            if self.accept("["):
                index = self.expression()
                self.take("]")
                left = ("index", left, index)
                continue
            if self.accept("."):
                field = self.take("IDENT").value
                left = ("field", left, field)
                continue
            if self.cur().kind == "{" and left[0] == "var":
                self.take("{")
                fields = {}
                if self.cur().kind != "}":
                    while True:
                        field = self.take("IDENT").value
                        self.take(":")
                        fields[field] = self.expression()
                        if not self.accept(","):
                            break
                self.take("}")
                left = ("construct", left[1], fields)
                continue
            op = self.cur().kind
            if op not in self.PRECEDENCE or self.PRECEDENCE[op] < min_precedence:
                break
            self.take()
            precedence = self.PRECEDENCE[op]
            right = self.expression(precedence + 1)
            left = ("binary", op, left, right)
        return left


def type_matches(type_name: str, value: Any, element_type: str | None = None) -> bool:
    if type_name == "numero":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_name == "texto":
        return isinstance(value, str)
    if type_name == "logico":
        return isinstance(value, bool)
    if type_name == "lista":
        return isinstance(value, list) and (
            element_type is None or all(type_matches(element_type, item) for item in value)
        )
    return isinstance(value, GPStructValue) and value.definition.name == type_name


def eval_expression(node: tuple, env: Environment) -> Any:
    tag = node[0]
    if tag == "lit":
        return node[1]
    if tag == "var":
        return env.get(node[1])
    if tag == "array":
        return [eval_expression(item, env) for item in node[1]]
    if tag == "unary":
        value = eval_expression(node[2], env)
        return not value if node[1] == "!" else -value
    if tag == "binary":
        op = node[1]
        left = eval_expression(node[2], env)
        if op == "&&" and not left:
            return False
        if op == "||" and left:
            return True
        right = eval_expression(node[3], env)
        operations = {
            "+": lambda: left + right, "-": lambda: left - right,
            "*": lambda: left * right, "/": lambda: left / right,
            "%": lambda: left % right, "==": lambda: left == right,
            "!=": lambda: left != right, ">": lambda: left > right,
            "<": lambda: left < right, ">=": lambda: left >= right,
            "<=": lambda: left <= right, "&&": lambda: bool(left and right),
            "||": lambda: bool(left or right),
        }
        try:
            return operations[op]()
        except (TypeError, ZeroDivisionError) as exc:
            raise GPError(f"Operação inválida '{op}': {exc}") from exc
    if tag == "call":
        callee = eval_expression(node[1], env)
        arguments = [eval_expression(arg, env) for arg in node[2]]
        return call_value(callee, arguments)
    if tag == "index":
        target = eval_expression(node[1], env)
        index = eval_expression(node[2], env)
        if not isinstance(target, (list, str)) or not isinstance(index, int):
            raise GPError("Índice exige lista/texto e número inteiro")
        try:
            return target[index]
        except IndexError as exc:
            raise GPError(f"Índice fora dos limites: {index}") from exc
    if tag == "field":
        target = eval_expression(node[1], env)
        if isinstance(target, GPModule):
            return target.env.get(node[2])
        if not isinstance(target, GPStructValue):
            raise GPError("Acesso a campo exige uma estrutura ou módulo")
        if node[2] not in target.values:
            raise GPError(f"Campo não existe: {node[2]}")
        return target.values[node[2]]
    if tag == "construct":
        definition = env.get(node[1])
        if not isinstance(definition, GPStructDef):
            raise GPError(f"Tipo de estrutura não declarado: {node[1]}")
        supplied = node[2]
        expected = {name for _, name in definition.fields}
        if set(supplied) != expected:
            missing = sorted(expected - set(supplied))
            extra = sorted(set(supplied) - expected)
            raise GPError(f"Campos inválidos em {node[1]}; faltando={missing}, extras={extra}")
        values = {}
        for field_type, field_name in definition.fields:
            value = eval_expression(supplied[field_name], env)
            if not type_matches(field_type, value):
                raise GPError(f"Tipo incompatível no campo {field_name}: esperado {field_type}")
            values[field_name] = value
        return GPStructValue(definition, values)
    raise GPError(f"Expressão interna desconhecida: {tag}")


def assign_target(target: tuple, value: Any, env: Environment) -> None:
    tag = target[0]
    if tag == "var":
        env.assign(target[1], value)
        return
    if tag == "index":
        sequence = eval_expression(target[1], env)
        index = eval_expression(target[2], env)
        if not isinstance(sequence, list) or not isinstance(index, int):
            raise GPError("Atribuição por índice exige lista e número inteiro")
        if index < 0 or index >= len(sequence):
            raise GPError(f"Índice fora dos limites: {index}")
        if isinstance(sequence, GPArray) and sequence.element_type is not None:
            if not type_matches(sequence.element_type, value):
                raise GPError(f"Tipo incompatível no array: esperado {sequence.element_type}")
        sequence[index] = value
        return
    if tag == "field":
        instance = eval_expression(target[1], env)
        field_name = target[2]
        if not isinstance(instance, GPStructValue) or field_name not in instance.values:
            raise GPError(f"Campo inválido: {field_name}")
        field_type = next(t for t, n in instance.definition.fields if n == field_name)
        if not type_matches(field_type, value):
            raise GPError(f"Tipo incompatível no campo {field_name}: esperado {field_type}")
        instance.values[field_name] = value
        return
    raise GPError("Destino inválido para atribuição")


def call_value(callee: Any, arguments: list[Any]) -> Any:
    if isinstance(callee, GPBuiltin):
        return callee.implementation(arguments)
    if not isinstance(callee, GPFunction):
        raise GPError("O valor chamado não é uma função")
    if len(arguments) != len(callee.params):
        raise GPError(
            f"Função {callee.name} esperava {len(callee.params)} argumento(s), recebeu {len(arguments)}"
        )
    local = Environment(callee.closure)
    # A function cannot break/continue a caller's loop.
    local.loop_depth = 0
    for (type_name, name), value in zip(callee.params, arguments):
        if not type_matches(type_name, value):
            raise GPError(f"Argumento '{name}' incompatível: esperado {type_name}")
        if type_name == "lista" and not isinstance(value, GPArray):
            value = GPArray(value)
        local.define(name, value, type_name)
    try:
        execute_block(callee.body, local, new_scope=False)
        result = None
    except ReturnSignal as signal:
        result = signal.value
    if callee.return_type is not None and not type_matches(callee.return_type, result):
        raise GPError(
            f"Retorno de {callee.name} incompatível: esperado {callee.return_type}"
        )
    return result


def execute_block(block: tuple | None, env: Environment, new_scope: bool = True) -> None:
    if block is None:
        return
    target = Environment(env) if new_scope else env
    for statement in block[1]:
        execute_statement(statement, target)


def execute_statement(node: tuple, env: Environment) -> None:
    tag = node[0]
    if tag in ("empty",):
        return
    if tag == "block":
        execute_block(node, env)
    elif tag == "declare":
        type_name, element_type, name, expression = node[1:]
        value = eval_expression(expression, env)
        if not type_matches(type_name, value, element_type):
            raise GPError(f"Tipo incompatível para {name}: esperado {type_name}")
        if type_name == "lista":
            value = GPArray(value, element_type)
        env.define(name, value, type_name, element_type)
    elif tag == "assign":
        value = eval_expression(node[2], env)
        assign_target(node[1], value, env)
    elif tag == "expression":
        eval_expression(node[1], env)
    elif tag == "print":
        print(*[eval_expression(value, env) for value in node[1]])
    elif tag == "if":
        branch = node[2] if eval_expression(node[1], env) else node[3]
        execute_block(branch, env)
    elif tag == "function":
        _, name, params, return_type, body = node
        env.define(name, GPFunction(name, params, return_type, body, env))
    elif tag == "struct":
        _, name, fields = node
        env.define(name, GPStructDef(name, fields))
    elif tag == "import":
        _, module_path, alias = node
        path = (env.base_dir / module_path).resolve()
        if not path.is_file():
            raise GPError(f"Módulo não encontrado: {path}")
        module = env.module_cache.get(path)
        if module is None:
            module_env = Environment(env, base_dir=path.parent)
            module = GPModule(path, module_env)
            env.module_cache[path] = module
            try:
                module_source = path.read_text(encoding="utf-8")
                module_tree = Parser(lex(module_source)).parse()
                execute_block(module_tree, module_env, new_scope=False)
            except Exception:
                env.module_cache.pop(path, None)
                raise
        env.define(alias, module)
    elif tag == "return":
        raise ReturnSignal(None if node[1] is None else eval_expression(node[1], env))
    elif tag == "break":
        if env.loop_depth <= 0:
            raise GPError("quebrar só pode ser usado dentro de um laço")
        raise BreakSignal()
    elif tag == "continue":
        if env.loop_depth <= 0:
            raise GPError("continuar só pode ser usado dentro de um laço")
        raise ContinueSignal()
    elif tag == "while":
        env.loop_depth += 1
        try:
            while eval_expression(node[1], env):
                try:
                    execute_block(node[2], env)
                except ContinueSignal:
                    continue
                except BreakSignal:
                    break
        finally:
            env.loop_depth -= 1
    elif tag == "for":
        loop_env = Environment(env)
        execute_statement(node[1], loop_env)
        loop_env.loop_depth += 1
        try:
            while eval_expression(node[2], loop_env):
                try:
                    execute_block(node[4], loop_env)
                except ContinueSignal:
                    pass
                except BreakSignal:
                    break
                execute_statement(node[3], loop_env)
        finally:
            loop_env.loop_depth -= 1
    else:
        raise GPError(f"Instrução interna desconhecida: {tag}")


def _builtin_size(arguments: list[Any]) -> int:
    if len(arguments) != 1 or not isinstance(arguments[0], (list, str)):
        raise GPError("tamanho() recebe uma lista ou texto")
    return len(arguments[0])


def _builtin_add(arguments: list[Any]) -> Any:
    if len(arguments) != 2 or not isinstance(arguments[0], list):
        raise GPError("adicionar() recebe uma lista e um valor")
    array, value = arguments
    if isinstance(array, GPArray) and array.element_type is not None:
        if not type_matches(array.element_type, value):
            raise GPError(f"Tipo incompatível no array: esperado {array.element_type}")
    array.append(value)
    return array


def _builtin_remove(arguments: list[Any]) -> Any:
    if len(arguments) != 2 or not isinstance(arguments[0], list) or not isinstance(arguments[1], int):
        raise GPError("remover() recebe uma lista e um índice inteiro")
    array, index = arguments
    if index < 0 or index >= len(array):
        raise GPError(f"Índice fora dos limites: {index}")
    return array.pop(index)


def _builtin_join_texts(arguments: list[Any]) -> str:
    if len(arguments) != 1 or not isinstance(arguments[0], list):
        raise GPError("unir_textos() recebe uma lista de textos")
    parts = arguments[0]
    total_bytes = 0
    for part in parts:
        if not isinstance(part, str):
            raise GPError("unir_textos() exige que todos os itens sejam texto")
        try:
            part_bytes = len(part.encode("utf-8", errors="strict"))
        except UnicodeEncodeError as exc:
            raise GPError("unir_textos() recebeu texto Unicode inválido") from exc
        if part_bytes > GP_MAX_TEXT_JOIN_BYTES - total_bytes:
            raise GPError("unir_textos() excede o limite de 64 MiB")
        total_bytes += part_bytes
    return "".join(parts)


def run_source(source: str, base_dir: str | Path | None = None) -> None:
    tokens = lex(source)
    tree = Parser(tokens).parse()
    root = Environment(base_dir=Path(base_dir) if base_dir is not None else Path.cwd())
    root.define("tamanho", GPBuiltin("tamanho", _builtin_size))
    root.define("adicionar", GPBuiltin("adicionar", _builtin_add))
    root.define("remover", GPBuiltin("remover", _builtin_remove))
    root.define("unir_textos", GPBuiltin("unir_textos", _builtin_join_texts))
    try:
        execute_block(tree, root, new_scope=False)
    except ReturnSignal as exc:
        raise GPError("retornar só pode ser usado dentro de uma função") from exc
    except BreakSignal as exc:
        raise GPError("quebrar só pode ser usado dentro de um laço") from exc
    except ContinueSignal as exc:
        raise GPError("continuar só pode ser usado dentro de um laço") from exc


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("GP — Gabriel Programming v0.2.0")
        print("Uso: python gp.py arquivo.gp")
        return 2
    path = Path(args[0])
    try:
        run_source(path.read_text(encoding="utf-8"), base_dir=path.resolve().parent)
        return 0
    except (GPError, OSError, json.JSONDecodeError) as exc:
        print(f"Erro GP: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
