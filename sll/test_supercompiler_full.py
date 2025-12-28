import unittest
from sll.parser import parse, Parser, tokenize
from sll.supercompiler import Supercompiler
from sll.residualizer import Residualizer
from sll.ast_nodes import TypeExpr

CODE = """
type [Nat] : Z | S [Nat] .
type [Bool] : True | False .

<< Классическое сложение >>
fun (add [Nat] [Nat]) -> [Nat] :
    (add [Z] y) -> y
  | (add [S x] y) -> [S (add x y)] .

<< Сложение с аккумулятором (пример из методички, где растет второй аргумент) >>
fun (addAcc [Nat] [Nat]) -> [Nat] :
    (addAcc [Z] y) -> y
  | (addAcc [S x] y) -> (addAcc x [S y]) .

<< Проверка равенства >>
fun (eq [Nat] [Nat]) -> [Bool] :
    (eq [Z] [Z]) -> [True]
  | (eq [Z] [S x]) -> [False]
  | (eq [S x] [Z]) -> [False]
  | (eq [S x] [S y]) -> (eq x y) .
"""


class TestSupervisorFullIntegration(unittest.TestCase):

    def setUp(self):
        self.prog = parse(CODE)
        self.nat_type = TypeExpr("Nat", [])

    def run_spsc(self, expr_text, var_names):
        """Хелпер: запускает полный цикл суперкомпиляции."""
        print(f"\n--- Supercompiling: {expr_text} ---")

        # 1. Парсинг выражения
        start_expr = Parser(tokenize(expr_text)).parse_expr()

        # 2. Подготовка типов переменных
        start_var_types = {name: self.nat_type for name in var_names}

        # 3. Суперкомпиляция
        sc = Supercompiler(self.prog)
        sc.build_tree(start_expr, start_var_types)

        # 4. Резидуализация
        res = Residualizer(sc.tree)
        new_prog = res.residualize()

        print(f"Result:\n{new_prog}")
        return str(new_prog)

    def test_1_partial_eval(self):
        """
        Тест 1: add([S Z], a) -> [S a].
        Проверяем, что драйвер умеет вычислять код (Transient Step).
        """
        res = self.run_spsc("(add [S [Z]] a)", ["a"])

        self.assertNotIn("(add", res, "Вызов add должен исчезнуть")
        self.assertIn("S", res, "Конструктор S должен остаться")
        # Ожидаем что-то вроде: (f1 a) -> [S a]

    def test_2_folding(self):
        """
        Тест 2: add(a, b).
        Проверяем Folding (свертку).
        Граф должен зациклиться на корне, результат — рекурсивная функция.
        """
        res = self.run_spsc("(add a b)", ["a", "b"])

        # Должна сгенерироваться G-функция (ветвление по a)
        self.assertTrue("g1" in res or "f1" in res)
        # Должен быть рекурсивный вызов (имя функции встречается в теле)
        # Например: (g1 [S v1] v2) -> [S (g1 v1 v2)]
        self.assertTrue(any(line.count(line.split(' ')[0][1:]) > 1 for line in res.split('\n') if "->" in line))

    def test_3_generalization(self):
        """
        Тест 3: add(a, a).
        Это тест на СВИСТОК (HE) + MSG.
        add(a, a) -> ... -> add(v1, S v1).
        Это вложение! Должно сработать обобщение.
        """
        res = self.run_spsc("(add a a)", ["a"])

        # Если бы свисток не сработал, тест бы завис (RecursionError/Timeout).
        # Если мы получили результат — значит, HE и MSG отработали.
        self.assertTrue(len(res) > 0)

    def test_4_turchin_relation(self):
        """
        Тест 4: addAcc(a, b).
        Это тест на "Отношение Турчина" (рост аккумулятора).
        addAcc(a, b) -> ... -> addAcc(a', S(b)).
        HE должен увидеть, что addAcc(a, b) <| addAcc(a', S(b)) и свистнуть.
        """
        res = self.run_spsc("(addAcc a b)", ["a", "b"])

        # Опять же, главный критерий — завершаемость.
        # Результат будет (g1 a b), так как MSG обобщит S(b) до переменной.
        self.assertTrue(len(res) > 0)

        # Проверим, что нет бесконечного разворачивания S(S(S...))
        self.assertNotIn("[S [S [S", res)


if __name__ == '__main__':
    unittest.main()
