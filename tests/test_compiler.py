import contextlib
import io
import hashlib
import json
import random
import os
import shutil
import struct
import zlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from gp_compile import compile_source, compile_source_selfhosted, compile_source_selfhosted_document, encode_canonical_ir_native, write_bytecode_atomic
from gpcompiler.bytecode import decode, encode, encode_canonical_ir, MAGIC
from gpcompiler.ir import IRProgram
from gpcompiler.lower import Lowerer
from gpcompiler.vm import GPVirtualMachine, GPVMError


def _rewrite_binary_payload(bytecode, mutate):
    if not bytecode.startswith(b"GGPC") or len(bytecode) < 14:
        raise AssertionError("Bytecode binário GP esperado")
    magic, version, _, _ = struct.unpack(">4sHII", bytecode[:14])
    payload = json.loads(zlib.decompress(bytecode[14:]).decode("utf-8"))
    mutate(payload)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    header = struct.pack(">4sHII", magic, version, len(raw), zlib.crc32(raw) & 0xFFFFFFFF)
    return header + zlib.compress(raw, level=9)


def _rewrite_binary_program(bytecode, mutate):
    return _rewrite_binary_payload(bytecode, lambda payload: mutate(payload["program"]))


def _binary_with_trailing_compressed_bytes(bytecode):
    return bytecode + b"GP-TRAILING"


def _binary_with_duplicate_key(bytecode, key_marker):
    if not bytecode.startswith(b"GGPC") or len(bytecode) < 14:
        raise AssertionError("Bytecode binário GP esperado")
    magic, version, _, _ = struct.unpack(">4sHII", bytecode[:14])
    raw = zlib.decompress(bytecode[14:])
    if raw.count(key_marker) != 1:
        raise AssertionError("Marcador da chave JSON não encontrado unicamente")
    raw = raw.replace(key_marker, key_marker + b", " + key_marker, 1)
    header = struct.pack(">4sHII", magic, version, len(raw), zlib.crc32(raw) & 0xFFFFFFFF)
    return header + zlib.compress(raw, level=9)


def _binary_with_extra_json(bytecode, fragment):
    if not bytecode.startswith(b"GGPC") or len(bytecode) < 14:
        raise AssertionError("Bytecode binário GP esperado")
    magic, version, _, _ = struct.unpack(">4sHII", bytecode[:14])
    raw = zlib.decompress(bytecode[14:])
    if not raw.endswith(b"}"):
        raise AssertionError("Objeto JSON raiz esperado")
    raw = raw[:-1] + b', "extra":' + fragment + b'}'
    header = struct.pack(">4sHII", magic, version, len(raw), zlib.crc32(raw) & 0xFFFFFFFF)
    return header + zlib.compress(raw, level=9)


def _bytecode_with_malformed_jump(bytecode, target):
    def mutate(program):
        for instruction in program["main"]:
            if instruction.get("op") in {"JUMP", "JUMP_IF_FALSE"}:
                instruction["args"][0] = target
                return
        raise AssertionError("Programa de teste não contém salto")
    return _rewrite_binary_program(bytecode, mutate)


def _mutate_main_opcode(program, opcode, mutation):
    for instruction in program["main"]:
        if instruction.get("op") == opcode:
            mutation(instruction)
            return
    raise AssertionError(f"Programa de teste não contém {opcode}")


def _malformed_operand_cases():
    return [
        ("mostrar(42)", lambda p: _mutate_main_opcode(p, "CONST", lambda i: i["args"].__setitem__(0, {"bad": 1}))),
        ("numero x = 1; mostrar(x)", lambda p: _mutate_main_opcode(p, "LOAD", lambda i: i["args"].__setitem__(0, 42))),
        ("numero x = 1", lambda p: _mutate_main_opcode(p, "DECLARE", lambda i: i["args"].__setitem__(2, "numero"))),
        ("lista numero values = []", lambda p: _mutate_main_opcode(p, "MAKE_TYPED_ARRAY", lambda i: i["args"].__setitem__(0, 17))),
        ('''estrutura Pessoa { texto nome; } Pessoa p = Pessoa{nome: "Ada"}''', lambda p: _mutate_main_opcode(p, "BUILD_STRUCT", lambda i: i["args"][1][0].__setitem__(1, 42))),
        ('''estrutura Pessoa { texto nome; } Pessoa p = Pessoa{nome: "Ada"}''', lambda p: _mutate_main_opcode(p, "BUILD_STRUCT", lambda i: i["args"].__setitem__(0, 42))),
        ('''estrutura Pessoa { texto nome; numero idade; } Pessoa p = Pessoa{nome: "Ada", idade: 37}''', lambda p: _mutate_main_opcode(p, "BUILD_STRUCT", lambda i: i["args"][1][1].__setitem__(0, "nome"))),
        ("funcao dobro(numero n) -> numero { retornar n * 2 } mostrar(dobro(3))", lambda p: p["functions"]["dobro"]["parameters"][0].__setitem__(1, 42)),
        ("funcao dobro(numero n) -> numero { retornar n * 2 } mostrar(dobro(3))", lambda p: p["functions"]["dobro"]["parameters"][0].__setitem__(0, [])),
        ("funcao dobro(numero n) -> numero { retornar n * 2 } mostrar(dobro(3))", lambda p: p["functions"]["dobro"].__setitem__("return_type", [])),
        ("funcao dobro(numero n) -> numero { retornar n * 2 } mostrar(dobro(3))", lambda p: p["functions"]["dobro"].pop("return_type")),
        ("funcao somar(numero a, numero b) -> numero { retornar a + b } mostrar(somar(1, 2))", lambda p: _mutate_main_opcode(p, "CALL", lambda i: i["args"].__setitem__(1, True))),
        ("funcao somar(numero a, numero b) -> numero { retornar a + b } mostrar(somar(1, 2))", lambda p: p["functions"]["somar"]["parameters"][1].__setitem__(1, "a")),
    ]


NESTED_BACKPATCH_SOURCE = """
    funcao somar_com_controle(numero limite) -> numero {
        numero cursor = 0
        numero soma = 0
        enquanto (cursor < limite) {
            cursor = cursor + 1
            se (cursor == 2) { continuar }
            se (cursor == 5) { quebrar }
            soma = soma + cursor
        }
        retornar soma
    }
    numero outer = 0
    numero total = 0
    numero inner = 0
    enquanto (outer < 3) {
        outer = outer + 1
        inner = 0
        enquanto (inner < 5) {
            inner = inner + 1
            se (inner == 2) { continuar }
            senao { total = total + outer * inner }
            se (inner == 4) { quebrar }
        }
    }
    numero for_total = 0
    para (numero i = 0; i < 7; i = i + 1) {
        se (i == 2) { continuar }
        se (i == 5) { quebrar }
        se (i == 3) { for_total = for_total + i * 2 }
        senao { for_total = for_total + i }
    }
    mostrar(total, outer, for_total, somar_com_controle(8))
"""


