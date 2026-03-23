from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from sll.ast_nodes import Expr, Pattern, TypeExpr
from collections import Counter


@dataclass
class Contraction:
    """
    Описание ребра в дереве при ветвлении.
    Говорит: "Мы пошли по этой ветке, потому что заменили переменную var_name на паттерн pattern".
    Пример: var_name='x', pattern=[S v1]

    narrowings — полное сужение (несколько переменных одновременно):
      {var_name: Ctr-выражение}  — для паттернов с вложенными конструкторами
    is_default — ветка "default" (catch-all), переменные остаются переменными
    """
    var_name: str
    pattern: Optional[Pattern]
    value: Optional[Expr] = None
    narrowings: Optional[Dict] = None   # Dict[str, Expr]
    is_default: bool = False

@dataclass
class HeapBinding:
    """
    Binding в heap (как в ⟨H|e|K⟩).
    Храним имя (для восстановления/читаемости) и rhs-выражение.
    В tag-bag берётся ТОЛЬКО root-tag rhs.
    """
    name: str
    expr: Expr


@dataclass
class StackFrame:
    """
    Frame в стеке K.
    Для tag-bag нам нужен root-tag кадра.
    В MVP будем хранить только tag (и опционально kind для отладки).
    """
    tag: Optional[int]
    kind: str = "GEN"

@dataclass(eq=False)
class Node:
    """
    Узел дерева суперкомпиляции.
    """
    expr: Expr                          # Выражение в текущем состоянии

    # Словарь: имя переменной -> выражение типа
    var_types: Dict[str, TypeExpr]

    heap: List[HeapBinding] = field(default_factory=list)
    stack: List[StackFrame] = field(default_factory=list)

    bag: Optional[Counter] = None        # Мешок тегов (для свистка)

    parent: Optional['Node'] = None     # Родитель (Корень - None)
    children: List['Node'] = field(default_factory=list)

    # Мета-информация о том, как мы сюда попали
    contraction: Optional[Contraction] = None

    # Ссылка назад (для сворачивания графа)
    back_link: Optional['Node'] = None

    driven_from: Optional[Expr] = None
    driven_rule: Optional[Pattern] = None

    gen_alpha: Optional[Expr] = None   # что было до обобщения
    gen_beta: Optional[Expr] = None    # на чем свистнули
    gen_result: Optional[Expr] = None  # во что обобщили

    is_basis_ref: bool = False         # узел является ссылкой на корень другого дерева в лесу

    def add_child(self, node: 'Node', contraction: Optional[Contraction] = None):
        node.parent = self
        node.contraction = contraction

        node.heap = list(self.heap)
        node.stack = list(self.stack)

        self.children.append(node)
        return node

    def clone_state_from(self, parent: 'Node'):
        # shallow-copy списков достаточно: HeapBinding/StackFrame иммутабельны для MVP
        self.heap = list(parent.heap)
        self.stack = list(parent.stack)
        return self

    def push_frame(self, tag: Optional[int], kind: str = "GEN"):
        self.stack.append(StackFrame(tag=tag, kind=kind))

    def extend_heap(self, bindings: List[Tuple[str, Expr]]):
        for name, e in bindings:
            self.heap.append(HeapBinding(name=name, expr=e))

    def __str__(self):
        types_str = ", ".join(f"{k}:{v.name}" for k, v in self.var_types.items())
        return f"Node({self.expr}) {{{types_str}}}"

    def leaves(self) -> List['Node']:
        """Возвращает список всех листьев (необработанных узлов) в поддереве"""
        if self.back_link:
            return [] # Если узел свернут, он не лист
        if not self.children:
            return [self]
        res = []
        for c in self.children:
            res.extend(c.leaves())
        return res

    def ancestors(self) -> List['Node']:
        """Возвращает список предков от родителя до корня"""
        curr = self.parent
        res = []
        while curr:
            res.append(curr)
            curr = curr.parent
        return res