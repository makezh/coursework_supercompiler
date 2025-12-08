from sll.ast_nodes import FCall, Ctr, Var
from sll.matching import match, substitute


def step(expr, program):
    """
    Делает один шаг вычисления.
    Находит первый вызов функции, который можно выполнить, и раскрывает его.
    """

    # СЛУЧАЙ 1: Конструктор (например, [S (add ...)])
    # Сам конструктор не вычисляется, но внутри него могут быть вызовы.
    # Мы пытаемся вычислить аргументы слева направо.
    match expr:
        case Ctr(name, args):
            for i, arg in enumerate(args):
                new_arg = step(arg, program)
                if new_arg is not None:
                    new_args = list(args)
                    new_args[i] = new_arg
                    return Ctr(name, new_args, lineno=expr.lineno)
            return None

    # СЛУЧАЙ 2: Вызов функции (например, (add [Z] [Z]))
        case FCall(name, args):
            # ШАГ А: Пытаемся найти правило и применить его
            rules = [r for r in program.rules if r.pattern.name == name]

            for rule in rules:
                bindings = {}
                match_success = True

                # Сопоставляем все аргументы
                for call_arg, pat_arg in zip(args, rule.pattern.params):
                    res = match(pat_arg, call_arg)
                    if res is None:
                        match_success = False
                        break
                    bindings.update(res)

                if match_success:
                    # Нашли правило! Делаем подстановку (rewrite)
                    return substitute(rule.body, bindings)

            # ШАГ Б: Если правила не подошли, возможно, нам мешает невычисленный аргумент?
            # Научник просил проверять ВСЕ аргументы, а не только первый.
            # Ищем первый аргумент, который является вызовом функции, и пробуем его редуцировать.
            for i, arg in enumerate(args):
                if isinstance(arg, FCall):
                    new_arg = step(arg, program)
                    if new_arg is not None:
                        # Мы продвинулись внутри аргумента!
                        # Возвращаем обновленный внешний вызов
                        new_args = list(args)
                        new_args[i] = new_arg
                        return FCall(name, new_args, lineno=expr.lineno)

            return None # Тупик (Normal Form или ошибка)

        case _:
            return None
