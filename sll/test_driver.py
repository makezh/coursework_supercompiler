import unittest
from sll.parser import parse, Parser, tokenize
from sll.driver import Driver, TransientStep, DecomposeStep, VariantStep, StopStep
from sll.ast_nodes import Ctr, FCall

CODE = """
type [Nat] : Z | S [Nat] .

<< f-функция (равнодушная): просто оборачивает в конструктор >>
fun (f_wrap [Nat]) -> [Nat] :
    (f_wrap x) -> [S x] .

<< g-функция (любопытная): сложение >>
fun (g_add [Nat] [Nat]) -> [Nat] :
    (g_add [Z] y) -> y
  | (g_add [S x] y) -> [S (g_add x y)] .

<< g-функция: сравнение (для тестов глубокой вложенности) >>
fun (g_eq [Nat] [Nat]) -> [Nat] :
    (g_eq [Z] y) -> [Z]
  | (g_eq [S x] y) -> [S [Z]] . 
  
<< Еще одна g-функция для теста вложенной разгонки >>
fun (h_split [Nat]) -> [Nat] :
    (h_split [Z]) -> [Z]
  | (h_split [S x]) -> [S [S x]] .
"""


class TestDriverComprehensive(unittest.TestCase):

    def setUp(self):
        """Инициализация перед каждым тестом"""
        self.prog = parse(CODE)
        self.driver = Driver(self.prog)

    def _parse_expr(self, text):
        """Парсит строку как выражение (Expr), а не как программу"""
        return Parser(tokenize(text)).parse_expr()

    def test_1_stop_atoms(self):
        """Переменные и Литералы -> StopStep"""
        # Переменная
        step = self.driver.drive(self._parse_expr("x"))
        self.assertIsInstance(step, StopStep)

        # Число
        step = self.driver.drive(self._parse_expr("42"))
        self.assertIsInstance(step, StopStep)

    def test_2_decompose(self):
        """Конструктор -> DecomposeStep (разбиение на части)"""
        # [S [Z]] -> args: [[Z]]
        expr = self._parse_expr("[S [Z]]")
        step = self.driver.drive(expr)

        self.assertIsInstance(step, DecomposeStep)
        self.assertEqual(len(step.parts), 1)

        first_part = step.parts[0]
        self.assertIsInstance(first_part, Ctr)
        self.assertEqual(first_part.name, "Z")

    def test_3_f_function(self):
        """F-функция (равнодушная) -> TransientStep (всегда раскрывается)"""
        # (f_wrap a) -> [S a]
        expr = self._parse_expr("(f_wrap a)")
        step = self.driver.drive(expr)

        self.assertIsInstance(step, TransientStep)
        self.assertEqual(str(step.next_expr), "[S a]")

    def test_4_g_function_reduce(self):
        """G-функция с Конструктором -> TransientStep (обычная редукция)"""
        # (g_add [Z] y) -> y
        expr = self._parse_expr("(g_add [Z] y)")
        step = self.driver.drive(expr)

        self.assertIsInstance(step, TransientStep)
        self.assertEqual(str(step.next_expr), "y")

    def test_5_g_function_variant(self):
        """G-функция с Переменной -> VariantStep (Разгонка)"""
        # (g_add x y) -> Разгонка по x
        expr = self._parse_expr("(g_add x y)")
        step = self.driver.drive(expr)

        self.assertIsInstance(step, VariantStep)
        self.assertEqual(len(step.branches), 2)

        # Ветка 1: x -> [Z]
        # (g_add [Z] y) -> y
        res1, contr1 = step.branches[0]
        self.assertEqual(contr1.var_name, "x")
        self.assertEqual(contr1.pattern.name, "Z")
        self.assertEqual(str(res1), "y")

        # Ветка 2: x -> [S v1]
        # (g_add [S v1] y) -> [S (g_add v1 y)]
        res2, contr2 = step.branches[1]
        self.assertEqual(contr2.var_name, "x")
        self.assertEqual(contr2.pattern.name, "S")
        self.assertIsInstance(res2, Ctr)
        self.assertEqual(res2.name, "S")

    def test_6_nested_transient(self):
        """Вложенность: G(F(...)) -> TransientStep"""
        # Выражение: (g_add (f_wrap a) b)
        # Внутренний вызов (f_wrap a) возвращает TransientStep -> [S a]
        # Драйвер должен вернуть TransientStep для внешнего вызова: (g_add [S a] b)
        expr = self._parse_expr("(g_add (f_wrap a) b)")
        step = self.driver.drive(expr)

        self.assertIsInstance(step, TransientStep)
        self.assertEqual(str(step.next_expr), "(g_add [S a] b)")

        # Проверяем следующий шаг: теперь g_add должен сработать, т.к. [S a] - конструктор
        step2 = self.driver.drive(step.next_expr)
        self.assertIsInstance(step2, TransientStep)
        self.assertIn("S", str(step2.next_expr))

    def test_7_nested_variant(self):
        """Вложенность: G(G_inner(...)) -> VariantStep"""
        # Выражение: (g_eq (h_split a) z)
        # Внутренний (h_split a) хочет ветвиться по 'a'.
        # Драйвер должен пробросить это ветвление наружу.
        expr = self._parse_expr("(g_eq (h_split a) z)")
        step = self.driver.drive(expr)

        self.assertIsInstance(step, VariantStep)
        self.assertEqual(len(step.branches), 2)

        # Проверяем, что ветвление идет именно по переменной 'a'
        _, contr = step.branches[0]
        self.assertEqual(contr.var_name, "a")

        # Ветка a=Z: (g_eq (h_split [Z]) z) -> (g_eq [Z] z)
        res1, _ = step.branches[0]
        self.assertEqual(str(res1), "(g_eq [Z] z)")

        # Ветка a=S: (g_eq (h_split [S v1]) z) -> (g_eq [S [S v1]] z)
        res2, _ = step.branches[1]
        self.assertIsInstance(res2, FCall)
        self.assertEqual(res2.name, "g_eq")
        # Первый аргумент g_eq стал [S ...], значит внешний вызов ждет следующего шага
        arg0 = res2.args[0]
        self.assertIsInstance(arg0, Ctr)
        self.assertEqual(arg0.name, "S")


if __name__ == '__main__':
    unittest.main()
