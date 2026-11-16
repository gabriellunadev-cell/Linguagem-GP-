import copy
import unittest

from gpcompiler.module_graph import (
    GPModuleGraph,
    GPModuleImport,
    GPModuleUnit,
    module_graph_from_document,
    validate_module_graph_document,
)


def _nested_graph_document():
    return {
        "format": "GP-MODULE-GRAPH",
        "version": 1,
        "entry": "0",
        "units": [
            {"id": "0", "namespace": "", "parent": None, "alias": None, "exports": []},
            {"id": "1", "namespace": "__gp_namespace_base", "parent": "0", "alias": "base", "exports": ["quatro"]},
            {"id": "2", "namespace": "__gp_namespace_base__core", "parent": "1", "alias": "core", "exports": ["dobrar"]},
        ],
        "imports": [
            {"source": "0", "target": "1", "alias": "base", "path": "base.gp"},
            {"source": "1", "target": "2", "alias": "core", "path": "leaf.gp"},
        ],
        "order": ["2", "1", "0"],
    }


class ModuleGraphContractTests(unittest.TestCase):
    def test_nested_graph_round_trips_to_immutable_records(self):
        document = _nested_graph_document()
        graph = module_graph_from_document(document)
        self.assertEqual(graph.entry_id, "0")
        self.assertEqual(
            graph.dependency_order,
            ("2", "1", "0"),
        )
        self.assertEqual(
            graph.imports[1],
            GPModuleImport("1", "2", "core", "leaf.gp"),
        )
        self.assertEqual(graph.units[2].namespace, "__gp_namespace_base__core")
        self.assertEqual(graph.to_document(), document)

    def test_repeated_source_file_under_distinct_aliases_keeps_distinct_units(self):
        graph = GPModuleGraph(
            entry_id="root",
            units=(
                GPModuleUnit("root", "", None, None, ()),
                GPModuleUnit("left", "__gp_namespace_left", "root", "left", ("value",)),
                GPModuleUnit("right", "__gp_namespace_right", "root", "right", ("value",)),
            ),
            imports=(
                GPModuleImport("root", "left", "left", "shared.gp"),
                GPModuleImport("root", "right", "right", "shared.gp"),
            ),
            dependency_order=("left", "right", "root"),
        )
        document = graph.to_document()
        self.assertEqual(len(document["units"]), 3)
        self.assertEqual(document["units"][1]["exports"], ["value"])
        self.assertEqual(document["units"][2]["exports"], ["value"])
        self.assertNotEqual(document["units"][1]["namespace"], document["units"][2]["namespace"])

    def test_graph_fingerprint_is_deterministic(self):
        graph = module_graph_from_document(_nested_graph_document())
        self.assertEqual(graph.fingerprint(), graph.fingerprint())
        self.assertEqual(len(graph.fingerprint()), 64)

    def test_envelope_rejects_unknown_fields_and_versions(self):
        document = _nested_graph_document()
        extra = copy.deepcopy(document)
        extra["surprise"] = True
        with self.assertRaisesRegex(ValueError, "envelope inválido"):
            validate_module_graph_document(extra)
        wrong_version = copy.deepcopy(document)
        wrong_version["version"] = 2
        with self.assertRaisesRegex(ValueError, "versão não suportada"):
            validate_module_graph_document(wrong_version)

    def test_duplicate_alias_in_same_importer_is_rejected(self):
        document = _nested_graph_document()
        document["units"].append({
            "id": "3", "namespace": "__gp_namespace_other",
            "parent": "0", "alias": "base", "exports": [],
        })
        document["imports"].append({
            "source": "0", "target": "3", "alias": "base", "path": "other.gp",
        })
        document["order"] = ["2", "1", "3", "0"]
        with self.assertRaisesRegex(ValueError, "alias duplicado"):
            validate_module_graph_document(document)

    def test_dependency_must_precede_importer(self):
        document = _nested_graph_document()
        document["order"] = ["1", "2", "0"]
        with self.assertRaisesRegex(ValueError, "dependência deve preceder"):
            validate_module_graph_document(document)

    def test_missing_parent_link_and_unreachable_units_are_rejected(self):
        document = _nested_graph_document()
        document["units"][2]["parent"] = "0"
        with self.assertRaisesRegex(ValueError, "relação pai/alias inconsistente"):
            validate_module_graph_document(document)

        orphan = _nested_graph_document()
        orphan["units"].append({
            "id": "9", "namespace": "__orphan", "parent": "0",
            "alias": "orphan", "exports": [],
        })
        orphan["order"] = ["2", "1", "9", "0"]
        with self.assertRaisesRegex(ValueError, "unidade órfã"):
            validate_module_graph_document(orphan)

    def test_duplicate_and_invalid_exports_are_rejected(self):
        document = _nested_graph_document()
        document["units"][1]["exports"] = ["quatro", "quatro"]
        with self.assertRaisesRegex(ValueError, "export duplicado"):
            validate_module_graph_document(document)
        document["units"][1]["exports"] = ["nome inválido"]
        with self.assertRaisesRegex(ValueError, "export duplicado"):
            validate_module_graph_document(document)

    def test_duplicate_or_forged_namespace_is_rejected(self):
        document = _nested_graph_document()
        document["units"][2]["namespace"] = "__gp_namespace_base"
        with self.assertRaisesRegex(ValueError, "namespace duplicado ou inconsistente"):
            validate_module_graph_document(document)

        document = _nested_graph_document()
        document["units"][1]["namespace"] = "__forged_namespace"
        with self.assertRaisesRegex(ValueError, "namespace duplicado ou inconsistente"):
            validate_module_graph_document(document)

    def test_cycles_and_inconsistent_order_are_rejected(self):
        document = _nested_graph_document()
        document["imports"].append({
            "source": "2", "target": "0", "alias": "root", "path": "main.gp",
        })
        with self.assertRaisesRegex(ValueError, "referência de import inválida|relação pai/alias inconsistente"):
            validate_module_graph_document(document)


    def test_ast_linker_builds_explicit_graph_and_separates_repeated_aliases(self):
        import contextlib
        import io
        import tempfile
        from pathlib import Path

        from gp import Parser, lex
        from gp_compile import compile_source
        from gpcompiler.ast import from_parser_tree
        from gpcompiler.modules import build_module_link_plan
        from gpcompiler.vm import GPVirtualMachine

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "shared.gp").write_text(
                "funcao valor() -> numero { retornar 7 }",
                encoding="utf-8",
            )
            source_path = root / "main.gp"
            source = (
                'usar "shared.gp" como left\n'
                'usar "shared.gp" como right\n'
                "mostrar(left.valor() + right.valor())"
            )
            root_ast = from_parser_tree(Parser(lex(source)).parse())
            plan = build_module_link_plan(root_ast, source_path)
            document = plan.graph.to_document()

            self.assertEqual(document["order"], ["1", "2", "0"])
            self.assertEqual(
                [unit["namespace"] for unit in document["units"]],
                ["", "__gp_namespace_left", "__gp_namespace_right"],
            )
            self.assertEqual(
                [unit["exports"] for unit in document["units"][1:]],
                [["valor"], ["valor"]],
            )

            _, program, bytecode = compile_source(source, source_path=source_path)
            self.assertIn("__gp_namespace_left__valor", program.functions)
            self.assertIn("__gp_namespace_right__valor", program.functions)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                GPVirtualMachine().run_bytes(bytecode)
            self.assertEqual(output.getvalue(), "14\n")

    def test_ast_module_graph_rejects_namespace_collision(self):
        import tempfile
        from pathlib import Path

        from gp import Parser, lex
        from gpcompiler.ast import from_parser_tree
        from gpcompiler.modules import build_module_link_plan

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a.gp").write_text(
                'usar "leaf.gp" como core\nfuncao a() -> numero { retornar core.valor() }',
                encoding="utf-8",
            )
            (root / "b.gp").write_text(
                "funcao valor() -> numero { retornar 1 }",
                encoding="utf-8",
            )
            (root / "leaf.gp").write_text(
                "funcao valor() -> numero { retornar 2 }",
                encoding="utf-8",
            )
            source = (
                'usar "b.gp" como a__core\n'
                'usar "a.gp" como a\n'
                "mostrar(a__core.valor())"
            )
            root_ast = from_parser_tree(Parser(lex(source)).parse())
            with self.assertRaisesRegex(ValueError, "Namespace GP duplicado"):
                build_module_link_plan(root_ast, root / "main.gp")


if __name__ == "__main__":
    unittest.main()
