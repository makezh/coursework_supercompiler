import unittest
from sll.ast_nodes import Var, Ctr, IntLit, FCall
from sll.matching import match

class TestMatching(unittest.TestCase):

    def setUp(self):
        # Подготовка общих переменных
        self.var_x = Var("x")
        self.var_xs = Var("xs")
        self.z = Ctr("Z", [])
        self.nil = Ctr("Nil", [])

    def test_1_constructor_match(self):
        """Тест 1: Идеальное совпадение конструктора [Cons x xs]"""
        # Паттерн: [Cons x xs]
        pat = Ctr("Cons", [self.var_x, self.var_xs])
        # Аргумент: [Cons [Z] [Nil]]
        arg = Ctr("Cons", [self.z, self.nil])

        res = match(pat, arg)
        
        self.assertIsNotNone(res)
        # Проверяем, что x захватил Z
        self.assertEqual(str(res['x']), "[Z]")
        # Проверяем, что xs захватил Nil
        self.assertEqual(str(res['xs']), "[Nil]")
        print("✅ Тест 1 (Cons) прошел")

    def test_2_constructor_mismatch(self):
        """Тест 2: Несовпадение имен конструкторов"""
        # Паттерн: [Cons x xs]
        pat = Ctr("Cons", [self.var_x, self.var_xs])
        # Аргумент: [Nil]
        arg = self.nil

        res = match(pat, arg)
        
        self.assertIsNone(res)
        print("✅ Тест 2 (Mismatch) прошел")

    def test_3_nested_match(self):
        """Тест 3: Вложенность [S x]"""
        # Паттерн: [S x]
        pat = Ctr("S", [self.var_x])
        # Аргумент: [S [S [Z]]]
        arg = Ctr("S", [Ctr("S", [self.z])])

        res = match(pat, arg)
        
        self.assertIsNotNone(res)
        self.assertEqual(str(res['x']), "[S [Z]]")
        print("✅ Тест 3 (Nested) прошел")

    def test_4_integer_match(self):
        """Тест 4: Сопоставление чисел (НОВОЕ)"""
        # Паттерн: 42
        pat = IntLit(42)
        
        # Случай А: Совпало
        arg_ok = IntLit(42)
        res_ok = match(pat, arg_ok)
        self.assertIsNotNone(res_ok)
        self.assertEqual(res_ok, {}) # Пустой словарь, т.к. переменных нет
        
        # Случай Б: Не совпало значение
        arg_fail = IntLit(100)
        res_fail = match(pat, arg_fail)
        self.assertIsNone(res_fail)
        
        # Случай В: Пришел конструктор вместо числа
        res_ctr = match(pat, self.z)
        self.assertIsNone(res_ctr)
        
        print("✅ Тест 4 (IntLit) прошел")

    def test_5_integer_inside_pattern(self):
        """Тест 5: Число внутри конструктора [Pair 1 x]"""
        # Паттерн: [Pair 1 x]
        pat = Ctr("Pair", [IntLit(1), self.var_x])
        
        # Аргумент: [Pair 1 [Z]]
        arg_ok = Ctr("Pair", [IntLit(1), self.z])
        
        res = match(pat, arg_ok)
        self.assertIsNotNone(res)
        self.assertEqual(str(res['x']), "[Z]")
        
        # Аргумент: [Pair 2 [Z]] (Число не то)
        arg_fail = Ctr("Pair", [IntLit(2), self.z])
        self.assertIsNone(match(pat, arg_fail))
        
        print("✅ Тест 5 (Int inside Ctr) прошел")

    def test_6_function_call_match(self):
        """Тест 6: Сопоставление вызовов функций (FCall)"""
        # Паттерн: (add x y)
        var_y = Var("y")
        pat = FCall("add", [self.var_x, var_y])

        # Случай А: Успешное совпадение. (add [Z] [S x])
        # Это имитирует проверку: является ли (add [Z] [S x]) частным случаем (add x y)
        arg_ok = FCall("add", [self.z, Ctr("S", [self.var_x])])

        res = match(pat, arg_ok)
        self.assertIsNotNone(res)
        # x -> [Z]
        self.assertEqual(str(res['x']), "[Z]")
        # y -> [S x]
        self.assertIn("S", str(res['y']))

        # Случай Б: Не совпало имя функции (mult vs add)
        arg_fail_name = FCall("mult", [self.z, self.z])
        self.assertIsNone(match(pat, arg_fail_name))

        # Случай В: Не совпало количество аргументов
        arg_fail_arity = FCall("add", [self.z])
        self.assertIsNone(match(pat, arg_fail_arity))

        # Случай Г: Вложенные вызовы
        # Паттерн: (g (f x))
        # Аргумент: (g (f [Z]))
        pat_nested = FCall("g", [FCall("f", [self.var_x])])
        arg_nested = FCall("g", [FCall("f", [self.z])])

        res_nested = match(pat_nested, arg_nested)
        self.assertIsNotNone(res_nested)
        self.assertEqual(str(res_nested['x']), "[Z]")

        print("✅ Тест 6 (FCall) прошел")

if __name__ == '__main__':
    unittest.main()