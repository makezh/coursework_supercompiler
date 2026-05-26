import unittest
from collections import Counter
from sll.bag_of_tags import TagBag
from sll.ast_nodes import Ctr, Var, FCall
from sll.process_tree import Node

class TestBagOfTags(unittest.TestCase):

    def test_collect_with_none_tags(self):
        """Проверяем, что узлы с tag=None игнорируются при сборе."""
        nil = Ctr("Nil", [], tag=3)
        x = Var("x", tag=None)
        cons = Ctr("Cons", [x, nil], tag=1)
        node = Node(cons, {})

        bag = TagBag.collect(node)

        self.assertEqual(bag[1], TagBag.W_FOCUS)
        self.assertNotIn(None, bag, "None не должен попадать в мешок")
        self.assertEqual(len(bag), 1, "В focus только корневой тег [Cons]")

    def test_whistle_strict_growth(self):
        """Свисток должен срабатывать при росте количества тех же тегов."""
        bag_old = Counter({1: 1, 2: 1})
        bag_new = Counter({1: 2, 2: 1}) # Тег 1 вырос

        self.assertTrue(TagBag.is_dangerous(bag_old, bag_new),
                        "Должен свистеть: количество тега 1 увеличилось")

    def test_whistle_different_keys_safe(self):
        """Реализация консервативна: разные key-set → не дёргаем свисток."""
        bag_old = Counter({1: 1})
        bag_new = Counter({1: 1, 5: 1})

        self.assertFalse(TagBag.is_dangerous(bag_old, bag_new),
                          "Текущий is_dangerous требует совпадения set ключей")

    def test_whistle_not_a_superset(self):
        """Не должен свистеть, если хотя бы один старый тег пропал или уменьшился."""
        bag_old = Counter({1: 2, 2: 1})
        # Тег 2 пропал, хотя тег 1 сильно вырос. Это не надмножество.
        bag_new = Counter({1: 100})

        self.assertFalse(TagBag.is_dangerous(bag_old, bag_new),
                         "Не должен свистеть: тег 2 исчез, структура изменилась")

    def test_whistle_shrink(self):
        """Не должен свистеть, если мешок стал меньше."""
        bag_old = Counter({1: 10})
        bag_new = Counter({1: 5})

        self.assertFalse(TagBag.is_dangerous(bag_old, bag_new))

if __name__ == '__main__':
    unittest.main()