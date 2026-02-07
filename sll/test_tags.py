import unittest
from collections import Counter
from sll.ast_nodes import Var, Ctr, FCall, Program, Rule, Pattern, TypeExpr, FunSig
from sll.matching import substitute
from sll.bag_of_tags import TagBag
from sll.preprocessor import Tagger
from sll.supercompiler import Supercompiler

class TestBagOfTagsExact(unittest.TestCase):

    def test_01_tag_preservation_in_substitute(self):
        """
        Проверка: копирует ли substitute теги из исходного выражения?
        """
        # Создаем переменную x с тегом 500
        val = Var("x")
        val.tag = 500

        # Создаем конструктор [S x]
        # У S тег 10
        inner_var = Var("x") # переменная в паттерне
        pattern_expr = Ctr("S", [inner_var])
        pattern_expr.tag = 10

        # Делаем подстановку {x: val} в [S x]
        res = substitute(pattern_expr, {"x": val})

        # Проверяем результат: [S x]
        # Тег самого S должен быть 10, тег вложенного x должен быть 500
        self.assertEqual(res.tag, 10, "Тег конструктора потерян при подстановке")
        self.assertEqual(res.args[0].tag, 500, "Тег подставленной переменной потерян")

    def test_02_dangerous_criteria_strict(self):
        """
        Проверка: критерий научника (надмножество и рост).
        """
        # bag_new >= bag_old
        old = Counter({1: 1, 2: 1})

        # 1. Равно - не опасно (это для Folding)
        self.assertFalse(TagBag.is_dangerous(old, Counter({1: 1, 2: 1})))

        # 2. Надмножество (тег 1 вырос) - ОПАСНО
        self.assertTrue(TagBag.is_dangerous(old, Counter({1: 2, 2: 1})))

        # 3. Появился новый тег, старые на месте - ОПАСНО (надмножество)
        self.assertTrue(TagBag.is_dangerous(old, Counter({1: 1, 2: 1, 3: 1})))

        # 4. Один пропал - НЕ ОПАСНО
        self.assertFalse(TagBag.is_dangerous(old, Counter({1: 10})))

    def test_03_supercompiler_integration(self):
        """
        Проверка: видит ли Supercompiler опасного предка?
        """
        # Создаем минимальную корректную программу, чтобы SC не падал
        # fun (f [Nat]) -> [Nat] : (f x) -> [S x] .
        nat_type = TypeExpr("Nat", [])
        sig = FunSig("f", [nat_type], nat_type)
        prog = Program(rules=[], types=[], signatures=[sig])

        sc = Supercompiler(prog, strategy="TAG")

        # Эмулируем два узла
        # alpha: (f a) с тегом 1
        expr_alpha = FCall("f", [Var("a")])
        expr_alpha.tag = 1
        node_alpha = sc._create_node(expr_alpha, {"a": nat_type})

        # beta: (f [S a]) где f имеет тег 1, а S имеет тег 2
        s_ctr = Ctr("S", [Var("a")])
        s_ctr.tag = 2
        expr_beta = FCall("f", [s_ctr])
        expr_beta.tag = 1
        node_beta = sc._create_node(expr_beta, {"a": nat_type})

        # Связываем их
        node_beta.parent = node_alpha

        # Ищем предка
        found = sc._find_embedding_ancestor(node_beta)
        self.assertIs(found, node_alpha, "SC должен найти предка по мешку тегов")

    def test_04_tagger_uniqueness(self):
        """
        Проверка: дает ли Tagger разные теги разным частям выражения?
        """
        # fun (f [Nat]) -> [Nat] : (f x) -> [S [S x]] .
        # В теле [S [S x]] : 2 конструктора S и 1 переменная x. Итого 3 узла.
        body = Ctr("S", [Ctr("S", [Var("x")])])
        rule = Rule(Pattern("f", [Var("x")]), body)
        prog = Program(rules=[rule], types=[], signatures=[])

        Tagger().preprocess(prog)

        tags = []
        def collect_tags(e):
            tags.append(e.tag)
            if hasattr(e, 'args'):
                for a in e.args: collect_tags(a)

        collect_tags(prog.rules[0].body)

        # Проверяем уникальность
        self.assertEqual(len(tags), 3)
        self.assertEqual(len(set(tags)), 3, "Теги в одном правиле должны быть уникальными!")

if __name__ == '__main__':
    unittest.main()