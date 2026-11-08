"""Validated adapters for structured and legacy GP-owned IR envelopes.

The GP frontend transports typed JSON field arrays. The structured adapter
builds IRInstruction objects directly from those values; the legacy delimiter-
based reader remains separate for compatibility.
"""
from __future__ import annotations

import json
import math
from typing import Iterable

from .ir import IRFunction, IRInstruction, IRProgram, validate_ir


class SelfHostedIRError(ValueError):
    """Malformed or unsupported instruction in self-hosted GP IR."""


_NO_OPERAND = {
    "POP", "NEG", "NOT", "ADD", "SUB", "MUL", "DIV", "MOD",
    "EQ", "NE", "GT", "LT", "GE", "LE", "AND", "OR",
    "GET_INDEX", "SET_INDEX", "RETURN",
}


def _integer(value: object, context: str) -> int:
    """Require an actual JSON integer (never bool or numeric text)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise SelfHostedIRError(f"{context}: inteiro JSON inválido: {value!r}")
    if value < 0:
        raise SelfHostedIRError(f"{context}: inteiro negativo não permitido")
    return value


def _legacy_integer(value: str, context: str) -> int:
    try:
        parsed = int(value, 10)
    except (TypeError, ValueError) as exc:
        raise SelfHostedIRError(f"{context}: inteiro legado inválido: {value!r}") from exc
    if parsed < 0:
        raise SelfHostedIRError(f"{context}: inteiro legado negativo não permitido")
    return parsed


def _required_text(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise SelfHostedIRError(f"{context}: texto não vazio obrigatório")
    return value


def _constant(kind: str, raw: str):
    if kind == "NULO":
        if raw:
            raise SelfHostedIRError("CONST NULO não aceita payload")
        return None
    if kind == "NUMERO":
        if not raw:
            raise SelfHostedIRError("CONST NUMERO sem valor")
        try:
            number = float(raw) if any(mark in raw for mark in ".eE") else int(raw, 10)
        except ValueError as exc:
            raise SelfHostedIRError(f"CONST NUMERO inválida: {raw!r}") from exc
        if isinstance(number, float) and not math.isfinite(number):
            raise SelfHostedIRError("CONST NUMERO precisa ser finita")
        return number
    if kind == "TEXTO":
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SelfHostedIRError(f"CONST TEXTO inválida: {exc}") from exc
        if not isinstance(value, str):
            raise SelfHostedIRError("CONST TEXTO precisa conter uma string JSON")
        return value
    if kind in {"LOGICO", "PALAVRA_CHAVE"}:
        if raw == "verdadeiro":
            return True
        if raw == "falso":
            return False
        raise SelfHostedIRError(f"CONST lógica inválida: {raw!r}")
    raise SelfHostedIRError(f"Tipo de constante não suportado: {kind}")


def _instruction_fields(
    fields: list[object],
    context: str,
    struct_schemas: dict[str, list[tuple[str, str]]] | None = None,
) -> IRInstruction:
    """Build a typed IR instruction directly from a record's fields."""
    if not fields or not isinstance(fields[0], str) or not fields[0]:
        raise SelfHostedIRError(f"{context}: opcode ausente ou inválido")
    opcode = fields[0]
    operands = fields[1:]

    if opcode == "CONST":
        if len(operands) != 2 or not isinstance(operands[0], str):
            raise SelfHostedIRError(f"{context}: CONST exige tipo e payload tipado")
        kind, value = operands
        if kind == "NULO":
            if value is not None:
                raise SelfHostedIRError(f"{context}: CONST NULO precisa ser null")
        elif kind == "NUMERO":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise SelfHostedIRError(f"{context}: CONST NUMERO precisa ser número JSON")
            if isinstance(value, float) and not math.isfinite(value):
                raise SelfHostedIRError(f"{context}: CONST NUMERO precisa ser finita")
        elif kind in {"LOGICO", "PALAVRA_CHAVE"}:
            if not isinstance(value, bool):
                raise SelfHostedIRError(f"{context}: CONST lógica precisa ser booleano JSON")
        elif kind == "TEXTO":
            if not isinstance(value, str):
                raise SelfHostedIRError(f"{context}: CONST TEXTO precisa ser string JSON")
        else:
            raise SelfHostedIRError(f"{context}: tipo de constante não suportado: {kind!r}")
        return IRInstruction("CONST", (value,))

    if opcode == "DECLARE":
        if len(operands) == 2:
            name = _required_text(operands[0], f"{context} DECLARE nome")
            type_name = _required_text(operands[1], f"{context} DECLARE tipo")
            return IRInstruction("DECLARE", (name, type_name, None))
        if len(operands) == 3:
            name = _required_text(operands[0], f"{context} DECLARE nome")
            if operands[1] != "lista":
                raise SelfHostedIRError(f"{context}: DECLARE com 3 operandos exige tipo lista")
            element_type = _required_text(operands[2], f"{context} DECLARE elemento")
            return IRInstruction("DECLARE", (name, "lista", element_type))
        raise SelfHostedIRError(f"{context}: DECLARE exige nome, tipo e elemento opcional")

    if opcode == "BUILD_STRUCT":
        if len(operands) != 2:
            raise SelfHostedIRError(f"{context}: BUILD_STRUCT exige nome e quantidade")
        name = _required_text(operands[0], f"{context} BUILD_STRUCT nome")
        count = _integer(operands[1], context)
        schema = (struct_schemas or {}).get(name)
        if schema is None:
            raise SelfHostedIRError(f"{context}: esquema não declarado para estrutura {name}")
        if len(schema) != count:
            raise SelfHostedIRError(
                f"{context}: construtor {name} declara {count} campo(s), esquema possui {len(schema)}"
            )
        return IRInstruction(opcode, (name, schema))

    if opcode == "BUILD_ARRAY":
        if len(operands) != 1:
            raise SelfHostedIRError(f"{context}: BUILD_ARRAY exige quantidade")
        return IRInstruction(opcode, (_integer(operands[0], context),))

    if opcode == "MAKE_TYPED_ARRAY":
        if len(operands) != 1:
            raise SelfHostedIRError(f"{context}: MAKE_TYPED_ARRAY exige tipo de elemento")
        return IRInstruction(opcode, (_required_text(operands[0], context),))

    if opcode in {"LOAD", "STORE", "GET_FIELD", "SET_FIELD"}:
        if len(operands) != 1:
            raise SelfHostedIRError(f"{context}: {opcode} exige um nome")
        return IRInstruction(opcode, (_required_text(operands[0], context),))

    if opcode in {"PRINT", "JUMP", "JUMP_IF_FALSE"}:
        if len(operands) != 1:
            raise SelfHostedIRError(f"{context}: {opcode} exige quantidade/destino")
        return IRInstruction(opcode, (_integer(operands[0], context),))

    if opcode == "CALL":
        if len(operands) != 2:
            raise SelfHostedIRError(f"{context}: CALL exige nome e quantidade")
        name = _required_text(operands[0], f"{context} CALL nome")
        return IRInstruction(opcode, (name, _integer(operands[1], context)))

    if opcode in _NO_OPERAND:
        if operands:
            raise SelfHostedIRError(f"{context}: {opcode} não aceita operandos")
        return IRInstruction(opcode)

    raise SelfHostedIRError(f"{context}: opcode não suportado: {opcode!r}")


