from ast_nodes import Var, Ctr, FCall


def match(pattern_arg, call_arg):
    """
    Пытается сопоставить один аргумент из паттерна с аргументом вызова. \n
    pattern_arg: Часть паттерна (Var или Ctr) \n
    call_arg: То, с чем вызвали (Expr) \n

    Возвращает: dict {имя_переменной: значение} или None, если не совпало.
    """

    # СЛУЧАЙ 1: В паттерне стоит переменная (например, 'x')
    # Переменная "съедает" всё, что угодно.
    if isinstance(pattern_arg, Var):
        return {pattern_arg.name: call_arg}

    # СЛУЧАЙ 2: В паттерне стоит конструктор (например, [Cons x xs])
    # Мы должны убедиться, что в вызове ТОЖЕ конструктор с ТЕМ ЖЕ именем.
    if isinstance(pattern_arg, Ctr):

        # 2.1 Если пришел НЕ конструктор (например, вызов функции),
        # то в классической ленивой семантике мы пока не можем сопоставить.
        # Но для простого теста пока будем считать, что call_arg обязан быть Ctr.
        if not isinstance(call_arg, Ctr):
            return None

        # 2.2 Не совпали имена конструкторов (ждали [Z], пришло [S ...])
        if pattern_arg.name != call_arg.name:
            return None

        # 2.3 Количество аргументов у конструкторов должно совпадать
        if len(pattern_arg.args) != len(call_arg.args):
            return None

        # 2.4 Рекурсивно проверяем внутренности
        # Например: паттерн [Cons x xs], вызов [Cons [Z] [Nil]]
        # Нам нужно сопоставить x c [Z], и xs с [Nil]
        bindings = {}
        for p_sub, c_sub in zip(pattern_arg.args, call_arg.args):
            res = match(p_sub, c_sub)
            if res is None:
                return None  # Если хоть одно не подошло — всё не подошло
            bindings.update(res)

        return bindings

    return None


def substitute(expr, bindings):
    """
    Заменяет переменные в выражении expr на значения из словаря bindings. \n
    Например: expr = (add x y), bindings = {'x': [Z], 'y': [Nil]} \n
    Результат: (add [Z] [Nil])
    """
    # 1. Если это переменная - смотрим, есть ли для нее замена
    if isinstance(expr, Var):
        if expr.name in bindings:
            return bindings[expr.name]
        return expr  # Если замены нет, оставляем как есть

    # 2. Если это конструктор - рекурсивно меняем всё внутри него
    if isinstance(expr, Ctr):
        new_args = [substitute(arg, bindings) for arg in expr.args]
        return Ctr(expr.name, new_args)

    # 3. Если это вызов функции - тоже рекурсивно меняем аргументы
    if isinstance(expr, FCall):
        new_args = [substitute(arg, bindings) for arg in expr.args]
        return FCall(expr.name, new_args)

    return expr
