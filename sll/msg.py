from dataclasses import dataclass
from typing import Dict, Tuple
from sll.ast_nodes import Expr, Var, Ctr, FCall, IntLit

# Тип для ключа переменной: ('v', 10)
VarKey = Tuple[str, int]


@dataclass
class GenResult:
    """
    Результат обобщения:
    gen: Обобщенное выражение (паттерн с дырками)

    sub1: Словарь замен, чтобы получить исходное выражение 1
    Пример: { ('v', 1): [Z], ('v', 2): [S x] ... }

    sub2: Словарь замен, чтобы получить исходное выражение 2
    """
    gen: Expr
    sub1: Dict[VarKey, Expr]
    sub2: Dict[VarKey, Expr]


class MSGBuilder:
    def __init__(self):
        self.counter = 0
        # Значение: уже созданная переменная Var
        self.memo: Dict[Tuple[str, str], Var] = {}
        # Также нужно помнить ключи VarKey для этих переменных, чтобы не терять их
        self.memo_keys: Dict[Tuple[str, str], VarKey] = {}

    def _fresh_var_key(self) -> VarKey:
        """Возвращает кортеж ('v', номер), который идеально сортируется."""
        self.counter += 1
        return "v", self.counter

    def generalize(self, t1: Expr, t2: Expr) -> GenResult:
        self.counter = 0
        gen, s1, s2 = self._gen_recursive(t1, t2)
        return GenResult(gen, s1, s2)

    def _gen_recursive(self, t1: Expr, t2: Expr) -> Tuple[Expr, Dict[VarKey, Expr], Dict[VarKey, Expr]]:
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
                    # Возвращаем старую переменную.
                    # Словари подстановок пустые, т.к. они уже были заполнены в первый раз.
                    existing_var = self.memo[pair_key]
                    return existing_var, {}, {}

                # Если не видели — создаем новую
                key = self._fresh_var_key()
                name_str = f"{key[0]}{key[1]}"
                new_var = Var(name_str)

                # Запоминаем в кэш
                self.memo[pair_key] = new_var
                self.memo_keys[pair_key] = key

                return new_var, {key: t1}, {key: t2}

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


def msg(t1: Expr, t2: Expr) -> GenResult:
    """Удобная обертка для вызова"""
    return MSGBuilder().generalize(t1, t2)
