"""Portable reference VM for GP bytecode v1/v2."""
from __future__ import annotations
from .bytecode import decode


GP_MAX_HOST_SOURCE_BYTES = 16 * 1024 * 1024
GP_MAX_TEXT_JOIN_BYTES = 64 * 1024 * 1024


class GPVMError(Exception):
    pass


class GPTypedArray(list):
    def __init__(self, values=(), element_type=None):
        super().__init__(values)
        self.element_type = element_type

    def validate(self, value):
        if not GPVirtualMachine.matches(self.element_type, value):
            raise GPVMError(f"Array exige elemento {self.element_type}")


class GPStructValue:
    def __init__(self, name, fields, types):
        self.name = name
        self.fields = dict(fields)
        self.types = dict(types)

    def __repr__(self):
        values = ", ".join(f"{name}={value!r}" for name, value in self.fields.items())
        return f"{self.name}{{{values}}}"


class GPVirtualMachine:
    def __init__(self, max_steps: int = 1_000_000):
        if max_steps < 1:
            raise ValueError("max_steps deve ser maior que zero")
        self.max_steps = max_steps
        self.steps = 0
        self.globals = {}
        self.global_types = {}
        self._host_source = None

    @staticmethod
    def matches(type_name, value):
        if type_name in (None, "desconhecido"):
            return True
        if type_name == "numero":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if type_name == "texto":
            return isinstance(value, str)
        if type_name == "logico":
            return isinstance(value, bool)
        if type_name == "lista":
            return isinstance(value, list)
        if type_name.startswith("lista<") and type_name.endswith(">"):
            element_type = type_name[6:-1]
            return (
                isinstance(value, list)
                and bool(element_type)
                and all(GPVirtualMachine.matches(element_type, item) for item in value)
                and (
                    not isinstance(value, GPTypedArray)
                    or value.element_type in (None, element_type)
                )
            )
        if type_name == "vazio":
            return value is None
        return isinstance(value, GPStructValue) and value.name == type_name

    def _tick(self):
        self.steps += 1
        if self.steps > self.max_steps:
            raise GPVMError("Limite de instruções excedido")

    def _binary(self, op, a, b):
        try:
            operations = {
                "ADD": lambda: a + b, "SUB": lambda: a - b,
                "MUL": lambda: a * b, "DIV": lambda: a / b,
                "MOD": lambda: a % b, "EQ": lambda: a == b,
                "NE": lambda: a != b, "GT": lambda: a > b,
                "LT": lambda: a < b, "GE": lambda: a >= b,
                "LE": lambda: a <= b, "AND": lambda: bool(a and b),
                "OR": lambda: bool(a or b),
            }
            return operations[op]()
        except (KeyError, TypeError, ZeroDivisionError) as exc:
            raise GPVMError(f"Operação inválida {op}: {exc}") from exc

    def _call_builtin(self, name, args):
        if name == "entrada_fonte" and len(args) == 0:
            if self._host_source is None:
                raise GPVMError("entrada_fonte indisponível: o host não forneceu uma fonte")
            return self._host_source
        if name == "tamanho" and len(args) == 1 and isinstance(args[0], (str, list)):
            return len(args[0])
        if name == "unir_textos" and len(args) == 1 and isinstance(args[0], list):
            parts = args[0]
            total_bytes = 0
            for part in parts:
                if not isinstance(part, str):
                    raise GPVMError("unir_textos() exige que todos os itens sejam texto")
                try:
                    part_bytes = len(part.encode("utf-8", errors="strict"))
                except UnicodeEncodeError as exc:
                    raise GPVMError("unir_textos() recebeu texto Unicode inválido") from exc
                if part_bytes > GP_MAX_TEXT_JOIN_BYTES - total_bytes:
                    raise GPVMError("unir_textos() excede o limite de 64 MiB")
                total_bytes += part_bytes
            return "".join(parts)
        if name == "adicionar" and len(args) == 2 and isinstance(args[0], list):
            if isinstance(args[0], GPTypedArray):
                args[0].validate(args[1])
            args[0].append(args[1])
            return args[0]
        if name == "remover" and len(args) == 2 and isinstance(args[0], list) and isinstance(args[1], int):
            try:
                return args[0].pop(args[1])
            except IndexError as exc:
                raise GPVMError("Índice fora dos limites") from exc
        raise GPVMError(f"Função nativa ou assinatura inválida: {name}")

    def _execute(self, code, functions, local=None, parameter_types=None):
        local = {} if local is None else local
        local_types = dict(parameter_types or {})
        stack = []
        ip = 0
        while ip < len(code):
            self._tick()
            instruction = code[ip]
            op, args = instruction["op"], instruction.get("args", [])
            ip += 1
            if op == "CONST":
                stack.append(args[0])
            elif op == "LOAD":
                name = args[0]
                if name in local: stack.append(local[name])
                elif name in self.globals: stack.append(self.globals[name])
                else: raise GPVMError(f"Variável não definida: {name}")
            elif op == "DECLARE":
                name = args[0]
                typ = args[1] if len(args) > 1 else None
                element_type = args[2] if len(args) > 2 else None
                value = stack.pop()
                if name in local:
                    raise GPVMError(f"Identificador já declarado: {name}")
                if typ == "lista" and element_type:
                    if not isinstance(value, list):
                        raise GPVMError(f"{name} deveria ser uma lista")
                    typed = GPTypedArray(value, element_type)
                    for item in typed: typed.validate(item)
                    value = typed
                elif typ and not self.matches(typ, value):
                    raise GPVMError(f"Tipo incompatível em {name}: esperado {typ}")
                local[name] = value
                local_types[name] = (typ, element_type)
            elif op == "STORE":
                name, value = args[0], stack.pop()
                if name in local:
                    typ, element_type = local_types.get(name, (None, None))
                    if typ == "lista" and element_type and isinstance(local[name], GPTypedArray):
                        for item in value: local[name].validate(item)
                    elif typ and not self.matches(typ, value):
                        raise GPVMError(f"Tipo incompatível em {name}: esperado {typ}")
                    local[name] = value
                elif name in self.globals:
                    typ, element_type = self.global_types.get(name, (None, None))
                    if typ and not self.matches(typ, value):
                        raise GPVMError(f"Tipo incompatível em {name}: esperado {typ}")
                    self.globals[name] = value
                else: raise GPVMError(f"Variável não definida: {name}")
            elif op == "POP":
                if not stack: raise GPVMError("Pilha vazia em POP")
                stack.pop()
            elif op == "BUILD_ARRAY":
                count = args[0]
                values = stack[-count:] if count else []
                if count: del stack[-count:]
                stack.append(list(values))
            elif op == "MAKE_TYPED_ARRAY":
                values = stack.pop()
                array = GPTypedArray(values, args[0])
                for value in array: array.validate(value)
                stack.append(array)
            elif op == "BUILD_STRUCT":
                name, schema = args
                count = len(schema)
                values = stack[-count:] if count else []
                if count: del stack[-count:]
                fields, types = {}, {}
                for (field_name, field_type), value in zip(schema, values):
                    if not self.matches(field_type, value):
                        raise GPVMError(f"Tipo incompatível no campo {field_name}: esperado {field_type}")
                    fields[field_name], types[field_name] = value, field_type
                stack.append(GPStructValue(name, fields, types))
            elif op == "GET_FIELD":
                target = stack.pop()
                field_name = args[0]
                if not isinstance(target, GPStructValue) or field_name not in target.fields:
                    raise GPVMError(f"Campo inválido: {field_name}")
                stack.append(target.fields[field_name])
            elif op == "SET_FIELD":
                value, target = stack.pop(), stack.pop()
                field_name = args[0]
                if not isinstance(target, GPStructValue) or field_name not in target.fields:
                    raise GPVMError(f"Campo inválido: {field_name}")
                expected = target.types[field_name]
                if not self.matches(expected, value):
                    raise GPVMError(f"Tipo incompatível no campo {field_name}: esperado {expected}")
                target.fields[field_name] = value
            elif op == "GET_INDEX":
                index, target = stack.pop(), stack.pop()
                if not isinstance(target, (list, str)) or not isinstance(index, int):
                    raise GPVMError("Indexação exige lista/texto e índice inteiro")
                try: stack.append(target[index])
                except IndexError as exc: raise GPVMError("Índice fora dos limites") from exc
            elif op == "SET_INDEX":
                value, index, target = stack.pop(), stack.pop(), stack.pop()
                if not isinstance(target, list) or not isinstance(index, int):
                    raise GPVMError("Atribuição por índice exige lista e índice inteiro")
                if index < 0 or index >= len(target):
                    raise GPVMError("Índice fora dos limites")
                if isinstance(target, GPTypedArray): target.validate(value)
                target[index] = value
            elif op == "NEG":
                stack.append(-stack.pop())
            elif op == "NOT":
                stack.append(not stack.pop())
            elif op in ("ADD", "SUB", "MUL", "DIV", "MOD", "EQ", "NE",
                        "GT", "LT", "GE", "LE", "AND", "OR"):
                right, left = stack.pop(), stack.pop()
                stack.append(self._binary(op, left, right))
            elif op == "PRINT":
                count = args[0]
                values = stack[-count:] if count else []
                if count: del stack[-count:]
                print(*values)
            elif op == "JUMP":
                ip = args[0]
            elif op == "JUMP_IF_FALSE":
                if not stack.pop(): ip = args[0]
            elif op == "CALL":
                name, count = args
                call_args = stack[-count:] if count else []
                if count: del stack[-count:]
                if name in functions:
                    fn = functions[name]
                    params = fn["parameters"]
                    if len(params) != len(call_args):
                        raise GPVMError(f"{name}: quantidade incorreta de argumentos")
                    frame, frame_types = {}, {}
                    for (param_type, param_name), value in zip(params, call_args):
                        if not self.matches(param_type, value):
                            raise GPVMError(f"Parâmetro {param_name} de {name}: esperado {param_type}")
                        element_type = None
                        if param_type.startswith("lista<") and param_type.endswith(">"):
                            element_type = param_type[6:-1]
                            if isinstance(value, GPTypedArray):
                                if value.element_type not in (None, element_type):
                                    raise GPVMError(
                                        f"Parâmetro {param_name} de {name}: lista tipada incompatível"
                                    )
                                if value.element_type is None:
                                    value.element_type = element_type
                            else:
                                value = GPTypedArray(value, element_type)
                        frame[param_name], frame_types[param_name] = value, (
                            "lista" if element_type else param_type, element_type
                        )
                    result = self._execute(fn["code"], functions, frame, frame_types)
                    return_type = fn.get("return_type")
                    if return_type and not self.matches(return_type, result):
                        raise GPVMError(f"Retorno de {name}: esperado {return_type}")
                else:
                    result = self._call_builtin(name, call_args)
                stack.append(result)
            elif op == "RETURN":
                return stack.pop() if stack else None
            else:
                raise GPVMError(f"Opcode desconhecido: {op}")
        return None

    def run_payload(self, payload, *, host_source: str | None = None):
        if host_source is not None:
            if not isinstance(host_source, str):
                raise GPVMError("entrada_fonte precisa ser texto UTF-8")
            try:
                source_size = len(host_source.encode("utf-8", errors="strict"))
            except UnicodeEncodeError as exc:
                raise GPVMError("entrada_fonte contém Unicode inválido") from exc
            if source_size > GP_MAX_HOST_SOURCE_BYTES:
                raise GPVMError("entrada_fonte excede o limite de 16 MiB")
        program = payload["program"]
        if program.get("format") != "GP-IR":
            raise GPVMError("Seção de programa GP inválida")
        self.steps = 0
        self.globals = {}
        self.global_types = {}
        self._host_source = host_source
        try:
            return self._execute(program["main"], program.get("functions", {}), self.globals)
        finally:
            self._host_source = None

    def run_bytes(self, data: bytes, *, host_source: str | None = None):
        return self.run_payload(decode(data), host_source=host_source)
