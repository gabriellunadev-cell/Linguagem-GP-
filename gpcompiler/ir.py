"""Typed GP intermediate representation and normative in-memory validation."""
from dataclasses import dataclass
import math
from typing import Any

IR_FORMAT = "GP-IR"
IR_VERSION = 1


@dataclass
class IRInstruction:
    opcode: str
    operands: tuple[Any, ...] = ()


@dataclass
class IRFunction:
    name: str
    parameters: list[tuple[str, str]]
    return_type: str | None
    instructions: list[IRInstruction]


@dataclass
class IRProgram:
    version: str  # GP language version; deliberately distinct from IR_VERSION.
    instructions: list[IRInstruction]
    functions: dict[str, IRFunction]
    ir_version: int = IR_VERSION


_NO_ARGS = {
    "POP", "GET_INDEX", "SET_INDEX", "NEG", "NOT", "ADD", "SUB", "MUL",
    "DIV", "MOD", "EQ", "NE", "GT", "LT", "GE", "LE", "AND", "OR", "RETURN",
}


def validate_ir(program: IRProgram) -> IRProgram:
    """Validate GP-IR v1 independently of the bytecode container version.

    Raises ValueError for malformed in-memory IR and returns the same program
    on success, allowing validation at compiler and encoder boundaries.
    """
    def text(value: object, where: str) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError(f"GP-IR: texto não vazio obrigatório em {where}")

    def uint(value: object, where: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"GP-IR: inteiro não negativo inválido em {where}")

    def schema(value: object, where: str) -> None:
        if not isinstance(value, (list, tuple)):
            raise ValueError(f"GP-IR: schema inválido em {where}")
        seen = set()
        for pos, field in enumerate(value):
            if not isinstance(field, (list, tuple)) or len(field) != 2:
                raise ValueError(f"GP-IR: campo inválido em {where}[{pos}]")
            name, kind = field
            text(name, f"{where}[{pos}].nome")
            text(kind, f"{where}[{pos}].tipo")
            if name in seen:
                raise ValueError(f"GP-IR: campo duplicado {name!r} em {where}")
            seen.add(name)

    def block(code: object, where: str) -> None:
        if not isinstance(code, list):
            raise ValueError(f"GP-IR: bloco inválido em {where}")
        for index, ins in enumerate(code):
            at = f"{where}[{index}]"
            if not isinstance(ins, IRInstruction) or not isinstance(ins.opcode, str):
                raise ValueError(f"GP-IR: instrução inválida em {at}")
            op, args = ins.opcode, ins.operands
            if not isinstance(args, tuple):
                raise ValueError(f"GP-IR: operandos precisam ser tupla em {at}")
            if op == "CONST":
                if len(args) != 1:
                    raise ValueError(f"GP-IR: CONST exige 1 operando em {at}")
                value = args[0]
                if value is not None and not isinstance(value, (str, bool, int, float)):
                    raise ValueError(f"GP-IR: constante inválida em {at}")
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError(f"GP-IR: constante não finita em {at}")
                if isinstance(value, int) and not isinstance(value, bool):
                    try:
                        finite = math.isfinite(float(value))
                    except OverflowError:
                        finite = False
                    if not finite:
                        raise ValueError(f"GP-IR: constante numérica fora do intervalo em {at}")
            elif op == "DECLARE":
                if len(args) != 3:
                    raise ValueError(f"GP-IR: DECLARE exige 3 operandos em {at}")
                name, kind, element = args
                text(name, at); text(kind, at)
                if kind == "lista": text(element, at)
                elif element is not None: raise ValueError(f"GP-IR: tipo de elemento inesperado em {at}")
            elif op in {"LOAD", "STORE", "GET_FIELD", "SET_FIELD", "MAKE_TYPED_ARRAY"}:
                if len(args) != 1: raise ValueError(f"GP-IR: aridade inválida para {op} em {at}")
                text(args[0], at)
            elif op == "BUILD_STRUCT":
                if len(args) != 2: raise ValueError(f"GP-IR: BUILD_STRUCT exige 2 operandos em {at}")
                text(args[0], at); schema(args[1], at)
            elif op in {"BUILD_ARRAY", "PRINT", "JUMP", "JUMP_IF_FALSE"}:
                if len(args) != 1: raise ValueError(f"GP-IR: aridade inválida para {op} em {at}")
                uint(args[0], at)
                if op in {"JUMP", "JUMP_IF_FALSE"} and args[0] > len(code):
                    raise ValueError(f"GP-IR: destino de salto fora do bloco em {at}")
                if op in {"BUILD_ARRAY", "PRINT"} and args[0] > len(code):
                    raise ValueError(f"GP-IR: contagem excede o bloco em {at}")
            elif op == "CALL":
                if len(args) != 2: raise ValueError(f"GP-IR: CALL exige 2 operandos em {at}")
                text(args[0], at); uint(args[1], at)
                if args[1] > len(code): raise ValueError(f"GP-IR: aridade CALL excede bloco em {at}")
            elif op in _NO_ARGS:
                if args: raise ValueError(f"GP-IR: {op} não aceita operandos em {at}")
            else:
                raise ValueError(f"GP-IR: opcode desconhecido {op!r} em {at}")

    if not isinstance(program, IRProgram):
        raise ValueError("GP-IR: raiz precisa ser IRProgram")
    text(program.version, "language_version")
    if type(program.ir_version) is not int or program.ir_version != IR_VERSION:
        raise ValueError(f"GP-IR: versão de formato não suportada: {program.ir_version!r}")
    block(program.instructions, "main")
    if not isinstance(program.functions, dict):
        raise ValueError("GP-IR: functions precisa ser mapa")
    for name, fn in program.functions.items():
        text(name, "functions.nome")
        if not isinstance(fn, IRFunction) or fn.name != name:
            raise ValueError(f"GP-IR: definição inconsistente para função {name!r}")
        if not isinstance(fn.parameters, list):
            raise ValueError(f"GP-IR: parâmetros inválidos em {name}")
        seen = set()
        for pos, parameter in enumerate(fn.parameters):
            if not isinstance(parameter, (list, tuple)) or len(parameter) != 2:
                raise ValueError(f"GP-IR: parâmetro inválido em {name}[{pos}]")
            kind, param_name = parameter
            text(kind, f"{name}.parameters[{pos}].tipo")
            text(param_name, f"{name}.parameters[{pos}].nome")
            if param_name in seen: raise ValueError(f"GP-IR: parâmetro duplicado {param_name!r} em {name}")
            seen.add(param_name)
        if fn.return_type is not None: text(fn.return_type, f"{name}.return_type")
        block(fn.instructions, f"function:{name}")
    return program


