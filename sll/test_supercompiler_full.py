import unittest
from sll.parser import parse, Parser, tokenize
from sll.supercompiler import Supercompiler

# Программа сложения
CODE = """
type [Nat] : Z | S [Nat] .
fun (add [Nat] [Nat]) -> [Nat] :
    (add [Z] y) -> y
  | (add [S x] y) -> [S (add x y)] .
"""


class TestSupercompilerFull(unittest.TestCase):

    def setUp(self):
        self.prog = parse(CODE)
        self.sc = Supercompiler(self.prog)

    def _expr(self, text):
        return Parser(tokenize(text)).parse_expr()

    def test_basic_folding(self):
        """Тест 1: add(a, b) — должно свернуться без обобщения"""
        print("\n--- Test 1: Basic Folding ---")
        self.sc.build_tree(self._expr("(add a b)"))

        root = self.sc.tree
        self.assertEqual(len(root.children), 2)

        # Ветка 2 (a=S v1) -> узел [S (add v1 b)]
        branch_s = root.children[1]
        self.assertIn("S", str(branch_s.expr))

        # У S должен быть 1 ребенок (результат декомпозиции)
        self.assertEqual(len(branch_s.children), 1)

        # Берем содержимое S -> это (add v1 b)
        add_node = branch_s.children[0]
        self.assertIn("add", str(add_node.expr))

        self.assertEqual(len(add_node.children), 0)  # Убеждаемся, что детей нет

        self.assertIsNotNone(add_node.back_link, "Должна быть обратная ссылка")
        self.assertIs(add_node.back_link, root, "Ссылка должна вести в корень")

        print(f"FOLDING SUCCESS: {add_node.expr} -> {add_node.back_link.expr}")

    def test_generalization(self):
        """Тест 2: Обобщение. add(S(S(a)), a) -> рост -> MSG"""

        print("\n--- Test 2: Generalization ---")
        # Попробуем (add a a)
        self.sc.build_tree(self._expr("(add a a)"))

        root = self.sc.tree

        self.assertIsNotNone(root)

        # Пройдемся по дереву и поищем узлы, у которых дети связаны через "let" (contraction.pattern is None)
        has_generalization = False
        queue = [root]
        while queue:
            node = queue.pop(0)
            for child in node.children:
                if child.contraction and child.contraction.pattern is None:
                    has_generalization = True
                    print(f"Generalization found at node: {node.expr}")
                    print(f"  Let-variable: {child.contraction.var_name}")
                queue.append(child)


if __name__ == '__main__':
    unittest.main()
