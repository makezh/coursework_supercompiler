from sll.ast_nodes import (Program, Var, Ctr, FCall, IntLit, TypeExpr,
                           TypeDef, ConstrDef, FunSig)


class TypeCheckerError(Exception):
    pass


class TypeContext:
    def __init__(self):
        self.defined_types = {}
        self.constructors = {}
        self.functions = {}


def types_match(actual: TypeExpr, expected: TypeExpr, ctx: TypeContext, allow_instantiation: bool = False) -> bool:
    """
    Проверяет, подходит ли тип actual под требования expected.
    """
    # Дженерик совместим с чем угодно.
    if expected.name not in ctx.defined_types:
        return True
    if actual.name not in ctx.defined_types:
        if allow_instantiation:
            return True
        return False

    # Имена должны совпадать (List == List)
    if actual.name != expected.name:
        return False

    # Количество параметров внутри [] должно совпадать
    if len(actual.params) != len(expected.params):
        return False

    # Рекурсивно проверяем внутренности
    return all(types_match(p1, p2, ctx, allow_instantiation) for p1, p2 in zip(actual.params, expected.params))


def resolve_type(abstract_type: TypeExpr, mapping: dict) -> TypeExpr:
    """
    Заменяет переменные типа на конкретные типы по карте.
    mapping = {'a': TypeExpr('Int')}
    Вход: TypeExpr('a') -> Выход: TypeExpr('Int')
    Вход: TypeExpr('List', ['a']) -> Выход: TypeExpr('List', ['Int'])
    """
    # Если имя типа — меняем на конкретный тип
    if abstract_type.name in mapping:
        return mapping[abstract_type.name]

    # Иначе рекурсивно ныряем внутрь
    new_params = [resolve_type(p, mapping) for p in abstract_type.params]

    # Возвращаем новый тип с подставленными значениями
    return TypeExpr(abstract_type.name, new_params, lineno=abstract_type.lineno)


def check_pattern(pat, expected: TypeExpr, ctx: TypeContext, scopes: dict):
    match pat:
        # 1. ПЕРЕМЕННАЯ (x)
        # Если мы встретили x, и мы ожидали Int, значит x имеет тип Int.
        case Var(name):
            # нельзя (add x x)
            if name in scopes:
                raise TypeCheckerError(f"Строка {pat.lineno}: Переменная '{name}' уже объявлена")
            scopes[name] = expected

        # 2. ЧИСЛО (42)
        case IntLit():
            if expected.name != 'Int':
                raise TypeCheckerError(f"Строка {pat.lineno}: Ожидался {expected}, получено число")

        # 3. КОНСТРУКТОР ([Cons x xs])
        case Ctr(name, args):
            # Знаем ли мы такой конструктор?
            if name not in ctx.constructors:
                raise TypeCheckerError(f"Строка {pat.lineno}: Неизвестный конструктор {name}")

            # Достаем его определение из справочника
            type_def, c_arg_types = ctx.constructors[name]

            # Тот ли это тип?
            if type_def.name != expected.name:
                raise TypeCheckerError(
                    f"Строка {pat.lineno}: Конструктор {name} создает {type_def.name}, а нужно {expected.name}")

            # Вычисляем mapping
            # Definition: [List a]
            # Expected:   [List Int]
            # Значит:     a -> Int
            if len(type_def.params) != len(expected.params):
                raise TypeCheckerError(f"Строка {pat.lineno}: Несовпадение параметров типа")

            # Создаем словарь {'a': Int}
            mapping = {t_var: t_conc for t_var, t_conc in zip(type_def.params, expected.params)}

            # Проверяем аргументы конструктора
            if len(args) != len(c_arg_types):
                raise TypeCheckerError(f"Строка {pat.lineno}: Конструктор {name} ждет {len(c_arg_types)} аргументов")

            for arg_node, abstract_type in zip(args, c_arg_types):
                # Превращаем абстрактное 'a' в 'Int'
                concrete_type = resolve_type(abstract_type, mapping)
                # Рекурсивно проверяем аргумент
                check_pattern(arg_node, concrete_type, ctx, scopes)

        case _:
            raise TypeCheckerError(f"Строка {pat.lineno}: Ошибка в паттерне")