def _records_to_program(records: list[list[object]], version: str) -> IRProgram:
    if (
        not records
        or not isinstance(records[0], list)
        or len(records[0]) != 2
        or records[0][0] != "GP-IR"
        or type(records[0][1]) is not int
        or records[0][1] != 1
    ):
        raise SelfHostedIRError("Cabeçalho GP-IR versão 1 ausente ou inválido")
    if any(not isinstance(record, list) or not record for record in records):
        raise SelfHostedIRError("Registro vazio no envelope GP-IR")

    main: list[IRInstruction] = []
    functions: dict[str, IRFunction] = {}
    struct_schemas: dict[str, list[tuple[str, str]]] = {}
    index = 1

    while index < len(records) and records[index][0] == "STRUCT":
        header = records[index]
        if len(header) != 3:
            raise SelfHostedIRError(f"Metadado STRUCT inválido: {header!r}")
        name = _required_text(header[1], "STRUCT nome")
        count = _integer(header[2], f"estrutura {name}")
        if name in struct_schemas:
            raise SelfHostedIRError(f"Estrutura duplicada no envelope: {name}")
        index += 1
        schema: list[tuple[str, str]] = []
        while index < len(records) and records[index][0] == "STRUCT_FIELD":
            field = records[index]
            if len(field) != 3:
                raise SelfHostedIRError(f"Campo inválido em {name}: {field!r}")
            field_type = _required_text(field[1], f"Campo de {name} tipo")
            field_name = _required_text(field[2], f"Campo de {name} nome")
            if any(existing_name == field_name for _, existing_name in schema):
                raise SelfHostedIRError(f"Campo duplicado em {name}: {field_name}")
            schema.append((field_name, field_type))
            index += 1
        if len(schema) != count:
            raise SelfHostedIRError(
                f"Estrutura {name} declara {count} campo(s), mas {len(schema)} foram recebidos"
            )
        struct_schemas[name] = schema

    while index < len(records):
        record = records[index]
        opcode = record[0] if isinstance(record[0], str) else ""
        if opcode != "FUNCTION":
            if opcode in {"PARAM", "CODE_BEGIN", "CODE_END"}:
                raise SelfHostedIRError(f"Metadado de função fora de seção: {record!r}")
            main.append(_instruction_fields(record, f"main[{len(main)}]", struct_schemas))
            index += 1
            continue

        if len(record) != 4:
            raise SelfHostedIRError(f"Cabeçalho de função inválido: {record!r}")
        name = _required_text(record[1], "FUNCTION nome")
        return_name = _required_text(record[2], f"FUNCTION {name} retorno")
        parameter_count = _integer(record[3], f"função {name}")
        if name in functions:
            raise SelfHostedIRError(f"Função duplicada no IR: {name}")
        index += 1

        parameters: list[tuple[str, str]] = []
        while index < len(records) and records[index][0] == "PARAM":
            parts = records[index]
            if len(parts) != 3:
                raise SelfHostedIRError(f"Parâmetro inválido em {name}: {parts!r}")
            parameters.append((
                _required_text(parts[1], f"Parâmetro {name} tipo"),
                _required_text(parts[2], f"Parâmetro {name} nome"),
            ))
            index += 1
        if len(parameters) != parameter_count:
            raise SelfHostedIRError(
                f"{name}: cabeçalho declara {parameter_count} parâmetro(s), "
                f"mas {len(parameters)} foram encontrados"
            )

        expected_begin = ["CODE_BEGIN", name]
        if index >= len(records) or records[index] != expected_begin:
            raise SelfHostedIRError(f"Marcador {expected_begin!r} ausente")
        index += 1

        code: list[IRInstruction] = []
        expected_end = ["CODE_END", name]
        while index < len(records) and records[index] != expected_end:
            opcode = records[index][0] if isinstance(records[index][0], str) else ""
            if opcode in {"FUNCTION", "PARAM", "CODE_BEGIN", "CODE_END"}:
                raise SelfHostedIRError(f"Seção de função aninhada ou malformada em {name}")
            code.append(_instruction_fields(records[index], f"{name}[{len(code)}]", struct_schemas))
            index += 1
        if index >= len(records):
            raise SelfHostedIRError(f"Marcador {expected_end!r} ausente")
        index += 1
        functions[name] = IRFunction(
            name=name,
            parameters=parameters,
            return_type=None if return_name == "vazio" else return_name,
            instructions=code,
        )

    program = IRProgram(version, main, functions)
    _validate_targets(program.instructions, "main")
    for name, function in functions.items():
        _validate_targets(function.instructions, name)
    return validate_ir(program)


