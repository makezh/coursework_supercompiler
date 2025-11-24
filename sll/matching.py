from sll.ast_nodes import Var, Ctr, FCall, IntLit


def match(pattern_arg, call_arg):
    """
    Пытается сопоставить один аргумент из паттерна с аргументом вызова.
    """

    # 1. Переменная "съедает" всё
    if isinstance(pattern_arg, Var):
        return {pattern_arg.name: call_arg}

    # 2. Числовой литерал (НОВОЕ)
    # Если паттерн ждет число (например, 1), а пришло 1 — это успех.
    if isinstance(pattern_arg, IntLit):
        # Проверяем: пришло ли число и равно ли оно нашему
        if isinstance(call_arg, IntLit) and pattern_arg.value == call_arg.value:
            return {}  # Совпало, новых переменных не нашли
        return None  # Не совпало

    # 3. Конструктор
    if isinstance(pattern_arg, Ctr):
        if not isinstance(call_arg, Ctr):
            return None  # Ждали конструктор, пришло что-то другое

        if pattern_arg.name != call_arg.name:
            return None  # Не совпало имя (Cons vs Nil)

        if len(pattern_arg.args) != len(call_arg.args):
            return None

        bindings = {}
        for p_sub, c_sub in zip(pattern_arg.args, call_arg.args):
            res = match(p_sub, c_sub)
            if res is None:
                return None
            bindings.update(res)

        return bindings

    return None


def substitute(expr, bindings):
    """
    Заменяет переменные в выражении expr на значения из словаря bindings.
    """
    # 1. Переменная — заменяем, если есть на что
    if isinstance(expr, Var):
        if expr.name in bindings:
            return bindings[expr.name]
        return expr

    # 2. Число — оставляем как есть (заменять внутри числа нечего)
    if isinstance(expr, IntLit):
        return expr

    # 3. Конструктор — рекурсивно заходим внутрь
    if isinstance(expr, Ctr):
        new_args = [substitute(arg, bindings) for arg in expr.args]
        return Ctr(expr.name, new_args)

    # 4. Вызов функции — рекурсивно заходим внутрь
    if isinstance(expr, FCall):
        new_args = [substitute(arg, bindings) for arg in expr.args]
        return FCall(expr.name, new_args)

    return expr
