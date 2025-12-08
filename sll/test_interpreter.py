import unittest
import sys
import os

# --- Хак для импортов ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from sll.parser import parse, tokenize, Parser
from sll.interpreter import step
from sll.ast_nodes import FCall, Ctr

class TestInterpreter(unittest.TestCase):

    def parse_expr_helper(self, text):
        """Помощник: парсит одну строку-выражение"""
        return Parser(tokenize(text)).parse_expr()

    def run_until_normal_form(self, expr, program, max_steps=20):
        """Помощник: крутит цикл step, пока не вернется None"""
        current = expr
        for _ in range(max_steps):
            next_expr = step(current, program)
            if next_expr is None:
                return current
            current = next_expr
        raise TimeoutError("Превышен лимит шагов (возможно, зацикливание)")

    def test_1_basic_arithmetic(self):
        """
        Тест 1: Классика 1 + 1 = 2
        """
        code = """
        type [Nat] : Z | S [Nat].
        fun (add [Nat] [Nat]) -> [Nat]:
            (add [Z] y) -> y |
            (add [S x] y) -> [S (add x y)].
        """
        prog = parse(code)

        # (add [S Z] [S Z])
        expr = self.parse_expr_helper("(add [S [Z]] [S [Z]])")

        result = self.run_until_normal_form(expr, prog)

        print(f"1+1 result: {result}")
        # Ожидаем [S [S [Z]]]
        self.assertTrue(str(result) == "[S [S [Z]]]")

    def test_2_deep_reduction_args(self):
        """
        Тест 2: Интерпретатор должен уметь вычислять аргументы функции,
        даже если они не на первой позиции.

        Пример: (f [Z] (g [Z]))
        Функция f ждет [Z] на второй позиции.
        Но там стоит вызов (g [Z]).
        Интерпретатор должен сначала вычислить g.
        """
        code = """
        type [Nat] : Z.
        
        fun (g [Nat]) -> [Nat]:
            (g x) -> [Z].       << g возвращает Z >>
            
        fun (f [Nat] [Nat]) -> [Nat]:
            (f a [Z]) -> [Z].   << f матчится, только если второй аргумент Z >>
        """
        prog = parse(code)

        # Выражение: (f [Z] (g [Z]))
        expr = self.parse_expr_helper("(f [Z] (g [Z]))")

        # Шаг 1: Интерпретатор видит, что f не матчится (второй арг не Z).
        # Он должен зайти во второй аргумент и сделать шаг в (g [Z]).
        expr = step(expr, prog)
        print(f"Deep reduction step 1: {expr}")

        # Теперь выражение должно стать (f [Z] [Z])
        self.assertTrue(str(expr) == "(f [Z] [Z])")

        # Шаг 2: Теперь f матчится
        expr = step(expr, prog)
        print(f"Deep reduction step 2: {expr}")
        self.assertTrue(str(expr) == "[Z]")

    def test_3_reduction_inside_constructor(self):
        """
        Тест 3: Вычисление внутри конструктора.
        [S (add [Z] [Z])] -> [S [Z]]
        """
        code = """
        type [Nat] : Z | S [Nat].
        fun (add [Nat] [Nat]) -> [Nat]:
            (add [Z] y) -> y.
        """
        prog = parse(code)

        expr = self.parse_expr_helper("[S (add [Z] [Z])]")

        # Шаг: (add ...) внутри S должно вычислиться
        expr = step(expr, prog)
        print(f"Constructor reduction: {expr}")

        self.assertTrue(str(expr) == "[S [Z]]")

    def test_4_multiple_blocking_args(self):
        """
        Тест 4: Два аргумента требуют вычисления.
        (add (g [Z]) (g [Z]))
        Интерпретатор должен вычислить сначала первый, потом второй.
        """
        code = """
        type [Nat] : Z | S [Nat].
        
        fun (g [Nat]) -> [Nat]:
            (g x) -> [Z].
            
        fun (add [Nat] [Nat]) -> [Nat]:
            (add [Z] y) -> y.
        """
        prog = parse(code)

        # Выражение: (add (g [Z]) (g [Z]))
        expr = self.parse_expr_helper("(add (g [Z]) (g [Z]))")
        print(f"\nStart Multiple: {expr}")

        expr = step(expr, prog)
        print(f"Step 1: {expr}")
        self.assertTrue(str(expr) == "(add [Z] (g [Z]))")

        expr = step(expr, prog)
        print(f"Step 2: {expr}")
        # Тут сработает правило (add [Z] y) -> y, где y = (g [Z])
        self.assertTrue(str(expr) == "(g [Z])")

        # Шаг 3: Довычисляем остаток
        expr = step(expr, prog)
        print(f"Step 3: {expr}")
        self.assertTrue(str(expr) == "[Z]")

    def test_5_blocking_argument_at_end(self):
        """
        Тест 5: Блокирующий вызов стоит последним (3-м) аргументом.
        Проверяем, что цикл `for` в интерпретаторе доходит до конца.
        """
        code = """
        type [T] : A | B | C | OK.
        
        fun (get_c [T]) -> [T]:
            (get_c x) -> [C].
            
        fun (check [T] [T] [T]) -> [T]:
            (check [A] [B] [C]) -> [OK].
        """
        prog = parse(code)
        expr = self.parse_expr_helper("(check [A] [B] (get_c [A]))")

        expr = step(expr, prog)
        print(f"\nCheck 3rd arg: {expr}")

        self.assertTrue(str(expr) == "(check [A] [B] [C])")

        expr = step(expr, prog)
        self.assertTrue(str(expr) == "[OK]")

    def test_6_nested_chain_calls(self):
        """
        Тест 6: Цепочка вызовов (f (g (h [Z])))
        """
        code = """
        type [Nat] : Z.
        fun (h [Nat]) -> [Nat]: (h x) -> [Z].
        fun (g [Nat]) -> [Nat]: (g [Z]) -> [Z].
        fun (f [Nat]) -> [Nat]: (f [Z]) -> [Z].
        """
        prog = parse(code)

        expr = self.parse_expr_helper("(f (g (h [Z])))")

        print(f"\nStart Chain: {expr}")

        expr = step(expr, prog)
        print(f"Step 1: {expr}")
        self.assertTrue(str(expr) == "(f (g [Z]))")

        expr = step(expr, prog)
        print(f"Step 2: {expr}")
        self.assertTrue(str(expr) == "(f [Z])")

        expr = step(expr, prog)
        print(f"Step 3: {expr}")
        self.assertTrue(str(expr) == "[Z]")

if __name__ == '__main__':
    unittest.main()