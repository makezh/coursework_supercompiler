import unittest
from sll.parser import parse, Parser, tokenize
from sll.he import he

class TestHomeomorphicEmbedding(unittest.TestCase):

    def _expr(self, text):
        """Вспомогательный метод для парсинга выражения"""
        return Parser(tokenize(text)).parse_expr()

    def assertEmbedded(self, s1, s2):
        """Проверяет, что s1 <| s2"""
        t1 = self._expr(s1)
        t2 = self._expr(s2)
        self.assertTrue(he(t1, t2), f"Ожидалось: '{s1}' ВЛОЖЕНО В '{s2}'")

    def assertNotEmbedded(self, s1, s2):
        """Проверяет, что s1 НЕ <| s2"""
        t1 = self._expr(s1)
        t2 = self._expr(s2)
        self.assertFalse(he(t1, t2), f"Ожидалось: '{s1}' НЕ ВЛОЖЕНО В '{s2}'")

    def test_1_vars(self):
        """Правило: Переменные (Variable)"""
        self.assertEmbedded("x", "y")  # Имена не важны, важна суть "переменная"
        self.assertEmbedded("x", "x")
        self.assertNotEmbedded("x", "[Z]") # Переменная не вкладывается в конструктор (напрямую)

    def test_2_literals(self):
        """Правило: Литералы (IntLit)"""
        self.assertEmbedded("42", "42")
        self.assertNotEmbedded("42", "100")
        # Число может быть вложено в структуру: 1 <| [S 1]
        self.assertEmbedded("1", "[S 1]")

    def test_3_coupling(self):
        """Правило: Сочетание (Coupling) - сохранение структуры"""
        # Конструкторы
        self.assertEmbedded("[S x]", "[S y]")
        self.assertEmbedded("[Cons x xs]", "[Cons y ys]")

        # Функции
        self.assertEmbedded("(f x)", "(f y)")

        # Несовпадение имен
        self.assertNotEmbedded("[Z]", "[S x]")
        self.assertNotEmbedded("(f x)", "(g x)")

    def test_4_diving(self):
        """Правило: Ныряние (Diving) - поиск в глубину"""
        # x <| [S x]  (нашли x внутри S)
        self.assertEmbedded("x", "[S x]")

        # [Z] <| [S [S [Z]]] (ныряем дважды)
        self.assertEmbedded("[Z]", "[S [S [Z]]]")

        # (f x) <| (g (f x)) (вызов внутри другого вызова)
        self.assertEmbedded("(f x)", "(g (f x))")

    def test_5_complex_mix(self):
        """Сложные случаи (Coupling + Diving)"""
        # add(x, y) <| add(S(x), y)
        # 1. add == add (Coupling)
        # 2. x <| S(x) (через Diving)
        # 3. y <| y (через Var)
        self.assertEmbedded("(add x y)", "(add [S x] y)")

        # add(S(x), y) НЕ <| add(x, y)
        # S(x) больше, чем x, поэтому левое "не влезает" в правое
        self.assertNotEmbedded("(add [S x] y)", "(add x y)")

    def test_6_turchin_relation(self):
        """
        Тест на 'Отношение Турчина' (Рост стека).
        Проверяем, что HE ловит ситуацию g(f(x)) -> g(g(f(x))).
        """
        t1 = "(g (f x))"
        t2 = "(g (g (f x)))"

        # Гомеоморфное вложение работает так:
        # 1. g == g (Coupling)
        # 2. Сравниваем аргументы: (f x) <| (g (f x)) ?
        # 3. (f x) != (g ...) (Coupling failed)
        # 4. Ныряем в (g (f x)): (f x) <| (f x) ? -> ДА!
        self.assertEmbedded(t1, t2)

if __name__ == '__main__':
    unittest.main()