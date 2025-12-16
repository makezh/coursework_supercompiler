from typing import Optional

from sll.ast_nodes import Program, Expr
from sll.process_tree import Node
from sll.driver import Driver, TransientStep, DecomposeStep, VariantStep, StopStep
from sll.matching import match


class Supercompiler:
    def __init__(self, program: Program):
        self.program = program
        self.driver = Driver(program)
        self.tree = None

    def build_tree(self, start_expr: Expr):
        """Строит дерево процессов для заданного выражения."""
        self.tree = Node(start_expr)

        # Очередь необработанных узлов (можно использовать leaves(), но список быстрее)
        unprocessed = [self.tree]

        while unprocessed:
            # Берем первый узел (стратегия в ширину/глубину зависит от pop(0) или pop())
            beta = unprocessed.pop(0)

            # 1. Проверка на зацикливание (Folding)
            # Ищем предка, который "похож" на текущий узел (instance of)
            # Для простоты 2-го этапа: ищем полное совпадение с точностью до переименования
            ancestor = self._find_renaming_ancestor(beta)
            if ancestor:
                # Нашли! Ставим ссылку назад и не обрабатываем детей
                beta.back_link = ancestor
                continue

            # 2. Если не свернули, то Драйвим (делаем шаг)
            step = self.driver.drive(beta.expr)

            new_children = []

            match step:
                case StopStep():
                    pass  # Лист, дальше не идем

                case TransientStep(next_expr):
                    child = Node(next_expr)
                    beta.add_child(child)
                    new_children.append(child)

                case DecomposeStep(parts):
                    for part in parts:
                        child = Node(part)
                        beta.add_child(child)
                        new_children.append(child)

                case VariantStep(branches):
                    for expr_branch, contraction in branches:
                        child = Node(expr_branch)
                        beta.add_child(child, contraction)
                        new_children.append(child)

            # Добавляем новых детей в очередь на обработку
            unprocessed.extend(new_children)

    def _find_renaming_ancestor(self, node: Node) -> Optional[Node]:
        """
        Ищет предка, который является переименованием текущего узла.
        (Упрощенная версия: проверяем Instance Of в обе стороны).
        """
        for alpha in node.ancestors():
            # Проверяем: alpha <= beta И beta <= alpha
            # Это значит, что они отличаются только именами переменных.
            if self._is_instance_of(node.expr, alpha.expr) and \
                    self._is_instance_of(alpha.expr, node.expr):
                return alpha
        return None

    def _is_instance_of(self, t1: Expr, t2: Expr) -> bool:
        """
        Проверяет, является ли t1 частным случаем t2.
        То есть, существует ли подстановка S, что t2 * S = t1.
        Используем наш match, но он работает для паттернов.
        Здесь t2 - как бы паттерн.
        """
        # Наш match из sll.matching умеет матчить Ctr и Var.
        # Этого достаточно.
        # ВАЖНО: match(pattern, call) -> проверяет call соответсвует pattern.
        # Значит вызываем match(t2, t1).
        return match(t2, t1) is not None
