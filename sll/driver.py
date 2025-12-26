from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

from sll.ast_nodes import Expr, Var, Ctr, FCall, Program, Pattern, IntLit, TypeExpr
from sll.matching import match as match_term, substitute  # Переименовал match, чтобы не путать с match/case
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
            case FCall(name, args):
                # Здесь будет основная логика (Transient / Variant / Nested)
                return self._drive_call(expr, var_types)

            case _:
                return StopStep()

    def _drive_call(self, expr: FCall, var_types: Dict[str, TypeExpr]) -> DriveStep:
        return StopStep()

    def _is_g_function(self, name: str) -> bool:
        """
        Функция смотрит в правила функции и выясняет, 'любопытная' она (G) или нет (F)
        """
        # Бежим по правилам в программе (add, sub, mul...)
        for rule in self.program.rules:
            if rule.pattern.name == name:
                if rule.pattern.params: # Если аргументы вообще есть
                    if isinstance(rule.pattern.params[0], Ctr):
                        return True # G

        return False # F

    def _try_reduce(self, expr: FCall) -> Optional[Expr]:
        """
        Функция пытается выполнить один шаг редукции.
        Возвращает новое выражение или None, если правило не нашлось.
        """
        for rule in self.program.rules:
            if rule.pattern.name == expr.name:
                # Пытаемся сопоставить аргументы вызова с паттерном правила
                full_bindings = {}
                is_match = True

                # Обрабатываем несколько аргументов
                for p_arg, call_arg in zip(rule.pattern.params, expr.args):
                    res = match_term(p_arg, call_arg)
                    if res is None:
                        is_match = False
                        break
                    full_bindings.update(res)

                if is_match:
                    # Делаем подстановку в правую часть.
                    return substitute(rule.body, full_bindings)

        return None

    def _drive_variable(self, expr: FCall, var_name: str, var_types: Dict[str, TypeExpr]) -> DriveStep:
        """
        Разгоняем вызов функции по переменной var_name.
        """
        # Проверяем, знаем ли мы тип этой переменной
        if var_name not in var_types:
            return StopStep()

        type_expr = var_types[var_name]
        type_name = type_expr.name

        # Ищем определение типа в программе (type Nat : Z | S Nat)
        if type_name not in self.type_map:
            return StopStep()

        type_def = self.type_map[type_name]

        branches = []

        # Пробегаем по всем конструкторам типа
        for constr in type_def.constructors:
            fresh_vars = []
            # Копируем таблицу типов - добавляем туда новые переменные для этой ветки
            new_branch_types = var_types.copy()

            for arg_type in constr.arg_types:
                # Генерируем уникальное имя (v1, v2...)
                new_var_name = self.name_gen.fresh_var()
                fresh_var = Var(new_var_name)
                fresh_vars.append(fresh_var)

                # Записываем тип новой переменной!
                new_branch_types[new_var_name] = arg_type

        # Создаем конструктор с новыми переменными: [S v1]
            fresh_ctr = Ctr(constr.name, fresh_vars)

            # Подставляем: было g(x), стало g([S v1])
            bindings = {var_name: fresh_ctr}
            new_expr = substitute(expr, bindings)

            # Пытаемся сразу вычислить (Transient Step)
            reduced_expr = self._try_reduce(new_expr)

            # Если не раскроется (частичная функция) — оставляем как есть (new_expr)
            final_expr = reduced_expr if reduced_expr else new_expr

            # Записываем эту ветку
            contraction = Contraction(var_name, Pattern(fresh_ctr.name, fresh_vars))
            branches.append((final_expr, contraction, new_branch_types))

        # Возвращаем все найденные варианты
        return VariantStep(branches=branches)
