import unittest
from collections import Counter
from sll.bag_of_tags import TagBag
from sll.ast_nodes import Ctr, Var, FCall

class TestBagOfTags(unittest.TestCase):

    def test_collect_with_none_tags(self):
        """Проверяем, что узлы с tag=None игнорируются при сборе."""
        # [Cons x [Nil]]
        # Теги есть только у Cons и Nil. У переменной x тега нет.
        nil = Ctr("Nil", [], tag=3)
        x = Var("x", tag=None)
        cons = Ctr("Cons", [x, nil], tag=1)

        bag = TagBag.collect(cons)

        self.assertEqual(bag[1], 1, "Тег 1 должен быть в мешке")
        self.assertEqual(bag[3], 1, "Тег 3 должен быть в мешке")
        self.assertNotIn(None, bag, "None не должен попадать в мешок")
        self.assertEqual(len(bag), 2, "В мешке должно быть только 2 уникальных тега")
        self.assertEqual(bag.total(), 2)

    def test_whistle_strict_growth(self):
        """Свисток должен срабатывать при росте количества тех же тегов."""
        bag_old = Counter({1: 1, 2: 1})
        bag_new = Counter({1: 2, 2: 1}) # Тег 1 вырос

        self.assertTrue(TagBag.is_dangerous(bag_old, bag_new),
                        "Должен свистеть: количество тега 1 увеличилось")

    def test_whistle_superset_with_new_tags(self):
        """
        Свисток должен срабатывать, даже если появились новые теги,
        но старые сохранились/выросли.
        """
        bag_old = Counter({1: 1})
        # В новом мешке старый тег сохранился, и добавился новый тег 5.
        # Математически {1, 5} является надмножеством {1}.
        bag_new = Counter({1: 1, 5: 1})

        self.assertTrue(TagBag.is_dangerous(bag_old, bag_new),
                         "Должен свистеть: новый мешок включает в себя старый и он больше")

    def test_whistle_not_a_superset(self):
        """Не должен свистеть, если хотя бы один старый тег пропал или уменьшился."""
        bag_old = Counter({1: 2, 2: 1})
        # Тег 2 пропал, хотя тег 1 сильно вырос. Это не надмножество.
        bag_new = Counter({1: 100})

        self.assertFalse(TagBag.is_dangerous(bag_old, bag_new),
                         "Не должен свистеть: тег 2 исчез, структура изменилась")

    def test_whistle_identical_bags(self):
        """
        Не должен свистеть на идентичных мешках.
        Идентичные случаи — это Folding (свертка), а не опасность зацикливания.
        """
        bag_old = Counter({1: 1, 2: 1})
        bag_new = Counter({1: 1, 2: 1})

        self.assertFalse(TagBag.is_dangerous(bag_old, bag_new),
                         "Не должен свистеть: мешки идентичны (это случай для свертки)")

    def test_whistle_shrink(self):
        """Не должен свистеть, если мешок стал меньше."""
        bag_old = Counter({1: 10})
        bag_new = Counter({1: 5})

        self.assertFalse(TagBag.is_dangerous(bag_old, bag_new))

if __name__ == '__main__':
    unittest.main()