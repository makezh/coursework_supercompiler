from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

from sll.ast_nodes import Expr, Var, Ctr, FCall, Program, Pattern, IntLit, TypeExpr
from sll.matching import match as match_term, substitute, \
    MatchSuccess, MatchNarrowing, MatchFail  # Переименовал match, чтобы не путать с match/case
from sll.process_tree import Contraction


# --- Генератор имен ---
class NameGen:
    def __init__(self):
        self.counter = 0

    def fresh_var(self, prefix="v") -> str:
        self.counter += 1
        return f"{prefix}{self.counter}"


# --- Результаты шага драйвинга ---
# TransientStep (Транзитный шаг) — шаг вычисления, при котором вызов функции
# однозначно заменяется на её тело без ветвления.

# DecomposeStep (Декомпозиция) — шаг разбиения пассивного конструктора (например, [Cons x xs])
# на составные части-аргументы для их независимой обработки.

# VariantStep (Ветвление) — шаг разбора случаев, при котором выполнение расщепляется
# на несколько веток в зависимости от всех конструкторов типа этой переменной

# StopStep (Остановка) — терминальный шаг, означающий, что выражение (свободная переменная или литерал)
# не может быть вычислено или преобразовано дальше.

@dataclass
class DriveStep: pass


@dataclass
class TransientStep(DriveStep):
    next_expr: Expr


@dataclass
class DecomposeStep(DriveStep):
    parts: List[Expr]


@dataclass
class VariantStep(DriveStep):
    # Возвращаем не только выражение ветки, но и новые типы для нее
    branches: List[Tuple[Expr, Contraction, Dict[str, TypeExpr]]]


@dataclass
class StopStep(DriveStep):
    pass


# --- Драйвер ---

