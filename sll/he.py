from sll.ast_nodes import Expr, Var, Ctr, FCall, IntLit


def he(t1: Expr, t2: Expr) -> bool:
    """
    Проверяет, вкладывается ли t1 в t2 гомеоморфно (t1 <| t2).
    """

    # 1. Сначала проверяем прямое сходство (Coupling / Variables / Literals)
    match (t1, t2):

        # Переменные: Любая переменная вкладывается в любую переменную
        case (Var(_), Var(_)):
            return True

        # Числа: Должны быть равны
        case (IntLit(v1), IntLit(v2)):
            if v1 == v2:
                return True

        # Сочетание (Coupling) для Конструкторов
        # Имена совпадают, арность совпадает -> проверяем аргументы попарно
        case (Ctr(n1, args1), Ctr(n2, args2)) if n1 == n2:
            assert len(args1) == len(args2), f"Арность конструктора {n1} не совпадает: {len(args1)} vs {len(args2)}"
            # Проверяем: a1 <| b1 И a2 <| b2 ...
            if all(he(a, b) for a, b in zip(args1, args2)):
                return True

        # Сочетание (Coupling) для Функций
        # g(a) <| g(b)
        case (FCall(n1, args1), FCall(n2, args2)) if n1 == n2:
            assert len(args1) == len(args2), f"Арность функции {n1} не совпадает!"
            if all(he(a, b) for a, b in zip(args1, args2)):
                return True

        case _:
            pass # Если не совпало - идем к правилу diving

    # 2. Если прямое сходство не сработало, пробуем diving
    # Пытаемся найти t1 где-то в глубине аргументов t2.
    match t2:
        case Ctr(_, args) | FCall(_, args):
            # t1 <| f(b1...bn), если t1 <| b1 ИЛИ t1 <| b2 ...
            return any(he(t1, arg) for arg in args)

        case _:
            return False