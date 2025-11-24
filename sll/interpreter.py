from ast_nodes import FCall, Ctr, Var
from matching import match, substitute

def step(expr, program):
    """
    Делает один шаг вычисления.
    Находит первый вызов функции, который можно выполнить, и раскрывает его.
    """

    # СЛУЧАЙ 1: Конструктор (например, [S (add ...)])
    # Сам конструктор не вычисляется, но внутри него могут быть вызовы.
    # Мы пытаемся вычислить аргументы слева направо.
    if isinstance(expr, Ctr):
        for i, arg in enumerate(expr.args):
            # Пробуем сделать шаг в аргументе
            new_arg = step(arg, program)
            if new_arg is not None:
                # Если аргумент изменился, возвращаем обновленный конструктор
                new_args = list(expr.args) # Копируем список
                new_args[i] = new_arg
                return Ctr(expr.name, new_args)
        return None # Если внутри всё чисто (нет вызовов), шаг сделать нельзя

    # СЛУЧАЙ 2: Вызов функции (например, (add [Z] [Z]))
    if isinstance(expr, FCall):
        # Сначала проверим, не нужно ли вычислить аргументы?
        # В "ленивом" языке (как SLL) мы обычно НЕ вычисляем аргументы сразу,
        # а передаем их как есть. НО! Чтобы сработал паттерн-матчинг,
        # нам нужно, чтобы первый аргумент был Конструктором, а не другим вызовом.

        # Пример: (add (add [Z] [Z]) [Z])
        # Мы не можем выполнить внешний add, пока не посчитаем внутренний,
        # потому что паттерн ждет [Z] или [S], а видит (add ...).

        # Поэтому: Если первый аргумент - это вызов функции, надо сначала посчитать его.
        if len(expr.args) > 0 and isinstance(expr.args[0], FCall):
             new_first_arg = step(expr.args[0], program)
             if new_first_arg is not None:
                 new_args = list(expr.args)
                 new_args[0] = new_first_arg
                 return FCall(expr.name, new_args)

        # Теперь пытаемся найти правило в программе
        rules = []
        # Ищем правила для этой функции.
        # (В реальном проекте тут должен быть словарь {func_name: [rules]}, чтобы не бегать циклом)
        for rule in program.rules:
            if rule.pattern.name == expr.name:
                rules.append(rule)

        # Пробегаем по правилам и ищем подходящее
        for rule in rules:
            # Собираем общий словарь подстановок для ВСЕХ аргументов
            all_bindings = {}
            match_success = True

            # Сопоставляем каждый аргумент вызова с аргументом паттерна
            # Вызов: (add [Z] y)
            # Паттерн: (add [Z] k)
            for call_arg, pat_arg in zip(expr.args, rule.pattern.params):
                res = match(pat_arg, call_arg)
                if res is None:
                    match_success = False
                    break
                all_bindings.update(res)

            if match_success:
                # УРА! Нашли правило.
                # Берем правую часть правила и подставляем значения
                return substitute(rule.body, all_bindings)

        return None # Тупик (нет подходящего правила)

    # Переменные и прочее не вычисляются
    return None