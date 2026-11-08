import hashlib
import contextlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gp_compile import (
    compile_source,
    compile_source_selfhosted,
    compile_source_selfhosted_document,
    generate_selfhosted_runner_artifact,
    load_selfhosted_runner_artifact,
    _selfhosted_runner_source,
)
from gpcompiler.bytecode import decode, encode, encode_canonical_ir
from gpcompiler.selfhosted_ir import SelfHostedIRError, canonical_ir_to_program, structured_ir_to_program, textual_ir_to_program
from gpcompiler.lower import ir_to_dict
from gpcompiler.vm import GPVirtualMachine


class SelfHostedIRAdapterTests(unittest.TestCase):
    def test_native_runner_timeout_must_be_a_bounded_positive_integer(self):
        for invalid in (0, -1, 3601, True, 1.5, "300"):
            with self.subTest(timeout=invalid):
                with self.assertRaisesRegex(ValueError, "runner_timeout_seconds"):
                    compile_source_selfhosted_document(
                        "mostrar(1)",
                        runner_backend="native",
                        runner_timeout_seconds=invalid,
                    )

    def test_canonical_gp_ir_hydrates_and_executes_functions_and_structs(self):
        document = {
            "format": "GP-IR", "ir_version": 1, "version": "0.4",
            "main": [
                {"op": "CONST", "args": ["Ada"]},
                {"op": "CONST", "args": [37]},
                {"op": "BUILD_STRUCT", "args": ["Pessoa", [["nome", "texto"], ["idade", "numero"]]]},
                {"op": "PRINT", "args": [1]},
            ],
            "functions": {
                "dobro": {"return_type": "numero", "parameters": [["numero", "n"]],
                          "code": [{"op": "LOAD", "args": ["n"]}, {"op": "CONST", "args": [2]},
                                   {"op": "MUL", "args": []}, {"op": "RETURN", "args": []}]}
            },
        }
        program = canonical_ir_to_program(document)
        self.assertEqual(program.instructions[2].operands[1], [("nome", "texto"), ("idade", "numero")])
        self.assertEqual(program.functions["dobro"].parameters, [("numero", "n")])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue(), "Pessoa{nome='Ada', idade=37}\n")

    def test_direct_document_path_does_not_hydrate_runtime_ir(self):
        source = "numero valor = 40 + 2; mostrar(valor)"
        with patch(
            "gpcompiler.selfhosted_ir.canonical_ir_to_program",
            side_effect=AssertionError("hidratação não pode ocorrer no caminho direto"),
        ):
            document = compile_source_selfhosted_document(source)
            bytecode = encode_canonical_ir(document)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(bytecode)
        self.assertEqual(output.getvalue(), "42\n")

    def test_frontend_document_encodes_directly_and_matches_compatibility_api(self):
        source = """
            funcao fatorial(numero n) -> numero {
                se (n <= 1) { retornar 1 }
                retornar n * fatorial(n - 1)
            }
            estrutura Pessoa { texto nome; numero idade; }
            lista numero dados = [2, 3, 4]
            Pessoa pessoa = Pessoa("Ada", fatorial(5))
            mostrar(pessoa.nome, pessoa.idade, dados[1])
        """
        document = compile_source_selfhosted_document(source)
        self.assertIsInstance(document, dict)
        direct = encode_canonical_ir(document)
        compatibility = encode(compile_source_selfhosted(source))
        self.assertEqual(direct, compatibility)
        output_direct = io.StringIO()
        output_compat = io.StringIO()
        with contextlib.redirect_stdout(output_direct):
            GPVirtualMachine().run_bytes(direct)
        with contextlib.redirect_stdout(output_compat):
            GPVirtualMachine().run_bytes(compatibility)
        self.assertEqual(output_direct.getvalue(), output_compat.getvalue())
        self.assertEqual(output_direct.getvalue(), "Ada 120 3\n")

    def test_frontend_and_bootstrap_match_if_without_else_and_empty_else(self):
        source = """
            funcao escolher(logico condition) -> numero {
                numero value = 0
                se (condition) { value = 1 }
                se (condition) { value = 2 } senao {}
                se (condition) { value = 3 } senao { value = 4 }
                retornar value
            }
            mostrar(escolher(falso))
        """
        _ast, bootstrap_program, _bytecode = compile_source(source)
        bootstrap = ir_to_dict(bootstrap_program)
        direct = compile_source_selfhosted_document(source)
        self.assertEqual(direct["main"], bootstrap["main"])
        self.assertEqual(direct["functions"], json.loads(json.dumps(bootstrap["functions"])))
        self.assertEqual(
            [item["op"] for item in direct["functions"]["escolher"]["code"]].count("JUMP"),
            2,
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode_canonical_ir(direct))
        self.assertEqual(output.getvalue(), "4\n")

    def test_self_hosted_runner_receives_source_as_host_data_not_code(self):
        source = 'texto sentinela = "GP_HOST_SOURCE_SENTINEL_2026"\nmostrar(sentinela)'
        original = GPVirtualMachine.run_bytes
        observed = {}

        def inspect_runner(vm, bytecode, **kwargs):
            observed["host_source"] = kwargs.get("host_source")
            observed["runner_payload"] = decode(bytecode)
            return original(vm, bytecode, **kwargs)

        with patch.object(GPVirtualMachine, "run_bytes", inspect_runner):
            document = compile_source_selfhosted_document(source)

        self.assertIsInstance(document, dict)
        self.assertEqual(observed["host_source"], source)
        serialized_runner = json.dumps(observed["runner_payload"], ensure_ascii=False)
        self.assertNotIn("GP_HOST_SOURCE_SENTINEL_2026", serialized_runner)
        self.assertIn("entrada_fonte", serialized_runner)

    def test_production_runner_excludes_top_level_test_harness(self):
        source = _selfhosted_runner_source()
        self.assertIn("funcao analisar_semantica_ast_gp", source)
        self.assertIn("funcao gerar_ir_ast_gp", source)
        self.assertIn("texto gp_selfhosted_fonte = entrada_fonte()", source)
        self.assertNotIn("exemplo_ast_valido", source)
        self.assertNotIn("exemplo_semantica_ast_valida", source)
        self.assertNotIn("Parser GP valido:", source)
        self.assertNotIn("Semantica GP aceita programa tipado:", source)

    def test_bootstrap_runner_source_preserves_real_line_breaks(self):
        from gp_compile import _selfhosted_runner_source
        source = _selfhosted_runner_source()
        lines = source.splitlines()
        self.assertGreater(len(lines), 1000)
        self.assertTrue(lines[0].startswith("funcao __gp_namespace_lexer__letra_gp"))
        self.assertIn("texto gp_selfhosted_fonte = entrada_fonte()", source)
        self.assertNotIn("\\nfuncao", source)

    def test_bootstrap_runner_artifact_is_reused_and_integrity_checked(self):
        manifest = generate_selfhosted_runner_artifact()
        bytecode = load_selfhosted_runner_artifact()
        rebuilt_manifest = generate_selfhosted_runner_artifact(force=True)
        rebuilt_bytecode = load_selfhosted_runner_artifact()
        self.assertEqual(manifest["bytecode_sha256"], rebuilt_manifest["bytecode_sha256"])
        self.assertEqual(bytecode, rebuilt_bytecode)
        self.assertEqual(manifest["bytecode_size"], len(bytecode))
        self.assertEqual(
            manifest["bytecode_sha256"],
            hashlib.sha256(bytecode).hexdigest(),
        )
        with patch("gp_compile.compile_source", side_effect=AssertionError("runner rebuilt")):
            self.assertEqual(load_selfhosted_runner_artifact(), bytecode)

        with patch("gp_compile.compile_source", side_effect=AssertionError("Python bootstrap invoked")):
            strict_manifest = generate_selfhosted_runner_artifact(allow_python_bootstrap=False)
            strict_bytecode = load_selfhosted_runner_artifact(require_existing=True)
        self.assertEqual(strict_manifest["bytecode_sha256"], hashlib.sha256(strict_bytecode).hexdigest())
        self.assertEqual(strict_bytecode, bytecode)

    def test_bootstrap_seed_strict_mode_fails_closed_without_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("gp_compile.BOOTSTRAP_RUNNER_BYTECODE", root / "missing.gbc"), patch(
                "gp_compile.BOOTSTRAP_RUNNER_MANIFEST", root / "missing.json"
            ), patch("gp_compile.compile_source", side_effect=AssertionError("Python bootstrap invoked")):
                with self.assertRaisesRegex(ValueError, "Seed bootstrap GP ausente"):
                    generate_selfhosted_runner_artifact(allow_python_bootstrap=False)

    def test_self_hosted_frontend_runner_matches_on_native_vm(self):
        clang = shutil.which("clang")
        if not clang:
            self.skipTest("Clang não instalado")
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            native_vm = Path(directory) / "gpvm-native"
            built = subprocess.run(
                [
                    clang, "-std=c11", "-O2", "-Wall", "-Wextra",
                    str(project / "gpvm_native.c"), "-lz", "-lm", "-o", str(native_vm),
                ],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            source = "texto nome = entrada_fonte()\nmostrar(nome)"
            python_document = compile_source_selfhosted_document(source)
            native_document = compile_source_selfhosted_document(
                source, runner_backend="native", native_vm=native_vm
            )
            self.assertEqual(native_document, python_document)

    def test_self_hosted_frontend_named_struct_accepts_empty_typed_list_field(self):
        source = """
            estrutura Caixa {
                lista numero itens;
            }
            Caixa caixa = Caixa{itens: []}
            mostrar(tamanho(caixa.itens))
        """
        document = compile_source_selfhosted_document(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode_canonical_ir(document))
        self.assertEqual(output.getvalue(), "0\n")

    def test_self_hosted_frontend_reassigns_empty_typed_list(self):
        source = """
            lista numero values = [1, 2]
            values = []
            mostrar(tamanho(values))
        """
        document = compile_source_selfhosted_document(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode_canonical_ir(document))
        self.assertEqual(output.getvalue(), "0\n")

    def test_self_hosted_frontend_accepts_standalone_call_statements(self):
        source = """
            lista numero values = []
            adicionar(values, 7)
            mostrar(values[0], tamanho(values))
        """
        document = compile_source_selfhosted_document(source)
        self.assertIn("POP", [item["op"] for item in document["main"]])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode_canonical_ir(document))
        self.assertEqual(output.getvalue(), "7 1\n")

    def test_self_hosted_frontend_accepts_standalone_user_function_call(self):
        source = """
            funcao incrementar(numero value) -> numero {
                retornar value + 1
            }
            incrementar(41)
            mostrar(42)
        """
        document = compile_source_selfhosted_document(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode_canonical_ir(document))
        self.assertEqual(output.getvalue(), "42\n")

    def test_self_hosted_frontend_semantically_checks_standalone_calls(self):
        with self.assertRaisesRegex(ValueError, "adicionar exige uma lista"):
            compile_source_selfhosted_document("adicionar(1, 2)")

    def test_self_hosted_frontend_named_struct_list_field_and_parameter(self):
        source = """
            estrutura Box {
                lista numero values;
            }
            funcao criar(lista numero values) -> Box {
                retornar Box{values: values}
            }
            lista numero items = [1, 2]
            Box box = criar(items)
            mostrar(tamanho(box.values))
        """
        document = compile_source_selfhosted_document(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode_canonical_ir(document))
        self.assertEqual(output.getvalue(), "2\n")

    def test_self_hosted_frontend_accepts_empty_statements_and_block_terminators(self):
        source = """
            numero value = 0
            ;
            se (verdadeiro) { value = value + 1 };
            enquanto (falso) { value = value + 100 };
            mostrar(value)
        """
        document = compile_source_selfhosted_document(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode_canonical_ir(document))
        self.assertEqual(output.getvalue(), "1\n")

    def test_self_hosted_frontend_accepts_function_call_as_statement(self):
        source = """
            lista numero valores = []
            funcao registrar(numero valor) {
                adicionar(valores, valor)
            }
            registrar(7)
            mostrar(tamanho(valores), valores[0])
        """
        document = compile_source_selfhosted_document(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode_canonical_ir(document))
        self.assertEqual(output.getvalue(), "1 7\n")

    def test_self_hosted_frontend_compiles_host_source_intrinsic(self):
        source = "mostrar(entrada_fonte())"
        document = compile_source_selfhosted_document(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(
                encode_canonical_ir(document), host_source="texto em tempo de execução"
            )
        self.assertEqual(output.getvalue(), "texto em tempo de execução\n")

    def test_self_hosted_frontend_rejects_host_source_arguments(self):
        with self.assertRaisesRegex(ValueError, "entrada_fonte nao aceita argumentos"):
            compile_source_selfhosted_document('mostrar(entrada_fonte("nao permitido"))')

    def test_canonical_gp_ir_rejects_unknown_version(self):
        with self.assertRaisesRegex(SelfHostedIRError, "Versão do documento"):
            canonical_ir_to_program({"format": "GP-IR", "ir_version": 2, "version": "0.4", "main": [], "functions": {}})

    def test_text_envelope_converts_to_typed_program(self):
        program = textual_ir_to_program([
            "GP-IR|1",
            "CONST|NUMERO|42",
            "DECLARE|answer|numero",
            "LOAD|answer",
            "PRINT|1",
            "CALL|sum|2",
            "FUNCTION|sum|numero|2",
            "PARAM|numero|left",
            "PARAM|numero|right",
            "CODE_BEGIN|sum",
            "LOAD|left",
            "LOAD|right",
            "ADD",
            "RETURN",
            "CONST|NULO|",
            "RETURN",
            "CODE_END|sum",
        ])
        self.assertEqual([item.opcode for item in program.instructions],
                         ["CONST", "DECLARE", "LOAD", "PRINT", "CALL"])
        self.assertEqual(program.instructions[0].operands, (42,))
        self.assertEqual(program.instructions[1].operands, ("answer", "numero", None))
        self.assertEqual(program.instructions[-1].operands, ("sum", 2))
        function = program.functions["sum"]
        self.assertEqual(function.parameters, [("numero", "left"), ("numero", "right")])
        self.assertEqual(function.return_type, "numero")
        self.assertEqual([item.opcode for item in function.instructions],
                         ["LOAD", "LOAD", "ADD", "RETURN", "CONST", "RETURN"])

    def test_structured_ir_records_convert_to_typed_program(self):
        program = structured_ir_to_program([
            ["GP-IR", 1],
            ["CONST", "NUMERO", 42],
            ["DECLARE", "answer", "numero"],
            ["LOAD", "answer"],
            ["PRINT", 1],
        ])
        self.assertEqual(
            [item.opcode for item in program.instructions],
            ["CONST", "DECLARE", "LOAD", "PRINT"],
        )
        self.assertEqual(program.instructions[0].operands, (42,))

    def test_structured_ir_preserves_pipe_and_escaped_text_payload(self):
        program = structured_ir_to_program([
            ["GP-IR", 1],
            ["CONST", "TEXTO", "alpha|beta\nsecond line"],
            ["PRINT", 1],
        ])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue(), "alpha|beta\nsecond line\n")

    def test_structured_ir_rejects_non_string_fields(self):
        with self.assertRaisesRegex(SelfHostedIRError, "inteiro JSON inválido"):
            structured_ir_to_program([["GP-IR", 1], ["PRINT", True]])

    def test_structured_ir_emits_native_json_constant_types(self):
        program = structured_ir_to_program([
            ["GP-IR", 1],
            ["CONST", "NUMERO", 12.5],
            ["CONST", "LOGICO", True],
            ["CONST", "NULO", None],
            ["PRINT", 3],
        ])
        self.assertEqual([item.operands for item in program.instructions[:3]],
                         [(12.5,), (True,), (None,)])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue().strip(), "12.5 True None")

    def test_structured_ir_rejects_numeric_text_operand(self):
        with self.assertRaisesRegex(SelfHostedIRError, "inteiro JSON inválido"):
            structured_ir_to_program([["GP-IR", 1], ["PRINT", "1"]])

    def test_structured_ir_rejects_wrong_constant_payload_type(self):
        with self.assertRaisesRegex(SelfHostedIRError, "precisa ser número JSON"):
            structured_ir_to_program([["GP-IR", 1], ["CONST", "NUMERO", "42"]])

    def test_structured_ir_rejects_boolean_header_version(self):
        with self.assertRaisesRegex(SelfHostedIRError, "Cabeçalho GP-IR"):
            structured_ir_to_program([["GP-IR", True], ["PRINT", 0]])

    def test_structured_ir_rejects_malformed_record(self):
        with self.assertRaisesRegex(SelfHostedIRError, "lista não vazia"):
            structured_ir_to_program([["GP-IR", 1], []])

    def test_text_constants_decode_json_and_boolean_literals(self):
        program = textual_ir_to_program([
            "GP-IR|1",
            'CONST|TEXTO|"barra|linha\\ntexto"',
            "CONST|PALAVRA_CHAVE|verdadeiro",
            "CONST|PALAVRA_CHAVE|falso",
            "CONST|NULO|",
        ])
        self.assertEqual(program.instructions[0].operands, ("barra|linha\ntexto",))
        self.assertEqual(program.instructions[1].operands, (True,))
        self.assertEqual(program.instructions[2].operands, (False,))
        self.assertEqual(program.instructions[3].operands, (None,))

    def test_structure_metadata_is_attached_to_build_struct(self):
        program = textual_ir_to_program([
            "GP-IR|1",
            "STRUCT|Pessoa|2",
            "STRUCT_FIELD|texto|nome",
            "STRUCT_FIELD|numero|idade",
            'CONST|TEXTO|"Ana"',
            "CONST|NUMERO|29",
            "BUILD_STRUCT|Pessoa|2",
        ])
        self.assertEqual(
            program.instructions[-1].operands,
            ("Pessoa", [("nome", "texto"), ("idade", "numero")]),
        )

    def test_rejects_incomplete_structure_metadata(self):
        with self.assertRaisesRegex(SelfHostedIRError, "declara 2 campo"):
            textual_ir_to_program([
                "GP-IR|1", "STRUCT|Pessoa|2",
                "STRUCT_FIELD|texto|nome",
                "CONST|NULO|",
            ])

    def test_rejects_build_struct_without_schema(self):
        with self.assertRaisesRegex(SelfHostedIRError, "esquema não declarado"):
            textual_ir_to_program(["GP-IR|1", "BUILD_STRUCT|Pessoa|0"])

    def test_rejects_unknown_opcode(self):
        with self.assertRaisesRegex(SelfHostedIRError, "opcode não suportado"):
            textual_ir_to_program(["GP-IR|1", "INVENTADO"])

    def test_rejects_bad_jump_target(self):
        with self.assertRaisesRegex(SelfHostedIRError, "destino 8 fora"):
            textual_ir_to_program(["GP-IR|1", "JUMP|8"])

    def test_rejects_missing_or_extra_function_parameters(self):
        with self.assertRaisesRegex(SelfHostedIRError, "declara 2 parâmetro"):
            textual_ir_to_program([
                "GP-IR|1", "FUNCTION|sum|numero|2",
                "PARAM|numero|a", "CODE_BEGIN|sum", "RETURN", "CODE_END|sum",
            ])

    def test_self_hosted_frontend_compiles_recursive_function(self):
        source = """
            funcao fatorial(numero n) -> numero {
                se (n <= 1) { retornar 1 }
                senao { retornar n * fatorial(n - 1) }
            }
            numero result = fatorial(5)
            mostrar("fatorial:", result)
        """
        program = compile_source_selfhosted(source)
        self.assertIn("fatorial", program.functions)
        self.assertTrue(any(item.opcode == "CALL" for item in program.instructions))
        bytecode = encode(program)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(bytecode)
        self.assertEqual(output.getvalue().strip(), "fatorial: 120")

    def test_self_hosted_frontend_preserves_pipe_escaped_text_and_booleans(self):
        source = (
            'texto message = "alpha|beta' + chr(92) + 'nsecond line"; '
            'logico enabled = verdadeiro; mostrar(message, enabled)'
        )
        program = compile_source_selfhosted(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue(), "alpha|beta\nsecond line True\n")

    def test_self_hosted_frontend_functions_accept_and_return_typed_lists(self):
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
        program = compile_source_selfhosted(source)
        self.assertEqual(program.functions["ajustar"].parameters, [("lista<numero>", "values")])
        self.assertEqual(program.functions["ampliar"].return_type, "lista<numero>")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue().strip(), "9 7 3 9")

    def test_self_hosted_frontend_rejects_wrong_typed_list_function_argument(self):
        source = """
            funcao contar(lista numero values) -> numero { retornar tamanho(values) }
            lista texto names = ["Ana"]
            mostrar(contar(names))
        """
        with self.assertRaisesRegex(ValueError, "Tipo incorreto nos argumentos"):
            compile_source_selfhosted(source)

    def test_self_hosted_frontend_rejects_wrong_typed_list_function_return(self):
        source = """
            funcao nomes() -> lista numero {
                retornar ["Ana"]
            }
            lista numero values = nomes()
        """
        with self.assertRaisesRegex(ValueError, "Retorno incompativel"):
            compile_source_selfhosted(source)

    def test_self_hosted_frontend_constructs_and_mutates_struct_fields(self):
        source = """
            estrutura Pessoa {
                texto nome;
                numero idade;
                logico ativa;
            }
            Pessoa pessoa = Pessoa("Ana", 29, verdadeiro)
            mostrar(pessoa.nome, pessoa.idade, pessoa.ativa)
            pessoa.idade = 30
            pessoa.nome = "Ana Luna"
            mostrar(pessoa.nome, pessoa.idade)
        """
        program = compile_source_selfhosted(source)
        operations = [item.opcode for item in program.instructions]
        self.assertIn("BUILD_STRUCT", operations)
        self.assertIn("GET_FIELD", operations)
        self.assertIn("SET_FIELD", operations)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue().splitlines(), ["Ana 29 True", "Ana Luna 30"])

    def test_self_hosted_frontend_supports_named_struct_initializers_and_schema_order(self):
        source = """
            estrutura Endereco { texto rua; numero cep; }
            estrutura Pessoa { texto nome; Endereco endereco; }
            Endereco endereco = Endereco{cep: 28900, rua: "Centro"}
            Pessoa pessoa = Pessoa{endereco: endereco, nome: "Ada"}
            mostrar(pessoa.nome, pessoa.endereco.rua, pessoa.endereco.cep)
        """
        document = compile_source_selfhosted_document(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode_canonical_ir(document))
        self.assertEqual(output.getvalue(), "Ada Centro 28900\n")

    def test_self_hosted_frontend_rejects_invalid_named_struct_initializers(self):
        cases = [
            (
                'estrutura Pessoa { texto nome; numero idade; } Pessoa p = Pessoa{nome: "Ana", idade: 2, apelido: "A"}',
                "Campo desconhecido no construtor nomeado",
            ),
            (
                'estrutura Pessoa { texto nome; numero idade; } Pessoa p = Pessoa{nome: "Ana", nome: "Bia"}',
                "Campo duplicado no construtor nomeado",
            ),
            (
                'estrutura Pessoa { texto nome; numero idade; } Pessoa p = Pessoa{nome: "Ana"}',
                "Campo ausente no construtor nomeado",
            ),
            (
                'estrutura Pessoa { texto nome; numero idade; } Pessoa p = Pessoa{nome: 7, idade: 2}',
                "Tipo incorreto no campo nomeado",
            ),
        ]
        for source, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                with self.assertRaisesRegex(ValueError, diagnostic):
                    compile_source_selfhosted(source)

    def test_self_hosted_frontend_passes_and_returns_lists_of_structs(self):
        source = """
            estrutura Pessoa { texto nome; numero idade; }
            funcao primeiro_nome(lista Pessoa pessoas) -> texto {
                retornar pessoas[0].nome
            }
            funcao adicionar_pessoa(lista Pessoa pessoas) -> lista Pessoa {
                pessoas = adicionar(pessoas, Pessoa("Bia", 26))
                retornar pessoas
            }
            lista Pessoa pessoas = [Pessoa("Ana", 29)]
            mostrar(primeiro_nome(pessoas))
            lista Pessoa ampliada = adicionar_pessoa(pessoas)
            mostrar(tamanho(ampliada), ampliada[1].nome)
        """
        program = compile_source_selfhosted(source)
        self.assertEqual(
            program.functions["primeiro_nome"].parameters,
            [("lista<Pessoa>", "pessoas")],
        )
        self.assertEqual(program.functions["adicionar_pessoa"].return_type, "lista<Pessoa>")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue().splitlines(), ["Ana", "2 Bia"])

    def test_self_hosted_frontend_rejects_unknown_list_field_element_type(self):
        source = """
            estrutura Equipe {
                lista Fantasma integrantes;
            }
        """
        with self.assertRaisesRegex(ValueError, "Tipo de campo desconhecido: Fantasma"):
            compile_source_selfhosted(source)

    def test_self_hosted_frontend_supports_list_fields_of_structs(self):
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
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue().splitlines(), ["Ana", "30"])

    def test_self_hosted_frontend_runs_struct_list_indexing_inside_loop(self):
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
        program = compile_source_selfhosted(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue().strip(), "26 Ana")

    def test_self_hosted_frontend_supports_nested_structures(self):
        source = """
            estrutura Endereco { texto cidade; numero cep; }
            estrutura Pessoa { texto nome; Endereco endereco; }
            Endereco local = Endereco("Cabo Frio", 28900)
            Pessoa pessoa = Pessoa("Ana", local)
            mostrar(pessoa.nome, pessoa.endereco.cidade, pessoa.endereco.cep)
            pessoa.endereco.cep = 289001
            mostrar(pessoa.endereco.cep)
        """
        program = compile_source_selfhosted(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue().splitlines(), [
            "Ana Cabo Frio 28900", "289001"
        ])

    def test_self_hosted_frontend_passes_structures_to_functions(self):
        source = """
            estrutura Pessoa { texto nome; numero idade; }
            funcao idade_da(Pessoa pessoa) -> numero {
                retornar pessoa.idade
            }
            Pessoa ana = Pessoa("Ana", 29)
            mostrar(idade_da(ana))
        """
        program = compile_source_selfhosted(source)
        self.assertIn("idade_da", program.functions)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue().strip(), "29")

    def test_self_hosted_frontend_rejects_struct_constructor_with_wrong_field_count(self):
        source = 'estrutura Pessoa { texto nome; } Pessoa p = Pessoa("Ana", 29)'
        with self.assertRaisesRegex(ValueError, "Quantidade de campos incorreta"):
            compile_source_selfhosted(source)

    def test_self_hosted_frontend_compiles_typed_arrays_and_index_mutation(self):
        source = """
            lista numero values = [2, 3]
            numero first = values[0]
            values[1] = 7
            lista numero expanded = adicionar(values, 4)
            numero removed = remover(expanded, 0)
            mostrar(first, values[1], tamanho(values), tamanho(expanded), removed, expanded[0])
        """
        program = compile_source_selfhosted(source)
        instructions = [item.opcode for item in program.instructions]
        self.assertIn("BUILD_ARRAY", instructions)
        self.assertIn("MAKE_TYPED_ARRAY", instructions)
        self.assertIn("GET_INDEX", instructions)
        self.assertIn("SET_INDEX", instructions)
        self.assertIn("CALL", instructions)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue().strip(), "2 7 3 2 2 7")

    def test_self_hosted_frontend_lowers_break_continue_in_while(self):
        source = """
            numero cursor = 0
            numero total = 0
            enquanto (cursor < 8) {
                cursor = cursor + 1
                se (cursor == 2) { continuar }
                se (cursor == 6) { quebrar }
                total = total + cursor
            }
            mostrar(total, cursor)
        """
        program = compile_source_selfhosted(source)
        jumps = [item.operands[0] for item in program.instructions
                 if item.opcode == "JUMP"]
        self.assertTrue(jumps)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue().strip(), "13 6")

    def test_self_hosted_frontend_accepts_call_expression_in_for_increment(self):
        source = """
            numero contador = 0
            funcao identidade(numero valor) -> numero {
                mostrar(valor)
                retornar valor
            }
            para (numero indice = 0; contador < 1; identidade(2)) {
                contador = contador + 1
            }
            mostrar(contador)
        """
        document = compile_source_selfhosted_document(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode_canonical_ir(document))
        self.assertEqual(output.getvalue(), '2\n1\n')
    def test_self_hosted_frontend_lowers_break_continue_in_for(self):
        source = """
            numero total = 0
            para (numero cursor = 0; cursor < 7; cursor = cursor + 1) {
                se (cursor == 2) { continuar }
                se (cursor == 5) { quebrar }
                total = total + cursor
            }
            mostrar(total)
        """
        program = compile_source_selfhosted(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue().strip(), "8")

    def test_self_hosted_frontend_nested_loops_target_innermost_loop(self):
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
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue().strip(), "24 3 8")

    def test_self_hosted_function_loops_have_independent_label_state(self):
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
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue().strip(), "8 2")

    def test_self_hosted_frontend_compiles_empty_typed_array_and_text_index(self):
        source = """
            lista texto names = []
            names = adicionar(names, "Luna")
            texto word = "GP"
            mostrar(tamanho(names), word[1])
        """
        program = compile_source_selfhosted(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode(program))
        self.assertEqual(output.getvalue().strip(), "1 P")


if __name__ == "__main__":
    unittest.main()
