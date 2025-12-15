from dataclasses import dataclass
from typing import List, Optional, Tuple

from sll.ast_nodes import Expr, Var, Ctr, FCall, Program, Pattern, IntLit
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
# на несколько веток в зависимости от возможных конструкторов неизвестной переменной.

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
    # Список веток: (Выражение, Описание_Подстановки)
    branches: List[Tuple[Expr, Contraction]]


@dataclass
class StopStep(DriveStep):
    pass


# --- Драйвер ---

class Driver:
    def __init__(self, program: Program):
        self.program = program
        self.name_gen = NameGen()

    def drive(self, expr: Expr) -> DriveStep:
        """
        Анализирует выражение и возвращает следующий шаг.
        """
        match expr:

            # 1. Конструктор -> Декомпозиция
            case Ctr(_, args):
                return DecomposeStep(parts=args)

            # 2. Переменная или Число -> Стоп
            case Var(_) | IntLit(_):
                return StopStep()

            # 3. Вызов функции
            case FCall(name, args):
                if self._is_g_function(name):
                    # --- G-функция ---
                    match args:
                        case [arg0, *rest]:
                            match arg0:
                                # 3.1 Аргумент - Конструктор -> Редукция
                                case Ctr(_, _):
                                    if res := self._try_reduce(expr):
                                        return TransientStep(next_expr=res)
                                    return StopStep()

                                # 3.2 Аргумент - Вложенный вызов -> Ныряем (Driving in the accumulation)
                                case FCall(_, _) as inner_call:
                                    # Рекурсивно драйвим внутренний вызов
                                    inner_step = self.drive(inner_call)

                                    match inner_step:
                                        # Если внутри что-то вычислилось (Transient)
                                        # g(f(x), y) -> g(res, y)
                                        case TransientStep(next_inner):
                                            new_expr = FCall(name, [next_inner, *rest])
                                            return TransientStep(next_expr=new_expr)

                                        # Если внутри случилось ветвление (Variant)
                                        # g(case x of ..., y) -> case x of g(..., y) ...
                                        case VariantStep(branches):
                                            new_branches = []
                                            for branch_expr, contr in branches:
                                                # Оборачиваем результат ветки обратно в g(...)
                                                new_root = FCall(name, [branch_expr, *rest])
                                                new_branches.append((new_root, contr))
                                            return VariantStep(branches=new_branches)

                                        # Если внутри застряли (Stop/Decompose), то и снаружи стоим
                                        case _:
                                            return StopStep()

                                # 3.3 Аргумент - Переменная -> Разгонка
                                case Var(_) as var:
                                    return self._drive_variable(expr, var)

                                case _:
                                    return StopStep()
                        case _:
                            return StopStep()
                else:
                    # --- F-функция ---
                    if res := self._try_reduce(expr):
                        return TransientStep(next_expr=res)
                    return StopStep()

            case _:
                return StopStep()

    def _is_g_function(self, name: str) -> bool:
        """Проверяет, является ли функция g-функцией (есть ли паттерны в правилах)."""
        for rule in self.program.rules:
            if rule.pattern.name == name:
                match rule.pattern.params:
                    # Если первый параметр в паттерне — конструктор, то это g-функция
                    case [Ctr(_, _), *rest]:
                        return True
        return False

    def _try_reduce(self, expr: Expr) -> Optional[Expr]:
        """
        Пытается выполнить один шаг редукции.
        Принимает любой Expr, но срабатывает только для FCall.
        """
        # Сначала проверяем, что нам вообще передали вызов функции
        match expr:
            case FCall(name, args):
                # Ищем правило
                for rule in self.program.rules:
                    if rule.pattern.name == name:
                        full_bindings = {}
                        is_match = True

                        for p_arg, call_arg in zip(rule.pattern.params, args):
                            res = match_term(p_arg, call_arg)
                            if res is None:
                                is_match = False
                                break
                            full_bindings.update(res)

                        if is_match:
                            return substitute(rule.body, full_bindings)
                return None

            case _:
                return None

    def _drive_variable(self, expr: Expr, var: Var) -> DriveStep:
        """
        Реализация разгонки (Case Analysis).
        expr имеет вид g(x, ...), где x - переменная.
        """
        match expr:
            case FCall(name, _):
                # Ищем правила для этой функции
                rules = [r for r in self.program.rules if r.pattern.name == name]
                if not rules:
                    return StopStep()

                branches = []

                for rule in rules:
                    match rule.pattern.params:
                        case [Ctr(c_name, c_args), *rest]:
                            # 1. Создаем свежие переменные (v1, v2...)
                            fresh_vars = [Var(self.name_gen.fresh_var()) for _ in c_args]

                            # 2. Создаем "Прототип" конструктора: [S v1]
                            fresh_ctr = Ctr(c_name, fresh_vars)

                            # 3. Подставляем [S v1] вместо переменной x
                            bindings = {var.name: fresh_ctr}
                            new_expr = substitute(expr, bindings)

                            # 4. Сразу же редуцируем полученное выражение
                            if reduced_expr := self._try_reduce(new_expr):
                                # 5. Запоминаем информацию о ветке
                                contraction_info = Contraction(
                                    var_name=var.name,
                                    # Хак: используем Pattern как контейнер для (ConstrName, vars)
                                    pattern=Pattern(fresh_ctr.name, fresh_vars)
                                )
                                branches.append((reduced_expr, contraction_info))

                        case _:
                            continue

                if branches:
                    return VariantStep(branches=branches)

                return StopStep()

            case _:
                return StopStep()
