import contextlib
import io
import unittest

from gp_compile import compile_source
from gpcompiler.host_abi import (
    HOST_ABI_PREFIX,
    HOST_ABI_VERSION,
    HOST_MAX_CALLS_PER_RUN,
    HOST_CAPABILITIES,
    HostABI,
    HostABIError,
    host_capabilities_manifest,
)
from gpcompiler.vm import GPVirtualMachine, GPVMError


class HostABITests(unittest.TestCase):
    def run_gp(self, source):
        _ast, _ir, bytecode = compile_source(source)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(bytecode)
        return output.getvalue()

    def test_abi_is_versioned_and_manifest_is_stable(self):
        manifest = host_capabilities_manifest()
        self.assertEqual(HOST_ABI_VERSION, 1)
        self.assertEqual(HOST_ABI_PREFIX, "gp.core.v1.")
        self.assertEqual(manifest["abiVersion"], HOST_ABI_VERSION)
        self.assertTrue(manifest["defaultEnabled"])
        self.assertEqual(manifest["maxCallsPerRun"], HOST_MAX_CALLS_PER_RUN)
        self.assertEqual(
            [item["identifier"] for item in manifest["capabilities"]],
            sorted(HOST_CAPABILITIES),
        )
        self.assertGreaterEqual(len(HOST_CAPABILITIES), 20)

    def test_bootstrap_interpreter_uses_the_same_host_abi(self):
        from gp import run_source
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            run_source('mostrar(host_chamar("gp.core.v1.math.factorial", [5]))')
        self.assertEqual(output.getvalue(), "120\n")

    def test_gp_host_capabilities_run_without_python_opt_in(self):
        output = self.run_gp(
            'numero raiz = host_chamar("gp.core.v1.math.sqrt", [81])\n'
            'numero fatorial = host_chamar("gp.core.v1.math.factorial", [5])\n'
            'numero divisor = host_chamar("gp.core.v1.math.gcd", [18, 24])\n'
            'mostrar(raiz, fatorial, divisor)'
        )
        self.assertEqual(output, "9.0 120 6\n")

    def test_statistics_capabilities(self):
        output = self.run_gp(
            'numero media = host_chamar("gp.core.v1.statistics.mean", [[2, 4, 6, 8]])\n'
            'numero mediana = host_chamar("gp.core.v1.statistics.median", [[1, 3, 5]])\n'
            'numero variancia = host_chamar("gp.core.v1.statistics.pvariance", [[2, 4, 6]])\n'
            'mostrar(media, mediana, variancia)'
        )
        self.assertEqual(output, "5.0 3.0 2.6666666666666665\n")

    def test_gp_host_calls_python_and_selfhosted_frontends_share_call_shape(self):
        from gp_compile import compile_source_selfhosted_document
        source = 'mostrar(host_chamar("gp.core.v1.math.factorial", [6]))'
        document = compile_source_selfhosted_document(source)
        from gpcompiler.bytecode import encode_canonical_ir
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            GPVirtualMachine().run_bytes(encode_canonical_ir(document))
        self.assertEqual(output.getvalue(), "720\n")

    def test_unknown_capability_is_rejected_without_dynamic_resolution(self):
        bridge = HostABI()
        with self.assertRaisesRegex(HostABIError, "desconhecida"):
            bridge.call("gp.core.v1.os.system", ["echo nope"])
        with self.assertRaisesRegex(HostABIError, "desconhecida"):
            bridge.call("math.sqrt", [81])

    def test_host_abi_rejects_invalid_signatures_and_domains(self):
        bridge = HostABI()
        with self.assertRaisesRegex(HostABIError, "lista"):
            bridge.call("gp.core.v1.statistics.mean", 42)
        with self.assertRaisesRegex(HostABIError, "exige 1"):
            bridge.call("gp.core.v1.math.sqrt", [])
        with self.assertRaisesRegex(HostABIError, "negativo"):
            bridge.call("gp.core.v1.math.sqrt", [-1])
        with self.assertRaisesRegex(HostABIError, "entre 0 e 18"):
            bridge.call("gp.core.v1.math.factorial", [19])
        with self.assertRaisesRegex(HostABIError, "entre 2"):
            bridge.call("gp.core.v1.statistics.stdev", [[1]])

    def test_host_abi_rejects_nonfinite_inputs_except_finite_probe(self):
        bridge = HostABI()
        with self.assertRaisesRegex(HostABIError, "finito"):
            bridge.call("gp.core.v1.math.sqrt", [float("inf")])
        self.assertFalse(bridge.call("gp.core.v1.math.is_finite", [float("inf")]))
        self.assertTrue(bridge.call("gp.core.v1.math.is_finite", [12]))

    def test_host_abi_rejects_oversized_lists_and_unsafe_integers(self):
        bridge = HostABI()
        with self.assertRaisesRegex(HostABIError, "10.000"):
            bridge.call("gp.core.v1.statistics.mean", [[1] * 10_001])
        with self.assertRaisesRegex(HostABIError, "limite seguro"):
            bridge.call("gp.core.v1.math.factorial", [2**53])

    def test_host_abi_call_budget_resets_per_execution(self):
        bridge = HostABI(max_calls=1)
        self.assertEqual(bridge.call("gp.core.v1.math.factorial", [5]), 120)
        with self.assertRaisesRegex(HostABIError, "limite de chamadas"):
            bridge.call("gp.core.v1.math.factorial", [6])
        bridge.reset()
        self.assertEqual(bridge.call("gp.core.v1.math.factorial", [6]), 720)

    def test_vm_resets_host_budget_at_each_program_execution(self):
        _ast, _ir, bytecode = compile_source(
            'mostrar(host_chamar("gp.core.v1.math.factorial", [5]))'
        )
        vm = GPVirtualMachine()
        for _ in range(2):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                vm.run_bytes(bytecode)
            self.assertEqual(output.getvalue(), "120\n")


if __name__ == "__main__":
    unittest.main()
