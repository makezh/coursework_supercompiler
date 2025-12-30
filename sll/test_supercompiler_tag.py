import unittest
from sll.parser import parse, Parser, tokenize
from sll.supercompiler import Supercompiler
from sll.ast_nodes import TypeExpr

# Простая программа сложения
CODE = """
type [Nat] : Z | S [Nat] .

fun (add [Nat] [Nat]) -> [Nat] :
    (add [Z] y) -> y
  | (add [S x] y) -> [S (add x y)] .
"""

class TestStrategyTag(unittest.TestCase):

    def test_add_aa_tag_strategy(self):
        print("\n--- Test: add(a, a) using BAG OF TAGS ---")

        prog = parse(CODE)
        sc = Supercompiler(prog, strategy="TAG")

        start_expr = Parser(tokenize("(add a a)")).parse_expr()
        start_types = {"a": TypeExpr("Nat", [])}

        sc.build_tree(start_expr, start_types)
        root = sc.tree

        # 1. Проверяем, что теги собрались
        self.assertIsNotNone(root.bag)
        self.assertGreater(root.bag.total(), 0)

        # 2. Ищем следы работы свистка: Обобщение ИЛИ Свертка (из-за MSG)
        has_generalization = False
        has_folding = False

        queue = [root]
        visited = set()

        while queue:
            node = queue.pop(0)
            if id(node) in visited: continue
            visited.add(id(node))

            # Проверяем обобщение (let)
            for child in node.children:
                if child.contraction and child.contraction.pattern is None:
                    has_generalization = True
                    print(f"✅ Found Generalization (Let) at: {node.expr}")
                queue.append(child)

            # Проверяем свертку
            if node.back_link:
                has_folding = True
                print(f"✅ Found Folding (Loop) at: {node.expr} -> {node.back_link.expr}")

        # Свисток сработал, если мы либо перестроили дерево (Generalization),
        # либо нашли цикл, который предотвратил бесконечный рост (Folding).
        # В случае add(a, a) с TagBag может произойти и то, и другое.
        if has_generalization or has_folding:
            print("Test PASSED: Whistle prevented infinite expansion.")
        else:
            self.fail("Tree grew infinitely or stopped prematurely without folding/generalization.")

if __name__ == '__main__':
    unittest.main()