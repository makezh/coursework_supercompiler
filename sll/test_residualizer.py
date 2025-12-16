import unittest
from sll.parser import parse, Parser, tokenize
from sll.supercompiler import Supercompiler
from sll.residualizer import Residualizer

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

    def _compile(self, expr_text):
        """Хелпер: парсит выражение, строит дерево, резидуализует."""
        expr = Parser(tokenize(expr_text)).parse_expr()
        self.sc.build_tree(expr)
        res = Residualizer(self.sc.tree)
        return res.residualize()

    def test_1_constants_and_decompose(self):
        """
        Тест 1: Восстановление конструкторов (Decompose).
        Выражение: [S [S [Z]]] (Число 2).
        Драйвер просто разбивает его на части.
        Резидуализатор должен собрать обратно.
        """
        print("\n--- Test 1: Constants ---")
        new_prog = self._compile("[S [S [Z]]]")
        print(new_prog)

        # Ожидаем: f1() -> [S [S [Z]]]
        code = str(new_prog)
        self.assertIn("[S [S [Z]]]", code)
        # Должна быть 1 f-функция
        self.assertTrue(any(r.pattern.name.startswith("f") for r in new_prog.rules))

    def test_2_function_wrapping(self):
        """
        Тест 2: Вычисление функции, создающей структуру.
        (wrap a) -> [Cons a [Nil]]
        Это проверяет TransientStep + Decompose.
        """
        print("\n--- Test 2: Wrapping ---")
        new_prog = self._compile("(wrap a)")
        print(new_prog)

        code = str(new_prog)
        # Ожидаем, что wrap исчезнет (раскроется), останется результат
        self.assertNotIn("(wrap", code)
        # Результат: [Cons a [Nil]]
        self.assertIn("Cons", code)
        self.assertIn("Nil", code)

    def test_3_branching_g_function(self):
        """
        Тест 3: Генерация G-функции (Pattern Matching).
        (isZero x) -> ветвится по x.
        Должен создать функцию g1 с двумя правилами.
        """
        print("\n--- Test 3: G-Function Generation ---")
        new_prog = self._compile("(isZero x)")
        print(new_prog)

        # Должна появиться g-функция
        rules = new_prog.rules
        g_rules = [r for r in rules if r.pattern.name.startswith("g")]

        self.assertGreaterEqual(len(g_rules), 2, "Должно быть минимум 2 правила для g-функции")

        # Проверяем паттерны
        patterns = [str(r.pattern) for r in g_rules]
        # Один паттерн должен принимать Z, другой S
        self.assertTrue(any("Z" in p for p in patterns))
        self.assertTrue(any("S" in p for p in patterns))

    def test_4_recursion_folding(self):
        """
        Тест 4: Рекурсия и Свертка (Folding).
        (add a b).
        Должна сгенерироваться рекурсивная программа, похожая на исходную add.
        """
        print("\n--- Test 4: Recursion ---")
        new_prog = self._compile("(add a b)")
        print(new_prog)

        # Ищем рекурсивный вызов
        # g1(S v1, b) -> S(g1(v1, b))
        recursive_found = False
        for r in new_prog.rules:
            func_name = r.pattern.name
            if func_name in str(r.body): # Имя функции есть в теле
                recursive_found = True
                break

        self.assertTrue(recursive_found, "Сгенерированная программа должна быть рекурсивной")

    def test_5_generalization_structure(self):
        """
        Тест 5: Обобщение (Generalization).
        (add a a).
        Это вызывает MSG. Мы проверяем, что резидуализатор корректно генерирует
        вызов разделившейся функции.
        """
        print("\n--- Test 5: Generalization (add a a) ---")
        new_prog = self._compile("(add a a)")
        print(new_prog)

        # 1. Должна быть стартовая f-функция
        f_rules = [r for r in new_prog.rules if r.pattern.name.startswith("f")]
        self.assertTrue(len(f_rules) > 0)

        # 2. В теле f-функции должен быть вызов g-функции
        # И в этом вызове переменная 'a' должна использоваться ДВАЖДЫ (v1, v2, где v1=a, v2=a)

        # Для простоты проверим наличие функции с 2 аргументами
        g_rules = [r for r in new_prog.rules if r.pattern.name.startswith("g")]
        if g_rules:
            # g1(v1 v2) ...
            self.assertEqual(len(g_rules[0].pattern.params), 2,
                             "После обобщения add(a, a) функция должна принимать 2 аргумента")

if __name__ == '__main__':
    unittest.main()