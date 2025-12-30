import unittest
from collections import Counter
from sll.bag_of_tags import TagBag
from sll.ast_nodes import Ctr, Var

class TestBagOfTags(unittest.TestCase):

    def test_collect(self):
        """Проверяем сбор тегов с дерева."""
        # Строим структуру вручную: [Cons x [Nil]]
        # Cons(tag=1) -> x(tag=2), Nil(tag=3)
        nil = Ctr("Nil", [], tag=3)
        x = Var("x", tag=2)
        cons = Ctr("Cons", [x, nil], tag=1)

        bag = TagBag.collect(cons)

        print(f"Bag: {bag}")
        self.assertEqual(bag[1], 1)
        self.assertEqual(bag[2], 1)
        self.assertEqual(bag[3], 1)
        self.assertEqual(bag.total(), 3)

    def test_whistle_growth(self):
        """Проверяем срабатывание свистка при росте."""
        # Старый: {1: 1, 2: 1} (размер 2)
        bag_old = Counter({1: 1, 2: 1})

        # Новый: {1: 10, 2: 5} (размер 15) -> Те же теги, но их больше
        bag_new = Counter({1: 10, 2: 5})

        self.assertTrue(TagBag.is_dangerous(bag_old, bag_new),
                        "Должен свистеть: теги те же, но количество выросло")

    def test_whistle_different_set(self):
        """Не должен свистеть, если состав тегов изменился."""
        # Старый: {1: 1}
        bag_old = Counter({1: 1})

        # Новый: {1: 100, 5: 1} -> Появился тег 5
        # Это значит мы зашли в новый кусок кода, свистеть рано.
        bag_new = Counter({1: 100, 5: 1})

        self.assertFalse(TagBag.is_dangerous(bag_old, bag_new),
                         "Не должен свистеть: появился новый тег 5")

    def test_whistle_shrink(self):
        """Не должен свистеть, если размер уменьшился."""
        bag_old = Counter({1: 10})
        bag_new = Counter({1: 5})

        self.assertFalse(TagBag.is_dangerous(bag_old, bag_new))

if __name__ == '__main__':
    unittest.main()