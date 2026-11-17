import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from gp_ide_server import (
    GPBridgeHandler,
    LoopbackHTTPServer,
    BridgeError,
    DEFAULT_HOST,
    MAX_REQUEST_BYTES,
    execute_project,
    execute_source,
    allowed_hosts,
    allowed_origins,
    validate_payload,
    validate_project_payload,
)


class GPBridgeTests(unittest.TestCase):
    def test_allowed_hosts_default_to_loopback(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(allowed_hosts(), {"127.0.0.1", "localhost"})

    def test_allowed_hosts_normalize_explicit_configuration(self):
        with patch.dict(os.environ, {"GP_BRIDGE_HOSTS": " localhost, GP.GPTV.ONLINE ,,127.0.0.1 "}):
            self.assertEqual(allowed_hosts(), {"localhost", "gp.gptv.online", "127.0.0.1"})

    def test_allowed_hosts_fail_closed_for_empty_explicit_list(self):
        with patch.dict(os.environ, {"GP_BRIDGE_HOSTS": " , , "}):
            self.assertEqual(allowed_hosts(), set())

    def test_bridge_binds_to_loopback_only(self):
        self.assertEqual(DEFAULT_HOST, "127.0.0.1")

    def test_default_cors_allows_local_vite_dev_origin(self):
        origins = allowed_origins()
        self.assertIn("http://localhost:5173", origins)
        self.assertIn("http://127.0.0.1:5173", origins)

    def test_payload_accepts_simple_gp_file(self):
        source, file_name, python_interop = validate_payload({"source": 'mostrar("Olá")', "fileName": "principal.gp"})
        self.assertEqual(source, 'mostrar("Olá")')
        self.assertEqual(file_name, "principal.gp")
        self.assertFalse(python_interop)

    def test_payload_requires_boolean_python_interop_opt_in(self):
        source, _name, enabled = validate_payload({
            "source": 'mostrar(py_chamar("math.sqrt", [81]))',
            "pythonInterop": True,
        })
        self.assertIn("py_chamar", source)
        self.assertTrue(enabled)
        with self.assertRaisesRegex(BridgeError, "precisa ser booleano"):
            validate_payload({"source": "mostrar(1)", "pythonInterop": "true"})

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

    def test_run_endpoint_executes_python_interop_only_when_requested(self):
        source = 'mostrar("Python:", py_chamar("math.sqrt", [144]))'
        denied = execute_source(source, "principal.gp", run=True)
        self.assertFalse(denied["ok"])
        self.assertIn("ative --python-interop", denied["stderr"])
        enabled = execute_source(source, "principal.gp", run=True, python_interop=True)
        self.assertTrue(enabled["ok"], enabled["stderr"])
        self.assertIn("Python: 12.0", enabled["stdout"])

    def test_project_payload_accepts_relative_module_tree(self):
        entry, files, python_interop = validate_project_payload({
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
        self.assertFalse(python_interop)

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

    def test_project_execution_can_opt_in_to_python_standard_library(self):
        result = execute_project(
            "app/principal.gp",
            {
                "app/principal.gp": (
                    'numero raiz = py_chamar("math.sqrt", [81])\n'
                    'numero media = py_chamar("statistics.mean", [[2, 4, 6, 8]])\n'
                    'mostrar("Híbrido:", raiz, media)'
                ),
            },
            run=True,
            python_interop=True,
        )
        self.assertTrue(result["ok"], result["stderr"])
        self.assertIn("Híbrido: 9.0 5.0", result["stdout"])

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
                    {"path": "principal.gp", "source": 'usar "lib\\\\math.gp" como math\nmostrar(1)'},
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


class GPBridgeHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LoopbackHTTPServer(("127.0.0.1", 0), GPBridgeHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address
        cls.base_url = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request_json(self, method, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if data is not None else {},
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = json.loads(error.read().decode("utf-8"))
            return error.code, body

    def test_health_endpoint_over_real_http(self):
        status, body = self.request_json("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertTrue(body["projectApi"])
        self.assertEqual(body["bridgeVersion"], "0.3")
        self.assertTrue(body["pythonInterop"]["available"])
        self.assertFalse(body["pythonInterop"]["defaultEnabled"])
        self.assertIn("math.sqrt", body["pythonInterop"]["allowlist"])
        self.assertEqual(body["hostCapabilities"]["abiVersion"], 1)
        self.assertTrue(body["hostCapabilities"]["defaultEnabled"])
        self.assertIn(
            "gp.core.v1.math.sqrt",
            [item["identifier"] for item in body["hostCapabilities"]["capabilities"]],
        )

    def test_configured_public_host_is_accepted_over_real_http(self):
        request = urllib.request.Request(
            self.base_url + "/api/health",
            headers={"Host": "gp.gptv.online", "Origin": "https://gp.gptv.online"},
        )
        environment = {
            "GP_BRIDGE_HOSTS": "127.0.0.1,localhost,gp.gptv.online",
            "GP_BRIDGE_ORIGINS": "https://gp.gptv.online",
        }
        with patch.dict(os.environ, environment):
            with urllib.request.urlopen(request, timeout=8) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(
                    response.headers.get("Access-Control-Allow-Origin"),
                    "https://gp.gptv.online",
                )

    def test_unconfigured_public_host_is_rejected_over_real_http(self):
        request = urllib.request.Request(
            self.base_url + "/api/health",
            headers={"Host": "attacker.invalid"},
        )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(request, timeout=8)
        self.assertEqual(context.exception.code, 403)

    def test_vite_dev_origin_preflight_over_real_http(self):
        request = urllib.request.Request(
            self.base_url + "/api/compile-project",
            method="OPTIONS",
            headers={"Origin": "http://localhost:5173"},
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            self.assertEqual(response.status, 204)
            self.assertEqual(
                response.headers.get("Access-Control-Allow-Origin"),
                "http://localhost:5173",
            )
            self.assertIn("POST", response.headers.get("Access-Control-Allow-Methods", ""))

    def test_run_endpoint_over_real_http_can_opt_in_to_python(self):
        status, body = self.request_json("POST", "/api/run", {
            "fileName": "principal.gp",
            "source": 'mostrar("Python:", py_chamar("math.sqrt", [144]))',
            "pythonInterop": True,
        })
        self.assertEqual(status, 200, body)
        self.assertTrue(body["ok"], body["stderr"])
        self.assertIn("Python: 12.0", body["stdout"])

    def test_run_endpoint_over_real_http_rejects_non_boolean_python_interop(self):
        status, body = self.request_json("POST", "/api/run", {
            "fileName": "principal.gp",
            "source": "mostrar(1)",
            "pythonInterop": "true",
        })
        self.assertEqual(status, 400)
        self.assertIn("precisa ser booleano", body["error"])

    def test_project_compile_endpoint_over_real_http(self):
        status, body = self.request_json("POST", "/api/compile-project", {
            "entryFile": "app/principal.gp",
            "files": [
                {
                    "path": "app/principal.gp",
                    "source": 'usar "lib/matematica.gp" como math\nmostrar(math.somar(20, 22))',
                },
                {
                    "path": "app/lib/matematica.gp",
                    "source": (
                        "funcao somar(numero a, numero b) -> numero {\n"
                        "    retornar a + b\n"
                        "}\n"
                    ),
                },
            ],
        })
        self.assertEqual(status, 200, body)
        self.assertTrue(body["ok"], body["stderr"])
        self.assertEqual(body["exitCode"], 0)
        self.assertIn("bytecode binário v2", body["stdout"])

    def test_project_run_endpoint_over_real_http(self):
        status, body = self.request_json("POST", "/api/run-project", {
            "entryFile": "app/principal.gp",
            "files": [
                {
                    "path": "app/principal.gp",
                    "source": 'usar "lib/matematica.gp" como math\nmostrar("HTTP:", math.somar(19, 23))',
                },
                {
                    "path": "app/lib/matematica.gp",
                    "source": (
                        "funcao somar(numero a, numero b) -> numero {\n"
                        "    retornar a + b\n"
                        "}\n"
                    ),
                },
            ],
        })
        self.assertEqual(status, 200, body)
        self.assertTrue(body["ok"], body["stderr"])
        self.assertIn("HTTP: 42", body["stdout"])

    def test_project_run_endpoint_over_real_http_can_opt_in_to_python(self):
        status, body = self.request_json("POST", "/api/run-project", {
            "entryFile": "app/principal.gp",
            "files": [{
                "path": "app/principal.gp",
                "source": 'mostrar("Python:", py_chamar("math.sqrt", [169]))',
            }],
            "pythonInterop": True,
        })
        self.assertEqual(status, 200, body)
        self.assertTrue(body["ok"], body["stderr"])
        self.assertIn("Python: 13.0", body["stdout"])

    def test_project_endpoint_rejects_outside_import_over_real_http(self):
        status, body = self.request_json("POST", "/api/compile-project", {
            "entryFile": "app/principal.gp",
            "files": [
                {
                    "path": "app/principal.gp",
                    "source": 'usar "../../escape.gp" como x\nmostrar(1)',
                },
            ],
        })
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])
        self.assertIn("sair do diretório", body["error"])

    def test_single_file_endpoint_rejects_import_over_real_http(self):
        status, body = self.request_json("POST", "/api/compile", {
            "fileName": "principal.gp",
            "source": 'usar "modulo.gp" como modulo\nmostrar(1)',
        })
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])
        self.assertIn("projeto completo", body["error"])


if __name__ == "__main__":
    unittest.main()
