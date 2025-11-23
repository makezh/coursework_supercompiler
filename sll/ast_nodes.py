from dataclasses import dataclass
from typing import List


class Expr:
    """
    Базовый класс для всего, что может быть выражением
    """
    pass


@dataclass
class Var(Expr):
    """
    Переменная: просто имя ("x", "xs", "ys" etc.)
    """
    name: str

    def __str__(self):
        return self.name


@dataclass
class Ctr(Expr):
    """
    Конструктор: Данные \n
    name - имя конструктора ("Cons", "Nil", "S" etc.) \n
    args - список того, что лежит внутри
    """
    name: str
    args: List[Expr]

    def __str__(self):
        # Если аргументов нет, просто [Nil]
        if not self.args:
            return f"[{self.name}]"
        # Если есть, собираем их через пробел: [Cons x xs]
        args_str = " ".join(str(arg) for arg in self.args)
        return f"[{self.name} {args_str}]"


@dataclass
class FCall(Expr):
    """
    Вызов функции: Действие \n
    name - имя функции ("append", "map" etc.) \n
    args - аргументы, с которыми функцию вызвали
    """
    name: str
    args: List[Expr]

    def __str__(self):
        # Собираем строку вида (fun_name arg1 arg2)
        args_str = " ".join(str(arg) for arg in self.args)
        return f"({self.name} {args_str})"


@dataclass
class Let(Expr):
    """
    Let-выражение: связывает переменную с выражением в теле \n
    var_name - имя переменной \n
    val - выражение, которое связывается с переменной \n
    body - тело, в котором переменная доступна
    """
    var_name: str
    val: Expr
    body: Expr

    def __str__(self):
        return f"let {self.var_name} = {self.val} in {self.body}"
