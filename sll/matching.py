from dataclasses import dataclass
from typing import Dict, Optional

from sll.ast_nodes import Var, Ctr, FCall, IntLit, Expr


# --- Результаты сопоставления ---

@dataclass
class MatchResult:
    pass


@dataclass
class MatchSuccess(MatchResult):
    """
    <A> - Assignment (Присваивание).
    Успешное сопоставление.
    bindings: словарь {имя_переменной_паттерна: выражение_из_вызова}
    """
    bindings: Dict[str, Expr]


@dataclass
class MatchNarrowing(MatchResult):
    """
    <C> - Contraction (Сужение).
    Сопоставление невозможно, пока мы не уточним переменную в вызове.
    var_name: имя переменной, которую надо сузить (из вызова).
    constr_name: имя конструктора, который требует паттерн.
    constr_args_count: сколько аргументов у этого конструктора (чтобы создать свежие переменные).
    """
    var_name: str
    constr_name: str
    constr_args_count: int


@dataclass
class MatchFail(MatchResult):
    """Решений нет (конфликт конструкторов)."""
    pass


def match(pattern: Expr, expr: Expr) -> MatchResult:
    """
    Обобщенное сопоставление (General Matching).
    Проверяет, подходит ли expr под pattern.
    """

    match pattern:
        # 1. Переменная в паттерне — жадно захватывает всё
        case Var(name):
            return MatchSuccess(bindings={name: expr})

        # 2. Число в паттерне (42)
        case IntLit(p_val):
            # Проверяем, что пришло тоже число и оно равно нашему
            match expr:
                case IntLit(e_val) if e_val == p_val:
                    return MatchSuccess(bindings={})
                case _:
                    return MatchFail()

        # 3. Конструктор в паттерне ([Cons ...])
        case Ctr(p_name, p_args):
            match expr:
                case Ctr(c_name, e_args):
                    if p_name != c_name or len(p_args) != len(e_args):
                        return MatchFail()

                    total_bindings = {}

                    for p_arg, e_arg in zip(p_args, e_args):
                        res = match(p_arg, e_arg)

                        match res:
                            case MatchFail():
                                return MatchFail() # Если хоть одно не совпало

                            case MatchNarrowing(_, _, _):
                                return res # Пробрасываем сужение вверх

                            case MatchSuccess(bindings):
                                total_bindings.update(bindings) # Собираем все подстановки

                    return MatchSuccess(bindings=total_bindings)

                case Var(var_name):
                    # Нужно сузить эту переменную до конструктора
                    return MatchNarrowing(
                        var_name=var_name,
                        constr_name=p_name,
                        constr_args_count=len(p_args)
                    )

                case _:
                    return MatchFail()

        # 4. Вызов функции
        # Нужно, чтобы понять, что add(a, b) — это предок для add(v1, b)
        case FCall(p_name, p_args):
            match expr:
                case FCall(e_name, e_args) if p_name == e_name and len(p_args) == len(e_args):
                    total_bindings = {}
                    for p_arg, e_arg in zip(p_args, e_args):
                        res = match(p_arg, e_arg)
                        match res:
                            case MatchFail():
                                return MatchFail()
                            case MatchNarrowing(_, _, _):
                                return res
                            case MatchSuccess(bindings):
                                total_bindings.update(bindings)
                    return MatchSuccess(bindings=total_bindings)
                case _:
                    return MatchFail()

        case _:
            return MatchFail()


def substitute(expr, bindings):
    """
    Заменяет переменные в выражении на значения из bindings.
    """
    match expr:
        case Var(name):
            return bindings.get(name, expr)

        case Ctr(name, args):
            new_args = [substitute(a, bindings) for a in args]
            return Ctr(name, new_args, lineno=expr.lineno, tag=expr.tag)

        case FCall(name, args):
            new_args = [substitute(a, bindings) for a in args]
            return FCall(name, new_args, lineno=expr.lineno, tag=expr.tag)

        case IntLit():
            return expr

        case _:
            return expr
