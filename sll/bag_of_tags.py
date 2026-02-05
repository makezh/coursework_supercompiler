from collections import Counter
from sll.ast_nodes import Expr, Ctr, FCall, Let

class TagBag:
    """
    Логика работы с мешками тегов.
    """

    @staticmethod
    def collect(expr: Expr) -> Counter:
        """
        Рекурсивно собирает теги, пришедшие из исходной программы.
        Если у узла tag=None, он игнорируется (не вносит вклад в мешок).
        """
        bag = Counter()

        # Добавляем тег только если он существует
        if expr.tag is not None:
            bag[expr.tag] += 1

        # Рекурсивный спуск по всем видам узлов
        match expr:
            case Ctr(_, args) | FCall(_, args):
                for arg in args:
                    bag.update(TagBag.collect(arg))

            case Let(_, val, body):
                bag.update(TagBag.collect(val))
                bag.update(TagBag.collect(body))

            case _:
                pass

        return bag

    @staticmethod
    def is_dangerous(bag_old: Counter, bag_new: Counter) -> bool:
        """
        Проверяет условие свистка.
        Возвращает True, если bag_new 'больше и опаснее' bag_old.

        Критерий (по Bolingbroke & Peyton Jones):
        1. Множество уникальных тегов совпадает (set(B1) == set(B2)).
           Это значит, мы не зашли в новый код, а крутимся в старом.
        2. Общее количество тегов выросло (sum(B2) > sum(B1)).
           Это значит, данные накапливаются.
        """
        # Если мешок пуст, сравнивать нечего
        if not bag_old:
            return False

        # 1. Проверяем мультимножественное включение
        is_superset = (bag_new >= bag_old)

        if not is_superset:
            return False

        # 2. Если это надмножество, проверяем, вырос ли вес
        # (чтобы не свистеть на идентичных конфигурациях, их обработает Folding)
        return bag_new.total() > bag_old.total()