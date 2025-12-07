from sll.ast_nodes import Var, Ctr, FCall, IntLit


def match(pattern_arg, call_arg):
    """
    Пытается сопоставить один аргумент из паттерна с аргументом вызова.
    """

    match pattern_arg:
        # 1. Переменная в паттерне — жадно захватывает всё
        case Var(name):
            return {name: call_arg}

        # 2. Число в паттерне (42)
        case IntLit(p_val):
            # Проверяем, что пришло тоже число и оно равно нашему
            match call_arg:
                case IntLit(c_val) if c_val == p_val:
                    return {}
                case _:
                    return None

        # 3. Конструктор в паттерне ([Cons ...])
        case Ctr(p_name, p_args):
            match call_arg:
                case Ctr(c_name, c_args):
                    if p_name != c_name or len(p_args) != len(c_args):
                        return None

                    bindings = {}
                    for p_sub, c_sub in zip(p_args, c_args):
                        res = match(p_sub, c_sub)
                        if res is None:
                            return None
                        bindings.update(res)
                    return bindings
                case _:
                    # Если ждали конструктор, а пришел вызов функции или число
                    return None

        case _:
            return None


def substitute(expr, bindings):
    """
    Заменяет переменные в выражении на значения из bindings.
    """
    match expr:
        case Var(name):
            return bindings.get(name, expr)

        case Ctr(name, args):
            new_args = [substitute(a, bindings) for a in args]
            return Ctr(name, new_args, lineno=expr.lineno)

        case FCall(name, args):
            new_args = [substitute(a, bindings) for a in args]
            return FCall(name, new_args, lineno=expr.lineno)

        case IntLit():
            return expr

        case _:
            return expr