def _legacy_record(line: str) -> list[object]:
    if not line:
        raise SelfHostedIRError("Linha vazia no envelope GP-IR")
    if line.startswith("CONST|"):
        parts = line.split("|", 2)
        if len(parts) != 3:
            raise SelfHostedIRError("CONST exige tipo e valor")
        return [parts[0], parts[1], _constant(parts[1], parts[2])]
    parts = line.split("|")
    numeric_fields = {
        "GP-IR": {1}, "STRUCT": {2}, "BUILD_STRUCT": {2},
        "BUILD_ARRAY": {1}, "PRINT": {1}, "JUMP": {1},
        "JUMP_IF_FALSE": {1}, "CALL": {2}, "FUNCTION": {3},
    }
    result: list[object] = [parts[0]]
    for field_index, value in enumerate(parts[1:], 1):
        if field_index in numeric_fields.get(parts[0], set()):
            result.append(_legacy_integer(value, parts[0]))
        else:
            result.append(value)
    return result


def textual_ir_to_program(records: Iterable[str], version: str = "0.4") -> IRProgram:
    """Read the legacy delimiter-based GP IR envelope for compatibility."""
    lines = [line.rstrip("\r\n") for line in records]
    if not lines or lines[0] != "GP-IR|1":
        raise SelfHostedIRError("Cabeçalho GP-IR|1 ausente ou inválido")
    return _records_to_program([_legacy_record(line) for line in lines], version)


