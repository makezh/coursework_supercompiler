from dataclasses import dataclass
from typing import Dict, Tuple
from sll.ast_nodes import Expr, Var, Ctr, FCall, IntLit

@dataclass
class GenResult:
    """
    Результат обобщения:
    gen: Обобщенное выражение (паттерн с дырками)
    sub1: Словарь замен, чтобы получить исходное выражение 1
    sub2: Словарь замен, чтобы получить исходное выражение 2
    """
    gen: Expr
    sub1: Dict[str, Expr]
    sub2: Dict[str, Expr]

class MSGBuilder:
    def __init__(self):
        self.counter = 0

    def _fresh_var(self) -> str:
        self.counter += 1
        return f"v{self.counter}"

    def generalize(self, t1: Expr, t2: Expr) -> GenResult:
        self.counter = 0
        gen, s1, s2 = self._gen_recursive(t1, t2)
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
                # 3. Если корни РАЗНЫЕ — это конфликт.
                # Создаем общую переменную-дырку.
                # t1=A, t2=B  --->  gen=v, sub1={v:A}, sub2={v:B}
                new_var_name = self._fresh_var()
                new_var = Var(new_var_name)
                return new_var, {new_var_name: t1}, {new_var_name: t2}

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