class GPCompilerTests(unittest.TestCase):
    def test_atomic_bytecode_publish_replaces_complete_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "program.gbc"
            output.write_bytes(b"OLD-COMPLETE")
            write_bytecode_atomic(output, b"GGPC-NEW-COMPLETE")
            self.assertEqual(output.read_bytes(), b"GGPC-NEW-COMPLETE")
            self.assertEqual(
                sorted(path.name for path in Path(directory).iterdir()),
                ["program.gbc"],
            )

    def test_atomic_bytecode_publish_preserves_previous_file_on_replace_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "program.gbc"
            output.write_bytes(b"OLD-COMPLETE")
            with mock.patch("gp_compile.os.replace", side_effect=OSError("simulated replace failure")):
                with self.assertRaisesRegex(ValueError, "publicar bytecode atomicamente"):
                    write_bytecode_atomic(output, b"GGPC-NEW-COMPLETE")
            self.assertEqual(output.read_bytes(), b"OLD-COMPLETE")
            self.assertEqual(
                sorted(path.name for path in Path(directory).iterdir()),
                ["program.gbc"],
            )

    def test_atomic_bytecode_publish_rejects_empty_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "bytes não vazios"):
                write_bytecode_atomic(Path(directory) / "empty.gbc", b"")

    def compile_and_run(self, source, source_path=None):
        _, _, bytecode = compile_source(source, source_path=source_path)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(bytecode)
        return output.getvalue().strip().splitlines(), bytecode

    def test_lowerer_backpatch_rejects_invalid_indices_targets_and_opcodes(self):
        lowerer = Lowerer()
        with self.assertRaisesRegex(ValueError, "Índice de backpatch inválido"):
            lowerer.patch(0, 0)
        jump_index = lowerer.emit("JUMP", -1)
        with self.assertRaisesRegex(ValueError, "Destino de backpatch inválido"):
            lowerer.patch(jump_index, -1)
        with self.assertRaisesRegex(ValueError, "Destino de backpatch inválido"):
            lowerer.patch(jump_index, True)
        lowerer.patch(jump_index, len(lowerer.code))
        self.assertEqual(lowerer.code[jump_index].operands, (1,))
        lowerer.emit("CONST", 42)
        with self.assertRaisesRegex(ValueError, "não aceita backpatch"):
            lowerer.patch(1, 1)

    def test_host_source_input_is_explicit_bounded_and_per_execution(self):
        source = "mostrar(entrada_fonte())"
        _, _, bytecode = compile_source(source)
        vm = GPVirtualMachine()
        for host_source in ("Olá, GP\nsegunda linha", "fonte seguinte"):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                vm.run_bytes(bytecode, host_source=host_source)
            self.assertEqual(output.getvalue(), host_source + "\n")
        with self.assertRaisesRegex(GPVMError, "host não forneceu"):
            vm.run_bytes(bytecode)
        with self.assertRaisesRegex(GPVMError, "16 MiB"):
            vm.run_bytes(bytecode, host_source="x" * (16 * 1024 * 1024 + 1))
        with self.assertRaisesRegex(GPVMError, "Unicode inválido"):
            vm.run_bytes(bytecode, host_source="\ud800")

    def test_python_vm_cli_accepts_explicit_host_source_file(self):
        source = "mostrar(entrada_fonte())"
        _, _, bytecode = compile_source(source)
        bytecode_path = Path(tempfile.gettempdir()) / "gp-host-input-cli.gbc"
        input_path = Path(tempfile.gettempdir()) / "gp-host-input-cli.txt"
        bytecode_path.write_bytes(bytecode)
        input_path.write_text("texto vindo do host", encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1] / "gp_vm.py"),
                 str(bytecode_path), "--source-input", str(input_path)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "texto vindo do host\n")
        finally:
            bytecode_path.unlink(missing_ok=True)
            input_path.unlink(missing_ok=True)

    def test_host_source_input_rejects_arguments(self):
        with self.assertRaisesRegex(ValueError, "entrada_fonte\\(\\) não aceita argumentos"):
            compile_source('mostrar(entrada_fonte("não permitido"))')

    def test_compile_nested_loop_backpatch_targets(self):
        output, _ = self.compile_and_run(NESTED_BACKPATCH_SOURCE)
        self.assertEqual(output, ["48 3 11 8"])

    def test_bytecode_rejects_malformed_operand_schemas(self):
        for index, (source, mutation) in enumerate(_malformed_operand_cases()):
            with self.subTest(case=index):
                _, _, bytecode = compile_source(source)
                corrupt = _rewrite_binary_program(bytecode, mutation)
                with self.assertRaises(ValueError):
                    decode(corrupt)

    def test_bytecode_rejects_non_integer_jump_destinations(self):
        _, _, bytecode = compile_source("se (verdadeiro) { mostrar(1) }")
        for malformed in (True, False, 0.0, 1.0, 1e0):
            with self.subTest(target=malformed):
                corrupt = _bytecode_with_malformed_jump(bytecode, malformed)
                with self.assertRaisesRegex(ValueError, "Destino de salto inválido"):
                    decode(corrupt)

    def test_compile_arithmetic_and_print(self):
        output, _ = self.compile_and_run("""
            numero a = 20
            numero b = 22
            mostrar("Resposta:", a + b)
        """)
        self.assertEqual(output, ["Resposta: 42"])

    def test_self_hosted_backend_compiles_and_runs(self):
        source = """
            funcao fatorial(numero n) -> numero {
                se (n <= 1) { retornar 1 }
                senao { retornar n * fatorial(n - 1) }
            }
            mostrar(fatorial(6))
        """
        program = compile_source_selfhosted(source)
        data = encode(program)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(data)
        self.assertEqual(output.getvalue().strip(), "720")

    def test_compile_function_and_recursion(self):
        output, _ = self.compile_and_run("""
            funcao fatorial(numero n) -> numero {
                se (n <= 1) { retornar 1 }
                retornar n * fatorial(n - 1)
            }
            mostrar(fatorial(6))
        """)
        self.assertEqual(output, ["720"])

    def test_compile_for_and_while(self):
        output, _ = self.compile_and_run("""
            numero total = 0
            para (numero i = 1; i <= 5; i = i + 1) {
                total = total + i
            }
            numero n = 0
            enquanto (n < 2) { n = n + 1 }
            mostrar(total, n)
        """)
        self.assertEqual(output, ["15 2"])

    def test_compile_break_continue(self):
        output, _ = self.compile_and_run("""
            numero total = 0
            para (numero i = 0; i < 7; i = i + 1) {
                se (i == 1) { continuar }
                se (i == 5) { quebrar }
                total = total + i
            }
            mostrar(total)
        """)
        self.assertEqual(output, ["9"])

    def test_compile_builtins(self):
        output, _ = self.compile_and_run("""
            lista texto partes = ["Ga", "briel"]
            mostrar(tamanho("Gabriel"), unir_textos(partes))
        """)
        self.assertEqual(output, ["7 Gabriel"])

    def test_python_vm_unir_textos_rejects_non_text_items(self):
        _, _, bytecode = compile_source("""
            lista numero partes = [1, 2]
            mostrar(unir_textos(partes))
        """)
        with self.assertRaisesRegex(GPVMError, "todos os itens sejam texto"):
            GPVirtualMachine().run_bytes(bytecode)

    def test_self_hosted_backend_compiles_and_runs_unir_textos(self):
        source = """
            lista texto partes = ["Auto", "hospedado", " GP"]
            mostrar(unir_textos(partes))
        """
        program = compile_source_selfhosted(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue().strip(), "Autohospedado GP")

    def test_semantic_type_error_rejected(self):
        with self.assertRaisesRegex(ValueError, "Tipo de idade"):
            compile_source('numero idade = "vinte"')

    def test_unknown_variable_rejected(self):
        with self.assertRaisesRegex(ValueError, "não declarado"):
            compile_source('mostrar(nao_existe)')

    def test_bytecode_rejects_invalid_json_string_escapes(self):
        _, _, bytecode = compile_source("mostrar(42)")
        invalid_cases = (
            b'"' + bytes([92]) + b'q"',
            b'"' + bytes([92]) + b'u12XZ"',
            b'"' + bytes([1]) + b'"',
            b'"' + bytes([92]) + b'u0000"',
            b'"' + bytes([92]) + b'uD800"',
            b'"' + bytes([92]) + b'uDC00"',
            b'"' + bytes([92]) + b'uD800' + bytes([92]) + b'u0041"',
        )
        for invalid in invalid_cases:
            with self.subTest(invalid=invalid):
                corrupt = _binary_with_extra_json(bytecode, invalid)
                with self.assertRaises(ValueError):
                    decode(corrupt)

    def test_bytecode_rejects_trailing_compressed_bytes(self):
        _, _, bytecode = compile_source("mostrar(42)")
        corrupt = _binary_with_trailing_compressed_bytes(bytecode)
        with self.assertRaisesRegex(ValueError, "dados extras"):
            decode(corrupt)

    def test_bytecode_rejects_duplicate_json_keys(self):
        _, _, bytecode = compile_source("mostrar(42)")
        corrupt = _binary_with_duplicate_key(bytecode, b'"format":"GP-IR"')
        with self.assertRaisesRegex(ValueError, "Chave JSON duplicada"):
            decode(corrupt)

    def test_bytecode_rejects_excessive_json_depth(self):
        _, _, bytecode = compile_source("mostrar(42)")
        nested = b"[" * 520 + b"0" + b"]" * 520
        corrupt = _binary_with_extra_json(bytecode, nested)
        with self.assertRaisesRegex(ValueError, "Profundidade máxima"):
            decode(corrupt)

    def test_bytecode_rejects_nonstandard_json_constants(self):
        _, _, bytecode = compile_source("mostrar(42)")
        corrupt = _binary_with_extra_json(bytecode, b"NaN")
        with self.assertRaisesRegex(ValueError, "Constante JSON não padrão"):
            decode(corrupt)

    def test_bytecode_rejects_non_object_json_roots(self):
        for raw in (b"[]", b"null", b"true", b"42", b'"texto"'):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, "objeto JSON"):
                    decode(raw)

    def test_bytecode_rejects_non_finite_json_constants(self):
        _, _, bytecode = compile_source("mostrar(42)")
        corrupt = _rewrite_binary_program(
            bytecode,
            lambda program: _mutate_main_opcode(
                program, "CONST", lambda instruction: instruction["args"].__setitem__(0, float("nan"))
            ),
        )
        with self.assertRaisesRegex(ValueError, "Constante JSON não padrão|Constante numérica não finita"):
            decode(corrupt)

    def test_bytecode_rejects_mismatched_language_version(self):
        _, _, bytecode = compile_source("mostrar(42)")
        corrupt = _rewrite_binary_payload(bytecode, lambda payload: payload.__setitem__("language_version", "9.9"))
        with self.assertRaisesRegex(ValueError, "Versão da linguagem inconsistente"):
            decode(corrupt)

    def test_bytecode_rejects_boolean_version(self):
        payload = {
            "magic": MAGIC,
            "bytecode_version": True,
            "language_version": "0.4",
            "program": {
                "format": "GP-IR",
                "version": "0.4",
                "main": [],
                "functions": {},
            },
        }
        with self.assertRaisesRegex(ValueError, "Versão de bytecode inválida"):
            decode(json.dumps(payload).encode("utf-8"))

    def test_binary_bytecode_rejects_internal_version_mismatch(self):
        _, _, bytecode = compile_source("mostrar(42)")
        corrupt = _rewrite_binary_payload(bytecode, lambda payload: payload.update(bytecode_version=1))
        with self.assertRaisesRegex(ValueError, "não confere com o cabeçalho"):
            decode(corrupt)

    def test_bytecode_binary_round_trip(self):
        _, ir, data = compile_source('mostrar(42)')
        self.assertTrue(data.startswith(b"GGPC"))
        payload = decode(data)
        self.assertEqual(payload["magic"], MAGIC)
        self.assertEqual(payload["bytecode_version"], 2)
        self.assertEqual(payload["program"]["format"], "GP-IR")
        self.assertEqual(decode(encode(ir))["bytecode_version"], 2)

    def test_legacy_json_bytecode_is_still_readable(self):
        _, _, data = compile_source('mostrar(42)')
        payload = decode(data)
        payload["bytecode_version"] = 1
        legacy = (json.dumps(payload, separators=(",", ":")) + "\n").encode()
        self.assertEqual(decode(legacy)["bytecode_version"], 1)

    def test_binary_bytecode_rejects_decompression_size_overflow(self):
        import struct
        _, _, data = compile_source('mostrar("payload")')
        header = struct.Struct(">4sHII")
        compressed = data[header.size:]
        forged = header.pack(b"GGPC", 2, 1, 0) + compressed
        with self.assertRaisesRegex(ValueError, "excede o tamanho declarado"):
            decode(forged)

    def test_corrupt_binary_bytecode_is_rejected(self):
        _, _, data = compile_source('mostrar(42)')
        damaged = data[:-1] + bytes([data[-1] ^ 0xFF])
        with self.assertRaises(ValueError):
            decode(damaged)

    def test_semantic_diagnostic_has_line_and_column(self):
        with self.assertRaisesRegex(ValueError, r"linha 2, coluna 12: Identificador não declarado"):
            compile_source("numero x = 1;\nnumero y = ausente")

    def test_semantic_diagnostic_includes_source_path(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "app.gp"
            with self.assertRaisesRegex(ValueError, r"app\.gp: linha 2, coluna 12"):
                compile_source("numero x = 1;\nnumero y = ausente", source_path=source_path)

    def test_syntax_diagnostic_has_line_and_column(self):
        from gp import GPError
        with self.assertRaisesRegex(GPError, r"linha 2, coluna"):
            compile_source("numero x = 1;\nmostrar(x + )")

    def test_bytecode_rejects_unknown_opcode(self):
        _, _, data = compile_source("mostrar(42)")
        payload = decode(data)
        payload["program"]["main"][0]["op"] = "EXECUTE_SHELL"
        legacy = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        with self.assertRaisesRegex(ValueError, "Opcode/operandos inválidos"):
            decode(legacy)

    def test_gp_self_hosted_lexer_returns_lexemes(self):
        project = Path(__file__).resolve().parents[1]
        source_path = project / "exemplos" / "lexer_demo.gp"
        source = source_path.read_text(encoding="utf-8")
        _, _, data = compile_source(source, source_path=source_path)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(data)
        self.assertIn("Quantidade: 11", output.getvalue())
        self.assertIn("'numero'", output.getvalue())
        self.assertIn("'mostrar'", output.getvalue())
        self.assertIn("==", output.getvalue())
        self.assertIn("2.5", output.getvalue())
        self.assertIn("PALAVRA_CHAVE:numero", output.getvalue())
        self.assertIn("IDENTIFICADOR:total", output.getvalue())
        self.assertIn("NUMERO:42", output.getvalue())
        self.assertIn("DELIMITADOR:;", output.getvalue())
        self.assertIn("Classificacao: DELIMITADOR OPERADOR NUMERO INVALIDO INVALIDO", output.getvalue())

    def test_gp_self_hosted_semantic_symbol_table(self):
        source_path = Path(__file__).resolve().parents[1] / "linguagem" / "semantica_gp.gp"
        source = source_path.read_text(encoding="utf-8")
        output, _ = self.compile_and_run(source, source_path=source_path)
        self.assertIn("Declaracao global: True", output)
        self.assertIn("Duplicata global rejeitada: True", output)
        self.assertIn("Sombreamento local permitido: True", output)
        self.assertIn("Variavel local: texto", output)
        self.assertIn("Heranca de escopo: texto", output)
        self.assertIn("Tipo global: numero", output)
        self.assertIn("Desconhecido: True", output)
        self.assertIn("Total de simbolos: 3", output)

    def test_gp_self_hosted_parser_accepts_and_rejects_expressions(self):
        project = Path(__file__).resolve().parents[1]
        source_path = project / "linguagem" / "parser_gp.gp"
        source = source_path.read_text(encoding="utf-8")
        _, _, data = compile_source(source, source_path=source_path)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine(max_steps=5_000_000).run_bytes(data)
        rendered = output.getvalue()
        self.assertIn("Parser GP valido: True", rendered)
        self.assertIn("Parser GP rejeita erro: True", rendered)
        self.assertIn("Expressao invalida", rendered)
        self.assertIn("AST raiz: PROGRAMA| 3", rendered)
        self.assertIn("AST primeiro comando: DECLARACAO|numero|total 1", rendered)
        self.assertIn("Linha AST declaracao: 1", rendered)
        self.assertIn("Coluna AST declaracao:", rendered)
        self.assertIn("Parser GP aceita se/senao: True", rendered)
        self.assertIn("AST condicional: SE|senao 3", rendered)
        self.assertIn("AST bloco entao: BLOCO| 2", rendered)
        self.assertIn("Parser GP rejeita bloco incompleto: True", rendered)
        self.assertIn("Parser GP aceita enquanto aninhado: True", rendered)
        self.assertIn("AST enquanto: ENQUANTO| 2", rendered)
        self.assertIn("AST corpo enquanto: BLOCO| 2", rendered)
        self.assertIn("Parser GP aceita para: True", rendered)
        self.assertIn("AST para: PARA| 4", rendered)
        self.assertIn("Parser GP aceita funcao/retornar: True", rendered)
        self.assertIn("AST funcao: FUNCAO|somar -> numero 3", rendered)
        self.assertIn("AST parametro: PARAMETRO|numero|a", rendered)
        self.assertIn("AST retorno: RETORNAR|", rendered)
        self.assertIn("Parser GP aceita estrutura: True", rendered)
        self.assertIn("AST estrutura: ESTRUTURA|Pessoa 3", rendered)
        self.assertIn("AST campo declarado: CAMPO_DECLARADO|texto|nome", rendered)
        self.assertIn("Parser GP aceita quebrar/continuar: True", rendered)
        self.assertIn("AST quebrar: QUEBRAR|", rendered)
        self.assertIn("AST continuar: CONTINUAR|", rendered)
        self.assertIn("Parser GP rejeita quebrar fora de laco: True", rendered)
        self.assertIn("Parser GP rejeita continuar fora de laco: True", rendered)
        self.assertIn("Parser GP rejeita retornar fora de funcao: True", rendered)
        self.assertIn("Semantica GP aceita programa tipado: True", rendered)
        self.assertIn("Semantica GP rejeita tipo incorreto: True", rendered)
        self.assertIn("Semantica GP rejeita nome desconhecido: True", rendered)
        self.assertIn("Semantica GP rejeita duplicata: True", rendered)
        self.assertIn("Semantica GP permite sombra local: True", rendered)
        self.assertIn("Semantica GP valida parametros e retorno: True", rendered)
        self.assertIn("Semantica GP rejeita argumento incorreto: True", rendered)
        self.assertIn("Semantica GP rejeita retorno incorreto: True", rendered)
        self.assertIn("Semantica GP aceita chamada antes da funcao: True", rendered)
        self.assertIn("Semantica GP rejeita quantidade incorreta: True", rendered)
        self.assertIn("Semantica GP rejeita parametro duplicado: True", rendered)
        self.assertIn("Semantica GP valida para, enquanto e controle de laco: True", rendered)
        self.assertIn("Semantica GP rejeita condicao de laco nao logica: True", rendered)
        self.assertIn("Semantica GP rejeita condicao de para nao logica: True", rendered)
        self.assertIn("Semantica GP valida listas tipadas e operacoes: True", rendered)
        self.assertIn("Semantica GP rejeita lista heterogenea: True", rendered)
        self.assertIn("Semantica GP rejeita elemento de lista incorreto: True", rendered)
        self.assertIn("Semantica GP rejeita indice nao numerico: True", rendered)
        self.assertIn("Semantica GP valida atribuicao por indice: True", rendered)
        self.assertIn("Semantica GP rejeita atribuicao de tipo incorreto na lista: True", rendered)
        self.assertIn("Semantica GP rejeita indice invalido na atribuicao: True", rendered)
        self.assertIn("Semantica GP valida estruturas, construtores e campos: True", rendered)
        self.assertIn("Semantica GP rejeita campo inexistente: True", rendered)
        self.assertIn("Semantica GP rejeita tipo incorreto no construtor: True", rendered)
        self.assertIn("Semantica GP rejeita atribuicao de tipo incorreto em campo: True", rendered)
        self.assertIn("Semantica GP rejeita quantidade incorreta no construtor: True", rendered)
        self.assertIn("Semantica GP valida estruturas aninhadas: True", rendered)
        self.assertIn("Semantica GP valida estrutura em parametro e retorno: True", rendered)
        self.assertIn("Semantica GP rejeita tipo desconhecido em parametro: True", rendered)
        self.assertIn("Semantica GP rejeita tipo desconhecido em retorno: True", rendered)
        self.assertIn("Semantica GP rejeita estrutura duplicada: True", rendered)
        self.assertIn("Semantica GP rejeita campo duplicado: True", rendered)
        self.assertIn("Semantica GP rejeita tipo de campo desconhecido: True", rendered)
        self.assertIn("Semantica GP rejeita tipo de variavel desconhecido: True", rendered)
        self.assertIn("Semantica GP aceita retorno em todos os ramos: True", rendered)
        self.assertIn("Semantica GP rejeita caminho sem retorno: True", rendered)
        self.assertIn("Semantica GP nao presume retorno dentro de laco: True", rendered)
        self.assertIn("Gerador GP produz IR para declaracao, expressao, saida e atribuicao: True", rendered)
        self.assertIn("Gerador GP produz IR para se, senao, enquanto e para: True", rendered)
        self.assertIn('IR-NUM: ["JUMP_IF_FALSE",11]', rendered)
        self.assertIn('IR-NUM: ["JUMP",13]', rendered)
        self.assertIn('IR-NUM: ["JUMP_IF_FALSE",22]', rendered)
        self.assertIn('IR-NUM: ["JUMP_IF_FALSE",37]', rendered)
        self.assertIn('IR-NUM: ["JUMP",24]', rendered)
        self.assertNotIn('IR-NUM: ["LABEL"', rendered)
        self.assertIn("Teste IR rejeita salto sem destino: True", rendered)
        self.assertIn("Teste IR rejeita rotulo duplicado: True", rendered)
        self.assertIn("Teste IR rejeita rotulo vazio: True", rendered)
        self.assertIn("Gerador GP produz secoes de funcao, parametros, CALL e RETURN: True", rendered)
        self.assertIn('IR-FN: ["CALL","somar",2]', rendered)
        self.assertIn('IR-FN: ["FUNCTION","somar","numero",2]', rendered)
        self.assertIn('IR-FN: ["PARAM","numero","a"]', rendered)
        self.assertIn('IR-FN: ["PARAM","numero","b"]', rendered)
        self.assertIn('IR-FN: ["CODE_BEGIN","somar"]', rendered)
        self.assertIn('IR-FN: ["LOAD","a"]', rendered)
        self.assertIn('IR-FN: ["LOAD","b"]', rendered)
        self.assertIn('IR-FN: ["ADD"]', rendered)
        self.assertIn('IR-FN: ["RETURN"]', rendered)
        self.assertIn('IR-FN: ["CODE_END","somar"]', rendered)
        self.assertIn("Gerador GP produz IR para funcao recursiva com fluxo de controle: True", rendered)
        self.assertIn('IR-REC: ["FUNCTION","fatorial","numero",1]', rendered)
        self.assertIn('IR-REC: ["PARAM","numero","n"]', rendered)
        self.assertIn('IR-REC: ["CALL","fatorial",1]', rendered)
        self.assertIn('IR-REC: ["JUMP_IF_FALSE",', rendered)
        self.assertIn('IR-REC: ["JUMP",', rendered)
        self.assertIn('IR: ["GP-IR",1]', rendered)
        self.assertIn('IR: ["CONST","NUMERO",10]', rendered)
        self.assertIn('IR: ["MUL"]', rendered)
        self.assertIn('IR: ["ADD"]', rendered)
        self.assertIn('IR: ["DECLARE","total","numero"]', rendered)
        self.assertIn('IR: ["PRINT",2]', rendered)
        self.assertIn('IR: ["STORE","total"]', rendered)
        self.assertIn("Semantica GP valida atribuicao por indice: True", rendered)
        self.assertIn("Semantica GP rejeita atribuicao de tipo incorreto na lista: True", rendered)
        self.assertIn("Semantica GP rejeita indice invalido na atribuicao: True", rendered)
        self.assertIn("AST expressao declaracao: BINARIO|+ 2", rendered)
        self.assertIn("AST precedencia: BINARIO|*", rendered)
        self.assertIn("AST chamada: CHAMADA|somar 2", rendered)
        self.assertIn("AST array: ARRAY| 2", rendered)
        self.assertIn("AST logico: BINARIO|||", rendered)
        self.assertIn("AST campo: CAMPO|nome", rendered)
        self.assertIn("AST indice: INDICE|[]", rendered)

    def test_bad_bytecode_signature(self):
        with self.assertRaisesRegex(ValueError, "Assinatura"):
            decode(b'{"magic":"not-gp"}')

    def test_vm_step_limit(self):
        _, _, data = compile_source('enquanto (verdadeiro) {}')
        with self.assertRaisesRegex(GPVMError, "Limite de instruções"):
            GPVirtualMachine(max_steps=50).run_bytes(data)

    def test_typed_array_declaration_copies_collection_result(self):
        source = """
            lista numero original = [2, 3]
            lista numero expanded = adicionar(original, 4)
            numero removed = remover(expanded, 0)
            mostrar(original[1], tamanho(original), tamanho(expanded), removed)
        """
        output, _ = self.compile_and_run(source)
        self.assertEqual(output, ["3 3 2 2"])

    def test_compile_arrays_and_indexing(self):
        output, _ = self.compile_and_run("""
            lista numero valores = [10, 20, 30]
            valores[1] = 25
            adicionar(valores, 40)
            numero total = 0
            para (numero i = 0; i < tamanho(valores); i = i + 1) {
                total = total + valores[i]
            }
            mostrar(tamanho(valores), total, remover(valores, 0), valores[0])
        """)
        self.assertEqual(output, ["4 105 10 25"])

    def test_typed_array_rejects_invalid_mutation(self):
        _, _, data = compile_source("""
            lista numero valores = [1, 2]
            valores[0] = "texto"
        """)
        with self.assertRaisesRegex(GPVMError, "Array exige elemento numero"):
            GPVirtualMachine().run_bytes(data)

    def test_typed_array_rejects_wrong_initial_element(self):
        with self.assertRaisesRegex(ValueError, "Elemento de valores"):
            compile_source('lista numero valores = [1, "dois"]')

    def test_function_local_can_shadow_global(self):
        output, _ = self.compile_and_run("""
            numero valor = 10
            funcao calcular() -> numero {
                numero valor = 20
                retornar valor
            }
            mostrar(calcular(), valor)
        """)
        self.assertEqual(output, ["20 10"])

    def test_struct_construction_access_and_assignment(self):
        output, _ = self.compile_and_run("""
            estrutura Pessoa {
                texto nome;
                numero idade;
            }
            Pessoa p = Pessoa{nome: "Ada", idade: 37}
            p.idade = 38
            mostrar(p.nome, p.idade)
        """)
        self.assertEqual(output, ["Ada 38"])

    def test_struct_field_type_is_checked(self):
        with self.assertRaisesRegex(ValueError, "Tipo do campo idade"):
            compile_source("""
                estrutura Pessoa { numero idade; }
                Pessoa p = Pessoa{idade: "trinta"}
            """)

    def test_unknown_struct_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Campo não declarado"):
            compile_source("""
                estrutura Pessoa { numero idade; }
                Pessoa p = Pessoa{nome: "Ada"}
            """)

    def test_self_hosted_backend_expands_local_module_namespace(self):
        source_path = Path("exemplos/modulos/aplicacao.gp").resolve()
        source = source_path.read_text(encoding="utf-8")
        program = compile_source_selfhosted(source, source_path=source_path)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue().strip(), "Resultado do módulo: 42")
        self.assertIn("__gp_namespace_math__somar", program.functions)

    def test_self_hosted_backend_expands_module_internal_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "calc.gp").write_text("""
                programa "Biblioteca de cálculo"
                funcao dobro(numero n) -> numero { retornar n * 2 }
                funcao quadruplicar(numero n) -> numero { retornar dobro(dobro(n)) }
            """, encoding="utf-8")
            source = 'programa "Modulo self-hosted"\nusar "calc.gp" como c\nmostrar(c.quadruplicar(5))'
            program = compile_source_selfhosted(source, source_path=root / "main.gp")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                GPVirtualMachine().run_bytes(encode(program))
            self.assertEqual(output.getvalue().strip(), "20")
            self.assertEqual(
                set(program.functions),
                {"__gp_namespace_c__dobro", "__gp_namespace_c__quadruplicar"},
            )

    def test_reference_and_self_hosted_backends_expand_nested_modules_equally(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "leaf.gp").write_text(
                "funcao dobrar(numero n) -> numero { retornar n * 2 }",
                encoding="utf-8",
            )
            (root / "base.gp").write_text(
                'usar "leaf.gp" como core\n'
                "funcao quatro(numero n) -> numero { retornar core.dobrar(core.dobrar(n)) }",
                encoding="utf-8",
            )
            source_path = root / "main.gp"
            source = 'usar "base.gp" como base\nmostrar(base.quatro(5))'
            _, _, reference_bytecode = compile_source(source, source_path=source_path)
            self_hosted_program = compile_source_selfhosted(
                source, source_path=source_path,
            )
            self_hosted_bytecode = encode(self_hosted_program)
            reference_output = io.StringIO()
            native_frontend_output = io.StringIO()
            with contextlib.redirect_stdout(reference_output):
                GPVirtualMachine().run_bytes(reference_bytecode)
            with contextlib.redirect_stdout(native_frontend_output):
                GPVirtualMachine().run_bytes(self_hosted_bytecode)
            self.assertEqual(reference_output.getvalue(), "20\n")
            self.assertEqual(native_frontend_output.getvalue(), reference_output.getvalue())

    def test_reference_backend_rejects_cyclic_module_imports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.gp").write_text(
                'usar "b.gp" como b\nfuncao a() -> numero { retornar b.b() }',
                encoding="utf-8",
            )
            (root / "b.gp").write_text(
                'usar "a.gp" como a\nfuncao b() -> numero { retornar 2 }',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Ciclo de importação GP detectado"):
                compile_source(
                    'usar "a.gp" como a\nmostrar(a.a())',
                    source_path=root / "main.gp",
                )

    def test_self_hosted_backend_expands_nested_local_modules(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "leaf.gp").write_text(
                "funcao dobrar(numero n) -> numero { retornar n * 2 }",
                encoding="utf-8",
            )
            (root / "base.gp").write_text("""
                programa "Módulo base"
                usar "leaf.gp" como core
                funcao quatro(numero n) -> numero {
                    retornar core.dobrar(core.dobrar(n))
                }
            """, encoding="utf-8")
            source = """
                programa "Aplicação com módulos aninhados"
                usar "base.gp" como base
                mostrar(base.quatro(5))
            """
            program = compile_source_selfhosted(
                source, source_path=root / "main.gp",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                GPVirtualMachine().run_bytes(encode(program))
            self.assertEqual(output.getvalue().strip(), "20")
            self.assertIn("__gp_namespace_base__quatro", program.functions)
            self.assertIn("__gp_namespace_base__core__dobrar", program.functions)

    def test_self_hosted_backend_rejects_cyclic_module_imports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.gp").write_text(
                'usar "b.gp" como b\nfuncao a() -> numero { retornar b.b() }',
                encoding="utf-8",
            )
            (root / "b.gp").write_text(
                'usar "a.gp" como a\nfuncao b() -> numero { retornar 2 }',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Ciclo de importação GP detectado"):
                compile_source_selfhosted(
                    'usar "a.gp" como a\nmostrar(a.a())',
                    source_path=root / "main.gp",
                )

    def test_self_hosted_backend_rejects_duplicate_nested_module_alias(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "leaf.gp").write_text(
                "funcao valor() -> numero { retornar 7 }",
                encoding="utf-8",
            )
            (root / "base.gp").write_text(
                'usar "leaf.gp" como x\nusar "leaf.gp" como x\n'
                "funcao usar_valor() -> numero { retornar x.valor() }",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Alias de módulo duplicado"):
                compile_source_selfhosted(
                    'usar "base.gp" como base\nmostrar(base.usar_valor())',
                    source_path=root / "main.gp",
                )

    def test_reference_and_self_hosted_backends_enforce_actual_module_file_read_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            module = root / "oversized.gp"
            module.write_bytes(
                b"//" + b"x" * (4 * 1024 * 1024) + bytes([10]) +
                b"funcao valor() -> numero { retornar 7 }",
            )
            source = 'usar "oversized.gp" como large' + chr(10) + 'mostrar(large.valor())'
            for compiler in (compile_source, compile_source_selfhosted):
                with self.subTest(compiler=compiler.__name__):
                    with self.assertRaisesRegex(ValueError, "excede o limite de 4 MiB"):
                        compiler(source, source_path=root / "main.gp")

    def test_reference_and_self_hosted_backends_enforce_actual_module_graph_byte_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            module_size = 3 * 1024 * 1024 + 512 * 1024
            payload = b"//" + b"x" * (module_size - 3) + bytes([10])
            declarations = []
            for index in range(5):
                name = f"m{index}"
                (root / f"{name}.gp").write_bytes(payload)
                declarations.append(f'usar "{name}.gp" como {name}')
            source = chr(10).join(declarations) + chr(10) + "mostrar(1)"
            for compiler in (compile_source, compile_source_selfhosted):
                with self.subTest(compiler=compiler.__name__):
                    with self.assertRaisesRegex(ValueError, "Grafo de módulos GP excede o limite total de 16 MiB"):
                        compiler(source, source_path=root / "main.gp")

    def test_reference_and_self_hosted_backends_reject_symlink_loop_modules(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first.gp"
            second = root / "second.gp"
            try:
                first.symlink_to(second)
                second.symlink_to(first)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks indisponíveis neste ambiente")
            source = 'usar "first.gp" como loop' + chr(10) + 'mostrar(1)'
            for compiler in (compile_source, compile_source_selfhosted):
                with self.subTest(compiler=compiler.__name__):
                    with self.assertRaisesRegex(ValueError, "Caminho de módulo GP inválido"):
                        compiler(source, source_path=root / "main.gp")

    def test_reference_and_self_hosted_backends_reject_nested_symlink_loop_modules(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first.gp"
            second = root / "second.gp"
            parent = root / "parent.gp"
            try:
                first.symlink_to(second)
                second.symlink_to(first)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks indisponíveis neste ambiente")
            parent.write_text(
                'usar "first.gp" como loop' + chr(10) +
                'funcao valor() -> numero { retornar 7 }',
                encoding="utf-8",
            )
            source = 'usar "parent.gp" como parent' + chr(10) + 'mostrar(parent.valor())'
            for compiler in (compile_source, compile_source_selfhosted):
                with self.subTest(compiler=compiler.__name__):
                    with self.assertRaisesRegex(ValueError, "Caminho de módulo GP inválido"):
                        compiler(source, source_path=root / "main.gp")

    def test_reference_and_self_hosted_backends_reject_non_regular_module_files(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO indisponível neste ambiente")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fifo = root / "pipe.gp"
            try:
                os.mkfifo(fifo)
            except (OSError, NotImplementedError):
                self.skipTest("Criação de FIFO indisponível neste ambiente")
            source = 'usar "pipe.gp" como pipe' + chr(10) + 'mostrar(1)'
            for compiler in (compile_source, compile_source_selfhosted):
                with self.subTest(compiler=compiler.__name__):
                    with self.assertRaisesRegex(ValueError, "deve ser arquivo regular"):
                        compiler(source, source_path=root / "main.gp")

    def test_self_hosted_backend_rejects_module_depth_over_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index in range(34):
                next_import = (
                    f'usar "m{index + 1}.gp" como proximo\n'
                    if index < 33 else ""
                )
                (root / f"m{index}.gp").write_text(
                    next_import + f"funcao valor{index}() -> numero {{ retornar {index} }}",
                    encoding="utf-8",
                )
            with self.assertRaisesRegex(ValueError, "Profundidade de módulos GP excede 32"):
                compile_source_selfhosted(
                    'usar "m0.gp" como inicio\nmostrar(inicio.valor0())',
                    source_path=root / "main.gp",
                )

    def test_self_hosted_backend_rejects_missing_module(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Módulo GP não encontrado"):
                compile_source_selfhosted(
                    'usar "nao_existe.gp" como mod',
                    source_path=Path(temp) / "main.gp",
                )

    def test_self_hosted_backend_rejects_duplicate_module_alias(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "calc.gp").write_text(
                "funcao valor() -> numero { retornar 7 }", encoding="utf-8"
            )
            source = 'usar "calc.gp" como c\nusar "calc.gp" como c'
            with self.assertRaisesRegex(ValueError, "Alias de módulo duplicado"):
                compile_source_selfhosted(source, source_path=root / "main.gp")

    def test_module_function_namespace(self):
        source_path = Path("exemplos/modulos/aplicacao.gp").resolve()
        source = source_path.read_text(encoding="utf-8")
        output, _ = self.compile_and_run(source, source_path=source_path)
        self.assertEqual(output, ["Resultado do módulo: 42"])

    def test_module_function_internal_call(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "calc.gp").write_text("""
                funcao dobro(numero n) -> numero { retornar n * 2 }
                funcao quadruplicar(numero n) -> numero { retornar dobro(dobro(n)) }
            """, encoding="utf-8")
            main = 'usar "calc.gp" como c\nmostrar(c.quadruplicar(5))'
            output, _ = self.compile_and_run(main, source_path=root / "main.gp")
            self.assertEqual(output, ["20"])

    def test_missing_module_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Módulo GP não encontrado"):
                compile_source('usar "missing.gp" como m', source_path=Path(temp) / "main.gp")

    @unittest.skipUnless(shutil.which("clang"), "Clang não instalado; teste nativo ignorado")
    def test_native_arm64_backend_compiles_and_runs(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "native.gp"
            executable = root / "native-program"
            source.write_text("""
                funcao somar(numero a, numero b) -> numero {
                    retornar a + b
                }
                numero total = 0
                logico ativo = verdadeiro
                para (numero i = 1; i <= 5; i = i + 1) {
                    total = total + i
                }
                mostrar("Soma:", somar(19, 23))
                mostrar("Total:", total)
                mostrar("Ativo:", ativo)
            """, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(project / "gp_native.py"), str(source),
                 "-o", str(executable), "--run"],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Soma: 42", result.stdout)
            self.assertIn("Total: 15", result.stdout)
            self.assertIn("Ativo: verdadeiro", result.stdout)
            self.assertTrue(executable.is_file())


class GPNativeVMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import shutil
        cls.project = Path(__file__).resolve().parents[1]
        cls.temp = tempfile.TemporaryDirectory()
        cls.vm_binary = Path(cls.temp.name) / "gpvm-native"
        clang = shutil.which("clang")
        if not clang:
            raise unittest.SkipTest("Clang não instalado; VM nativa ignorada")
        result = subprocess.run(
            [clang, "-std=c11", "-O2", "-Wall", "-Wextra",
             str(cls.project / "gpvm_native.c"), "-lz", "-lm", "-o", str(cls.vm_binary)],
            text=True, capture_output=True, check=False,
        )
        if result.returncode:
            raise RuntimeError("Falha ao compilar VM C: " + result.stderr)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temp"):
            cls.temp.cleanup()

    def run_native(self, source, source_path=None, extra=()):
        _, _, bytecode = compile_source(source, source_path=source_path)
        path = Path(self.temp.name) / "case.gbc"
        path.write_bytes(bytecode)
        return subprocess.run(
            [str(self.vm_binary), str(path), *extra],
            text=True, capture_output=True, check=False,
        )

    def test_native_vm_unir_textos_handles_unicode_and_empty_list(self):
        result = self.run_native("""
            lista texto partes = ["Olá", " ", "GP", " 🚀"]
            lista texto vazia = []
            mostrar(unir_textos(partes))
            mostrar(tamanho(unir_textos(vazia)))
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Olá GP 🚀\n0\n")

    def test_native_vm_unir_textos_rejects_non_text_items(self):
        result = self.run_native("""
            lista numero partes = [1, 2]
            mostrar(unir_textos(partes))
        """)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("todos os itens sejam texto", result.stderr)

    def test_python_and_native_reject_noncanonical_gp_ir_fields(self):
        source = self.project / "tests" / "fixtures" / "bytecode_v2" / "recursive_function.gp"
        _, _, bytecode = compile_source(source.read_text(encoding="utf-8"), source_path=source)

        mutations = [
            (
                "instruction",
                lambda program: program["main"][0].__setitem__("x-extension", True),
            ),
            (
                "function",
                lambda program: next(iter(program["functions"].values())).__setitem__("x-extension", True),
            ),
            (
                "program",
                lambda program: (
                    program.pop("ir_version", None),
                    program.__setitem__("x-extension", True),
                ),
            ),
        ]
        for label, mutate in mutations:
            with self.subTest(field=label):
                malformed = _rewrite_binary_program(bytecode, mutate)
                with self.assertRaises(ValueError):
                    decode(malformed)
                path = Path(self.temp.name) / f"noncanonical-{label}.gbc"
                path.write_bytes(malformed)
                result = subprocess.run(
                    [str(self.vm_binary), str(path)],
                    text=True, capture_output=True, check=False,
                )
                self.assertNotEqual(result.returncode, 0, result.stderr)

    def test_native_encoder_rejects_extra_instruction_properties(self):
        import gp_compile
        fixture = self.project / "tests" / "fixtures" / "bytecode_v2" / "arithmetic.gp"
        document = compile_source_selfhosted_document(
            fixture.read_text(encoding="utf-8"),
            source_path=fixture,
        )
        raw = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
        self.assertIn('"op":"CONST"', raw)
        malformed = raw.replace('"op":"CONST"', '"op":"CONST","extension":true', 1)
        with self.assertRaisesRegex(ValueError, "rejeitou GP-IR"):
            gp_compile.encode_canonical_ir_native_json(malformed, self.vm_binary)

    def test_native_raw_json_path_skips_python_ir_hydration(self):
        import gp_compile
        from unittest import mock

        fixture = self.project / "tests" / "fixtures" / "bytecode_v2" / "unicode_text.gp"
        source = fixture.read_text(encoding="utf-8")
        reference_document = compile_source_selfhosted_document(source, source_path=fixture)
        reference = encode_canonical_ir(reference_document)

        with mock.patch(
            "gp_compile.validate_canonical_ir",
            side_effect=AssertionError("raw native path must not materialize a Python IR dict"),
        ):
            raw_json = gp_compile._compile_source_selfhosted_document(
                source,
                source_path=fixture,
                runner_backend="native",
                native_vm=self.vm_binary,
                _raw_json_output=True,
            )
            self.assertIsInstance(raw_json, str)
            self.assertTrue(raw_json.startswith('{"format":"GP-IR"'))
            native = gp_compile.encode_canonical_ir_native_json(raw_json, self.vm_binary)

        self.assertEqual(decode(native)["program"], decode(reference)["program"])
        self.assertEqual(native, reference)

    def test_native_encoder_accepts_gp_ir_from_stdin(self):
        fixture = self.project / "tests" / "fixtures" / "bytecode_v2" / "unicode_text.gp"
        document = compile_source_selfhosted_document(
            fixture.read_text(encoding="utf-8"),
            source_path=fixture,
        )
        raw = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        reference = encode_canonical_ir(document)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "stdin.gbc"
            result = subprocess.run(
                [str(self.vm_binary), "--encode-ir", "-", str(output)],
                input=raw, capture_output=True, timeout=30, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
            self.assertTrue(output.is_file())
            self.assertEqual(output.read_bytes(), reference)

    def test_native_encoder_rejects_empty_invalid_utf8_and_nul_stdin(self):
        invalid_inputs = {
            "empty": b"",
            "invalid_utf8": b'{"format":"GP-IR"}' + bytes([0xFF]),
            "nul": b'{"format":"GP-IR"}' + bytes([0]),
        }
        for label, raw in invalid_inputs.items():
            with self.subTest(input=label), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "invalid.gbc"
                result = subprocess.run(
                    [str(self.vm_binary), "--encode-ir", "-", str(output)],
                    input=raw, capture_output=True, timeout=30, check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_native_encoder_matches_python_reference_for_gp_ir_corpus(self):
        fixtures = self.project / "tests" / "fixtures" / "bytecode_v2"
        sources = sorted(fixtures.glob("*.gp"))
        self.assertGreaterEqual(len(sources), 6)
        for source_path in sources:
            with self.subTest(fixture=source_path.name):
                document = compile_source_selfhosted_document(
                    source_path.read_text(encoding="utf-8"),
                    source_path=source_path,
                )
                reference = encode_canonical_ir(document)
                native = encode_canonical_ir_native(document, self.vm_binary)
                self.assertEqual(native, reference)
                self.assertEqual(decode(native)["program"], decode(reference)["program"])

    def test_native_encoder_rejects_invalid_gp_ir_without_publishing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "invalid.gp-ir.json"
            output = Path(directory) / "invalid.gbc"
            source.write_text(
                '{"format":"GP-IR","ir_version":2,"version":"0.4","main":[],"functions":{}}',
                encoding="utf-8",
            )
            result = subprocess.run(
                [str(self.vm_binary), "--encode-ir", str(source), str(output)],
                text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("GP-IR v1 inválido", result.stderr)
            self.assertFalse(output.exists())

    def test_native_encoder_accepts_escaped_unicode_strings(self):
        fixture = self.project / "tests" / "fixtures" / "bytecode_v2" / "unicode_text.gp"
        document = compile_source_selfhosted_document(
            fixture.read_text(encoding="utf-8"),
            source_path=fixture,
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "escaped.gp-ir.json"
            output = Path(directory) / "escaped.gbc"
            source.write_text(
                json.dumps(document, ensure_ascii=True, separators=(",", ":")),
                encoding="utf-8",
            )
            result = subprocess.run(
                [str(self.vm_binary), "--encode-ir", str(source), str(output)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                decode(output.read_bytes())["program"],
                decode(encode_canonical_ir(document))["program"],
            )

    def test_native_encoder_rejects_oversized_json_before_allocation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "oversized.gp-ir.json"
            output = Path(directory) / "oversized.gbc"
            with source.open("wb") as stream:
                stream.truncate(64 * 1024 * 1024 + 1)
            result = subprocess.run(
                [str(self.vm_binary), "--encode-ir", str(source), str(output)],
                text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("acima de 64 MiB", result.stderr)
            self.assertFalse(output.exists())

    def test_native_encoder_rejects_oversized_stdin_without_allocation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "oversized-stdin.gbc"
            process = subprocess.Popen(
                [str(self.vm_binary), "--encode-ir", "-", str(output)],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            chunk = b" " * (1024 * 1024)
            try:
                if process.stdin is None or process.stderr is None:
                    self.fail("pipes do encoder não foram criados")
                for _ in range(64):
                    process.stdin.write(chunk)
                process.stdin.write(b" ")
                process.stdin.close()
                returncode = process.wait(timeout=60)
                stderr = process.stderr.read().decode("utf-8", errors="replace")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if process.stdin is not None and not process.stdin.closed:
                    process.stdin.close()
                if process.stderr is not None:
                    process.stderr.close()
            self.assertNotEqual(returncode, 0)
            self.assertIn("acima de 64 MiB", stderr)
            self.assertFalse(output.exists())

    def test_native_encoder_rejects_malformed_json_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "malformed.gp-ir.json"
            output = Path(directory) / "malformed.gbc"
            source.write_text(
                '{"format":"GP-IR","ir_version":1,"version":"0.4","main":[}',
                encoding="utf-8",
            )
            result = subprocess.run(
                [str(self.vm_binary), "--encode-ir", str(source), str(output)],
                text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_native_encoder_rejects_nested_duplicate_json_keys(self):
        fixture = self.project / "tests" / "fixtures" / "bytecode_v2" / "arithmetic.gp"
        document = compile_source_selfhosted_document(
            fixture.read_text(encoding="utf-8"),
            source_path=fixture,
        )
        encoded = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
        self.assertIn('"op":"CONST"', encoded)
        duplicated = encoded.replace('"op":"CONST"', '"op":"CONST","op":"CONST"', 1)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "duplicate.gp-ir.json"
            output = Path(directory) / "duplicate.gbc"
            source.write_text(duplicated, encoding="utf-8")
            result = subprocess.run(
                [str(self.vm_binary), "--encode-ir", str(source), str(output)],
                text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("chaves duplicadas", result.stderr)
            self.assertFalse(output.exists())

    def test_native_encoder_rejects_non_utf8_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "invalid-utf8.gp-ir.json"
            output = Path(directory) / "invalid-utf8.gbc"
            source.write_bytes(
                b'{"format":"GP-IR","ir_version":1,"version":"0.4","main":[],"functions":{}}' + bytes([0xFF])
            )
            result = subprocess.run(
                [str(self.vm_binary), "--encode-ir", str(source), str(output)],
                text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("UTF-8", result.stderr)
            self.assertFalse(output.exists())

    def test_native_encoder_writes_restrictive_atomic_output(self):
        fixture = self.project / "tests" / "fixtures" / "bytecode_v2" / "arithmetic.gp"
        document = compile_source_selfhosted_document(
            fixture.read_text(encoding="utf-8"),
            source_path=fixture,
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.gp-ir.json"
            output = Path(directory) / "output.gbc"
            source.write_text(
                json.dumps(document, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            result = subprocess.run(
                [str(self.vm_binary), "--encode-ir", str(source), str(output)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.is_file())
            self.assertEqual(output.read_bytes()[:4], b"GGPC")
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(Path(directory).glob("output.gbc.tmp.*")), [])

    def test_native_encoder_cleans_temporary_file_when_publish_fails(self):
        fixture = self.project / "tests" / "fixtures" / "bytecode_v2" / "arithmetic.gp"
        document = compile_source_selfhosted_document(
            fixture.read_text(encoding="utf-8"),
            source_path=fixture,
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.gp-ir.json"
            output = Path(directory) / "blocked.gbc"
            output.mkdir()
            source.write_text(
                json.dumps(document, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            result = subprocess.run(
                [str(self.vm_binary), "--encode-ir", str(source), str(output)],
                text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(output.is_dir())
            self.assertEqual(list(Path(directory).glob("blocked.gbc.tmp.*")), [])

    def test_self_hosted_native_runner_uses_native_encoder_in_cli(self):
        source = self.project / "tests" / "fixtures" / "bytecode_v2" / "arithmetic.gp"
        output = Path(self.temp.name) / "native-cli.gbc"
        native_default = self.project / "build" / "gpvm-native"
        native_default.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.vm_binary, native_default)
        result = subprocess.run(
            [
                sys.executable, str(self.project / "gp_compile.py"), str(source),
                "--self-hosted", "--runner-vm", "native", "--run", "--run-vm", "native",
                "--dump-ir", "-o", str(output),
            ],
            cwd=self.project, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("encoder C nativo", result.stdout)
        self.assertIn('"format": "GP-IR"', result.stdout)
        self.assertIn("GP VM (native): execução iniciada", result.stdout)
        self.assertIn("11 24 5", result.stdout)
        self.assertIn("GP Native VM", result.stderr)
        document = compile_source_selfhosted_document(
            source.read_text(encoding="utf-8"),
            source_path=source,
            runner_backend="native", native_vm=self.vm_binary,
        )
        self.assertEqual(output.read_bytes(), encode_canonical_ir(document))

    def test_compile_cli_runs_target_bytecode_on_native_vm(self):
        source = Path(self.temp.name) / "native-runtime.gp"
        output = Path(self.temp.name) / "native-runtime.gbc"
        source.write_text('mostrar("resultado", 6 * 7)', encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable, str(self.project / "gp_compile.py"), str(source),
                "--run", "--run-vm", "native", "--native-vm", str(self.vm_binary),
                "-o", str(output),
            ],
            cwd=self.project, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(output.is_file())
        self.assertIn("GP VM (native): execução iniciada", result.stdout)
        self.assertIn("resultado 42", result.stdout)
        self.assertIn("GP Native VM", result.stderr)

    def test_compile_cli_native_runtime_enforces_target_step_limit(self):
        source = Path(self.temp.name) / "native-runtime-loop.gp"
        output = Path(self.temp.name) / "native-runtime-loop.gbc"
        source.write_text("enquanto (verdadeiro) {}", encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable, str(self.project / "gp_compile.py"), str(source),
                "--run", "--run-vm", "native", "--native-vm", str(self.vm_binary),
                "--run-max-steps", "25", "-o", str(output),
            ],
            cwd=self.project, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(output.is_file())
        self.assertIn("limite de instruções", result.stderr.lower())

    def test_compile_cli_rejects_invalid_target_runtime_limits(self):
        source = Path(self.temp.name) / "limit-validation.gp"
        source.write_text("mostrar(1)", encoding="utf-8")
        for flag, value in (("--run-max-steps", "0"), ("--run-timeout-seconds", "3601")):
            with self.subTest(flag=flag):
                result = subprocess.run(
                    [sys.executable, str(self.project / "gp_compile.py"), str(source), flag, value],
                    cwd=self.project, text=True, capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn(flag, result.stderr)

    def test_python_and_native_accept_historical_gp_ir_without_ir_version(self):
        source = self.project / "tests" / "fixtures" / "bytecode_v2" / "arithmetic.gp"
        _, _, bytecode = compile_source(source.read_text(encoding="utf-8"), source_path=source)
        historical = _rewrite_binary_program(
            bytecode, lambda program: program.pop("ir_version", None)
        )
        decoded = decode(historical)
        self.assertNotIn("ir_version", decoded["program"])
        path = Path(self.temp.name) / "historical-no-ir-version.gbc"
        path.write_bytes(historical)
        result = subprocess.run(
            [str(self.vm_binary), str(path)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_native_vm_rejects_unknown_ir_format_version(self):
        _, _, bytecode = compile_source("mostrar(17)")
        mutated = _rewrite_binary_program(
            bytecode, lambda program: program.__setitem__("ir_version", 2)
        )
        path = Path(self.temp.name) / "unknown-ir-version.gbc"
        path.write_bytes(mutated)
        result = subprocess.run(
            [str(self.vm_binary), str(path)], text=True, capture_output=True, check=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ir inválida", result.stderr.lower())

    def test_native_vm_reads_only_explicit_host_source_input(self):
        source = "mostrar(entrada_fonte())"
        _, _, bytecode = compile_source(source)
        bytecode_path = Path(self.temp.name) / "host-source.gbc"
        input_path = Path(self.temp.name) / "host-source.txt"
        bytecode_path.write_bytes(bytecode)
        host_source = "Olá, GP\nfonte externa"
        input_path.write_text(host_source, encoding="utf-8")

        result = subprocess.run(
            [str(self.vm_binary), str(bytecode_path), "--source-input", str(input_path)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, host_source + "\n")

        without_input = subprocess.run(
            [str(self.vm_binary), str(bytecode_path)],
            text=True, capture_output=True, check=False,
        )
        self.assertNotEqual(without_input.returncode, 0)
        self.assertIn("host não forneceu", without_input.stderr)

    def test_native_vm_reads_explicit_host_source_stdin(self):
        _, _, bytecode = compile_source("mostrar(entrada_fonte())")
        bytecode_path = Path(self.temp.name) / "host-source-stdin.gbc"
        bytecode_path.write_bytes(bytecode)
        host_source = "Olá, GP\nfonte enviada por stdin"
        result = subprocess.run(
            [str(self.vm_binary), str(bytecode_path), "--source-input", "-"],
            input=host_source, text=True, encoding="utf-8",
            capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, host_source + "\n")

        empty = subprocess.run(
            [str(self.vm_binary), str(bytecode_path), "--source-input", "-"],
            input="", text=True, encoding="utf-8",
            capture_output=True, check=False,
        )
        self.assertEqual(empty.returncode, 0, empty.stderr)
        self.assertEqual(empty.stdout, "\n")

    def test_native_vm_rejects_invalid_host_source_stdin(self):
        _, _, bytecode = compile_source("mostrar(entrada_fonte())")
        bytecode_path = Path(self.temp.name) / "host-source-stdin-invalid.gbc"
        bytecode_path.write_bytes(bytecode)
        for invalid in (b"\xff", "texto\x00inválido".encode("utf-8")):
            with self.subTest(invalid=invalid):
                result = subprocess.run(
                    [str(self.vm_binary), str(bytecode_path), "--source-input", "-"],
                    input=invalid, capture_output=True, check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("UTF-8 válido sem NUL", result.stderr.decode("utf-8"))

    def test_native_vm_rejects_oversized_host_source_stdin(self):
        _, _, bytecode = compile_source("mostrar(entrada_fonte())")
        bytecode_path = Path(self.temp.name) / "host-source-stdin-oversized.gbc"
        bytecode_path.write_bytes(bytecode)
        result = subprocess.run(
            [str(self.vm_binary), str(bytecode_path), "--source-input", "-"],
            input=b"x" * (16 * 1024 * 1024 + 1),
            capture_output=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("16 MiB", result.stderr.decode("utf-8"))

    def test_native_vm_rejects_oversized_host_source(self):
        _, _, bytecode = compile_source("mostrar(entrada_fonte())")
        bytecode_path = Path(self.temp.name) / "host-source-oversized.gbc"
        input_path = Path(self.temp.name) / "host-source-oversized.txt"
        bytecode_path.write_bytes(bytecode)
        with input_path.open("wb") as handle:
            handle.truncate(16 * 1024 * 1024 + 1)
        result = subprocess.run(
            [str(self.vm_binary), str(bytecode_path), "--source-input", str(input_path)],
            text=True, capture_output=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("16 MiB", result.stderr)

    def test_native_vm_rejects_invalid_utf8_host_source(self):
        _, _, bytecode = compile_source("mostrar(entrada_fonte())")
        bytecode_path = Path(self.temp.name) / "host-source-invalid.gbc"
        input_path = Path(self.temp.name) / "host-source-invalid.txt"
        bytecode_path.write_bytes(bytecode)
        input_path.write_bytes(b"\xff")
        result = subprocess.run(
            [str(self.vm_binary), str(bytecode_path), "--source-input", str(input_path)],
            text=True, capture_output=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("UTF-8 válido", result.stderr)

    def test_native_vm_matches_python_on_v2_golden_fixture_corpus(self):
        fixture_root = self.project / "tests" / "fixtures" / "bytecode_v2"
        expected_outputs = {
            "arithmetic.gbc": ["11 24 5"],
            "control_flow_nested.gbc": ["48 3 11 8"],
            "recursive_function.gbc": ["120"],
            "structs_and_fields.gbc": ["Ana 38"],
            "unicode_text.gbc": ["Olá, GP 7"],
            "opcode_catalog.gbc": ["11 5 24 2", "9 3 0 GP GP 9 5"],
        }
        allowed_opcodes = {
            "CONST", "LOAD", "DECLARE", "STORE", "POP", "BUILD_ARRAY",
            "MAKE_TYPED_ARRAY", "BUILD_STRUCT", "GET_FIELD", "SET_FIELD",
            "GET_INDEX", "SET_INDEX", "NEG", "NOT", "ADD", "SUB", "MUL",
            "DIV", "MOD", "EQ", "NE", "GT", "LT", "GE", "LE", "AND",
            "OR", "PRINT", "JUMP", "JUMP_IF_FALSE", "CALL", "RETURN",
        }
        found_opcodes = set()
        manifest = {}
        for line in (fixture_root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            checksum, filename, _size = line.split(maxsplit=2)
            manifest[filename] = checksum
        for filename, expected in expected_outputs.items():
            with self.subTest(fixture=filename):
                path = fixture_root / filename
                bytecode = path.read_bytes()
                self.assertEqual(hashlib.sha256(bytecode).hexdigest(), manifest[filename])
                payload = decode(bytecode)
                self.assertEqual(payload["bytecode_version"], 2)
                program = payload["program"]
                found_opcodes.update(item["op"] for item in program["main"])
                for function in program["functions"].values():
                    found_opcodes.update(item["op"] for item in function["code"])
                python_output = io.StringIO()
                with contextlib.redirect_stdout(python_output):
                    GPVirtualMachine().run_bytes(bytecode)
                self.assertEqual(python_output.getvalue().splitlines(), expected)
                native_result = subprocess.run(
                    [str(self.vm_binary), str(path)],
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(native_result.returncode, 0, native_result.stderr)
                self.assertEqual(native_result.stdout.splitlines(), expected)
                self.assertEqual(native_result.stdout, python_output.getvalue())
        self.assertEqual(found_opcodes, allowed_opcodes)

    def test_native_vm_and_python_decoder_agree_on_mutated_golden_corpus(self):
        fixture_root = self.project / "tests" / "fixtures" / "bytecode_v2"
        fixtures = sorted(fixture_root.glob("*.gbc"))
        self.assertEqual(len(fixtures), 6)

        def flip(data, offset):
            damaged = bytearray(data)
            damaged[offset] ^= 0x01
            return bytes(damaged)

        def corrupt_opcode(data):
            return _rewrite_binary_program(
                data,
                lambda program: program["main"][0].__setitem__("op", "GP_UNKNOWN_OPCODE"),
            )

        def corrupt_arities(data):
            return _rewrite_binary_program(
                data,
                lambda program: program["main"][0].__setitem__("args", {"not": "an array"}),
            )

        mutations = (
            ("short_header", lambda data: data[:13]),
            ("short_zlib", lambda data: data[:-1]),
            ("trailing_zlib", _binary_with_trailing_compressed_bytes),
            ("bad_magic", lambda data: flip(data, 0)),
            ("bad_version", lambda data: flip(data, 5)),
            ("bad_size", lambda data: flip(data, 9)),
            ("bad_crc", lambda data: flip(data, 13)),
            ("bad_deflate", lambda data: flip(data, 14 + max(0, (len(data) - 14) // 2))),
            ("duplicate_key", lambda data: _binary_with_duplicate_key(data, b'"format":"GP-IR"')),
            ("unknown_opcode", corrupt_opcode),
            ("bad_args_shape", corrupt_arities),
        )
        case_index = 0
        for fixture in fixtures:
            original = fixture.read_bytes()
            for mutation_name, mutate in mutations:
                with self.subTest(fixture=fixture.name, mutation=mutation_name):
                    damaged = mutate(original)
                    try:
                        decode(damaged)
                    except Exception:
                        python_accepted = False
                    else:
                        python_accepted = True
                    path = Path(self.temp.name) / f"mutation-{case_index}.gbc"
                    path.write_bytes(damaged)
                    native = subprocess.run(
                        [str(self.vm_binary), str(path)],
                        text=True, capture_output=True, check=False,
                    )
                    native_accepted = native.returncode == 0
                    self.assertFalse(python_accepted, f"Python aceitou {fixture.name}/{mutation_name}")
                    self.assertFalse(native_accepted, f"VM C aceitou {fixture.name}/{mutation_name}: {native.stdout}")
                    self.assertEqual(python_accepted, native_accepted)
                    case_index += 1
        self.assertEqual(case_index, len(fixtures) * len(mutations))

    def test_native_vm_and_python_decoder_agree_on_seeded_bitflip_fuzz(self):
        fixture_root = self.project / "tests" / "fixtures" / "bytecode_v2"
        fixtures = sorted(fixture_root.glob("*.gbc"))
        self.assertEqual(len(fixtures), 6)
        rng = random.Random(0x47505632)
        cases = 0
        for fixture in fixtures:
            original = fixture.read_bytes()
            for iteration in range(8):
                damaged = bytearray(original)
                offset = rng.randrange(len(damaged))
                damaged[offset] ^= 1 << rng.randrange(8)
                mutated = bytes(damaged)
                with self.subTest(fixture=fixture.name, iteration=iteration, offset=offset):
                    try:
                        decode(mutated)
                    except Exception:
                        python_accepted = False
                    else:
                        python_accepted = True
                    path = Path(self.temp.name) / f"seeded-bitflip-{cases}.gbc"
                    path.write_bytes(mutated)
                    native = subprocess.run(
                        [str(self.vm_binary), str(path)],
                        text=True, capture_output=True, check=False,
                    )
                    native_accepted = native.returncode == 0
                    self.assertFalse(python_accepted, f"Python aceitou mutação {fixture.name}/{iteration}")
                    self.assertFalse(native_accepted, f"VM C aceitou mutação {fixture.name}/{iteration}")
                    self.assertEqual(python_accepted, native_accepted)
                    cases += 1
        self.assertEqual(cases, 48)

    def test_native_vm_backpatches_nested_loops_and_function_jumps(self):
        result = self.run_native(NESTED_BACKPATCH_SOURCE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "48 3 11 8")

    def test_native_vm_rejects_malformed_operand_schemas(self):
        for index, (source, mutation) in enumerate(_malformed_operand_cases()):
            with self.subTest(case=index):
                _, _, bytecode = compile_source(source)
                corrupt = _rewrite_binary_program(bytecode, mutation)
                path = Path(self.temp.name) / f"malformed-operands-{index}.gbc"
                path.write_bytes(corrupt)
                result = subprocess.run(
                    [str(self.vm_binary), str(path)],
                    text=True, capture_output=True, check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("estrutura IR inválida", result.stderr)

    def test_native_vm_rejects_non_integer_jump_destinations(self):
        _, _, bytecode = compile_source("se (verdadeiro) { mostrar(1) }")
        for malformed in (True, False, 0.0, 1.0, 1e0):
            with self.subTest(target=malformed):
                corrupt = _bytecode_with_malformed_jump(bytecode, malformed)
                path = Path(self.temp.name) / "malformed-jump.gbc"
                path.write_bytes(corrupt)
                result = subprocess.run(
                    [str(self.vm_binary), str(path)],
                    text=True, capture_output=True, check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("estrutura IR inválida", result.stderr)

    def test_native_vm_typed_array_declaration_copies_collection_result(self):
        source = """
            lista numero original = [2, 3]
            lista numero expanded = adicionar(original, 4)
            numero removed = remover(expanded, 0)
            mostrar(original[1], tamanho(original), tamanho(expanded), removed)
        """
        result = self.run_native(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "3 3 2 2")

    def test_native_vm_indexes_large_instruction_blocks_and_jumps(self):
        declarations = "\n".join(f"numero value_{i} = {i}" for i in range(160))
        source = declarations + """
numero total = 0
para (numero i = 0; i < 4; i = i + 1) {
    total = total + i
}
mostrar(total, value_159)
"""
        result = self.run_native(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "6 159")

    def test_native_vm_make_typed_array_rejects_wrong_element_type(self):
        _, _, bytecode = compile_source("lista numero values = [1]")

        def mutate(program):
            instructions = program["main"]
            typed_index = next(
                i for i, instruction in enumerate(instructions)
                if instruction.get("op") == "MAKE_TYPED_ARRAY"
            )
            instructions[typed_index]["args"][0] = "texto"
            declaration = next(
                instruction for instruction in instructions[typed_index + 1:]
                if instruction.get("op") == "DECLARE"
            )
            declaration["op"] = "POP"
            declaration["args"] = []

        mutated = _rewrite_binary_program(bytecode, mutate)
        path = Path(self.temp.name) / "typed-array-wrong-element.gbc"
        path.write_bytes(mutated)
        result = subprocess.run(
            [str(self.vm_binary), str(path)],
            text=True, capture_output=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tipo de elemento inválido no array", result.stderr)

    def test_native_env_reserve_keeps_reallocated_pointers_on_oom(self):
        import shutil
        clang = shutil.which("clang")
        self.assertIsNotNone(clang, "Clang é necessário para o teste do alocador")
        harness = Path(self.temp.name) / "env-reserve-oom.c"
        executable = Path(self.temp.name) / "env-reserve-oom"
        harness_text = r"""#define main gpvm_native_program_main
#include "__GPVM_NATIVE_C__"
#undef main
static int allocation_is_tracked(const void *pointer) {
    for (GPAllocHeader *header = gp_allocations; header; header = header->h.next)
        if ((const void *)(header + 1) == pointer) return 1;
    return 0;
}
int main(void) {
    Env env = {0};
    if (!env_reserve(&env)) return 10;
    for (size_t i = 0; i < env.cap; i++) {
        env.names[i] = copy_string("name");
        env.values[i] = number_value(1);
        env.types[i] = copy_string("numero");
        env.element_types[i] = NULL;
        if (!env.names[i] || !env.types[i]) return 11;
    }
    env.len = env.cap;
    size_t before = GP_MAX_HEAP_BYTES - 200u;
    gp_heap_bytes = before;
    if (env_reserve(&env)) return 12;
    if (gp_heap_bytes != before + 16u * sizeof(char *)) return 13;
    if (!allocation_is_tracked(env.names) || !allocation_is_tracked(env.values) ||
        !allocation_is_tracked(env.types) || !allocation_is_tracked(env.element_types)) return 14;
    env_destroy(&env);
    gp_memory_cleanup();
    return 0;
}
"""
        harness.write_text(
            harness_text.replace("__GPVM_NATIVE_C__", (self.project / "gpvm_native.c").as_posix()),
            encoding="utf-8",
        )
        compiled = subprocess.run(
            [clang, "-std=c11", "-O2", "-Wall", "-Wextra", str(harness), "-lz", "-lm", "-o", str(executable)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        result = subprocess.run([str(executable)], text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_native_vm_self_hosted_structs_fields_and_function_parameters(self):
        source = """
            estrutura Pessoa {
                texto nome;
                numero idade;
                logico ativa;
            }
            funcao idade_da(Pessoa pessoa) -> numero {
                retornar pessoa.idade
            }
            Pessoa ana = Pessoa("Ana", 29, verdadeiro)
            mostrar(ana.nome, idade_da(ana), ana.ativa)
            ana.idade = 30
            ana.nome = "Ana Luna"
            mostrar(ana.nome, ana.idade)
        """
        program = compile_source_selfhosted(source)
        path = Path(self.temp.name) / "selfhosted-structs.gbc"
        path.write_bytes(encode(program))
        result = subprocess.run(
            [str(self.vm_binary), str(path)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "Ana 29 verdadeiro")
        self.assertEqual(result.stdout.splitlines()[1], "Ana Luna 30")

    def test_native_vm_self_hosted_typed_list_parameters_and_returns(self):
        source = """
            funcao ajustar(lista numero values) -> numero {
                values[0] = values[0] + 5
                retornar values[0] + tamanho(values)
            }
            funcao ampliar(lista numero values) -> lista numero {
                values = adicionar(values, 9)
                retornar values
            }
            lista numero data = [2, 4]
            numero result = ajustar(data)
            lista numero expanded = ampliar(data)
            mostrar(result, data[0], tamanho(expanded), expanded[2])
        """
        document = compile_source_selfhosted_document(source)
        path = Path(self.temp.name) / "selfhosted-list-functions.gbc"
        path.write_bytes(encode_canonical_ir(document))
        result = subprocess.run(
            [str(self.vm_binary), str(path)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "9 7 3 9")

    def test_native_vm_self_hosted_struct_list_indexing_inside_loop(self):
        source = """
            estrutura Pessoa { texto nome; numero idade; }
            lista Pessoa pessoas = [Pessoa("Ana", 29), Pessoa("Bia", 26)]
            numero i = 0
            numero total = 0
            enquanto (i < tamanho(pessoas)) {
                i = i + 1
                se (i == 1) { continuar }
                total = total + pessoas[i - 1].idade
                se (i == 2) { quebrar }
            }
            mostrar(total, pessoas[0].nome)
        """
        document = compile_source_selfhosted_document(source)
        path = Path(self.temp.name) / "selfhosted-struct-list-loop.gbc"
        path.write_bytes(encode_canonical_ir(document))
        result = subprocess.run(
            [str(self.vm_binary), str(path)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "26 Ana")

    def test_native_vm_self_hosted_lists_of_structs_and_list_fields(self):
        source = """
            estrutura Pessoa { texto nome; numero idade; }
            estrutura Equipe { lista Pessoa integrantes; }
            lista Pessoa pessoas = [Pessoa("Ana", 29)]
            Equipe equipe = Equipe(pessoas)
            mostrar(equipe.integrantes[0].nome)
            equipe.integrantes[0].idade = 30
            mostrar(equipe.integrantes[0].idade)
        """
        program = compile_source_selfhosted(source)
        path = Path(self.temp.name) / "selfhosted-list-fields.gbc"
        path.write_bytes(encode(program))
        result = subprocess.run(
            [str(self.vm_binary), str(path)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "Ana")
        self.assertEqual(result.stdout.splitlines()[1], "30")

    def test_native_vm_self_hosted_functions_accept_and_return_lists_of_structs(self):
        source = """
            estrutura Pessoa { texto nome; numero idade; }
            funcao adicionar_pessoa(lista Pessoa pessoas) -> lista Pessoa {
                pessoas = adicionar(pessoas, Pessoa("Bia", 26))
                retornar pessoas
            }
            lista Pessoa pessoas = [Pessoa("Ana", 29)]
            lista Pessoa ampliada = adicionar_pessoa(pessoas)
            mostrar(tamanho(ampliada), ampliada[1].nome)
        """
        program = compile_source_selfhosted(source)
        path = Path(self.temp.name) / "selfhosted-list-struct-functions.gbc"
        path.write_bytes(encode(program))
        result = subprocess.run(
            [str(self.vm_binary), str(path)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "2 Bia")

    def test_native_vm_self_hosted_function_uses_own_loop_labels(self):
        source = """
            funcao somar_com_controle(numero limite) -> numero {
                numero cursor = 0
                numero total = 0
                enquanto (cursor < limite) {
                    cursor = cursor + 1
                    se (cursor == 2) { continuar }
                    se (cursor == 5) { quebrar }
                    total = total + cursor
                }
                retornar total
            }
            numero main_cursor = 0
            enquanto (main_cursor < 2) {
                main_cursor = main_cursor + 1
            }
            mostrar(somar_com_controle(8), main_cursor)
        """
        program = compile_source_selfhosted(source)
        path = Path(self.temp.name) / "selfhosted-function-loops.gbc"
        path.write_bytes(encode(program))
        result = subprocess.run(
            [str(self.vm_binary), str(path)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "8 2")

    def test_native_vm_runs_self_hosted_break_continue_and_nested_loops(self):
        source = """
            numero outer = 0
            numero total = 0
            numero inner = 0
            enquanto (outer < 3) {
                outer = outer + 1
                inner = 0
                enquanto (inner < 4) {
                    inner = inner + 1
                    se (inner == 2) { continuar }
                    se (inner == 4) { quebrar }
                    total = total + outer * inner
                }
            }
            numero for_total = 0
            para (numero cursor = 0; cursor < 7; cursor = cursor + 1) {
                se (cursor == 2) { continuar }
                se (cursor == 5) { quebrar }
                for_total = for_total + cursor
            }
            mostrar(total, outer, for_total)
        """
        program = compile_source_selfhosted(source)
        path = Path(self.temp.name) / "selfhosted-loops.gbc"
        path.write_bytes(encode(program))
        result = subprocess.run(
            [str(self.vm_binary), str(path)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "24 3 8")

    def test_native_vm_runs_self_hosted_typed_array_bytecode(self):
        source = """
            lista numero values = [2, 3]
            numero first = values[0]
            values[1] = 7
            lista numero expanded = adicionar(values, 4)
            numero removed = remover(expanded, 0)
            mostrar(first, values[1], tamanho(expanded), removed)
        """
        program = compile_source_selfhosted(source)
        path = Path(self.temp.name) / "selfhosted-arrays.gbc"
        path.write_bytes(encode(program))
        result = subprocess.run(
            [str(self.vm_binary), str(path)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "2 7 2 2")

    def test_native_vm_runs_self_hosted_backend_bytecode(self):
        source = """
            funcao fatorial(numero n) -> numero {
                se (n <= 1) { retornar 1 }
                senao { retornar n * fatorial(n - 1) }
            }
            mostrar(fatorial(6))
        """
        document = compile_source_selfhosted_document(source)
        path = Path(self.temp.name) / "selfhosted.gbc"
        path.write_bytes(encode_canonical_ir(document))
        result = subprocess.run(
            [str(self.vm_binary), str(path)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "720")

    def test_native_vm_matches_python_for_functions_arrays_and_structs(self):
        source = """
            estrutura Pessoa {
                texto nome;
                numero idade;
            }
            funcao fatorial(numero n) -> numero {
                se (n <= 1) { retornar 1 }
                retornar n * fatorial(n - 1)
            }
            lista numero valores = [2, 3]
            adicionar(valores, 4)
            numero removido = remover(valores, 0)
            Pessoa p = Pessoa{nome: "Ada", idade: 37}
            p.idade = p.idade + fatorial(3)
            mostrar(p.nome, p.idade, tamanho(valores), valores[0], removido)
        """
        _, _, bytecode = compile_source(source)
        expected = io.StringIO()
        with contextlib.redirect_stdout(expected):
            GPVirtualMachine().run_bytes(bytecode)
        path = Path(self.temp.name) / "equivalence.gbc"
        path.write_bytes(bytecode)
        result = subprocess.run([str(self.vm_binary), str(path)], text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), expected.getvalue().strip())

    def test_native_vm_executes_gp_lexer_with_compound_operators(self):
        source_path = Path(__file__).resolve().parents[1] / "exemplos" / "lexer_demo.gp"
        source = source_path.read_text(encoding="utf-8")
        result = self.run_native(source, source_path=source_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("==", result.stdout)
        self.assertIn("2.5", result.stdout)
        self.assertIn("PALAVRA_CHAVE:numero", result.stdout)
        self.assertIn("IDENTIFICADOR:total", result.stdout)
        self.assertIn("NUMERO:42", result.stdout)
        self.assertIn("Classificacao: DELIMITADOR OPERADOR NUMERO INVALIDO INVALIDO", result.stdout)

    def test_native_vm_executes_gp_semantic_symbol_table(self):
        source_path = Path(__file__).resolve().parents[1] / "linguagem" / "semantica_gp.gp"
        source = source_path.read_text(encoding="utf-8")
        result = self.run_native(source, source_path=source_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Declaracao global: verdadeiro", result.stdout)
        self.assertIn("Duplicata global rejeitada: verdadeiro", result.stdout)
        self.assertIn("Sombreamento local permitido: verdadeiro", result.stdout)
        self.assertIn("Variavel local: texto", result.stdout)
        self.assertIn("Heranca de escopo: texto", result.stdout)
        self.assertIn("Tipo global: numero", result.stdout)
        self.assertIn("Desconhecido: verdadeiro", result.stdout)
        self.assertIn("Total de simbolos: 3", result.stdout)

    def test_native_vm_executes_gp_self_hosted_parser(self):
        source_path = Path(__file__).resolve().parents[1] / "linguagem" / "parser_gp.gp"
        source = source_path.read_text(encoding="utf-8")
        result = self.run_native(
            source,
            source_path=source_path,
            extra=("--max-steps", "5000000"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Parser GP valido: verdadeiro", result.stdout)
        self.assertIn("Parser GP rejeita erro: verdadeiro", result.stdout)
        self.assertIn("AST raiz: PROGRAMA| 3", result.stdout)
        self.assertIn("Linha AST declaracao: 1", result.stdout)
        self.assertIn("Parser GP aceita se/senao: verdadeiro", result.stdout)
        self.assertIn("AST condicional: SE|senao 3", result.stdout)
        self.assertIn("AST bloco entao: BLOCO| 2", result.stdout)
        self.assertIn("Parser GP rejeita bloco incompleto: verdadeiro", result.stdout)
        self.assertIn("Parser GP aceita enquanto aninhado: verdadeiro", result.stdout)
        self.assertIn("AST enquanto: ENQUANTO| 2", result.stdout)
        self.assertIn("AST corpo enquanto: BLOCO| 2", result.stdout)
        self.assertIn("Parser GP aceita para: verdadeiro", result.stdout)
        self.assertIn("AST para: PARA| 4", result.stdout)
        self.assertIn("Parser GP aceita funcao/retornar: verdadeiro", result.stdout)
        self.assertIn("AST funcao: FUNCAO|somar -> numero 3", result.stdout)
        self.assertIn("AST parametro: PARAMETRO|numero|a", result.stdout)
        self.assertIn("AST retorno: RETORNAR|", result.stdout)
        self.assertIn("Parser GP aceita estrutura: verdadeiro", result.stdout)
        self.assertIn("AST estrutura: ESTRUTURA|Pessoa 3", result.stdout)
        self.assertIn("AST campo declarado: CAMPO_DECLARADO|texto|nome", result.stdout)
        self.assertIn("Parser GP aceita quebrar/continuar: verdadeiro", result.stdout)
        self.assertIn("AST quebrar: QUEBRAR|", result.stdout)
        self.assertIn("AST continuar: CONTINUAR|", result.stdout)
        self.assertIn("Parser GP rejeita quebrar fora de laco: verdadeiro", result.stdout)
        self.assertIn("Parser GP rejeita continuar fora de laco: verdadeiro", result.stdout)
        self.assertIn("Parser GP rejeita retornar fora de funcao: verdadeiro", result.stdout)
        self.assertIn("Semantica GP aceita programa tipado: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita tipo incorreto: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita nome desconhecido: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita duplicata: verdadeiro", result.stdout)
        self.assertIn("Semantica GP permite sombra local: verdadeiro", result.stdout)
        self.assertIn("Semantica GP valida parametros e retorno: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita argumento incorreto: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita retorno incorreto: verdadeiro", result.stdout)
        self.assertIn("Semantica GP aceita chamada antes da funcao: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita quantidade incorreta: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita parametro duplicado: verdadeiro", result.stdout)
        self.assertIn("Semantica GP valida para, enquanto e controle de laco: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita condicao de laco nao logica: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita condicao de para nao logica: verdadeiro", result.stdout)
        self.assertIn("Semantica GP valida listas tipadas e operacoes: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita lista heterogenea: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita elemento de lista incorreto: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita indice nao numerico: verdadeiro", result.stdout)
        self.assertIn("Semantica GP valida atribuicao por indice: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita atribuicao de tipo incorreto na lista: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita indice invalido na atribuicao: verdadeiro", result.stdout)
        self.assertIn("Semantica GP valida estruturas, construtores e campos: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita campo inexistente: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita tipo incorreto no construtor: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita atribuicao de tipo incorreto em campo: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita quantidade incorreta no construtor: verdadeiro", result.stdout)
        self.assertIn("Semantica GP valida estruturas aninhadas: verdadeiro", result.stdout)
        self.assertIn("Semantica GP valida estrutura em parametro e retorno: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita tipo desconhecido em parametro: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita tipo desconhecido em retorno: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita estrutura duplicada: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita campo duplicado: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita tipo de campo desconhecido: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita tipo de variavel desconhecido: verdadeiro", result.stdout)
        self.assertIn("Semantica GP aceita retorno em todos os ramos: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita caminho sem retorno: verdadeiro", result.stdout)
        self.assertIn("Semantica GP nao presume retorno dentro de laco: verdadeiro", result.stdout)
        self.assertIn("Gerador GP produz IR para declaracao, expressao, saida e atribuicao: verdadeiro", result.stdout)
        self.assertIn("Gerador GP produz IR para se, senao, enquanto e para: verdadeiro", result.stdout)
        self.assertIn('IR-NUM: ["JUMP_IF_FALSE",11]', result.stdout)
        self.assertIn('IR-NUM: ["JUMP",13]', result.stdout)
        self.assertIn('IR-NUM: ["JUMP_IF_FALSE",22]', result.stdout)
        self.assertIn('IR-NUM: ["JUMP_IF_FALSE",37]', result.stdout)
        self.assertIn('IR-NUM: ["JUMP",24]', result.stdout)
        self.assertNotIn('IR-NUM: ["LABEL"', result.stdout)
        self.assertIn("Teste IR rejeita salto sem destino: verdadeiro", result.stdout)
        self.assertIn("Teste IR rejeita rotulo duplicado: verdadeiro", result.stdout)
        self.assertIn("Teste IR rejeita rotulo vazio: verdadeiro", result.stdout)
        self.assertIn("Gerador GP produz secoes de funcao, parametros, CALL e RETURN: verdadeiro", result.stdout)
        self.assertIn('IR-FN: ["CALL","somar",2]', result.stdout)
        self.assertIn('IR-FN: ["FUNCTION","somar","numero",2]', result.stdout)
        self.assertIn('IR-FN: ["PARAM","numero","a"]', result.stdout)
        self.assertIn('IR-FN: ["PARAM","numero","b"]', result.stdout)
        self.assertIn('IR-FN: ["CODE_BEGIN","somar"]', result.stdout)
        self.assertIn('IR-FN: ["LOAD","a"]', result.stdout)
        self.assertIn('IR-FN: ["LOAD","b"]', result.stdout)
        self.assertIn('IR-FN: ["ADD"]', result.stdout)
        self.assertIn('IR-FN: ["RETURN"]', result.stdout)
        self.assertIn('IR-FN: ["CODE_END","somar"]', result.stdout)
        self.assertIn("Gerador GP produz IR para funcao recursiva com fluxo de controle: verdadeiro", result.stdout)
        self.assertIn('IR-REC: ["FUNCTION","fatorial","numero",1]', result.stdout)
        self.assertIn('IR-REC: ["PARAM","numero","n"]', result.stdout)
        self.assertIn('IR-REC: ["CALL","fatorial",1]', result.stdout)
        self.assertIn('IR-REC: ["JUMP_IF_FALSE",', result.stdout)
        self.assertIn('IR-REC: ["JUMP",', result.stdout)
        self.assertIn('IR: ["GP-IR",1]', result.stdout)
        self.assertIn('IR: ["CONST","NUMERO",10]', result.stdout)
        self.assertIn('IR: ["MUL"]', result.stdout)
        self.assertIn('IR: ["ADD"]', result.stdout)
        self.assertIn('IR: ["DECLARE","total","numero"]', result.stdout)
        self.assertIn('IR: ["PRINT",2]', result.stdout)
        self.assertIn('IR: ["STORE","total"]', result.stdout)
        self.assertIn("Semantica GP valida atribuicao por indice: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita atribuicao de tipo incorreto na lista: verdadeiro", result.stdout)
        self.assertIn("Semantica GP rejeita indice invalido na atribuicao: verdadeiro", result.stdout)
        self.assertIn("Coluna AST declaracao:", result.stdout)
        self.assertIn("AST precedencia: BINARIO|*", result.stdout)
        self.assertIn("AST chamada: CHAMADA|somar 2", result.stdout)
        self.assertIn("AST array: ARRAY| 2", result.stdout)
        self.assertIn("AST logico: BINARIO|||", result.stdout)
        self.assertIn("AST campo: CAMPO|nome", result.stdout)
        self.assertIn("AST indice: INDICE|[]", result.stdout)

    def test_native_vm_runs_expanded_local_module(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "math.gp").write_text(
                "funcao somar(numero a, numero b) -> numero { retornar a + b }",
                encoding="utf-8",
            )
            source_path = root / "main.gp"
            source = 'usar "math.gp" como math\nmostrar(math.somar(19, 23))'
            result = self.run_native(source, source_path=source_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "42")

    def test_native_cli_runs_nested_local_module_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "leaf.gp").write_text(
                "funcao dobrar(numero n) -> numero { retornar n * 2 }",
                encoding="utf-8",
            )
            (root / "base.gp").write_text(
                'usar "leaf.gp" como core\n'
                "funcao quatro(numero n) -> numero { retornar core.dobrar(core.dobrar(n)) }",
                encoding="utf-8",
            )
            source_path = root / "main.gp"
            source_path.write_text(
                'usar "base.gp" como base\nmostrar(base.quatro(5))',
                encoding="utf-8",
            )
            output_path = root / "nested-native.gbc"
            result = subprocess.run(
                [
                    sys.executable, str(self.project / "gp_compile.py"), str(source_path),
                    "--self-hosted", "--runner-vm", "native", "--run", "--run-vm", "native",
                    "--native-vm", str(self.vm_binary), "-o", str(output_path),
                ],
                cwd=self.project, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(output_path.is_file())
            self.assertIn("GP VM (native): execução iniciada", result.stdout)
            self.assertEqual(result.stdout.splitlines()[-1], "20")
            self.assertIn("GP Native VM", result.stderr)

    def test_native_vm_runs_self_hosted_local_module_bytecode(self):
        source_path = self.project / "exemplos" / "modulos" / "aplicacao.gp"
        source = source_path.read_text(encoding="utf-8")
        program = compile_source_selfhosted(source, source_path=source_path)
        path = Path(self.temp.name) / "selfhosted-module.gbc"
        path.write_bytes(encode(program))
        result = subprocess.run(
            [str(self.vm_binary), str(path)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "Resultado do módulo: 42")

    def test_native_vm_runs_self_hosted_typed_json_constants(self):
        source = """
            numero decimal = 4.5
            logico ativo = verdadeiro
            texto mensagem = "alpha|beta\\nsegunda linha"
            mostrar(decimal, ativo, mensagem)
        """
        program = compile_source_selfhosted(source)
        path = Path(self.temp.name) / "selfhosted-typed-constants.gbc"
        path.write_bytes(encode(program))
        result = subprocess.run(
            [str(self.vm_binary), str(path)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "4.5 verdadeiro alpha|beta\nsegunda linha\n")

    def test_native_vm_enforces_step_limit(self):
        result = self.run_native("enquanto (verdadeiro) {}",
                                 extra=("--max-steps", "25"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("limite de instruções", result.stderr)

    def test_native_vm_utf8_codepoint_count_and_index(self):
        result = self.run_native('texto frase = "ação 🧠 café"\nmostrar(tamanho(frase), frase[0], frase[5], frase[7])')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "11 a 🧠 c")

    def test_native_vm_ascii_string_index_reuses_cached_characters(self):
        source = """
            texto fonte = "abcdef"
            texto atual = ""
            numero i = 0
            enquanto (i < 5000) {
                atual = fonte[i % 6]
                i = i + 1
            }
            mostrar(atual)
        """
        result = self.run_native(source, extra=("--gc-threshold", "1024"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "b")
        self.assertRegex(result.stderr, r"GP GC: [0-9]{1,2} objetos gerenciados alocados")

    def test_native_vm_memory_peak_is_reported(self):
        result = self.run_native('mostrar("memória")')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("GP memória: pico", result.stderr)
        self.assertIn("limite 256 MiB", result.stderr)

    def test_native_vm_reports_separate_memory_pools_and_bootstrap_cap(self):
        import json
        import os

        _ast, program, _bytecode = compile_source('mostrar("memoria")')
        bytecode_path = Path(self.temp.name) / "memory-pools.gbc"
        report_path = Path(self.temp.name) / "memory-pools.json"
        bytecode_path.write_bytes(encode(program))
        env = os.environ.copy()
        env["GPVM_MEMORY_REPORT"] = str(report_path)
        result = subprocess.run(
            [str(self.vm_binary), str(bytecode_path)],
            text=True, capture_output=True, check=False, env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        live_total = (
            report["native_live_bytes"]
            + report["managed_live_bytes"]
            + report["stack_live_bytes"]
        )
        self.assertEqual(live_total, report["total_heap_live_bytes"])
        self.assertLessEqual(report["total_heap_peak_bytes"], 256 * 1024 * 1024)
        self.assertGreater(report["native_peak_bytes"], 0)
        self.assertGreater(report["managed_peak_bytes"], 0)
        self.assertGreater(report["managed_payload_peak_bytes"], 0)
        self.assertGreater(report["process_rss_bytes"], 0)
        self.assertGreater(report["process_peak_rss_bytes"], 0)
        self.assertGreaterEqual(report["process_peak_rss_bytes"], report["process_rss_bytes"])
        self.assertEqual(
            report["process_memory_source"],
            "procfs VmRSS + getrusage ru_maxrss",
        )
        self.assertIn("GP memória: pico", result.stderr)

    def test_native_vm_garbage_collector_reclaims_garbage_and_keeps_roots(self):
        source = """
            estrutura Pessoa {
                texto nome;
                numero idade;
            }
            funcao exercitar() -> numero {
                lista numero raiz_dados = [42]
                lista numero temporaria = []
                texto frase_lixo = "inicio"
                Pessoa titular = Pessoa{nome: "Ada", idade: 37}
                numero i = 0
                enquanto (i < 6000) {
                    temporaria = [i, i + 1, i + 2, i + 3]
                    frase_lixo = "descartar " + "texto"
                    i = i + 1
                }
                retornar raiz_dados[0] + titular.idade + tamanho(titular.nome)
            }
            mostrar(exercitar())
        """
        result = self.run_native(source, extra=("--gc-threshold", "1024"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "82")
        self.assertRegex(result.stderr, r"GP GC: [1-9][0-9]* ciclos, [1-9][0-9]* objetos liberados")
        self.assertRegex(result.stderr, r"[0-9.]+ MiB recuperados")

    def test_native_vm_rejects_trailing_compressed_bytes(self):
        _, _, bytecode = compile_source("mostrar(42)")
        corrupt = _binary_with_trailing_compressed_bytes(bytecode)
        path = Path(self.temp.name) / "trailing-zlib-bytes.gbc"
        path.write_bytes(corrupt)
        result = subprocess.run([str(self.vm_binary), str(path)], text=True, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("payload zlib inválido", result.stderr)

    def test_native_vm_rejects_invalid_json_string_escapes(self):
        _, _, bytecode = compile_source("mostrar(42)")
        invalid_cases = (
            b'"' + bytes([92]) + b'q"',
            b'"' + bytes([92]) + b'u12XZ"',
            b'"' + bytes([1]) + b'"',
            b'"' + bytes([92]) + b'u0000"',
            b'"' + bytes([92]) + b'uD800"',
            b'"' + bytes([92]) + b'uDC00"',
            b'"' + bytes([92]) + b'uD800' + bytes([92]) + b'u0041"',
        )
        for index, invalid in enumerate(invalid_cases):
            with self.subTest(invalid=invalid):
                corrupt = _binary_with_extra_json(bytecode, invalid)
                path = Path(self.temp.name) / f"invalid-json-string-{index}.gbc"
                path.write_bytes(corrupt)
                result = subprocess.run([str(self.vm_binary), str(path)], text=True, capture_output=True, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertRegex(result.stderr, "JSON inválido|chaves JSON duplicadas ou estrutura JSON inválida")

    def test_native_vm_rejects_duplicate_json_keys(self):
        _, _, bytecode = compile_source("mostrar(42)")
        corrupt = _binary_with_duplicate_key(bytecode, b'"format":"GP-IR"')
        path = Path(self.temp.name) / "duplicate-json-key.gbc"
        path.write_bytes(corrupt)
        result = subprocess.run([str(self.vm_binary), str(path)], text=True, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("chaves JSON duplicadas", result.stderr)

    def test_native_vm_rejects_excessive_json_depth(self):
        _, _, bytecode = compile_source("mostrar(42)")
        nested = b"[" * 520 + b"0" + b"]" * 520
        corrupt = _binary_with_extra_json(bytecode, nested)
        path = Path(self.temp.name) / "excessive-json-depth.gbc"
        path.write_bytes(corrupt)
        result = subprocess.run([str(self.vm_binary), str(path)], text=True, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("aninhamento excessivo", result.stderr)

    def test_native_vm_rejects_nonstandard_json_constants(self):
        _, _, bytecode = compile_source("mostrar(42)")
        corrupt = _binary_with_extra_json(bytecode, b"NaN")
        path = Path(self.temp.name) / "nonstandard-json-constant.gbc"
        path.write_bytes(corrupt)
        result = subprocess.run([str(self.vm_binary), str(path)], text=True, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("primitivo JSON inválido", result.stderr)

    def test_native_vm_rejects_non_finite_json_constants(self):
        _, _, bytecode = compile_source("mostrar(42)")
        corrupt = _rewrite_binary_program(
            bytecode,
            lambda program: _mutate_main_opcode(
                program, "CONST", lambda instruction: instruction["args"].__setitem__(0, float("nan"))
            ),
        )
        path = Path(self.temp.name) / "non-finite-constant.gbc"
        path.write_bytes(corrupt)
        result = subprocess.run([str(self.vm_binary), str(path)], text=True, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr, "JSON inválido|estrutura IR inválida")

    def test_native_vm_rejects_mismatched_language_version(self):
        _, _, bytecode = compile_source("mostrar(42)")
        corrupt = _rewrite_binary_payload(bytecode, lambda payload: payload.__setitem__("language_version", "9.9"))
        path = Path(self.temp.name) / "wrong-language-version.gbc"
        path.write_bytes(corrupt)
        result = subprocess.run([str(self.vm_binary), str(path)], text=True, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("estrutura IR inválida", result.stderr)

    def test_native_vm_rejects_binary_internal_version_mismatch(self):
        _, _, bytecode = compile_source("mostrar(42)")
        corrupt = _rewrite_binary_payload(bytecode, lambda payload: payload.update(bytecode_version=1))
        path = Path(self.temp.name) / "wrong-internal-version.gbc"
        path.write_bytes(corrupt)
        result = subprocess.run(
            [str(self.vm_binary), str(path)],
            text=True, capture_output=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("versão interna", result.stderr.lower())

    def test_native_vm_rejects_corrupt_checksum(self):
        _, _, bytecode = compile_source('mostrar("integridade")')
        corrupt = bytearray(bytecode)
        corrupt[13] ^= 0x01
        path = Path(self.temp.name) / "corrupt.gbc"
        path.write_bytes(corrupt)
        result = subprocess.run([str(self.vm_binary), str(path)], text=True, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checksum", result.stderr.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