def check_expr(expr, expected: TypeExpr, ctx: TypeContext, scopes: dict):
    match expr:
        # 1. ПЕРЕМЕННАЯ
        case Var(name):
            if name not in scopes:
                raise TypeCheckerError(f"Строка {expr.lineno}: Неизвестная переменная '{name}'")
            actual = scopes[name]
            # Проверяем, совпадает ли тип переменной с тем, что мы должны вернуть
            if not types_match(actual, expected, ctx, allow_instantiation=False):
                raise TypeCheckerError(
                    f"Строка {expr.lineno}: Переменная '{name}' имеет тип {actual}, а ожидается {expected}")

        # 2. ЧИСЛО
        case IntLit():
            if expected.name != 'Int':
                raise TypeCheckerError(f"Строка {expr.lineno}: Ожидался тип {expected}, получено число")

        # 3. КОНСТРУКТОР
        case Ctr(name, args):
            if name not in ctx.constructors:
                raise TypeCheckerError(f"Строка {expr.lineno}: Неизвестный конструктор {name}")

            type_def, c_arg_types = ctx.constructors[name]

            if type_def.name != expected.name:
                raise TypeCheckerError(f"Строка {expr.lineno}: {name} создает {type_def.name}, а нужно {expected.name}")

            if len(type_def.params) != len(expected.params):
                raise TypeCheckerError(f"Строка {expr.lineno}: Несовпадение параметров типа")
            mapping = {t_var: t_conc for t_var, t_conc in zip(type_def.params, expected.params)}

            if len(args) != len(c_arg_types):
                raise TypeCheckerError(f"Строка {expr.lineno}: Неверное число аргументов у {name}")

            for arg_node, abstract_type in zip(args, c_arg_types):
                concrete_type = resolve_type(abstract_type, mapping)
                check_expr(arg_node, concrete_type, ctx, scopes)

        # 4. ВЫЗОВ ФУНКЦИИ
        case FCall(name, args):
            if name not in ctx.functions:
                raise TypeCheckerError(f"Строка {expr.lineno}: Вызов неизвестной функции {name}")

            sig = ctx.functions[name]

            # А. Возвращает ли функция то, что нам нужно?
            if not types_match(sig.ret_type, expected, ctx, allow_instantiation=True):
                raise TypeCheckerError(
                    f"Строка {expr.lineno}: Функция {name} возвращает {sig.ret_type}, а нужно {expected}")

            # Б. Проверяем количество аргументов
            if len(args) != len(sig.arg_types):
                raise TypeCheckerError(f"Строка {expr.lineno}: Неверное число аргументов у функции {name}")

            # В. Проверяем сами аргументы
            for arg_node, sig_arg_type in zip(args, sig.arg_types):
                # Рекурсивно проверяем, что переданный аргумент соответствует сигнатуре функции
                check_expr(arg_node, sig_arg_type, ctx, scopes)

        case _:
            raise TypeCheckerError(f"Строка {expr.lineno}: Неизвестное выражение")


def check_program(prog: Program):
    ctx = TypeContext()
    print("🔎 Запуск семантического анализа...")

    # Заполняем справочник Types
    for t in prog.types:
        if t.name in ctx.defined_types:
            raise TypeCheckerError(f"Строка {t.lineno}: Повторное определение типа {t.name}")
        ctx.defined_types[t.name] = t

        for c in t.constructors:
            if c.name in ctx.constructors:
                raise TypeCheckerError(f"Строка {c.lineno}: Повторное определение конструктора {c.name}")
            ctx.constructors[c.name] = (t, c.arg_types)

    # аполняем справочник Functions
    for s in prog.signatures:
        if s.name in ctx.functions:
            raise TypeCheckerError(f"Строка {s.lineno}: Повторное определение функции {s.name}")
        ctx.functions[s.name] = s

    # Проверяем каждое правило
    for rule in prog.rules:
        f_name = rule.pattern.name

        if f_name not in ctx.functions:
            raise TypeCheckerError(f"Строка {rule.lineno}: Правило для неизвестной функции '{f_name}'")

        sig = ctx.functions[f_name]

        if len(rule.pattern.params) != len(sig.arg_types):
            raise TypeCheckerError(f"Строка {rule.lineno}: Функция {f_name} ждет {len(sig.arg_types)} аргументов")

        var_scopes = {}

        # Проверяем Паттерн
        for pat_arg, expected_type in zip(rule.pattern.params, sig.arg_types):
            check_pattern(pat_arg, expected_type, ctx, var_scopes)

        # Проверяем Тело
        check_expr(rule.body, sig.ret_type, ctx, var_scopes)

    print("✅ Семантический анализ завершен успешно!")
