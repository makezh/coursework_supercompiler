from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from sll.ast_nodes import Expr, Pattern

@dataclass
class Contraction:
    """
    Описание ребра в дереве при ветвлении.
    Говорит: "Мы пошли по этой ветке, потому что заменили переменную var_name на паттерн pattern".
    Пример: var_name='x', pattern=[S v1]
    """
    var_name: str
    pattern: Pattern

@dataclass
class Node:
    """
    Узел дерева суперкомпиляции.
    """
    expr: Expr                          # Выражение в текущем состоянии
    parent: Optional['Node'] = None     # Родитель (Корень - None)
    children: List['Node'] = field(default_factory=list)

    # Мета-информация о том, как мы сюда попали
    contraction: Optional[Contraction] = None

    def add_child(self, node: 'Node', contraction: Optional[Contraction] = None):
        node.parent = self
        node.contraction = contraction
        self.children.append(node)
        return node

    def __str__(self):
        return f"Node({self.expr})"

    def leaves(self) -> List['Node']:
        """Возвращает список всех листьев (необработанных узлов) в поддереве"""
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