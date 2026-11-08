import json
import unittest

from gpcompiler.bytecode import BINARY_MAGIC, decode, encode, encode_canonical_ir
from gpcompiler.ir import IRFunction, IRInstruction, IRProgram, IR_VERSION, validate_ir
from gpcompiler.lower import ir_to_dict


class GPIRValidationTests(unittest.TestCase):
    def program(self, code=None, functions=None, ir_version=IR_VERSION):
        return IRProgram("0.4", code or [], functions or {}, ir_version)

    def test_format_version_is_independent_of_language_version(self):
        program = self.program([IRInstruction("CONST", (7,))])
        validate_ir(program)
        self.assertEqual(program.version, "0.4")
        self.assertEqual(program.ir_version, 1)
        self.assertEqual(ir_to_dict(program)["ir_version"], 1)

    def test_encoder_emits_explicit_ir_version_inside_v2_container(self):
        payload = decode(encode(self.program([IRInstruction("CONST", (7,))])))
        self.assertEqual(payload["bytecode_version"], 2)
        self.assertEqual(payload["program"]["ir_version"], 1)
        self.assertEqual(payload["language_version"], "0.4")

    def test_direct_canonical_encoder_is_byte_identical_to_typed_encoder(self):
        function = IRFunction(
            "fatorial",
            [("numero", "n")],
            "numero",
            [
                IRInstruction("LOAD", ("n",)),
                IRInstruction("CONST", (1,)),
                IRInstruction("LE"),
                IRInstruction("JUMP_IF_FALSE", (5,)),
                IRInstruction("CONST", (1,)),
                IRInstruction("RETURN"),
                IRInstruction("LOAD", ("n",)),
                IRInstruction("LOAD", ("n",)),
                IRInstruction("CONST", (1,)),
                IRInstruction("SUB"),
                IRInstruction("CALL", ("fatorial", 1)),
                IRInstruction("MUL"),
                IRInstruction("RETURN"),
            ],
        )
        program = self.program([
            IRInstruction("CONST", ("Ada",)),
            IRInstruction("CONST", (37,)),
            IRInstruction("BUILD_STRUCT", ("Pessoa", [("nome", "texto"), ("idade", "numero")])),
            IRInstruction("PRINT", (1,)),
            IRInstruction("CONST", (1,)),
            IRInstruction("CONST", (2,)),
            IRInstruction("BUILD_ARRAY", (2,)),
            IRInstruction("DECLARE", ("valores", "lista", "numero")),
            IRInstruction("JUMP", (9,)),
        ], {"fatorial": function})
        document = json.loads(json.dumps(ir_to_dict(program)))
        # Match the field order emitted by the GP frontend, not the legacy adapter.
        fn = document["functions"]["fatorial"]
        document["functions"]["fatorial"] = {
            "return_type": fn["return_type"],
            "parameters": fn["parameters"],
            "code": fn["code"],
        }
        direct = encode_canonical_ir(document)
        legacy = encode(program)
        self.assertEqual(direct, legacy)
        self.assertEqual(decode(direct), decode(legacy))

    def test_direct_encoder_rejects_unknown_opcode_without_hydration(self):
        document = {
            "format": "GP-IR", "ir_version": 1, "version": "0.4",
            "main": [{"op": "OPCODE_INVENTADO", "args": []}], "functions": {},
        }
        with self.assertRaisesRegex(ValueError, "opcode/operandos inválidos"):
            encode_canonical_ir(document)

    def test_both_ir_boundaries_reject_integer_outside_binary_numeric_range(self):
        too_large = 10 ** 500
        with self.assertRaisesRegex(ValueError, "fora do intervalo"):
            validate_ir(self.program([IRInstruction("CONST", (too_large,))]))
        with self.assertRaisesRegex(ValueError, "fora do intervalo"):
            encode_canonical_ir({
                "format": "GP-IR", "ir_version": 1, "version": "0.4",
                "main": [{"op": "CONST", "args": [too_large]}], "functions": {},
            })

    def test_canonical_encoder_rejects_extra_root_fields(self):
        document = {
            "format": "GP-IR", "ir_version": 1, "version": "0.4",
            "main": [], "functions": {}, "x-extension": True,
        }
        with self.assertRaisesRegex(ValueError, "envelope inválido"):
            encode_canonical_ir(document)

    def test_canonical_encoder_rejects_extra_function_fields(self):
        document = {
            "format": "GP-IR", "ir_version": 1, "version": "0.4",
            "main": [],
            "functions": {
                "f": {
                    "return_type": None,
                    "parameters": [],
                    "code": [],
                    "x-extension": True,
                }
            },
        }
        with self.assertRaisesRegex(ValueError, "definição inválida"):
            encode_canonical_ir(document)

    def test_rejects_unknown_ir_version(self):
        with self.assertRaisesRegex(ValueError, "versão de formato"):
            validate_ir(self.program(ir_version=2))

    def test_rejects_unknown_opcode(self):
        with self.assertRaisesRegex(ValueError, "opcode desconhecido"):
            validate_ir(self.program([IRInstruction("FUTURE_OP")]))

    def test_rejects_bad_operand_arity(self):
        with self.assertRaisesRegex(ValueError, "aridade inválida"):
            validate_ir(self.program([IRInstruction("LOAD", ())]))

    def test_rejects_boolean_jump_target(self):
        with self.assertRaisesRegex(ValueError, "inteiro não negativo"):
            validate_ir(self.program([IRInstruction("JUMP", (True,))]))

    def test_rejects_jump_past_end(self):
        with self.assertRaisesRegex(ValueError, "destino de salto fora"):
            validate_ir(self.program([IRInstruction("JUMP", (2,))]))

    def test_rejects_non_finite_constant(self):
        with self.assertRaisesRegex(ValueError, "constante não finita"):
            validate_ir(self.program([IRInstruction("CONST", (float("inf"),))]))

    def test_rejects_duplicate_function_parameters(self):
        fn = IRFunction("f", [("numero", "x"), ("texto", "x")], None, [])
        with self.assertRaisesRegex(ValueError, "parâmetro duplicado"):
            validate_ir(self.program(functions={"f": fn}))

    def test_rejects_mismatched_function_map_key(self):
        fn = IRFunction("other", [], None, [])
        with self.assertRaisesRegex(ValueError, "definição inconsistente"):
            validate_ir(self.program(functions={"f": fn}))

    def test_rejects_duplicate_struct_fields(self):
        ins = IRInstruction("BUILD_STRUCT", ("Pessoa", [("nome", "texto"), ("nome", "texto")]))
        with self.assertRaisesRegex(ValueError, "campo duplicado"):
            validate_ir(self.program([ins]))

    def test_decoder_rejects_explicit_unknown_ir_version(self):
        data = encode(self.program([IRInstruction("CONST", (1,))]))
        payload = decode(data)
        payload["program"]["ir_version"] = 99
        import zlib, struct
        raw = json.dumps(payload, separators=(",", ":")).encode()
        altered = struct.pack(">4sHII", BINARY_MAGIC, 2, len(raw), zlib.crc32(raw) & 0xffffffff) + zlib.compress(raw, 9)
        with self.assertRaisesRegex(ValueError, "Versão GP-IR não suportada"):
            decode(altered)


if __name__ == "__main__":
    unittest.main()
