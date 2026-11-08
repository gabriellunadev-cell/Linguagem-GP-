import unittest

from gp_ide_server import BridgeError, DEFAULT_HOST, MAX_REQUEST_BYTES, execute_source, validate_payload


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

    def test_payload_rejects_source_above_one_mib(self):
        with self.assertRaises(BridgeError) as ctx:
            validate_payload({"source": "x" * (MAX_REQUEST_BYTES + 1)})
        self.assertEqual(ctx.exception.status, 413)

    def test_payload_only_allows_reference_runtime(self):
        with self.assertRaises(BridgeError):
            validate_payload({"source": "mostrar(1)", "runtime": "native"}, require_runtime=True)

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


if __name__ == "__main__":
    unittest.main()
