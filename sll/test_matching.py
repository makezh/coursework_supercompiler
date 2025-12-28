import unittest
from sll.ast_nodes import Var, Ctr, IntLit, FCall
from sll.matching import match, MatchSuccess, MatchFail, MatchNarrowing

class TestMatching(unittest.TestCase):

    def setUp(self):
        # Подготовка общих переменных
        self.var_x = Var("x")
        self.var_xs = Var("xs")
        self.z = Ctr("Z", [])
        self.nil = Ctr("Nil", [])

    def test_1_constructor_match(self):
        """Тест 1: Идеальное совпадение конструктора [Cons x xs]"""
        pat = Ctr("Cons", [self.var_x, self.var_xs])
        arg = Ctr("Cons", [self.z, self.nil])

        res = match(pat, arg)

        # Ожидаем Успех
        self.assertIsInstance(res, MatchSuccess)
        # Проверяем bindings внутри объекта успеха
        self.assertEqual(str(res.bindings['x']), "[Z]")
        self.assertEqual(str(res.bindings['xs']), "[Nil]")
        print("✅ Тест 1 (Cons) прошел")

    def test_2_constructor_mismatch(self):
        """Тест 2: Несовпадение имен конструкторов"""
        pat = Ctr("Cons", [self.var_x, self.var_xs])
        arg = self.nil

        res = match(pat, arg)

        # Ожидаем Провал
        self.assertIsInstance(res, MatchFail)
        print("✅ Тест 2 (Mismatch) прошел")

    def test_3_nested_match(self):
        """Тест 3: Вложенность [S x]"""
        pat = Ctr("S", [self.var_x])
        arg = Ctr("S", [Ctr("S", [self.z])])

        res = match(pat, arg)

        self.assertIsInstance(res, MatchSuccess)
        self.assertEqual(str(res.bindings['x']), "[S [Z]]")
        print("✅ Тест 3 (Nested) прошел")

    def test_4_integer_match(self):
        """Тест 4: Сопоставление чисел"""
        pat = IntLit(42)

        # Случай А: Совпало
        arg_ok = IntLit(42)
        res_ok = match(pat, arg_ok)
        self.assertIsInstance(res_ok, MatchSuccess)
        self.assertEqual(res_ok.bindings, {})

        # Случай Б: Не совпало значение
        arg_fail = IntLit(100)
        res_fail = match(pat, arg_fail)
        self.assertIsInstance(res_fail, MatchFail)

        # Случай В: Пришел конструктор вместо числа
        res_ctr = match(pat, self.z)
        self.assertIsInstance(res_ctr, MatchFail)

        print("✅ Тест 4 (IntLit) прошел")

    def test_5_integer_inside_pattern(self):
        """Тест 5: Число внутри конструктора [Pair 1 x]"""
        pat = Ctr("Pair", [IntLit(1), self.var_x])

        arg_ok = Ctr("Pair", [IntLit(1), self.z])
        res = match(pat, arg_ok)
        self.assertIsInstance(res, MatchSuccess)
        self.assertEqual(str(res.bindings['x']), "[Z]")

        arg_fail = Ctr("Pair", [IntLit(2), self.z])
        self.assertIsInstance(match(pat, arg_fail), MatchFail)

        print("✅ Тест 5 (Int inside Ctr) прошел")

    def test_6_function_call_match(self):
        """Тест 6: Сопоставление вызовов функций (FCall)"""
        var_y = Var("y")
        pat = FCall("add", [self.var_x, var_y])

        # Случай А: Успешное совпадение
        arg_ok = FCall("add", [self.z, Ctr("S", [self.var_x])])

        res = match(pat, arg_ok)
        self.assertIsInstance(res, MatchSuccess)
        self.assertEqual(str(res.bindings['x']), "[Z]")
        self.assertIn("S", str(res.bindings['y']))

        # Случай Б: Не совпало имя функции
        arg_fail_name = FCall("mult", [self.z, self.z])
        self.assertIsInstance(match(pat, arg_fail_name), MatchFail)

        print("✅ Тест 6 (FCall) прошел")

    def test_7_narrowing(self):
        """
        Тест 7: СУЖЕНИЕ (Narrowing). Самое важное для Rule-Based Driving.
        Паттерн требует Конструктор, а пришла Переменная.
        """
        # Паттерн: [Z] (требуем ноль)
        pat = Ctr("Z", [])
        # Аргумент: x (переменная)
        arg = Var("x")

        res = match(pat, arg)

        # Ожидаем Narrowing
        self.assertIsInstance(res, MatchNarrowing)
        self.assertEqual(res.var_name, "x")
        self.assertEqual(res.constr_name, "Z")
        self.assertEqual(res.constr_args_count, 0)

        # Паттерн посложнее: [S y]
        pat2 = Ctr("S", [self.var_x])
        res2 = match(pat2, arg) # match([S x], x)

        self.assertIsInstance(res2, MatchNarrowing)
        self.assertEqual(res2.var_name, "x")
        self.assertEqual(res2.constr_name, "S")
        self.assertEqual(res2.constr_args_count, 1)

        print("✅ Тест 7 (Narrowing) прошел")

if __name__ == '__main__':
    unittest.main()