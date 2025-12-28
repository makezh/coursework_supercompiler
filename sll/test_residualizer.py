import unittest
from sll.parser import parse, Parser, tokenize
from sll.supercompiler import Supercompiler
from sll.residualizer import Residualizer
from sll.ast_nodes import TypeExpr

# Расширенная библиотека для тестов
CODE = """
type [Nat] : Z | S [Nat] .
type [List a] : Nil | Cons a [List a] .

<< Обычное сложение >>
fun (add [Nat] [Nat]) -> [Nat] :
    (add [Z] y) -> y
  | (add [S x] y) -> [S (add x y)] .

<< Функция, которая просто создает структуру (для теста Decompose) >>
fun (wrap [Nat]) -> [List [Nat]] :
    (wrap x) -> [Cons x [Nil]] .

<< Функция с двумя ветвлениями (для проверки генерации G-функций) >>
fun (isZero [Nat]) -> [Nat] :
    (isZero [Z]) -> [S [Z]]   
  | (isZero [S x]) -> [Z] .  
"""

class TestResidualizerExtended(unittest.TestCase):

    def setUp(self):
        self.prog = parse(CODE)
        self.sc = Supercompiler(self.prog)
        # Тип по умолчанию для всех переменных в тестах
        self.nat_type = TypeExpr("Nat", [])

    def _compile(self, expr_text, var_names=None):
        """
        Хелпер: парсит выражение, строит дерево (с типами!), резидуализует.
        var_names: список имен переменных, которые есть в выражении (все считаем Nat).
        """
        expr = Parser(tokenize(expr_text)).parse_expr()

        # Собираем контекст типов (Type Environment)
        # Для простоты считаем, что все переменные в тестах имеют тип [Nat]
        start_var_types = {}
        if var_names:
            for name in var_names:
                start_var_types[name] = self.nat_type

        # Запускаем суперкомпиляцию с типами!
        self.sc.build_tree(expr, start_var_types)

        res = Residualizer(self.sc.tree)
        return res.residualize()

    def test_1_constants_and_decompose(self):
        """
        Тест 1: Восстановление конструкторов (Decompose).
        Выражение: [S [S [Z]]] (Число 2).
        Переменных нет.
        """
        print("\n--- Test 1: Constants ---")
        new_prog = self._compile("[S [S [Z]]]", var_names=[])
        print(new_prog)

        # Ожидаем: f1() -> [S [S [Z]]]
        code = str(new_prog)
        self.assertIn("[S [S [Z]]]", code)
        self.assertTrue(any(r.pattern.name.startswith("f") for r in new_prog.rules))

    def test_2_function_wrapping(self):
        """
        Тест 2: Вычисление функции, создающей структуру.
        (wrap a) -> [Cons a [Nil]]
        Переменная: a.
        """
        print("\n--- Test 2: Wrapping ---")
        new_prog = self._compile("(wrap a)", var_names=["a"])
        print(new_prog)

        code = str(new_prog)
        # Ожидаем, что wrap исчезнет (раскроется)
        self.assertNotIn("(wrap", code)
        # Результат должен быть конструктором
        self.assertIn("Cons", code)
        self.assertIn("Nil", code)

    def test_3_branching_g_function(self):
        """
        Тест 3: Генерация G-функции (Type-Based Branching).
        (isZero x) -> ветвится по x (Z и S).
        """
        print("\n--- Test 3: G-Function Generation ---")
        new_prog = self._compile("(isZero x)", var_names=["x"])
        print(new_prog)

        # Должна появиться g-функция
        rules = new_prog.rules
        g_rules = [r for r in rules if r.pattern.name.startswith("g")]

        self.assertGreaterEqual(len(g_rules), 2, "Должно быть 2 правила (Z и S) для g-функции")

        patterns = [str(r.pattern) for r in g_rules]
        self.assertTrue(any("Z" in p for p in patterns))
        self.assertTrue(any("S" in p for p in patterns))

    def test_4_recursion_folding(self):
        """
        Тест 4: Рекурсия и Свертка (Folding).
        (add a b).
        """
        print("\n--- Test 4: Recursion ---")
        new_prog = self._compile("(add a b)", var_names=["a", "b"])
        print(new_prog)

        # Ищем рекурсивный вызов: g1(...) вызывает g1(...)
        recursive_found = False
        for r in new_prog.rules:
            func_name = r.pattern.name
            if func_name in str(r.body):
                recursive_found = True
                break

        self.assertTrue(recursive_found, "Сгенерированная программа должна быть рекурсивной")

    def test_5_generalization_structure(self):
        """
        Тест 5: Обобщение (Generalization).
        (add a a).
        Проверяем, что суперкомпиляция завершается успешно и генерирует код.
        """
        print("\n--- Test 5: Generalization (add a a) ---")
        new_prog = self._compile("(add a a)", var_names=["a"])
        print(new_prog)

        # Проверка 1: Программа не пустая
        self.assertTrue(len(new_prog.rules) > 0)

        # Проверка 2: Результат должен быть корректным кодом.
        # Поскольку add(a, a) обобщается до add(x, y), мы ожидаем увидеть
        # структуру рекурсивного сложения (ветвление на Z и S).
        code_str = str(new_prog)
        self.assertIn("Z", code_str)
        self.assertIn("S", code_str)

if __name__ == '__main__':
    unittest.main()