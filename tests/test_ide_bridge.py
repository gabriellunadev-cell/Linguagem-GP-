import unittest

from gp_ide_server import (
    BridgeError,
    DEFAULT_HOST,
    MAX_REQUEST_BYTES,
    execute_project,
    execute_source,
    validate_payload,
    validate_project_payload,
)


class GPBridgeTests(unittest.TestCase):
    def test_bridge_binds_to_loopback_only(self):
        self.assertEqual(DEFAULT_HOST, "127.0.0.1")

    def test_payload_accepts_simple_gp_file(self):
        source, file_name = validate_payload({"source": 'mostrar("Olá")', "fileName": "principal.gp"})
        self.assertEqual(source, 'mostrar("Olá")')
        self.assertEqual(file_name, "principal.gp")

    def test_payload_rejects_path_traversal(self):
        with self.assertRaises(BridgeError):
            validate_payload({"source": "mostrar(1)", "fileName": "../outside.gp"})

    def test_payload_rejects_source_above_request_limit(self):
        with self.assertRaises(BridgeError) as ctx:
            validate_payload({"source": "x" * (MAX_REQUEST_BYTES + 1)})
        self.assertEqual(ctx.exception.status, 413)

    def test_payload_only_allows_reference_runtime(self):
        with self.assertRaises(BridgeError):
            validate_payload({"source": "mostrar(1)", "runtime": "native"}, require_runtime=True)

    def test_single_file_payload_rejects_module_imports(self):
        source = 'usar "math.gp" como math\nmostrar(math.somar(20, 22))'
        with self.assertRaisesRegex(BridgeError, "projeto completo"):
            validate_payload({"source": source, "fileName": "principal.gp"})

    def test_compile_endpoint_executes_official_compiler(self):
        result = execute_source('mostrar("compilado")', "principal.gp", run=False)
        self.assertTrue(result["ok"], result["stderr"])
        self.assertEqual(result["exitCode"], 0)
        self.assertIn("bytecode binário v2", result["stdout"])

    def test_run_endpoint_executes_program_and_returns_stdout(self):
        result = execute_source('mostrar("GP Bridge ativo")', "principal.gp", run=True)
        self.assertTrue(result["ok"], result["stderr"])
        self.assertEqual(result["exitCode"], 0)
        self.assertIn("GP Bridge ativo", result["stdout"])

    def test_project_payload_accepts_relative_module_tree(self):
        entry, files = validate_project_payload({
            "entryFile": "app/principal.gp",
            "files": [
                {
                    "path": "app/principal.gp",
                    "source": 'usar "lib/matematica.gp" como math\nmostrar(math.somar(20, 22))',
                },
                {
                    "path": "app/lib/matematica.gp",
                    "source": "funcao somar(numero a, numero b) -> numero {\n retornar a + b\n}",
                },
            ],
        })
        self.assertEqual(entry, "app/principal.gp")
        self.assertEqual(len(files), 2)

    def test_project_execution_compiles_and_runs_all_modules(self):
        result = execute_project(
            "app/principal.gp",
            {
                "app/principal.gp": 'usar "lib/matematica.gp" como math\nmostrar("Resultado:", math.somar(19, 23))',
                "app/lib/matematica.gp": (
                    "funcao somar(numero a, numero b) -> numero {\n"
                    "    retornar a + b\n"
                    "}\n"
                ),
            },
            run=True,
        )
        self.assertTrue(result["ok"], result["stderr"])
        self.assertEqual(result["exitCode"], 0)
        self.assertIn("Resultado: 42", result["stdout"])

    def test_project_payload_rejects_entry_path_traversal(self):
        with self.assertRaises(BridgeError):
            validate_project_payload({
                "entryFile": "../principal.gp",
                "files": [{"path": "principal.gp", "source": "mostrar(1)"}],
            })

    def test_project_payload_rejects_dot_path_components(self):
        for path in ("app/./principal.gp", "app/../principal.gp", "app//principal.gp"):
            with self.subTest(path=path):
                with self.assertRaises(BridgeError):
                    validate_project_payload({
                        "entryFile": path,
                        "files": [{"path": path, "source": "mostrar(1)"}],
                    })

    def test_project_payload_rejects_duplicate_paths(self):
        with self.assertRaisesRegex(BridgeError, "duplicados"):
            validate_project_payload({
                "entryFile": "principal.gp",
                "files": [
                    {"path": "principal.gp", "source": "mostrar(1)"},
                    {"path": "principal.gp", "source": "mostrar(2)"},
                ],
            })

    def test_project_payload_requires_entry_file_in_file_list(self):
        with self.assertRaisesRegex(BridgeError, "não existe"):
            validate_project_payload({
                "entryFile": "principal.gp",
                "files": [{"path": "outro.gp", "source": "mostrar(1)"}],
            })

    def test_project_payload_rejects_absolute_imports(self):
        with self.assertRaisesRegex(BridgeError, "Importação GP inválida"):
            validate_project_payload({
                "entryFile": "principal.gp",
                "files": [
                    {"path": "principal.gp", "source": 'usar "/tmp/escape.gp" como x\nmostrar(1)'},
                ],
            })

    def test_project_payload_rejects_imports_outside_workspace(self):
        with self.assertRaisesRegex(BridgeError, "sair do diretório"):
            validate_project_payload({
                "entryFile": "app/principal.gp",
                "files": [
                    {"path": "app/principal.gp", "source": 'usar "../../escape.gp" como x\nmostrar(1)'},
                ],
            })

    def test_project_payload_rejects_backslash_imports(self):
        with self.assertRaisesRegex(BridgeError, "Importação GP inválida"):
            validate_project_payload({
                "entryFile": "principal.gp",
                "files": [
                    {"path": "principal.gp", "source": 'usar "lib\\math.gp" como math\nmostrar(1)'},
                ],
            })

    def test_project_payload_rejects_missing_modules(self):
        with self.assertRaisesRegex(BridgeError, "não encontrado"):
            validate_project_payload({
                "entryFile": "principal.gp",
                "files": [
                    {"path": "principal.gp", "source": 'usar "lib/math.gp" como math\nmostrar(1)'},
                ],
            })

    def test_project_payload_checks_imports_inside_nested_modules(self):
        with self.assertRaisesRegex(BridgeError, "sair do diretório"):
            validate_project_payload({
                "entryFile": "app/principal.gp",
                "files": [
                    {"path": "app/principal.gp", "source": 'usar "lib/base.gp" como base\nmostrar(1)'},
                    {"path": "app/lib/base.gp", "source": 'usar "../../../escape.gp" como escape\nfuncao ok() -> numero { retornar 1 }'},
                ],
            })


if __name__ == "__main__":
    unittest.main()