def validate_canonical_ir(document: object) -> dict:
    """Validate canonical JSON-shaped GP-IR v1 without creating IR dataclasses.

    The accepted shape is the envelope emitted by the GP frontend. Validation
    mirrors validate_ir so the direct encoder and the compatibility API share
    the same semantic boundary.
    """
    def text(value: object, where: str) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError(f"GP-IR canônico: texto não vazio obrigatório em {where}")

    def uint(value: object, where: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"GP-IR canônico: inteiro não negativo inválido em {where}")

    if (
        not isinstance(document, dict)
        or set(document) != {"format", "ir_version", "version", "main", "functions"}
        or document.get("format") != IR_FORMAT
    ):
        raise ValueError("GP-IR canônico: envelope inválido ou campos inesperados")
    if type(document.get("ir_version")) is not int or document["ir_version"] != IR_VERSION:
        raise ValueError(f"GP-IR canônico: versão não suportada: {document.get('ir_version')!r}")
    text(document.get("version"), "version")
    main = document.get("main")
    functions = document.get("functions")
    if not isinstance(main, list) or not isinstance(functions, dict):
        raise ValueError("GP-IR canônico: main/functions inválidos")

    no_args = _NO_ARGS
    known = no_args | {
        "CONST", "LOAD", "DECLARE", "STORE", "BUILD_ARRAY", "MAKE_TYPED_ARRAY",
        "BUILD_STRUCT", "GET_FIELD", "SET_FIELD", "PRINT", "JUMP",
        "JUMP_IF_FALSE", "CALL",
    }

    def schema(raw: object, where: str) -> None:
        if not isinstance(raw, list):
            raise ValueError(f"GP-IR canônico: schema inválido em {where}")
        seen = set()
        for pos, field in enumerate(raw):
            if not isinstance(field, list) or len(field) != 2:
                raise ValueError(f"GP-IR canônico: campo inválido em {where}[{pos}]")
            name, kind = field
            text(name, f"{where}[{pos}].nome")
            text(kind, f"{where}[{pos}].tipo")
            if name in seen:
                raise ValueError(f"GP-IR canônico: campo duplicado {name!r} em {where}")
            seen.add(name)

    def block(code: object, where: str) -> None:
        if not isinstance(code, list) or len(code) > 2_000_000:
            raise ValueError(f"GP-IR canônico: bloco inválido em {where}")
        for index, instruction in enumerate(code):
            at = f"{where}[{index}]"
            if not isinstance(instruction, dict) or set(instruction) != {"op", "args"}:
                raise ValueError(f"GP-IR canônico: instrução inválida em {at}")
            op, args = instruction["op"], instruction["args"]
            if not isinstance(op, str) or op not in known or not isinstance(args, list):
                raise ValueError(f"GP-IR canônico: opcode/operandos inválidos em {at}")
            if op == "CONST":
                if len(args) != 1:
                    raise ValueError(f"GP-IR canônico: CONST exige 1 operando em {at}")
                value = args[0]
                if value is not None and not isinstance(value, (str, bool, int, float)):
                    raise ValueError(f"GP-IR canônico: constante inválida em {at}")
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError(f"GP-IR canônico: constante não finita em {at}")
                if isinstance(value, int) and not isinstance(value, bool):
                    try:
                        finite = math.isfinite(float(value))
                    except OverflowError:
                        finite = False
                    if not finite:
                        raise ValueError(f"GP-IR canônico: constante fora do intervalo em {at}")
            elif op == "DECLARE":
                if len(args) != 3:
                    raise ValueError(f"GP-IR canônico: DECLARE exige 3 operandos em {at}")
                name, kind, element = args
                text(name, at); text(kind, at)
                if kind == "lista":
                    text(element, at)
                elif element is not None:
                    raise ValueError(f"GP-IR canônico: tipo de elemento inesperado em {at}")
            elif op in {"LOAD", "STORE", "GET_FIELD", "SET_FIELD", "MAKE_TYPED_ARRAY"}:
                if len(args) != 1:
                    raise ValueError(f"GP-IR canônico: aridade inválida para {op} em {at}")
                text(args[0], at)
            elif op == "BUILD_STRUCT":
                if len(args) != 2:
                    raise ValueError(f"GP-IR canônico: BUILD_STRUCT exige 2 operandos em {at}")
                text(args[0], at); schema(args[1], at)
            elif op in {"BUILD_ARRAY", "PRINT", "JUMP", "JUMP_IF_FALSE"}:
                if len(args) != 1:
                    raise ValueError(f"GP-IR canônico: aridade inválida para {op} em {at}")
                uint(args[0], at)
                if args[0] > len(code):
                    if op in {"JUMP", "JUMP_IF_FALSE"}:
                        raise ValueError(f"GP-IR canônico: destino de salto fora do bloco em {at}")
                    raise ValueError(f"GP-IR canônico: contagem excede bloco em {at}")
            elif op == "CALL":
                if len(args) != 2:
                    raise ValueError(f"GP-IR canônico: CALL exige 2 operandos em {at}")
                text(args[0], at); uint(args[1], at)
                if args[1] > len(code):
                    raise ValueError(f"GP-IR canônico: aridade CALL excede bloco em {at}")
            elif op in no_args:
                if args:
                    raise ValueError(f"GP-IR canônico: {op} não aceita operandos em {at}")

    block(main, "main")
    for name, function in functions.items():
        text(name, "functions.nome")
        if not isinstance(function, dict) or set(function) != {"return_type", "parameters", "code"}:
            raise ValueError(f"GP-IR canônico: definição inválida para função {name!r}")
        params = function["parameters"]
        if not isinstance(params, list):
            raise ValueError(f"GP-IR canônico: parâmetros inválidos em {name}")
        seen = set()
        for pos, parameter in enumerate(params):
            if not isinstance(parameter, list) or len(parameter) != 2:
                raise ValueError(f"GP-IR canônico: parâmetro inválido em {name}[{pos}]")
            kind, param_name = parameter
            text(kind, f"{name}.parameters[{pos}].tipo")
            text(param_name, f"{name}.parameters[{pos}].nome")
            if param_name in seen:
                raise ValueError(f"GP-IR canônico: parâmetro duplicado {param_name!r} em {name}")
            seen.add(param_name)
        return_type = function["return_type"]
        if return_type is not None:
            text(return_type, f"{name}.return_type")
        block(function["code"], f"function:{name}")
    return document
