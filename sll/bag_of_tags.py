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
        if not isinstance(expr, Expr):
            return bag

        # Добавляем тег только если он существует
        if expr.tag is not None:
            bag[expr.tag] += 1

        # Рекурсивный спуск по всем видам узлов
        match expr:
            case Ctr(_, args) | FCall(_, args):
                for arg in args:
                    bag.update(TagBag.collect(arg))

            case Let(bindings, body):
                # bindings: список (name, expr)
                for _, val_expr in bindings:
                    bag.update(TagBag.collect(val_expr))
                bag.update(TagBag.collect(body))

            case _:
                pass

        return bag

    @staticmethod
    def is_dangerous(bag_old: Counter, bag_new: Counter) -> bool:
        """
        Проверяет условие свистка.
        """
        # Если мешок пуст, сравнивать нечего
        if not bag_old:
            return False

        return bag_new >= bag_old