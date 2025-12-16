import unittest
from sll.parser import parse, Parser, tokenize
from sll.supercompiler import Supercompiler

CODE = """
type [Nat] : Z | S [Nat] .
fun (add [Nat] [Nat]) -> [Nat] :
    (add [Z] y) -> y
  | (add [S x] y) -> [S (add x y)] .
"""

class TestSupercompilerBasic(unittest.TestCase):
    def setUp(self):
        self.prog = parse(CODE)
        self.sc = Supercompiler(self.prog)

    def test_tree_construction_add(self):
        # Строим дерево для (add a b)
        expr = Parser(tokenize("(add a b)")).parse_expr()
        self.sc.build_tree(expr)

        root = self.sc.tree
        self.assertIsNotNone(root)
        print("\n--- Process Tree for (add a b) ---")
        self._print_tree(root)

        # Проверки
        # 1. Корень должен иметь 2 детей (ветвление по a)
        self.assertEqual(len(root.children), 2)

        # Ветка 1 (a=Z) -> результат b (StopStep)
        child1 = root.children[0]
        self.assertEqual(str(child1.expr), "b")
        self.assertEqual(len(child1.children), 0) # Лист

        # Ветка 2 (a=S v1) -> результат [S (add v1 b)] -> Decompose
        child2 = root.children[1]
        self.assertIn("S", str(child2.expr))
        # У child2 должен быть ребенок (декомпозиция S)
        self.assertEqual(len(child2.children), 1)

        # Внутри S лежит (add v1 b)
        grandchild = child2.children[0]
        self.assertIn("add", str(grandchild.expr))

        # А вот grandchild должен свернуться к корню!
        # (add v1 b) это переименование (add a b).
        # Проверим, сработал ли Folding.
        self.assertIsNotNone(grandchild.back_link)
        self.assertIs(grandchild.back_link, root)
        print(f"FOLDING DETECTED: {grandchild.expr} -> {grandchild.back_link.expr}")

    def _print_tree(self, node, level=0):
        indent = "  " * level
        info = ""
        if node.contraction:
            info = f" --[{node.contraction.var_name}={node.contraction.pattern}]--> "
        elif node.parent:
            info = " --> "

        folding = f" ===>>> JUMP TO {node.back_link.expr}" if node.back_link else ""

        print(f"{indent}{info}{node.expr}{folding}")
        for c in node.children:
            self._print_tree(c, level + 1)

if __name__ == '__main__':
    unittest.main()