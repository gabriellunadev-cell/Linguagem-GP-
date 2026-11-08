import contextlib
import io
import unittest
import tempfile
from pathlib import Path

from gp import GPError, run_source


class GPLanguageTests(unittest.TestCase):
    def execute(self, source):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            run_source(source)
        return output.getvalue().strip().splitlines()

    def test_legacy_language(self):
        output = self.execute('''
            programa "v0.1"
            numero x = (10 + 5) * 2
            se (x == 30) { mostrar("ok") } senao { mostrar("erro") }
        ''')
        self.assertEqual(output, ["ok"])

    def test_if_without_else_and_explicit_empty_else(self):
        output = self.execute("""
            numero value = 0
            se (falso) { value = 1 }
            se (falso) { value = 2 } senao {}
            mostrar(value)
        """)
        self.assertEqual(output, ["0"])

    def test_functions_recursion_and_return(self):
        output = self.execute('''
            funcao fatorial(numero n) -> numero {
                se (n <= 1) { retornar 1 }
                retornar n * fatorial(n - 1)
            }
            mostrar(fatorial(5))
        ''')
        self.assertEqual(output, ["120"])

    def test_for_while_and_arrays(self):
        output = self.execute('''
            lista numero dados = [2, 3, 4]
            numero soma = 0
            para (numero i = 0; i < 3; i = i + 1) {
                soma = soma + dados[i]
            }
            numero n = 0
            enquanto (n < 2) { n = n + 1 }
            mostrar(soma, n)
        ''')
        self.assertEqual(output, ["9 2"])

    def test_structs_and_field_assignment(self):
        output = self.execute('''
            estrutura Pessoa { texto nome; numero idade; }
            Pessoa p = Pessoa { nome: "Luna", idade: 2 }
            p.idade = p.idade + 1
            mostrar(p.nome, p.idade)
        ''')
        self.assertEqual(output, ["Luna 3"])

    def test_lexical_scope(self):
        with self.assertRaisesRegex(GPError, "não definido"):
            self.execute('''
                se (verdadeiro) { numero interno = 7 }
                mostrar(interno)
            ''')

    def test_type_safety(self):
        with self.assertRaisesRegex(GPError, "Tipo incompatível"):
            self.execute('numero idade = "vinte";')

    def test_array_bounds(self):
        with self.assertRaisesRegex(GPError, "fora dos limites"):
            self.execute('lista numero itens = [1]; mostrar(itens[3]);')

    def test_function_argument_count(self):
        with self.assertRaisesRegex(GPError, "esperava 2 argumento"):
            self.execute('''
                funcao somar(numero a, numero b) -> numero { retornar a + b }
                mostrar(somar(1))
            ''')

    def test_typed_variable_assignment(self):
        with self.assertRaisesRegex(GPError, "Tipo incompatível na atribuição"):
            self.execute('numero idade = 29; idade = "vinte";')

    def test_typed_array_item_assignment(self):
        with self.assertRaisesRegex(GPError, "Tipo incompatível no array"):
            self.execute('lista numero valores = [1, 2]; valores[0] = "erro";')

    def test_return_outside_function(self):
        with self.assertRaisesRegex(GPError, "dentro de uma função"):
            self.execute('retornar 10;')

    def test_break_outside_loop(self):
        with self.assertRaisesRegex(GPError, "dentro de um laço"):
            self.execute('quebrar;')

    def test_standard_library_array_functions(self):
        output = self.execute('''
            lista numero valores = [1, 2]
            adicionar(valores, 3)
            numero removido = remover(valores, 0)
            mostrar(tamanho(valores), removido, valores[0])
        ''')
        self.assertEqual(output, ["2 1 2"])

    def test_standard_library_text_join(self):
        output = self.execute("""
            lista texto partes = ["Olá", " ", "GP", " 🚀"]
            lista texto vazia = []
            mostrar(unir_textos(partes))
            mostrar(tamanho(unir_textos(vazia)))
        """)
        self.assertEqual(output, ["Olá GP 🚀", "0"])

    def test_standard_library_text_join_rejects_non_text_items(self):
        with self.assertRaisesRegex(GPError, "todos os itens sejam texto"):
            self.execute("""
                lista numero partes = [1, 2, 3]
                mostrar(unir_textos(partes))
            """)

    def test_module_import_and_namespace(self):
        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory) / "matematica.gp"
            module.write_text('''
                funcao somar(numero a, numero b) -> numero {
                    retornar a + b
                }
            ''', encoding="utf-8")
            source = '''
                usar "matematica.gp" como math
                mostrar(math.somar(20, 22))
            '''
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                run_source(source, base_dir=directory)
            self.assertEqual(output.getvalue().strip(), "42")

    def test_function_cannot_break_callers_loop(self):
        with self.assertRaisesRegex(GPError, "quebrar só pode ser usado"):
            self.execute('''
                funcao escapar() { quebrar }
                numero n = 0
                enquanto (n < 1) {
                    escapar()
                    n = n + 1
                }
            ''')

    def test_break_and_continue_inside_loops(self):
        output = self.execute('''
            numero soma = 0
            para (numero i = 0; i < 6; i = i + 1) {
                se (i == 1) { continuar }
                se (i == 4) { quebrar }
                soma = soma + i
            }
            mostrar(soma)
        ''')
        self.assertEqual(output, ["5"])

    def test_function_return_type_is_checked(self):
        with self.assertRaisesRegex(GPError, "Retorno de idade incompatível"):
            self.execute('''
                funcao idade() -> numero { retornar "vinte e nove" }
                idade()
            ''')


if __name__ == "__main__":
    unittest.main(verbosity=2)
