from sll.ast_nodes import Program, Var, Ctr, FCall, IntLit, TypeExpr


class TypeCheckerError(Exception):
    pass


class TypeContext:
    def __init__(self):
        self.defined_types = {}
        self.constructors = {}
        self.functions = {}


def check_program(prog: Program):
    ctx = TypeContext()
    print("🔎 Запуск семантического анализа...")

    # 1. СБОР ИНФОРМАЦИИ
    # Собираем типы
    for t in prog.types:
        if t.name in ctx.defined_types:
            raise TypeCheckerError(f"Повторное определение типа {t.name}")
        ctx.defined_types[t.name] = t

        for c in t.constructors:
            if c.name in ctx.constructors:
                raise TypeCheckerError(f"Повторное определение конструктора {c.name}")
            ctx.constructors[c.name] = (t, c.arg_types)

    # Собираем сигнатуры функций
    for s in prog.signatures:
        if s.name in ctx.functions:
            raise TypeCheckerError(f"Повторное определение функции {s.name}")
        ctx.functions[s.name] = s

    # 2. ПРОВЕРКА ТЕЛ ФУНКЦИЙ
    for rule in prog.rules:
        fun_name = rule.pattern.name

        # 2.1 Знаем ли мы такую функцию?
        if fun_name not in ctx.functions:
            raise TypeCheckerError(f"Правило для неизвестной функции '{fun_name}' (нет сигнатуры)")

        sig = ctx.functions[fun_name]

        # 2.2 Совпадает ли количество аргументов?
        if len(rule.pattern.params) != len(sig.arg_types):
            raise TypeCheckerError(
                f"Функция {fun_name} ждет {len(sig.arg_types)} аргументов, получено {len(rule.pattern.params)}")

        # var_types: Словарь { 'имя_переменной': TypeExpr }
        # Мы наполняем его, когда разбираем паттерн (слева)
        var_types = {}

        # 2.3 Проверка паттерна (Left Hand Side)
        for pat_arg, expected_type in zip(rule.pattern.params, sig.arg_types):
            check_pattern(pat_arg, expected_type, ctx, var_types)

        # 2.4 Проверка выражения (Right Hand Side)
        # Выражение должно возвращать тот тип, который заявлен в сигнатуре
        check_expr(rule.body, sig.ret_type, ctx, var_types)

    print("✅ Проверка типов пройдена успешно!")


def check_pattern(pat, expected_type: TypeExpr, ctx: TypeContext, var_types: dict):
    """Рекурсивно проверяет паттерн и заполняет var_types"""

    # А. Переменная (x)
    if isinstance(pat, Var):
        # Запоминаем, что x теперь имеет тип expected_type
        if pat.name in var_types:
            # Линейность: переменную нельзя использовать дважды в паттерне (add x x)
            raise TypeCheckerError(f"Переменная {pat.name} используется дважды в паттерне")
        var_types[pat.name] = expected_type
        return

    # Б. Число (42)
    if isinstance(pat, IntLit):
        # Для простоты считаем, что числа - это всегда Int - совместимо со всем
        return

    # В. Конструктор [S x]
    if isinstance(pat, Ctr):
        if pat.name not in ctx.constructors:
            raise TypeCheckerError(f"Неизвестный конструктор {pat.name}")

        type_def, arg_types_def = ctx.constructors[pat.name]

        # Проверяем, что конструктор относится к ожидаемому типу
        if type_def.name != expected_type.name:
            raise TypeCheckerError(
                f"Конструктор {pat.name} создает тип {type_def.name}, а ожидалось {expected_type.name}")

        if len(pat.args) != len(arg_types_def):
            raise TypeCheckerError(f"Конструктор {pat.name} ждет {len(arg_types_def)} арг, дано {len(pat.args)}")

        # Рекурсивно проверяем аргументы конструктора
        for sub_pat, sub_type in zip(pat.args, arg_types_def):
            check_pattern(sub_pat, sub_type, ctx, var_types)


def check_expr(expr, expected_type: TypeExpr, ctx: TypeContext, var_types: dict):
    """Проверяет выражение справа. Оно должно вернуть expected_type."""

    # 1. Переменная
    if isinstance(expr, Var):
        if expr.name not in var_types:
            raise TypeCheckerError(f"Неизвестная переменная '{expr.name}' (не объявлена в паттерне)")
        actual_type = var_types[expr.name]

        # Сравниваем имена типов
        if actual_type.name != expected_type.name:
            raise TypeCheckerError(
                f"Переменная '{expr.name}' имеет тип {actual_type.name}, а здесь ожидается {expected_type.name}")

    # 2. Число
    elif isinstance(expr, IntLit):
        pass  # Числа совместимы со всем (упростим)

    # 3. Конструктор [Cons x xs]
    elif isinstance(expr, Ctr):
        if expr.name not in ctx.constructors:
            raise TypeCheckerError(f"Неизвестный конструктор {expr.name}")

        type_def, arg_types_def = ctx.constructors[expr.name]

        if type_def.name != expected_type.name:
            raise TypeCheckerError(
                f"Конструктор {expr.name} возвращает {type_def.name}, а ожидалось {expected_type.name}")

        if len(expr.args) != len(arg_types_def):
            raise TypeCheckerError(f"Неверное число аргументов у {expr.name}")

        for arg, type_def_arg in zip(expr.args, arg_types_def):
            check_expr(arg, type_def_arg, ctx, var_types)

    # 4. Вызов функции (add x y)
    elif isinstance(expr, FCall):
        if expr.name not in ctx.functions:
            raise TypeCheckerError(f"Вызов неизвестной функции {expr.name}")

        sig = ctx.functions[expr.name]

        # Функция возвращает то, что нужно?
        if sig.ret_type.name != expected_type.name:
            raise TypeCheckerError(f"Функция {expr.name} возвращает {sig.ret_type.name}, а нужно {expected_type.name}")

        if len(expr.args) != len(sig.arg_types):
            raise TypeCheckerError(f"Неверное число аргументов в вызове {expr.name}")

        # Проверяем аргументы, которые мы передаем функции
        for arg, arg_expected_type in zip(expr.args, sig.arg_types):
            check_expr(arg, arg_expected_type, ctx, var_types)
