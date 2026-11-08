"""Semantic analysis for GP Core 0.4."""
from __future__ import annotations
from dataclasses import dataclass, field
from .ast import ASTNode


@dataclass
class Scope:
    parent: "Scope | None" = None
    symbols: dict[str, str] = field(default_factory=dict)

    def declare(self, name: str, type_name: str):
        if name in self.symbols:
            raise ValueError(f"Identificador duplicado no escopo: {name}")
        self.symbols[name] = type_name

    def lookup(self, name: str) -> str:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        raise ValueError(f"Identificador não declarado: {name}")


class SemanticAnalyzer:
    BUILTINS = {"tamanho", "adicionar", "remover", "entrada_fonte", "unir_textos"}

    def __init__(self):
        self.functions: dict[str, tuple[list[str], str | None]] = {}
        self.structs: dict[str, dict[str, str]] = {}
        self.errors: list[str] = []
        self.current_location: tuple[int, int] | None = None

    def analyze(self, root: ASTNode) -> list[str]:
        self.errors = []
        self.functions = {}
        self.structs = {}
        global_scope = Scope()
        for statement in root.args[0]:
            if statement.line is not None:
                self.current_location = (statement.line, statement.column or 1)
            if statement.kind == "function":
                name, params, return_type, _ = statement.args
                if name in self.functions:
                    self._error(f"Função duplicada: {name}")
                self.functions[name] = ([p[0] for p in params], return_type)
            elif statement.kind == "struct":
                name, fields = statement.args
                if name in self.structs:
                    self._error(f"Estrutura duplicada: {name}")
                self.structs[name] = {field_name: field_type for field_type, field_name in fields}
                if len(self.structs[name]) != len(fields):
                    self._error(f"Campo duplicado na estrutura {name}")
        for statement in root.args[0]:
            self._statement(statement, global_scope, None, 0)
        return self.errors

    def _error(self, message: str):
        if self.current_location:
            line, column = self.current_location
            message = f"linha {line}, coluna {column}: {message}"
        self.errors.append(message)

    def _qualified_callee(self, callee: ASTNode) -> str | None:
        if callee.kind == "var":
            return callee.args[0]
        if callee.kind == "field" and callee.args[0].kind == "var":
            # Module aliases are rewritten to a private function namespace.
            alias = callee.args[0].args[0]
            return alias + "__" + callee.args[1]
        return None

    def _expr(self, node: ASTNode, scope: Scope) -> str:
        if node.line is not None:
            self.current_location = (node.line, node.column or 1)
        kind, args = node.kind, node.args
        if kind == "lit":
            value = args[0]
            if isinstance(value, bool): return "logico"
            if isinstance(value, (int, float)): return "numero"
            if isinstance(value, str): return "texto"
            return "desconhecido"
        if kind == "var":
            try: return scope.lookup(args[0])
            except ValueError as exc:
                self._error(str(exc)); return "desconhecido"
        if kind == "array":
            types = [self._expr(item, scope) for item in args[0]]
            concrete = {item for item in types if item != "desconhecido"}
            if len(concrete) > 1: self._error("Array deve conter elementos de um único tipo")
            return "lista"
        if kind == "unary":
            op, value = args
            typ = self._expr(value, scope)
            expected = "logico" if op == "!" else "numero"
            if typ not in (expected, "desconhecido"):
                self._error(f"Operador unário {op} exige {expected}, recebeu {typ}")
            return expected
        if kind == "binary":
            op, left, right = args
            lt, rt = self._expr(left, scope), self._expr(right, scope)
            if op in ("+", "-", "*", "/", "%"):
                if op == "+" and lt == rt == "texto": return "texto"
                if lt not in ("numero", "desconhecido") or rt not in ("numero", "desconhecido"):
                    self._error(f"Operador {op} exige operandos numéricos")
                return "numero"
            if op in ("&&", "||"):
                if lt not in ("logico", "desconhecido") or rt not in ("logico", "desconhecido"):
                    self._error(f"Operador {op} exige operandos lógicos")
                return "logico"
            if lt != rt and "desconhecido" not in (lt, rt):
                self._error(f"Comparação {op} entre tipos incompatíveis: {lt} e {rt}")
            return "logico"
        if kind == "call":
            callee, arguments = args
            name = self._qualified_callee(callee)
            actual = [self._expr(item, scope) for item in arguments]
            if name is None:
                self._error("Chamada de função inválida")
                return "desconhecido"
            if name == "entrada_fonte":
                if actual: self._error("entrada_fonte() não aceita argumentos")
                return "texto"
            if name == "unir_textos":
                if len(actual) != 1: self._error("unir_textos() exige 1 argumento")
                elif actual[0] not in ("lista", "desconhecido"):
                    self._error("unir_textos() exige uma lista de textos")
                return "texto"
            if name == "tamanho":
                if len(actual) != 1: self._error("tamanho() exige 1 argumento")
                elif actual[0] not in ("texto", "lista", "desconhecido"):
                    self._error("tamanho() exige texto ou lista")
                return "numero"
            if name in ("adicionar", "remover"):
                if len(actual) != 2: self._error(f"{name}() exige 2 argumentos")
                elif actual[0] not in ("lista", "desconhecido"):
                    self._error(f"{name}() exige uma lista no primeiro argumento")
                if name == "adicionar" and len(actual) == 2: return "lista"
                return "desconhecido"
            signature = self.functions.get(name)
            if signature is None:
                self._error(f"Função não declarada: {name}")
                return "desconhecido"
            expected, result = signature
            if len(expected) != len(actual):
                self._error(f"Função {name} esperava {len(expected)} argumento(s), recebeu {len(actual)}")
            for index, (want, got) in enumerate(zip(expected, actual), 1):
                if want != got and got != "desconhecido":
                    self._error(f"Argumento {index} de {name}: esperado {want}, recebeu {got}")
            return result or "vazio"
        if kind == "index":
            base_type = self._expr(args[0], scope)
            index_type = self._expr(args[1], scope)
            if base_type not in ("lista", "texto", "desconhecido"):
                self._error("Indexação exige lista ou texto")
            if index_type not in ("numero", "desconhecido"):
                self._error("Índice deve ser numero")
            return "texto" if base_type == "texto" else "desconhecido"
        if kind == "field":
            base = self._expr(args[0], scope)
            field_name = args[1]
            fields = self.structs.get(base)
            if fields is None:
                self._error(f"Acesso a campo exige estrutura; recebido {base}")
                return "desconhecido"
            if field_name not in fields:
                self._error(f"Campo não declarado em {base}: {field_name}")
                return "desconhecido"
            return fields[field_name]
        if kind == "construct":
            struct_name, supplied = args
            fields = self.structs.get(struct_name)
            if fields is None:
                self._error(f"Estrutura não declarada: {struct_name}")
                return "desconhecido"
            for field_name in supplied:
                if field_name not in fields:
                    self._error(f"Campo não declarado em {struct_name}: {field_name}")
            for field_name, expected in fields.items():
                if field_name not in supplied:
                    self._error(f"Campo obrigatório ausente em {struct_name}: {field_name}")
                else:
                    actual = self._expr(supplied[field_name], scope)
                    if actual not in (expected, "desconhecido"):
                        self._error(f"Tipo do campo {field_name}: esperado {expected}, recebeu {actual}")
            return struct_name
        self._error(f"Expressão não suportada pelo analisador semântico: {kind}")
        return "desconhecido"

    def _block(self, node, scope, function_return, loop_depth, new_scope=True):
        current = Scope(scope) if new_scope else scope
        for statement in node.args[0]:
            self._statement(statement, current, function_return, loop_depth)

    def _statement(self, node, scope, function_return, loop_depth):
        if node.line is not None:
            self.current_location = (node.line, node.column or 1)
        kind, args = node.kind, node.args
        if kind in ("empty", "struct", "import"):
            return
        if kind == "declare":
            typ, element_type, name, expr = args
            actual = self._expr(expr, scope)
            if typ not in ("numero", "texto", "logico", "lista") and typ not in self.structs:
                self._error(f"Tipo não declarado: {typ}")
            if typ != actual and actual != "desconhecido":
                self._error(f"Tipo de {name}: declarado {typ}, expressão produz {actual}")
            if typ == "lista" and expr.kind == "array" and element_type:
                for item in expr.args[0]:
                    item_type = self._expr(item, scope)
                    if item_type not in (element_type, "desconhecido"):
                        self._error(f"Elemento de {name}: esperado {element_type}, recebeu {item_type}")
            try: scope.declare(name, typ)
            except ValueError as exc: self._error(str(exc))
            return
        if kind == "assign":
            target, expr = args
            actual = self._expr(expr, scope)
            if target.kind == "var":
                try:
                    expected = scope.lookup(target.args[0])
                    if expected != actual and actual != "desconhecido":
                        self._error(f"Atribuição em {target.args[0]}: esperado {expected}, recebeu {actual}")
                except ValueError as exc: self._error(str(exc))
            elif target.kind in ("field", "index"):
                expected = self._expr(target, scope)
                if expected != "desconhecido" and expected != actual:
                    self._error(f"Atribuição incompatível: esperado {expected}, recebeu {actual}")
            else:
                self._error("Destino de atribuição inválido")
            return
        if kind == "print":
            for value in args[0]: self._expr(value, scope)
            return
        if kind == "expression":
            self._expr(args[0], scope)
            return
        if kind == "if":
            cond, yes, no = args
            typ = self._expr(cond, scope)
            if typ not in ("logico", "desconhecido"): self._error("Condição de se deve ser lógica")
            self._block(yes, scope, function_return, loop_depth)
            if no is not None:
                self._block(no, scope, function_return, loop_depth)
            return
        if kind == "while":
            cond, body = args
            typ = self._expr(cond, scope)
            if typ not in ("logico", "desconhecido"): self._error("Condição de enquanto deve ser lógica")
            self._block(body, scope, function_return, loop_depth + 1)
            return
        if kind == "for":
            init, cond, update, body = args
            loop_scope = Scope(scope)
            if init.kind != "empty": self._statement(init, loop_scope, function_return, loop_depth)
            typ = self._expr(cond, loop_scope)
            if typ not in ("logico", "desconhecido"): self._error("Condição de para deve ser lógica")
            self._block(body, loop_scope, function_return, loop_depth + 1)
            if update.kind != "empty": self._statement(update, loop_scope, function_return, loop_depth)
            return
        if kind == "function":
            name, params, return_type, body = args
            fn_scope = Scope(scope)
            for typ, param_name in params:
                if typ not in ("numero", "texto", "logico", "lista") and typ not in self.structs:
                    self._error(f"Tipo de parâmetro não declarado: {typ}")
                try: fn_scope.declare(param_name, typ)
                except ValueError as exc: self._error(str(exc))
            self._block(body, fn_scope, return_type, 0)
            return
        if kind == "return":
            value = args[0]
            actual = "vazio" if value is None else self._expr(value, scope)
            if function_return is None: self._error("retornar fora de função")
            elif function_return != actual and actual != "desconhecido":
                self._error(f"Retorno incompatível: esperado {function_return}, recebeu {actual}")
            return
        if kind in ("break", "continue"):
            if loop_depth <= 0: self._error(f"{kind} fora de laço")
            return
        self._error(f"Instrução ainda não suportada pelo analisador semântico: {kind}")
