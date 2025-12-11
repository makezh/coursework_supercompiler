from sll.ast_nodes import (Program, Var, Ctr, FCall, IntLit, TypeExpr,
                           TypeDef, ConstrDef, FunSig)


class TypeCheckerError(Exception):
    def __init__(self, lineno, message):
        self.lineno = lineno
        self.message = message
        super().__init__(f"Строка {lineno}: {message}")


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
        return allow_instantiation

    # Имена должны совпадать (List == List)
    if actual.name != expected.name:
        return False

    # Количество параметров внутри [] должно совпадать
    if len(actual.params) != len(expected.params):
        return False

    # Рекурсивно проверяем внутренности
    return all(types_match(p1, p2, ctx, allow_instantiation) for p1, p2 in zip(actual.params, expected.params))


def unify(template: TypeExpr, concrete: TypeExpr, mapping: dict, ctx: TypeContext, lineno: int):
    """
    Сопоставляет Шаблон (template) с Конкретным типом (concrete).
    Наполняет mapping знаниями о дженериках.
    Если находит противоречие — кидает ошибку.
    """
    # 1. Если template — это Дженерик
    if template.name not in ctx.defined_types:

        # Если мы уже встречали этот дженерик раньше
        if template.name in mapping:
            known_type = mapping[template.name]
            # Проверяем, что новый тип (concrete) совместим с тем, что мы узнали ранее (known_type).
            # allow_instantiation=True, чтобы "гибкие" типы ([Nil], результат функции)
            # могли подстроиться под уже зафиксированный жесткий тип.
            if not types_match(concrete, known_type, ctx, allow_instantiation=True):
                raise TypeCheckerError(lineno,
                                       f"Конфликт типов для переменной '{template.name}': ожидали {known_type}, получили {concrete}")

        # Если это первая встреча с этим дженериком
        else:
            # Условно запоминаем: теперь 'x' — это 'Bool'
            mapping[template.name] = concrete
        return

    # 2. Если это конкретные типы (List, Nat, Bool)
    if template.name != concrete.name:
        raise TypeCheckerError(lineno, f"Несовпадение типов: ожидалось {template.name}, получено {concrete.name}")

    # 3. Количество параметров внутри [] должно совпадать
    if len(template.params) != len(concrete.params):
        raise TypeCheckerError(lineno, f"Неверное число параметров типа у {template.name}")

    # 4. Рекурсия: ныряем внутрь
    for p_temp, p_conc in zip(template.params, concrete.params):
        unify(p_temp, p_conc, mapping, ctx, lineno)


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


def infer_type(expr, ctx: TypeContext, scopes: dict) -> TypeExpr:
    """Вычисляет тип выражения"""
    match expr:
        case Var(name):
            if name not in scopes:
                raise TypeCheckerError(expr.lineno, f"Неизвестная переменная '{name}'")
            return scopes[name]

        case IntLit():
            return TypeExpr("Int", [], lineno=expr.lineno)

        case Ctr(name, args):
            if name not in ctx.constructors:
                raise TypeCheckerError(expr.lineno, f"Неизвестный конструктор {name}")

            type_def, arg_types_template = ctx.constructors[name]

            if len(args) != len(arg_types_template):
                raise TypeCheckerError(expr.lineno, f"Конструктор {name} ждет {len(arg_types_template)} аргументов")

            mapping = {}
            for arg_expr, arg_template in zip(args, arg_types_template):
                arg_actual_type = infer_type(arg_expr, ctx, scopes)
                unify(arg_template, arg_actual_type, mapping, ctx, expr.lineno)

            # Воссоздаем результирующий тип
            result_params = []
            for param_name in type_def.params:
                result_params.append(mapping.get(param_name, TypeExpr(param_name, [], lineno=expr.lineno)))

            return TypeExpr(type_def.name, result_params, lineno=expr.lineno)

        case FCall(name, args):
            if name not in ctx.functions:
                raise TypeCheckerError(expr.lineno, f"Вызов неизвестной функции {name}")

            sig = ctx.functions[name]

            if len(args) != len(sig.arg_types):
                raise TypeCheckerError(expr.lineno, f"Функция {name} ждет {len(sig.arg_types)} аргументов")

            mapping = {}
            for arg_expr, arg_template in zip(args, sig.arg_types):
                arg_actual_type = infer_type(arg_expr, ctx, scopes)
                unify(arg_template, arg_actual_type, mapping, ctx, expr.lineno)

            return resolve_type(sig.ret_type, mapping)

        case _:
            raise TypeCheckerError(expr.lineno, "Неизвестное выражение")


