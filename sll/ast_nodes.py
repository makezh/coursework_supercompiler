from dataclasses import dataclass, field
from typing import List


# --- Выражения ---
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
    lineno: int = field(default=0, compare=False, repr=False)

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
    lineno: int = field(default=0, compare=False, repr=False)

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
    lineno: int = field(default=0, compare=False, repr=False)

    def __str__(self):
        # Собираем строку вида (fun_name arg1 arg2)
        args_str = " ".join(str(arg) for arg in self.args)
        return f"({self.name} {args_str})"


@dataclass
class IntLit(Expr):
    value: int
    lineno: int = field(default=0, compare=False, repr=False)

    def __str__(self): return str(self.value)


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
    lineno: int = field(default=0, compare=False, repr=False)

    def __str__(self):
        return f"let {self.var_name} = {self.val} in {self.body}"
# --- Конец Выражений ---


# --- Типы, Сигнатуры и Определения ---
@dataclass
class TypeExpr:
    """Представление типа, например [Nat] или [List [Nat]]"""
    name: str
    params: List['TypeExpr'] = field(default_factory=list)
    lineno: int = field(default=0, compare=False, repr=False)

    def __str__(self):
        if not self.params:
            return f"[{self.name}]"
        return f"[{self.name} {' '.join(str(p) for p in self.params)}]"


@dataclass
class ConstrDef:
    """Определение конструктора: Z или S [Nat]"""
    name: str
    arg_types: List[TypeExpr]
    lineno: int = field(default=0, compare=False, repr=False)


@dataclass
class TypeDef:
    """Определение типа: type [Nat] : Z | S [Nat]."""
    name: str
    params: List[str]  # имена типовых переменных, например ['a'] для [List a]
    constructors: List[ConstrDef]
    lineno: int = field(default=0, compare=False, repr=False)


@dataclass
class FunSig:
    """Сигнатура функции: (add [Nat] [Nat]) -> [Nat]"""
    name: str
    arg_types: List[TypeExpr]
    ret_type: TypeExpr
    lineno: int = field(default=0, compare=False, repr=False)
# --- Конец Типов, Сигнатур и Определений ---


# --- Правила и Программы ---
# Описание паттерна (то, что слева в уравнении)
# Например: (append [Cons x xs] ys)
@dataclass
class Pattern:
    name: str  # Имя функции
    params: List[Expr]  # Параметры (там могут быть Var или Ctr)
    lineno: int = field(default=0, compare=False, repr=False)

    def __str__(self):
        params_str = " ".join(str(p) for p in self.params)
        return f"({self.name} {params_str})"


# Описание одного правила уравнения
# Например: (append [Nil] ys) = ys
@dataclass
class Rule:
    """
    Одно уравнение в программе
    pattern - левая часть уравнения \n
    body - правая часть уравнения (выражение)
    """
    pattern: Pattern
    body: Expr
    lineno: int = field(default=0, compare=False, repr=False)

    def __str__(self):
        return f"{self.pattern} -> {self.body}"



# Описание всей программы
@dataclass
class Program:
    """
    Вся программа: набор уравнений
    """
    rules: List[Rule]  # Список уравнений
    types: List[TypeDef]  # Список определений типов
    signatures: List[FunSig]   # Список сигнатур функций

    def __str__(self):
        res = ""
        # Вывод типов
        for t in self.types:
            # Формируем строку параметров: если есть params, добавляем пробел перед ними
            params_str = (" " + " ".join(t.params)) if t.params else ""

            constrs = " | ".join(f"{c.name} {' '.join(str(a) for a in c.arg_types)}" for c in t.constructors)

            res += f"type [{t.name}{params_str}] : {constrs} .\n"

        res += "\n"

        # Вывод сигнатур
        for s in self.signatures:
            args = " ".join(str(a) for a in s.arg_types)
            res += f"fun ({s.name} {args}) -> {s.ret_type} : ...\n"

        return res + "\n" + "\n".join(str(r) + ";" for r in self.rules)
# --- Конец Правил и Программ ---
