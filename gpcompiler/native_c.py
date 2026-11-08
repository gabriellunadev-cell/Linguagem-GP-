"""Experimental C/ARM64 ahead-of-time backend for a safe GP subset."""
from __future__ import annotations
import json
import re
from .ast import ASTNode


class NativeBackendError(ValueError):
    pass


class CBackend:
    C_TYPES = {"numero": "double", "texto": "const char *", "logico": "int", "vazio": "void"}

    def __init__(self):
        self.functions = {}
        self.globals = {}
        self.var_types = {}

    @staticmethod
    def ident(name):
        value = re.sub(r"[^A-Za-z0-9_]", lambda m: "_u%04x" % ord(m.group()), name)
        if not value or value[0].isdigit():
            value = "gp_" + value
        return "gp_" + value

    def ctype(self, type_name):
        if type_name not in self.C_TYPES:
            raise NativeBackendError(f"Tipo não suportado no backend nativo: {type_name}")
        return self.C_TYPES[type_name]

    def expr_type(self, node):
        kind, args = node.kind, node.args
        if kind == "lit":
            value = args[0]
            if isinstance(value, bool): return "logico"
            if isinstance(value, (int, float)): return "numero"
            if isinstance(value, str): return "texto"
        if kind == "var":
            return self.var_types.get(args[0], self.globals.get(args[0], "numero"))
        if kind == "unary":
            return "logico" if args[0] == "!" else self.expr_type(args[1])
        if kind == "binary":
            if args[0] in ("==", "!=", ">", "<", ">=", "<=", "&&", "||"): return "logico"
            left, right = self.expr_type(args[1]), self.expr_type(args[2])
            return "texto" if args[0] == "+" and left == right == "texto" else "numero"
        if kind == "call":
            callee = args[0]
            name = callee.args[0] if callee.kind == "var" else None
            if name in self.functions: return self.functions[name]
        return "numero"

    def expression(self, node):
        kind, args = node.kind, node.args
        if kind == "lit":
            value = args[0]
            if isinstance(value, bool): return "1" if value else "0"
            if isinstance(value, (int, float)): return repr(value)
            if isinstance(value, str): return json.dumps(value, ensure_ascii=False)
        if kind == "var":
            return self.ident(args[0])
        if kind == "unary":
            op = "!" if args[0] == "!" else "-"
            return f"({op}{self.expression(args[1])})"
        if kind == "binary":
            op, left, right = args
            a, b = self.expression(left), self.expression(right)
            if op == "+" and self.expr_type(left) == self.expr_type(right) == "texto":
                raise NativeBackendError("Concatenação de textos ainda não suportada no backend nativo")
            if op == "%": return f"fmod(({a}), ({b}))"
            return f"(({a}) {op} ({b}))"
        if kind == "call":
            callee, values = args
            if callee.kind == "var":
                name = callee.args[0]
            elif callee.kind == "field" and callee.args[0].kind == "var":
                name = callee.args[0].args[0] + "__" + callee.args[1]
            else:
                raise NativeBackendError("Chamada dinâmica não suportada no backend nativo")
            if name not in self.functions:
                raise NativeBackendError(f"Função nativa não disponível: {name}")
            return f"{self.ident('gp_' + name)}(" + ", ".join(self.expression(x) for x in values) + ")"
        raise NativeBackendError(f"Expressão não suportada no backend nativo: {kind}")

    def block(self, node, indent=1):
        lines = []
        for statement in node.args[0]:
            lines.extend(self.statement(statement, indent))
        return lines

    def statement(self, node, indent=1):
        pad = "    " * indent
        kind, args = node.kind, node.args
        if kind in ("empty", "struct", "import", "function"):
            return []
        if kind == "declare":
            typ, element_type, name, value = args
            if typ not in self.C_TYPES or typ == "vazio":
                raise NativeBackendError(f"Declaração {typ} não suportada no backend nativo")
            self.var_types[name] = typ
            return [pad + f"{self.ctype(typ)} {self.ident(name)} = {self.expression(value)};"]
        if kind == "assign":
            target, value = args
            if target.kind != "var":
                raise NativeBackendError("Backend nativo inicial suporta atribuição simples a variável")
            return [pad + f"{self.ident(target.args[0])} = {self.expression(value)};"]
        if kind == "print":
            lines = []
            for index, value in enumerate(args[0]):
                if index: lines.append(pad + 'printf(" ");')
                typ = self.expr_type(value)
                expression = self.expression(value)
                if typ == "texto":
                    lines.append(pad + f'printf("%s", {expression});')
                elif typ == "logico":
                    lines.append(pad + f'printf("%s", ({expression}) ? "verdadeiro" : "falso");')
                else:
                    lines.append(pad + f'printf("%g", (double)({expression}));')
            lines.append(pad + 'printf("\\n");')
            return lines
        if kind == "expression":
            return [pad + self.expression(args[0]) + ";"]
        if kind == "if":
            condition, yes, no = args
            lines = [pad + f"if ({self.expression(condition)}) {{"]
            lines += self.block(yes, indent + 1)
            if no is not None:
                lines.append(pad + "} else {")
                lines += self.block(no, indent + 1)
            lines.append(pad + "}")
            return lines
        if kind == "while":
            condition, body = args
            lines = [pad + f"while ({self.expression(condition)}) {{"]
            lines += self.block(body, indent + 1)
            lines.append(pad + "}")
            return lines
        if kind == "for":
            init, condition, update, body = args
            init_code = self.for_part(init) if init.kind != "empty" else ""
            update_code = self.for_part(update) if update.kind != "empty" else ""
            lines = [pad + f"for ({init_code}; {self.expression(condition)}; {update_code}) {{"]
            lines += self.block(body, indent + 1)
            lines.append(pad + "}")
            return lines
        if kind == "return":
            return [pad + ("return;" if args[0] is None else "return " + self.expression(args[0]) + ";")]
        if kind == "break": return [pad + "break;"]
        if kind == "continue": return [pad + "continue;"]
        raise NativeBackendError(f"Instrução não suportada no backend nativo: {kind}")

    def for_part(self, node):
        if node.kind == "declare":
            typ, element_type, name, value = node.args
            if typ not in self.C_TYPES or typ == "vazio":
                raise NativeBackendError(f"Tipo {typ} não suportado em para")
            self.var_types[name] = typ
            return f"{self.ctype(typ)} {self.ident(name)} = {self.expression(value)}"
        if node.kind == "assign":
            target, value = node.args
            if target.kind != "var": raise NativeBackendError("Atualização nativa exige variável")
            return f"{self.ident(target.args[0])} = {self.expression(value)}"
        if node.kind == "expression": return self.expression(node.args[0])
        raise NativeBackendError(f"Expressão de atualização não suportada: {node.kind}")

    def lower(self, root):
        statements = root.args[0]
        for item in statements:
            if item.kind == "function":
                name, params, return_type, body = item.args
                self.functions[name] = return_type or "vazio"
        # Collect top-level globals before rendering functions.
        globals_c = []
        main_statements = []
        for item in statements:
            if item.kind == "declare":
                typ, element_type, name, value = item.args
                if typ not in self.C_TYPES or typ == "vazio":
                    raise NativeBackendError(f"Global do tipo {typ} não suportada")
                if value.kind != "lit":
                    raise NativeBackendError("Inicializadores globais nativos devem ser literais")
                self.globals[name] = typ
                self.var_types[name] = typ
                globals_c.append(f"static {self.ctype(typ)} {self.ident(name)} = {self.expression(value)};")
            elif item.kind not in ("function", "struct", "empty"):
                main_statements.append(item)

        prototypes = []
        function_bodies = []
        for item in statements:
            if item.kind != "function": continue
            name, params, return_type, body = item.args
            ret = self.ctype(return_type or "vazio")
            args = ", ".join(f"{self.ctype(t)} {self.ident(n)}" for t, n in params) or "void"
            prototypes.append(f"static {ret} {self.ident('gp_' + name)}({args});")
            function_bodies.append(f"static {ret} {self.ident('gp_' + name)}({args}) {{")
            previous_types = dict(self.var_types)
            for parameter_type, parameter_name in params:
                self.var_types[parameter_name] = parameter_type
            function_bodies += self.block(body, 1)
            self.var_types = previous_types
            if return_type is None: function_bodies.append("    return;")
            function_bodies.append("}")
        main_body = self.block(ASTNode("block", (main_statements,)), 1)
        lines = [
            "#include <stdio.h>",
            "#include <math.h>",
            "",
            *globals_c,
            *prototypes,
            "",
            *function_bodies,
            "",
            "int main(void) {",
            *main_body,
            "    return 0;",
            "}",
            "",
        ]
        return "\n".join(lines)
