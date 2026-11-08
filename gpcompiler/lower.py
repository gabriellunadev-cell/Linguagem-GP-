"""AST-to-IR lowering for GP Core 0.4."""
from __future__ import annotations
from .ast import ASTNode
from .ir import IRInstruction as I, IRFunction, IRProgram, validate_ir

BIN_OPS = {
    "+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV", "%": "MOD",
    "==": "EQ", "!=": "NE", ">": "GT", "<": "LT",
    ">=": "GE", "<=": "LE", "&&": "AND", "||": "OR",
}


class Lowerer:
    def __init__(self):
        self.code = []
        self.functions = {}
        self.structs = {}
        self.loop_stack = []

    def emit(self, opcode, *operands):
        self.code.append(I(opcode, tuple(operands)))
        return len(self.code) - 1

    def patch(self, index, target):
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(self.code):
            raise ValueError(f"Índice de backpatch inválido: {index!r}")
        if isinstance(target, bool) or not isinstance(target, int) or not 0 <= target <= len(self.code):
            raise ValueError(f"Destino de backpatch inválido: {target!r}")
        old = self.code[index]
        if old.opcode not in {"JUMP", "JUMP_IF_FALSE"} or len(old.operands) != 1:
            raise ValueError(f"Instrução {index} não aceita backpatch: {old.opcode}")
        self.code[index] = I(old.opcode, (target,))

    def expression(self, node):
        kind, args = node.kind, node.args
        if kind == "lit": self.emit("CONST", args[0])
        elif kind == "var": self.emit("LOAD", args[0])
        elif kind == "unary":
            self.expression(args[1]); self.emit("NOT" if args[0] == "!" else "NEG")
        elif kind == "binary":
            self.expression(args[1]); self.expression(args[2]); self.emit(BIN_OPS[args[0]])
        elif kind == "array":
            for item in args[0]: self.expression(item)
            self.emit("BUILD_ARRAY", len(args[0]))
        elif kind == "index":
            self.expression(args[0]); self.expression(args[1]); self.emit("GET_INDEX")
        elif kind == "field":
            self.expression(args[0]); self.emit("GET_FIELD", args[1])
        elif kind == "construct":
            struct_name, supplied = args
            schema = self.structs.get(struct_name)
            if schema is None: raise ValueError(f"Estrutura não encontrada no compilador: {struct_name}")
            for field_name, field_type in schema:
                self.expression(supplied[field_name])
            self.emit("BUILD_STRUCT", struct_name, schema)
        elif kind == "call":
            callee, values = args
            if callee.kind == "var": name = callee.args[0]
            elif callee.kind == "field" and callee.args[0].kind == "var":
                name = callee.args[0].args[0] + "__" + callee.args[1]
            else: raise ValueError("Chamada GP exige função ou função qualificada por módulo")
            for value in values: self.expression(value)
            self.emit("CALL", name, len(values))
        else: raise ValueError(f"Expressão não suportada pelo bytecode 0.4: {kind}")

    def block(self, node):
        for statement in node.args[0]: self.statement(statement)

    def statement(self, node):
        kind, args = node.kind, node.args
        if kind in ("empty", "struct", "import"): return
        if kind == "function":
            name, params, return_type, body = args
            previous_code, previous_loops = self.code, self.loop_stack
            self.code, self.loop_stack = [], []
            self.block(body)
            self.emit("CONST", None); self.emit("RETURN")
            self.functions[name] = IRFunction(name, params, return_type, self.code)
            self.code, self.loop_stack = previous_code, previous_loops
        elif kind == "declare":
            typ, element_type, name, value = args
            self.expression(value)
            if typ == "lista": self.emit("MAKE_TYPED_ARRAY", element_type)
            self.emit("DECLARE", name, typ, element_type)
        elif kind == "assign":
            target, value = args
            if target.kind == "var":
                self.expression(value); self.emit("STORE", target.args[0])
            elif target.kind == "index":
                self.expression(target.args[0]); self.expression(target.args[1])
                self.expression(value); self.emit("SET_INDEX")
            elif target.kind == "field":
                self.expression(target.args[0]); self.expression(value)
                self.emit("SET_FIELD", target.args[1])
            else: raise ValueError("Destino de atribuição não suportado")
        elif kind == "print":
            for value in args[0]: self.expression(value)
            self.emit("PRINT", len(args[0]))
        elif kind == "expression":
            self.expression(args[0]); self.emit("POP")
        elif kind == "if":
            condition, yes, no = args
            self.expression(condition)
            jump_false = self.emit("JUMP_IF_FALSE", -1)
            self.block(yes)
            if no is not None:
                jump_end = self.emit("JUMP", -1)
                self.patch(jump_false, len(self.code)); self.block(no)
                self.patch(jump_end, len(self.code))
            else:
                self.patch(jump_false, len(self.code))
        elif kind == "while":
            condition, body = args
            start = len(self.code); self.expression(condition)
            exit_jump = self.emit("JUMP_IF_FALSE", -1)
            breaks, continues = [], []; self.loop_stack.append((breaks, continues))
            self.block(body)
            for jump in continues: self.patch(jump, start)
            self.emit("JUMP", start); end = len(self.code)
            self.patch(exit_jump, end)
            for jump in breaks: self.patch(jump, end)
            self.loop_stack.pop()
        elif kind == "for":
            init, condition, update, body = args
            if init.kind != "empty": self.statement(init)
            start = len(self.code); self.expression(condition)
            exit_jump = self.emit("JUMP_IF_FALSE", -1)
            breaks, continues = [], []; self.loop_stack.append((breaks, continues))
            self.block(body); update_start = len(self.code)
            for jump in continues: self.patch(jump, update_start)
            if update.kind != "empty": self.statement(update)
            self.emit("JUMP", start); end = len(self.code)
            self.patch(exit_jump, end)
            for jump in breaks: self.patch(jump, end)
            self.loop_stack.pop()
        elif kind == "return":
            if args[0] is None: self.emit("CONST", None)
            else: self.expression(args[0])
            self.emit("RETURN")
        elif kind == "break":
            if not self.loop_stack: raise ValueError("quebrar fora de laço")
            self.loop_stack[-1][0].append(self.emit("JUMP", -1))
        elif kind == "continue":
            if not self.loop_stack: raise ValueError("continuar fora de laço")
            self.loop_stack[-1][1].append(self.emit("JUMP", -1))
        else: raise ValueError(f"Instrução não suportada pelo bytecode 0.4: {kind}")

    def lower(self, root):
        for statement in root.args[0]:
            if statement.kind == "struct":
                name, fields = statement.args
                self.structs[name] = [(field_name, field_type) for field_type, field_name in fields]
        self.block(root)
        return validate_ir(IRProgram("0.4", self.code, self.functions))


def ir_to_dict(program):
    def instructions(items):
        return [{"op": item.opcode, "args": list(item.operands)} for item in items]
    return {
        "format": "GP-IR", "ir_version": program.ir_version, "version": program.version,
        "main": instructions(program.instructions),
        "functions": {
            name: {"parameters": params.parameters, "return_type": params.return_type,
                   "code": instructions(params.instructions)}
            for name, params in program.functions.items()
        },
    }
