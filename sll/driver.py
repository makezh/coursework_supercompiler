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
