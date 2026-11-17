import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gp_compile import compile_source
from gpcompiler.python_interop import (
    MAX_CALLS_PER_RUN,
    PythonInterop,
    PythonInteropError,
)
from gpcompiler.vm import GPVirtualMachine, GPVMError


class PythonInteropTests(unittest.TestCase):
    def run_gp(self, source: str, *, enabled: bool = True) -> str:
        _ast, _ir, bytecode = compile_source(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine(python_interop=enabled).run_bytes(bytecode)
        return output.getvalue()

    def test_gp_calls_allowlisted_math_and_statistics(self):
        output = self.run_gp(
            'numero raiz = py_chamar("math.sqrt", [81])\n'
            'numero media = py_chamar("statistics.mean", [[2, 4, 6, 8]])\n'
            'mostrar(raiz, media)'
        )
        self.assertEqual(output, "9.0 5.0\n")

    def test_gp_can_import_python_convenience_library(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".gp", prefix="gp-python-library-", dir=root,
            encoding="utf-8", delete=False
        ) as stream:
            source_path = Path(stream.name)
            stream.write(
                'usar "biblioteca/python.gp" como py\n'
                'numero raiz = py.raiz_quadrada(81)\n'
                'numero media = py.media([2, 4, 6, 8])\n'
                'mostrar(raiz, media)'
            )
        try:
            _ast, _ir, bytecode = compile_source(
                source_path.read_text(encoding="utf-8"), source_path=source_path
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                GPVirtualMachine(python_interop=True).run_bytes(bytecode)
            self.assertEqual(output.getvalue(), "9.0 5.0\n")
        finally:
            source_path.unlink(missing_ok=True)

    def test_gp_calls_hashlib_and_unicode_standard_library(self):
        output = self.run_gp(
            'texto digest = py_chamar("hashlib.sha256", ["GP"])\n'
            'texto normalizado = py_chamar("unicodedata.normalize", ["NFC", "á"])\n'
            'mostrar(tamanho(digest), normalizado)'
        )
        self.assertEqual(output, "64 á\n")

    def test_python_interop_is_disabled_by_default(self):
        _ast, _ir, bytecode = compile_source(
            'mostrar(py_chamar("math.sqrt", [81]))'
        )
        with self.assertRaisesRegex(GPVMError, "ative --python-interop"):
            GPVirtualMachine().run_bytes(bytecode)

    def test_unknown_modules_and_arbitrary_python_functions_are_rejected(self):
        for capability in ("os.system", "builtins.eval", "subprocess.run", "pathlib.Path.read_text"):
            with self.subTest(capability=capability):
                bridge = PythonInterop()
                with self.assertRaisesRegex(PythonInteropError, "não autorizada"):
                    bridge.call(capability, [])

    def test_python_interop_rejects_wrong_types_and_arity(self):
        bridge = PythonInterop()
        with self.assertRaisesRegex(PythonInteropError, "esperado numero"):
            bridge.call("math.sqrt", ["81"])
        with self.assertRaisesRegex(PythonInteropError, "exige 1 argumento"):
            bridge.call("math.sqrt", [])
        with self.assertRaisesRegex(PythonInteropError, "segundo argumento precisa ser uma lista"):
            bridge.call("math.sqrt", 81)

    def test_python_interop_rejects_out_of_domain_math(self):
        with self.assertRaisesRegex(PythonInteropError, "negativo"):
            PythonInterop().call("math.sqrt", [-1])
        with self.assertRaisesRegex(PythonInteropError, "entre 0 e 18"):
            PythonInterop().call("math.factorial", [19])

    def test_python_interop_rejects_nonfinite_and_nested_oversized_values(self):
        bridge = PythonInterop()
        with self.assertRaisesRegex(PythonInteropError, "finito"):
            bridge.call("math.sqrt", [float("inf")])
        with self.assertRaisesRegex(PythonInteropError, "profundidade máxima"):
            bridge.call("math.sqrt", [[[[[[[[[[81]]]]]]]]]])

    def test_python_interop_limits_calls_per_execution_and_can_reset(self):
        bridge = PythonInterop(max_calls=1)
        self.assertEqual(bridge.call("math.sqrt", [81]), 9.0)
        with self.assertRaisesRegex(PythonInteropError, "limite de chamadas"):
            bridge.call("math.sqrt", [16])
        bridge.reset()
        self.assertEqual(bridge.call("math.sqrt", [16]), 4.0)

    def test_python_interop_default_budget_is_bounded(self):
        self.assertEqual(MAX_CALLS_PER_RUN, 1024)

    def test_compiler_cli_requires_opt_in_and_python_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "interop.gp"
            output = Path(directory) / "interop.gbc"
            source.write_text('mostrar(py_chamar("math.sqrt", [81]))', encoding="utf-8")
            compiler = Path(__file__).resolve().parents[1] / "gp_compile.py"

            enabled = subprocess.run(
                [sys.executable, str(compiler), str(source), "--run", "--run-vm", "python", "--python-interop"],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(enabled.returncode, 0, enabled.stderr)
            self.assertIn("9.0", enabled.stdout)

            wrong_runtime = subprocess.run(
                [sys.executable, str(compiler), str(source), "--run", "--run-vm", "native", "--python-interop"],
                text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(wrong_runtime.returncode, 0)
            self.assertIn("somente com --run-vm python", wrong_runtime.stderr)

            no_run = subprocess.run(
                [sys.executable, str(compiler), str(source), "--python-interop"],
                text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(no_run.returncode, 0)
            self.assertIn("exige --run", no_run.stderr)

            compile_only = subprocess.run(
                [sys.executable, str(compiler), str(source), "--output", str(output)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(compile_only.returncode, 0, compile_only.stderr)
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
