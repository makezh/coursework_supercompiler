import unittest
from sll.parser import parse, Parser, tokenize
from sll.msg import msg
from sll.ast_nodes import Var

class TestMSG(unittest.TestCase):

    def _expr(self, text):
        return Parser(tokenize(text)).parse_expr()

    def test_identical(self):
        """Если выражения одинаковы -> Обобщение такое же"""
        t1 = self._expr("[S [Z]]")
        t2 = self._expr("[S [Z]]")

        res = msg(t1, t2)
        self.assertEqual(str(res.gen), "[S [Z]]")
        self.assertEqual(res.sub1, {})
        self.assertEqual(res.sub2, {})

    def test_simple_conflict(self):
        """Разные корни -> Переменная"""
        t1 = self._expr("[Z]")
        t2 = self._expr("[S x]")

        res = msg(t1, t2)
        # Ожидаем: v1
        self.assertIsInstance(res.gen, Var)
        self.assertEqual(res.gen.name, "v1")

        # sub1: v1 -> [Z]
        self.assertEqual(str(res.sub1[('v', 1)]), "[Z]")
        # sub2: v1 -> [S x]
        self.assertEqual(str(res.sub2[('v', 1)]), "[S x]")

    def test_common_structure(self):
        """Совпадение сверху, различие внутри"""
        # t1: [Cons [Z] xs]
        # t2: [Cons [S x] xs]
        # MSG: [Cons v1 xs]  <-- v1 заменила различие ([Z] и [S x])

        t1 = self._expr("[Cons [Z] xs]")
        t2 = self._expr("[Cons [S x] xs]")

        res = msg(t1, t2)

        # Проверяем структуру
        self.assertEqual(str(res.gen), "[Cons v1 xs]")

        # Проверяем подстановки
        # v1 -> [Z]
        self.assertEqual(str(res.sub1[('v', 1)]), "[Z]")
        # v1 -> [S x]
        self.assertEqual(str(res.sub2[('v', 1)]), "[S x]")

    def test_double_conflict(self):
        """Два различия в разных местах"""
        # t1: f(A, B)
        # t2: f(C, D)
        # MSG: f(v1, v2)

        t1 = self._expr("(f [A] [B])")
        t2 = self._expr("(f [C] [D])")

        res = msg(t1, t2)
        self.assertEqual(str(res.gen), "(f v1 v2)")

        self.assertEqual(str(res.sub1[('v', 1)]), "[A]")
        self.assertEqual(str(res.sub1[('v', 2)]), "[B]")

    def test_tight_generalization(self):
        """
        Тест на уплотнение (пример научника).
        t1 = [A [B x] y [B x] y]
        t2 = [A p [C r] p [C r]]

        Ожидаем: [A v1 v2 v1 v2]
        БЕЗ уплотнения было бы: [A v1 v2 v3 v4]
        """
        # Упростим пример для наглядности (без лишних вложенностей)
        # t1: f(x, y, x, y)
        # t2: f(a, b, a, b)

        t1 = self._expr("(f x y x y)")
        t2 = self._expr("(f a b a b)")

        res = msg(t1, t2)

        print(f"Gen: {res.gen}")
        print(f"Sub1: {res.sub1}")

        # Проверяем, что в результате только ДВЕ переменные (v1 и v2), а не 4
        # Текстовое представление должно быть (f v1 v2 v1 v2)
        self.assertEqual(str(res.gen), "(f v1 v2 v1 v2)")

        # Проверяем количество уникальных ключей в подстановке
        self.assertEqual(len(res.sub1), 2)

    def test_no_tight_if_different(self):
        """
        Проверяем, что разные пары все же дают разные переменные.
        t1: f(x, y)
        t2: f(a, b)
        """
        t1 = self._expr("(f x y)")
        t2 = self._expr("(f a b)")

        res = msg(t1, t2)
        self.assertEqual(str(res.gen), "(f v1 v2)")
        self.assertEqual(len(res.sub1), 2)

if __name__ == '__main__':
    unittest.main()