def structured_ir_to_program(records: Iterable[list[object]], version: str = "0.4") -> IRProgram:
    """Build typed IR directly from JSON records without rebuilding text lines."""
    if isinstance(records, (str, bytes, dict)):
        raise SelfHostedIRError("IR estruturado precisa ser uma lista de registros")
    normalized: list[list[object]] = []
    try:
        for index, record in enumerate(records):
            if not isinstance(record, list) or not record:
                raise SelfHostedIRError(f"Registro estruturado {index} precisa ser uma lista não vazia")
            normalized.append(record)
    except TypeError as exc:
        raise SelfHostedIRError("IR estruturado não é iterável") from exc
    if not normalized:
        raise SelfHostedIRError("IR estruturado não contém registros")
    return _records_to_program(normalized, version)

def _validate_targets(code: list[IRInstruction], context: str) -> None:
    for index, instruction in enumerate(code):
        if instruction.opcode in {"JUMP", "JUMP_IF_FALSE"}:
            target = instruction.operands[0]
            if not 0 <= target <= len(code):
                raise SelfHostedIRError(
                    f"{context}[{index}]: destino {target} fora do bloco de {len(code)} instruções"
                )


def canonical_ir_to_program(document: dict[str, object]) -> IRProgram:
    """Hydrate the canonical GP-IR object emitted and sectioned by GP."""
    if not isinstance(document, dict) or document.get("format") != "GP-IR":
        raise SelfHostedIRError("Documento canônico GP-IR inválido")
    if type(document.get("ir_version")) is not int or document["ir_version"] != 1:
        raise SelfHostedIRError("Versão do documento canônico GP-IR não suportada")
    version = document.get("version")
    if not isinstance(version, str) or not version:
        raise SelfHostedIRError("Versão da linguagem ausente no GP-IR canônico")

    def block(raw: object, where: str) -> list[IRInstruction]:
        if not isinstance(raw, list):
            raise SelfHostedIRError(f"Bloco canônico {where} inválido")
        result = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict) or set(item) != {"op", "args"}:
                raise SelfHostedIRError(f"Instrução canônica {where}[{index}] inválida")
            opcode, operands = item["op"], item["args"]
            if not isinstance(opcode, str) or not isinstance(operands, list):
                raise SelfHostedIRError(f"Opcode/operandos canônicos inválidos em {where}[{index}]")
            if opcode == "BUILD_STRUCT" and len(operands) == 2 and isinstance(operands[1], list):
                operands = [operands[0], [tuple(field) if isinstance(field, list) else field for field in operands[1]]]
            result.append(IRInstruction(opcode, tuple(operands)))
        return result

    raw_functions = document.get("functions")
    if not isinstance(raw_functions, dict):
        raise SelfHostedIRError("Mapa de funções canônico inválido")
    functions = {}
    for name, raw in raw_functions.items():
        if not isinstance(name, str) or not name or not isinstance(raw, dict):
            raise SelfHostedIRError("Definição de função canônica inválida")
        if set(raw) != {"return_type", "parameters", "code"}:
            raise SelfHostedIRError(f"Campos canônicos inválidos na função {name}")
        params = raw["parameters"]
        if not isinstance(params, list) or any(not isinstance(x, list) or len(x) != 2 for x in params):
            raise SelfHostedIRError(f"Parâmetros canônicos inválidos na função {name}")
        functions[name] = IRFunction(name, [tuple(x) for x in params], raw["return_type"], block(raw["code"], name))
    return validate_ir(IRProgram(version, block(document.get("main"), "main"), functions, document["ir_version"]))
