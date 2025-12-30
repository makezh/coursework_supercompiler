from collections import Counter
from sll.ast_nodes import Expr, Ctr, FCall, Let

class TagBag:
    """
    Логика работы с мешками тегов.
    """

    @staticmethod
    def collect(expr: Expr) -> Counter:
        """
        Рекурсивно собирает все теги из выражения в Counter.
        Игнорирует tag=None (свежие переменные и конструкторы, созданные драйвером).
        """
        bag = Counter()

        # Если у узла есть тег - добавляем его
        tag_val = expr.tag if expr.tag is not None else -1
        bag[tag_val] += 1

        # Рекурсивный спуск
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

        keys_old = set(bag_old.keys())
        keys_new = set(bag_new.keys())

        # 1. Проверка на совпадение "состава" (ингредиентов)
        # Если в новом появились теги, которых не было в старом - это не зацикливание,
        # это мы просто пошли в другую ветку кода.
        # А вот если ключи равны (или new подмножество old), то мы топчемся на месте.
        # В статье строгое равенство сетов:
        if keys_old != keys_new:
            return False

        # ОТЛАДКА
        # print(f"CHECK: {bag_old} vs {bag_new}")

        # 2. Проверка размера (Weight)
        size_old = bag_old.total() # Python 3.10+ метод total()
        size_new = bag_new.total()

        return size_new > size_old