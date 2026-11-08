"""Versioned compressed binary container for GP bytecode."""
from __future__ import annotations
import json
import math
import struct
import zlib
from pathlib import Path
from .ir import IRProgram, IR_VERSION, validate_ir, validate_canonical_ir
from .lower import ir_to_dict

MAGIC = "GABRIEL-GP-BYTECODE"
BINARY_MAGIC = b"GGPC"
BYTECODE_VERSION = 2
_HEADER = struct.Struct(">4sHII")  # magic, version, uncompressed size, CRC32
_MAX_PAYLOAD = 64 * 1024 * 1024
_MAX_COMPRESSED_PAYLOAD = _MAX_PAYLOAD * 2
_MAX_JSON_TOKENS = 2_000_000
_MAX_JSON_DEPTH = 512


def _encode_program_document(language_version: str, program_document: dict) -> bytes:
    payload = {
        "magic": MAGIC,
        "bytecode_version": BYTECODE_VERSION,
        "language_version": language_version,
        "program": program_document,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > _MAX_PAYLOAD:
        raise ValueError("Programa GP excede o tamanho máximo do bytecode")
    compressed = zlib.compress(raw, level=9)
    checksum = zlib.crc32(raw) & 0xFFFFFFFF
    return _HEADER.pack(BINARY_MAGIC, BYTECODE_VERSION, len(raw), checksum) + compressed


def encode(program: IRProgram) -> bytes:
    """Compatibility encoder for callers using the typed in-memory IR API."""
    validate_ir(program)
    return _encode_program_document(program.version, ir_to_dict(program))


def encode_canonical_ir(document: dict) -> bytes:
    """Encode canonical GP-IR JSON directly, without IRProgram/IRFunction objects.

    The document is validated in its JSON-native representation, then projected
    into the exact key ordering used by ir_to_dict so v2 output is byte-for-byte
    identical to encode(IRProgram) for equivalent programs.
    """
    validate_canonical_ir(document)

    def normalize_block(code):
        return [{"op": item["op"], "args": item["args"]} for item in code]

    normalized = {
        "format": "GP-IR",
        "ir_version": document["ir_version"],
        "version": document["version"],
        "main": normalize_block(document["main"]),
        "functions": {
            name: {
                "parameters": function["parameters"],
                "return_type": function["return_type"],
                "code": normalize_block(function["code"]),
            }
            for name, function in document["functions"].items()
        },
    }
    return _encode_program_document(document["version"], normalized)


def _reject_nonstandard_json_constant(value):
    raise ValueError(f"Constante JSON não padrão: {value}")


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Chave JSON duplicada: {key!r}")
        result[key] = value
    return result


def _validate_json_text(value):
    if chr(0) in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValueError("String JSON GP contém NUL ou surrogate Unicode isolado")


def _validate_json_limits(root):
    stack = [(root, 0)]
    token_count = 1
    while stack:
        value, depth = stack.pop()
        if depth > _MAX_JSON_DEPTH:
            raise ValueError("Profundidade máxima do JSON GP excedida")
        if isinstance(value, str):
            _validate_json_text(value)
        elif isinstance(value, dict):
            for key, child in value.items():
                _validate_json_text(key)
                token_count += 2  # token da chave e token do valor
                if depth + 1 > _MAX_JSON_DEPTH:
                    raise ValueError("Profundidade máxima do JSON GP excedida")
                stack.append((child, depth + 1))
        elif isinstance(value, list):
            token_count += len(value)
            if depth + 1 > _MAX_JSON_DEPTH and value:
                raise ValueError("Profundidade máxima do JSON GP excedida")
            for child in value:
                stack.append((child, depth + 1))
        if token_count > _MAX_JSON_TOKENS:
            raise ValueError("Limite de tokens JSON GP excedido")


def decode(data: bytes) -> dict:
    binary_version = None
    if data.startswith(BINARY_MAGIC):
        if len(data) < _HEADER.size:
            raise ValueError("Cabeçalho de bytecode GP truncado")
        magic, version, raw_size, checksum = _HEADER.unpack(data[:_HEADER.size])
        if magic != BINARY_MAGIC:
            raise ValueError("Assinatura binária GP inválida")
        if version != BYTECODE_VERSION:
            raise ValueError(f"Versão de bytecode não suportada: {version}")
        binary_version = version
        if raw_size < 1 or raw_size > _MAX_PAYLOAD:
            raise ValueError("Bytecode GP excede o limite de segurança")
        if len(data) > _MAX_COMPRESSED_PAYLOAD:
            raise ValueError("Arquivo comprimido GP excede o limite de segurança")
        try:
            inflater = zlib.decompressobj()
            raw = inflater.decompress(data[_HEADER.size:], raw_size + 1)
            if len(raw) > raw_size or inflater.unconsumed_tail:
                raise ValueError("Payload GP excede o tamanho declarado")
            raw += inflater.flush()
            if not inflater.eof or inflater.unused_data:
                raise ValueError("Payload GP truncado ou com dados extras")
        except zlib.error as exc:
            raise ValueError(f"Payload comprimido inválido: {exc}") from exc
        if len(raw) != raw_size:
            raise ValueError("Tamanho do bytecode GP não confere")
        if (zlib.crc32(raw) & 0xFFFFFFFF) != checksum:
            raise ValueError("Checksum do bytecode GP inválido")
    else:
        # Backward compatibility with experimental Core 0.3 JSON bytecode.
        if len(data) > _MAX_PAYLOAD:
            raise ValueError("Arquivo JSON GP excede o limite de segurança")
        raw = data
    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_nonstandard_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"Arquivo GP bytecode inválido: {exc}") from exc
    _validate_json_limits(payload)
    if not isinstance(payload, dict):
        raise ValueError("Cabeçalho de bytecode GP precisa ser um objeto JSON")
    if payload.get("magic") != MAGIC:
        raise ValueError("Assinatura de bytecode GP inválida")
    payload_version = payload.get("bytecode_version")
    if isinstance(payload_version, bool) or not isinstance(payload_version, int):
        raise ValueError(f"Versão de bytecode inválida: {payload_version!r}")
    if payload_version not in (1, BYTECODE_VERSION):
        raise ValueError(f"Versão de bytecode não suportada: {payload_version}")
    if binary_version is not None and payload_version != binary_version:
        raise ValueError("Versão interna do bytecode não confere com o cabeçalho binário")
    program = payload.get("program")
    if not isinstance(program, dict) or program.get("format") != "GP-IR":
        raise ValueError("Formato IR GP inválido")
    expected_program_keys = {"format", "version", "main", "functions"}
    if "ir_version" in program:
        expected_program_keys.add("ir_version")
    if set(program) != expected_program_keys:
        raise ValueError("Campos inesperados no envelope GP-IR")
    if not isinstance(program.get("main"), list) or not isinstance(program.get("functions"), dict):
        raise ValueError("Seções main/functions inválidas no bytecode GP")
    language_version = payload.get("language_version")
    if not isinstance(language_version, str) or not language_version:
        raise ValueError("Versão da linguagem ausente ou inválida no bytecode")
    if program.get("version") != language_version:
        raise ValueError("Versão da linguagem inconsistente no bytecode")
    ir_version = program.get("ir_version", 1)  # v2 fixtures predating explicit IR version are GP-IR v1.
    if type(ir_version) is not int or ir_version != IR_VERSION:
        raise ValueError(f"Versão GP-IR não suportada: {ir_version!r}")

    allowed = {
        "CONST": 1, "LOAD": 1, "DECLARE": 3, "STORE": 1, "POP": 0,
        "BUILD_ARRAY": 1, "MAKE_TYPED_ARRAY": 1, "BUILD_STRUCT": 2,
        "GET_FIELD": 1, "SET_FIELD": 1, "GET_INDEX": 0, "SET_INDEX": 0,
        "NEG": 0, "NOT": 0, "ADD": 0, "SUB": 0, "MUL": 0, "DIV": 0,
        "MOD": 0, "EQ": 0, "NE": 0, "GT": 0, "LT": 0, "GE": 0,
        "LE": 0, "AND": 0, "OR": 0, "PRINT": 1, "JUMP": 1,
        "JUMP_IF_FALSE": 1, "CALL": 2, "RETURN": 0,
    }

    def text_operand(value, context):
        if not isinstance(value, str) or not value:
            raise ValueError(f"Operando textual inválido: {context}")

    def validate_schema(schema, context):
        if not isinstance(schema, list):
            raise ValueError(f"Schema de estrutura inválido: {context}")
        names = set()
        for field_index, field in enumerate(schema):
            if not isinstance(field, list) or len(field) != 2:
                raise ValueError(f"Campo de estrutura inválido: {context}[{field_index}]")
            field_name, field_type = field
            text_operand(field_name, f"{context}[{field_index}] nome")
            text_operand(field_type, f"{context}[{field_index}] tipo")
            if field_name in names:
                raise ValueError(f"Campo de estrutura duplicado: {context}.{field_name}")
            names.add(field_name)

    def validate_code(code, label):
        if not isinstance(code, list) or len(code) > 2_000_000:
            raise ValueError(f"Bloco de instruções inválido: {label}")
        for index, instruction in enumerate(code):
            context = f"{label}[{index}]"
            if not isinstance(instruction, dict) or set(instruction) != {"op", "args"}:
                raise ValueError(f"Instrução inválida: {context}")
            op, args = instruction.get("op"), instruction.get("args")
            if not isinstance(op, str) or op not in allowed or not isinstance(args, list) or len(args) != allowed[op]:
                raise ValueError(f"Opcode/operandos inválidos: {context}")

            if op == "CONST":
                value = args[0]
                if value is not None and not isinstance(value, (str, bool, int, float)):
                    raise ValueError(f"Constante com tipo JSON inválido: {context}")
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError(f"Constante numérica não finita: {context}")
                if isinstance(value, int):
                    try:
                        finite = math.isfinite(float(value))
                    except OverflowError:
                        finite = False
                    if not finite:
                        raise ValueError(f"Constante numérica fora do intervalo: {context}")
            elif op in {"LOAD", "STORE", "GET_FIELD", "SET_FIELD", "MAKE_TYPED_ARRAY"}:
                text_operand(args[0], f"{context} {op}")
            elif op == "DECLARE":
                name, type_name, element_type = args
                text_operand(name, f"{context} DECLARE nome")
                text_operand(type_name, f"{context} DECLARE tipo")
                if type_name == "lista":
                    text_operand(element_type, f"{context} DECLARE tipo de elemento")
                elif element_type is not None:
                    raise ValueError(f"DECLARE não-lista não aceita tipo de elemento: {context}")
            elif op == "BUILD_STRUCT":
                text_operand(args[0], f"{context} BUILD_STRUCT nome")
                validate_schema(args[1], f"{context} BUILD_STRUCT schema")
            elif op in {"BUILD_ARRAY", "PRINT", "CALL", "JUMP", "JUMP_IF_FALSE"}:
                operand_index = 1 if op == "CALL" else 0
                value = args[operand_index]
                operand_name = "quantidade de argumentos" if op == "CALL" else "quantidade/destino"
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    if op in {"JUMP", "JUMP_IF_FALSE"}:
                        raise ValueError(f"Destino de salto inválido: {context}")
                    raise ValueError(f"{operand_name} inválida: {context}")
                if value > len(code):
                    if op in {"JUMP", "JUMP_IF_FALSE"}:
                        raise ValueError(f"Destino de salto inválido: {context}")
                    raise ValueError(f"{operand_name} inválida: {context}")
                if op == "CALL":
                    text_operand(args[0], f"{context} CALL nome")

    validate_code(program["main"], "main")
    for name, function in program["functions"].items():
        if (
            not isinstance(name, str) or not name
            or not isinstance(function, dict)
            or set(function) != {"parameters", "return_type", "code"}
        ):
            raise ValueError("Definição de função inválida")
        parameters = function.get("parameters")
        if not isinstance(parameters, list):
            raise ValueError(f"Parâmetros inválidos em {name}")
        parameter_names = set()
        for index, parameter in enumerate(parameters):
            if not isinstance(parameter, list) or len(parameter) != 2:
                raise ValueError(f"Parâmetro inválido em {name}[{index}]")
            parameter_type, parameter_name = parameter
            text_operand(parameter_type, f"{name}[{index}] tipo de parâmetro")
            text_operand(parameter_name, f"{name}[{index}] nome de parâmetro")
            if parameter_name in parameter_names:
                raise ValueError(f"Parâmetro duplicado em {name}: {parameter_name}")
            parameter_names.add(parameter_name)
        if "return_type" not in function:
            raise ValueError(f"Tipo de retorno ausente em {name}")
        return_type = function["return_type"]
        if return_type is not None:
            text_operand(return_type, f"{name} tipo de retorno")
        validate_code(function.get("code"), name)
    return payload


def write(program: IRProgram, path: str | Path):
    Path(path).write_bytes(encode(program))
