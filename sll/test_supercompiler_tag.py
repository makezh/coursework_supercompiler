import unittest
from sll.parser import parse
from sll.supercompiler import Supercompiler
from sll.ast_nodes import FCall, Ctr, Var, Expr

def tree_to_string(node, indent=0):
    """Вспомогательная функция для визуализации дерева"""
    res = "  " * indent + str(node.expr)
    if node.back_link:
        res += f"  --> [FOLD to {node.back_link.expr}]"
    if node.bag:
        res += f" (bag_size={node.bag.total()})"
    res += "\n"
    for child in node.children:
        res += tree_to_string(child, indent + 1)
    return res

class TestSupercompilerTag(unittest.TestCase):

    def test_simple_termination(self):
        """
        Тест 1: Сложение (add a b).
        Простая программа, должна завершиться по Folding (свертке).
        """
        print("\n=== RUNNING TEST: SIMPLE TERMINATION (add a b) ===")
        code = """
        type [Nat] : Z | S [Nat].
        fun (add [Nat] [Nat]) -> [Nat] :
          (add [Z] y) -> y
        | (add [S x] y) -> [S (add x y)].
        """
        program = parse(code)
        sc = Supercompiler(program, strategy='TAG')

        # Начальное выражение: (add a b)
        start_expr = FCall("add", [Var("a"), Var("b")])
        # Типы переменных: a и b - это Nat
        nat_type = program.types[0] # [Nat]
        var_types = {"a": nat_type, "b": nat_type}

        sc.build_tree(start_expr, var_types)

        print(tree_to_string(sc.tree))

        # Проверяем, что корень не пустой и есть дети
        self.assertIsNotNone(sc.tree)
        # Проверяем, что в дереве появилась хотя бы одна ссылка назад
        has_fold = any(n.back_link is not None for n in self._all_nodes(sc.tree))
        self.assertTrue(has_fold, "Дерево должно содержать свертку (back_link)")

    def test_tag_bag_whistle(self):
        """
        Тест 2: Бесконечный рост (loop x) -> (loop [S x]).
        Мешок тегов ДОЛЖЕН свистнуть на (loop [S [S ...]]).
        """
        print("\n=== RUNNING TEST: TAG-BAG WHISTLE (loop x) ===")
        code = """
        type [Nat] : Z | S [Nat].
        fun (loop [Nat]) -> [Nat] :
          (loop x) -> (loop [S x]).
        """
        program = parse(code)
        sc = Supercompiler(program, strategy='TAG')

        # (loop [Z])
        start_expr = FCall("loop", [Ctr("Z", [])])
        sc.build_tree(start_expr, {})

        print(tree_to_string(sc.tree))

        # Если мы здесь и тест не завис — значит свисток сработал.
        # Проверяем, что произошло обобщение (появился узел с MSG переменными v1, v2...)
        has_gen = any("v" in str(n.expr) for n in self._all_nodes(sc.tree))
        self.assertTrue(has_gen, "Должно было произойти обобщение (появились v-переменные)")

    def _all_nodes(self, node):
        """Хелпер для обхода всех узлов дерева"""
        nodes = [node]
        for child in node.children:
            nodes.extend(self._all_nodes(child))
        return nodes

if __name__ == "__main__":
    unittest.main()