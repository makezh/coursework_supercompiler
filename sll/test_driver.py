import unittest
from sll.parser import parse, Parser, tokenize
from sll.driver import Driver, TransientStep, DecomposeStep, VariantStep, StopStep
from sll.ast_nodes import TypeExpr

# Программа для тестов (Комментарии исправлены на << >>)
CODE = """
type [Nat] : Z | S [Nat] .
type [List a] : Nil | Cons a [List a] .

<< Функция, которая работает только с Z (частичная) >>
fun (onlyZero [Nat]) -> [Nat] :
    (onlyZero [Z]) -> [Z] .

<< Обычное сложение >>
fun (add [Nat] [Nat]) -> [Nat] :
    (add [Z] y) -> y
  | (add [S x] y) -> [S (add x y)] .

<< Функция с вложенным вызовом >>
fun (double [Nat]) -> [Nat] :
    (double x) -> (add x x) .
    
fun (eq [Nat] [Nat]) -> [Bool] :
    (eq [Z] [Z]) -> [True]
  | (eq [S x] [S y]) -> (eq x y)
  | (eq x y) -> [False] .
"""


class TestRuleBasedDriver(unittest.TestCase):

    def setUp(self):
        self.prog = parse(CODE)
        self.driver = Driver(self.prog)

    def _expr(self, text):
        return Parser(tokenize(text)).parse_expr()

    def test_transient_step(self):
        """Простая редукция: add([Z], y) -> y"""
        expr = self._expr("(add [Z] y)")
        # Типы не важны для редукции, но передадим пустой словарь
        step = self.driver.drive(expr, {})

        self.assertIsInstance(step, TransientStep)
        self.assertEqual(str(step.next_expr), "y")

    def test_partial_function_variants(self):
        """
        Тест на отличие Rule-Based от Type-Based.
        (onlyZero x).
        Rule-Based прогонка должна создать только ветку для Z,
        потому что в функции onlyZero есть только одно правило!
        """
        expr = self._expr("(onlyZero x)")
        var_types = {"x": TypeExpr("Nat", [])}

        step = self.driver.drive(expr, var_types)

        self.assertIsInstance(step, VariantStep)
        # Ожидаем 1 ветку (для Z), так как правило для S отсутствует
        self.assertEqual(len(step.branches), 1)

        br_expr, contr, _ = step.branches[0]
        self.assertEqual(contr.pattern.name, "Z")
        self.assertEqual(str(br_expr), "[Z]")

    def test_add_variants(self):
        """Разгонка (add x y) -> 2 ветки (Z и S), т.к. у add два правила"""
        expr = self._expr("(add x y)")
        var_types = {"x": TypeExpr("Nat", []), "y": TypeExpr("Nat", [])}

        step = self.driver.drive(expr, var_types)

        self.assertIsInstance(step, VariantStep)
        self.assertEqual(len(step.branches), 2)

        # Ветка 1: x=Z (из первого правила)
        self.assertEqual(step.branches[0][1].pattern.name, "Z")
        # Ветка 2: x=S (из второго правила)
        self.assertEqual(step.branches[1][1].pattern.name, "S")

    def test_nested_call(self):
        """
        Вложенный вызов: add(onlyZero(x), y).
        onlyZero(x) требует разгонки x.
        add не может сработать, т.к. аргумент - вызов.
        Драйвер должен 'нырнуть' в onlyZero и вернуть ветвление оттуда.
        """
        expr = self._expr("(add (onlyZero x) y)")
        var_types = {"x": TypeExpr("Nat", []), "y": TypeExpr("Nat", [])}

        step = self.driver.drive(expr, var_types)

        self.assertIsInstance(step, VariantStep)
        # Ветвление идет из onlyZero, там 1 правило -> 1 ветка
        self.assertEqual(len(step.branches), 1)

        # Проверяем, что ветка обернута обратно в add
        br_expr, _, _ = step.branches[0]
        # Результат onlyZero([Z]) -> [Z]. Итоговое: (add [Z] y)
        self.assertEqual(str(br_expr), "(add [Z] y)")

    def test_catch_all_order(self):
        """
        Тест на порядок правил.
        Выражение: (eq x x).

        Ожидание:
        Драйвер должен остановиться на 1-м правиле (eq [Z] [Z]), потому что оно требует сужения x -> Z.
        Он НЕ ДОЛЖЕН проскакивать к 3-му правилу (eq x y), которое дает False.

        Результат должен быть VariantStep (ветвление), а не TransientStep (False).
        """
        expr = self._expr("(eq x x)")
        var_types = {"x": TypeExpr("Nat", [])}

        step = self.driver.drive(expr, var_types)

        # Если драйвер работает неправильно, он вернет TransientStep с [False].
        if isinstance(step, TransientStep):
            self.fail(f"ОШИБКА! Драйвер проскочил сужение и вернул результат: {step.next_expr}")

        # Если правильно - должен вернуть Ветвление
        self.assertIsInstance(step, VariantStep)
        self.assertEqual(len(step.branches), 2) # Z и S
        print("✅ Тест на порядок правил прошел успешно (ветвление вместо False)")


if __name__ == '__main__':
    unittest.main()