class Driver:
    def __init__(self, program: Program):
        self.program = program
        self.name_gen = NameGen()

        # Словарь: Имя типа -> Определение (TypeDef)
        # Пример: 'List' -> TypeDef(name='List', constructors=[...])
        self.type_map = {t.name: t for t in program.types}

    def drive(self, expr: Expr, var_types: Dict[str, TypeExpr]) -> DriveStep:
        """
        Главная функция.
        Принимает выражение И известные типы переменных (var_types).
        """
        match expr:

            # 1. Конструктор (Пассивные данные)
            case Ctr(_, args):
                return DecomposeStep(parts=args)

            # 2. Переменная или Число (Лист)
            case Var(_) | IntLit(_):
                return StopStep()

            # 3. Вызов функции
            case FCall(_, _):
                # Здесь будет основная логика (Transient / Variant / Nested)
                return self._drive_call(expr, var_types)

            case _:
                return StopStep()

    def _drive_call(self, expr: FCall, var_types: Dict[str, TypeExpr]) -> DriveStep:
        """
        Rule-Based Driving для вызова функции.
        """
        branches = []

        # 1. Ищем правила для этой функции
        rules = [r for r in self.program.rules if r.pattern.name == expr.name]

        for rule in rules:
            pat_dummy = FCall("dummy", rule.pattern.params)
            call_dummy = FCall("dummy", expr.args)

            res = match_term(pat_dummy, call_dummy)

            match res:
                case MatchSuccess(bindings):
                    # Почему поменял:
                    # Если до этого мы уже нашли правила, требующие сужения (branches не пуст),
                    # то мы НЕ МОЖЕМ применять это правило, так как более приоритетные
                    # правила "застряли" на переменной. Мы обязаны делать ветвление.
                    if branches:
                        return VariantStep(branches=branches)

                    # Если препятствий не было — редуцируем
                    new_expr = substitute(rule.body, bindings)
                    return TransientStep(next_expr=new_expr)

                case MatchNarrowing(var_name, constr_name, _):
                    # Нашли переменную для сужения
                    branch = self._create_branch(expr, var_name, constr_name, var_types)
                    if branch:
                        branches.append(branch)
                    # Мы продолжаем цикл, чтобы собрать ветки для других конструкторов
                    # (например, Rule 1 требует Z, Rule 2 требует S)

                case MatchFail():
                    continue

        # Если вышли из цикла и есть ветки — возвращаем их
        if branches:
            return VariantStep(branches=branches)

        # Если веток нет, значит нам мешает вложенный вызов
        return self._drive_nested(expr, var_types)

    def _create_branch(self, expr: FCall, var_name: str, constr_name: str, var_types: Dict[str, TypeExpr]) -> Optional[
        Tuple[Expr, Contraction, Dict[str, TypeExpr]]]:
        """
        Создает одну ветку для VariantStep.
        заменяет переменную var_name в expr на конструктор constr_name с новыми переменными.
        """

        # Находим тип переменной
        if var_name not in var_types:
            return None  # Переменная не имеет типа

        type_name = var_types[var_name].name
        if type_name not in self.type_map:
            return None  # Неизвестный тип

        type_def = self.type_map[type_name]

        # Находим конструктор в типе
        constr_def = next((c for c in type_def.constructors if c.name == constr_name), None)
        if not constr_def:
            return None  # Неизвестный конструктор

        # Создаем новые переменные для аргументов конструктора
        fresh_vars = []
        new_branch_types = var_types.copy()

        for arg_type in constr_def.arg_types:
            v = Var(self.name_gen.fresh_var())
            fresh_vars.append(v)
            new_branch_types[v.name] = arg_type

        # Создаем новый конструктор с этими переменными
        fresh_ctr = Ctr(constr_name, fresh_vars)
        bindings = {var_name: fresh_ctr}

        # Делаем подстановку в исходное выражение
        new_expr = substitute(expr, bindings)

        # 4. Пытаемся сразу редуцировать (Transient Step)
        # f([Z]) -> body
        # Для этого нам нужно снова вызвать match (упрощенно) или рекурсивно _drive_call.
        # Но чтобы не усложнять, мы просто вернем new_expr.
        # На СЛЕДУЮЩЕМ шаге драйвер увидит f([Z]) и сделает TransientStep.
        # (Так работает SPSC Lite).

        # Но чтобы было красиво, попробуем редуцировать здесь:
        final_expr = new_expr
        # Ищем правило, которое теперь точно подойдет
        for rule in self.program.rules:
            if rule.pattern.name == expr.name:
                pat_dummy = FCall("dummy", rule.pattern.params)
                call_dummy = FCall("dummy", new_expr.args)  # Аргументы уже новые
                if isinstance(match_term(pat_dummy, call_dummy), MatchSuccess):
                    match_res = match_term(pat_dummy, call_dummy)  # Получаем bindings
                    final_expr = substitute(rule.body, match_res.bindings)
                    break

        contraction = Contraction(var_name, Pattern(constr_name, fresh_vars))
        return final_expr, contraction, new_branch_types


    def _drive_nested(self, expr: FCall, var_types: Dict[str, TypeExpr]) -> DriveStep:
        """
        Ищет первый вложенный вызов функции в аргументах expr и прогоняет его через драйвер.
        Возвращает TransientStep с обновленным выражением.
        """
        for i, arg in enumerate(expr.args):
            if isinstance(arg, FCall):
                inner_step = self.drive(arg, var_types)

                match inner_step:
                    case TransientStep(next_expr=nested_next):
                        # Обновляем аргумент и возвращаем новый вызов
                        new_args = list(expr.args)
                        new_args[i] = nested_next
                        new_expr = FCall(expr.name, new_args, lineno=expr.lineno, tag=expr.tag)
                        return TransientStep(next_expr=new_expr)

                    case VariantStep(branches):
                        # Выносим ветвление наружу
                        new_branches = []
                        for branch_expr, contraction, branch_var_types in branches:
                            new_args = list(expr.args)
                            new_args[i] = branch_expr
                            new_call = FCall(expr.name, new_args, lineno=expr.lineno, tag=expr.tag)
                            new_branches.append((new_call, contraction, branch_var_types))
                        return VariantStep(branches=new_branches)

                    case _:
                        pass

        # Если не нашли вложенных вызовов для продвижения, останавливаемся
        return StopStep()
