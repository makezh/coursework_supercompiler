from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from sll.ast_nodes import Expr, Pattern, TypeExpr


@dataclass
class Contraction:
    """
    Описание ребра в дереве при ветвлении.
    Говорит: "Мы пошли по этой ветке, потому что заменили переменную var_name на паттерн pattern".
    Пример: var_name='x', pattern=[S v1]
    """
    var_name: str
    pattern: Pattern

@dataclass(eq=False)
class Node:
    """
    Узел дерева суперкомпиляции.
    """
    expr: Expr                          # Выражение в текущем состоянии

    # Словарь: имя переменной -> выражение типа
    var_types: Dict[str, TypeExpr]

    parent: Optional['Node'] = None     # Родитель (Корень - None)
    children: List['Node'] = field(default_factory=list)

    # Мета-информация о том, как мы сюда попали
    contraction: Optional[Contraction] = None

    # Ссылка назад (для сворачивания графа)
    back_link: Optional['Node'] = None

    def add_child(self, node: 'Node', contraction: Optional[Contraction] = None):
        node.parent = self
        node.contraction = contraction
        self.children.append(node)
        return node

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