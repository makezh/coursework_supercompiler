from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# --- Выражения ---
class Expr:
    """
    Базовый класс для всего, что может быть выражением
    """
    lineno: int = field(default=0, compare=False, repr=False)
    # Тег не участвует в сравнении (eq), но важен для свистка
    tag: Optional[int] = field(default=None, compare=False, repr=False)

@dataclass
class Var(Expr):
    """
    Переменная: просто имя ("x", "xs", "ys" etc.)
    """
    name: str
    lineno: int = field(default=0, compare=False, repr=False)
    tag: Optional[int] = field(default=None, compare=False, repr=False)

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
    tag: Optional[int] = field(default=None, compare=False, repr=False)

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
    tag: Optional[int] = field(default=None, compare=False, repr=False)

    def __str__(self):
        # Собираем строку вида (fun_name arg1 arg2)
        args_str = " ".join(str(arg) for arg in self.args)
        return f"({self.name} {args_str})"


@dataclass
class IntLit(Expr):
    value: int
    lineno: int = field(default=0, compare=False, repr=False)
    tag: Optional[int] = field(default=None, compare=False, repr=False)

    def __str__(self): return str(self.value)


@dataclass
class Let(Expr):
    """
    Let-выражение (множественные связывания):
      let v1 = e1; v2 = e2; ... in body

    bindings: список пар (имя_переменной, выражение)
    body: выражение, в котором доступны связанные переменные
    """
    bindings: List[Tuple[str, 'Expr']] = field(default_factory=list)
    body: 'Expr' = None  # type: ignore

    lineno: int = field(default=0, compare=False, repr=False)
    tag: Optional[int] = field(default=None, compare=False, repr=False)

    def __str__(self):
        # Печать в стабильном виде, удобном для логов/graphviz
        binds = "; ".join(f"{name} = {expr}" for name, expr in self.bindings)
        return f"(let {binds} in {self.body})"
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
        # Конструктор в паттерне (имя с заглавной буквы) — квадратные скобки
        if self.name and self.name[0].isupper():
            return f"[{self.name} {params_str}]" if params_str else f"[{self.name}]"
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
        blocks = []

        for t in self.types:
            params_str = (" " + " ".join(t.params)) if t.params else ""
            constrs = " | ".join(
                (f"{c.name} {' '.join(str(a) for a in c.arg_types)}".rstrip())
                for c in t.constructors
            )
            blocks.append(f"type [{t.name}{params_str}] : {constrs} .")

        sig_by_name = {s.name: s for s in self.signatures}

        order = []
        clauses = {}
        for r in self.rules:
            if r.pattern.name not in clauses:
                clauses[r.pattern.name] = []
                order.append(r.pattern.name)
            clauses[r.pattern.name].append(r)

        for name in order:
            sig = sig_by_name.get(name)
            body = "\n  | ".join(str(r) for r in clauses[name])
            if sig is not None:
                args = " ".join(str(a) for a in sig.arg_types)
                head = f"({sig.name} {args})" if args else f"({sig.name})"
                blocks.append(f"fun {head} -> {sig.ret_type} :\n    {body} .")
            else:
                blocks.append("\n".join(str(r) + ";" for r in clauses[name]))

        return "\n\n".join(blocks)
# --- Конец Правил и Программ ---
