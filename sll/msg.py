import re
from dataclasses import dataclass
from typing import Dict, Tuple
from sll.ast_nodes import Expr, Var, Ctr, FCall, IntLit

def _replace_var(expr: Expr, old: str, new: str) -> Expr:
    """Заменяет все Var(old) на Var(new) внутри expr."""
    match expr:
        case Var(name) if name == old:
            return Var(new)

        case Ctr(name, args):
            return Ctr(name, [_replace_var(a, old, new) for a in args])

        case FCall(name, args):
            return FCall(name, [_replace_var(a, old, new) for a in args])

        case IntLit(_):
            return expr

        case _:
            return expr


@dataclass
class GenResult:
    """
    Результат обобщения:
    gen: Обобщенное выражение (паттерн с дырками)

    sub1: Словарь замен, чтобы получить исходное выражение 1
    Пример: { 'v1': [Z], 'v2': [S x] ... }

    sub2: Словарь замен, чтобы получить исходное выражение 2
    """
    gen: Expr
    sub1: Dict[str, Expr]
    sub2: Dict[str, Expr]


class MSGBuilder:
    def __init__(self):
        self.counter = 0
        # Значение: уже созданная переменная Var
        self.memo: Dict[Tuple[str, str], Var] = {}

    def _fresh_var_name(self) -> str:
        """Генерирует следующее имя переменной: v1, v2, v3..."""
        self.counter += 1
        return f"h{self.counter}"

    def generalize(self, t1: Expr, t2: Expr) -> GenResult:
        self.counter = 0
        self.memo = {}
        gen, s1, s2 = self._gen_recursive(t1, t2)
        gen, s1, s2 = self._merge_duplicate_holes(gen, s1, s2)
        return GenResult(gen, s1, s2)

    def _gen_recursive(self, t1: Expr, t2: Expr) -> Tuple[Expr, Dict[str, Expr], Dict[str, Expr]]:
        # 1. Если это ОДИНАКОВЫЕ переменные
        if isinstance(t1, Var) and isinstance(t2, Var) and t1.name == t2.name:
            return t1, {}, {}

        # 2. Если Корни совпадают (Конструктор или Функция)
        # C(a...) vs C(b...)
        match (t1, t2):
            case (Ctr(n1, args1), Ctr(n2, args2)) if n1 == n2:
                assert len(args1) == len(args2), f"Арность конструктора {n1} не совпадает!"
                return self._merge_args(n1, args1, args2, is_ctr=True)

            case (FCall(n1, args1), FCall(n2, args2)) if n1 == n2:
                assert len(args1) == len(args2), f"Арность функции {n1} не совпадает!"
                return self._merge_args(n1, args1, args2, is_ctr=False)

            # Литералы (числа)
            case (IntLit(v1), IntLit(v2)) if v1 == v2:
                return t1, {}, {}

            case _:
                # --- Тесное обобщение (Common Subexpression Elimination) ---
                # Проверяем, видели ли мы такую пару (t1, t2) раньше?
                pair_key = (str(t1), str(t2))

                if pair_key in self.memo:
                    # Если мы уже заменяли такую пару (t1, t2) на переменную,
                    # используем ту же самую переменную снова.
                    return self.memo[pair_key], {}, {}

                # Если не видели — создаем новую
                name = self._fresh_var_name()
                new_var = Var(name)

                # Запоминаем в кэш
                self.memo[pair_key] = new_var

                return new_var, {name: t1}, {name: t2}

    def _merge_args(self, name: str, args1: list, args2: list, is_ctr: bool):
        """
        Склеивает аргументы, если голова совпала.
        """
        new_args = []
        full_s1 = {}
        full_s2 = {}

        for a1, a2 in zip(args1, args2):
            g, s1, s2 = self._gen_recursive(a1, a2)
            new_args.append(g)
            full_s1.update(s1)
            full_s2.update(s2)

        if is_ctr:
            return Ctr(name, new_args), full_s1, full_s2
        else:
            return FCall(name, new_args), full_s1, full_s2

    def _merge_duplicate_holes(self, gen: Expr, s1: Dict[str, Expr], s2: Dict[str, Expr]):
        """
        Сливает разные переменные v_i, v_j в одну
        """
        groups: Dict[tuple, list[str]] = {}
        for v in list(s1.keys()):
            key = (str(s1[v]), str(s2.get(v)))
            groups.setdefault(key, []).append(v)

        for _, vars_ in groups.items():
            if len(vars_) <= 1:
                continue

            vars_.sort(key=natural_key)
            keep = vars_[0]

            for old in vars_[1:]:
                gen = _replace_var(gen, old, keep)
                s1.pop(old, None)
                s2.pop(old, None)

        return gen, s1, s2


def msg(t1: Expr, t2: Expr) -> GenResult:
    """Удобная обертка для вызова"""
    return MSGBuilder().generalize(t1, t2)

def natural_key(string_key):
    """Превращает 'v10' в ('v', 10) для правильной сортировки"""
    # Разделяем текст и числа
    match = re.match(r"([a-z]+)([0-9]+)", string_key)
    if match:
        return match.group(1), int(match.group(2))
    return string_key