def check_pattern(pat, expected: TypeExpr, ctx: TypeContext, scopes: dict):
    match pat:
        # 1. ПЕРЕМЕННАЯ (x)
        # Если мы встретили x, и мы ожидали Int, значит x имеет тип Int.
        case Var(name):
            # нельзя (add x x)
            if name in scopes:
                raise TypeCheckerError(pat.lineno, f"Переменная '{name}' уже объявлена")
            scopes[name] = expected

        # 2. ЧИСЛО (42)
        case IntLit():
            if expected.name != 'Int':
                raise TypeCheckerError(pat.lineno, f"Ожидался {expected}, получено число")

        # 3. КОНСТРУКТОР ([Cons x xs])
        case Ctr(name, args):
            # Знаем ли мы такой конструктор?
            if name not in ctx.constructors:
                raise TypeCheckerError(pat.lineno, f"Неизвестный конструктор {name}")

            # Достаем его определение из справочника
            type_def, c_arg_types = ctx.constructors[name]

            # Тот ли это тип?
            if type_def.name != expected.name:
                raise TypeCheckerError(pat.lineno,
                                       f"Конструктор {name} создает {type_def.name}, а нужно {expected.name}")

            # Вычисляем mapping
            # Definition: [List a]
            # Expected:   [List Int]
            # Значит:     a -> Int
            if len(type_def.params) != len(expected.params):
                raise TypeCheckerError(pat.lineno, f"Несовпадение параметров типа")

            # Создаем словарь {'a': Int}
            mapping = {t_var: t_conc for t_var, t_conc in zip(type_def.params, expected.params)}

            # Проверяем аргументы конструктора
            if len(args) != len(c_arg_types):
                raise TypeCheckerError(pat.lineno, f"Конструктор {name} ждет {len(c_arg_types)} аргументов")

            for arg_node, abstract_type in zip(args, c_arg_types):
                # Превращаем абстрактное 'a' в 'Int'
                concrete_type = resolve_type(abstract_type, mapping)
                # Рекурсивно проверяем аргумент
                check_pattern(arg_node, concrete_type, ctx, scopes)

        case _:
            raise TypeCheckerError(pat.lineno, f"Ошибка в паттерне")


def check_program(prog: Program):
    ctx = TypeContext()
    print("🔎 Запуск семантического анализа...")

    # Заполняем справочник Types
    for t in prog.types:
        if t.name in ctx.defined_types:
            raise TypeCheckerError(t.lineno, f"Повторное определение типа {t.name}")
        ctx.defined_types[t.name] = t

        for c in t.constructors:
            if c.name in ctx.constructors:
                raise TypeCheckerError(c.lineno, f"Повторное определение конструктора {c.name}")
            ctx.constructors[c.name] = (t, c.arg_types)

    # Заполняем справочник Functions
    for s in prog.signatures:
        if s.name in ctx.functions:
            raise TypeCheckerError(s.lineno, f"Повторное определение функции {s.name}")
        ctx.functions[s.name] = s

    # Проверяем каждое правило
    for rule in prog.rules:
        f_name = rule.pattern.name

        if f_name not in ctx.functions:
            raise TypeCheckerError(rule.lineno, f"Правило для неизвестной функции '{f_name}'")

        sig = ctx.functions[f_name]

        if len(rule.pattern.params) != len(sig.arg_types):
            raise TypeCheckerError(rule.lineno, f"Функция {f_name} ждет {len(sig.arg_types)} аргументов")

        var_scopes = {}

        # Проверяем Паттерн
        for pat_arg, expected_type in zip(rule.pattern.params, sig.arg_types):
            check_pattern(pat_arg, expected_type, ctx, var_scopes)

        # Проверяем Тело
        actual_body_type = infer_type(rule.body, ctx, var_scopes)

        # Разрешаем инстанциацию (allow_instantiation=True),
        # так как функция может возвращать дженерик [List x], который станет конкретным [List Int]
        if not types_match(actual_body_type, sig.ret_type, ctx, allow_instantiation=True):
            raise TypeCheckerError(rule.lineno, f"Функция {f_name} должна возвращать {sig.ret_type}, а возвращает {actual_body_type}")

    print("✅ Семантический анализ завершен успешно!")
