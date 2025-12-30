from typing import Dict, Optional

from sll.ast_nodes import Program, Expr, FCall, TypeExpr
from sll.he import he
from sll.msg import msg
from sll.process_tree import Node, Contraction
from sll.driver import Driver, TransientStep, DecomposeStep, VariantStep, StopStep
from sll.matching import match, MatchSuccess
from sll.preprocessor import add_tags, Tagger
from sll.bag_of_tags import TagBag



def _find_renaming_ancestor(node: Node) -> Node | None:
    """Ищет предка, который совпадает с точностью до переименования."""
    for alpha in node.ancestors():
        if _is_renaming(node.expr, alpha.expr):
            return alpha
    return None


def _remove_children_from_unprocessed(node: Node, unprocessed: list):
    """Рекурсивно удаляет потомков узла из очереди обработки."""
    for child in node.children:
        if child in unprocessed:
            unprocessed.remove(child)
        _remove_children_from_unprocessed(child, unprocessed)


def _is_renaming(t1: Expr, t2: Expr) -> bool:
    """
    Проверяет, является ли t1 переименованием t2.
    Эквивалентно: t1 <= t2 И t2 <= t1.
    """
    res1 = match(t2, t1)
    res2 = match(t1, t2)
    return isinstance(res1, MatchSuccess) and isinstance(res2, MatchSuccess)


class Supercompiler:
    def __init__(self, program: Program, strategy: str = "HE"):
        self.program = program
        self.driver = Driver(program)
        self.tree: Optional[Node] = None
        self.strategy = strategy

    def build_tree(self, start_expr: Expr, start_var_types: Dict[str, TypeExpr]):
        """Строит дерево процессов для заданного выражения.
        start_expr: Начальное выражение для суперкомпиляции.
        start_var_types: Типы переменных начального выражения.
        """
        if self.strategy == 'TAG':
            add_tags(self.program)
            tagger = Tagger()
            # Начинаем с большого числа, чтобы не пересечься с программой (хак, но рабочий)
            tagger.counter = 100000
            tagger._tag_expr(start_expr)

        self.tree = self._create_node(start_expr, start_var_types)

        # Очередь необработанных узлов
        unprocessed = [self.tree]

        while unprocessed:
            beta = unprocessed.pop(0)

            # 1. Проверка на зацикливание (Folding / Свертка)
            # Ищем предка, который "похож" на текущий узел (instance of)
            # Для простоты 2-го этапа: ищем полное совпадение с точностью до переименования
            ancestor = _find_renaming_ancestor(beta)
            if ancestor:
                # Нашли! Ставим ссылку назад и не обрабатываем детей
                beta.back_link = ancestor
                continue

            # --- 2. Whistle & Generalization ---
            # Проверяем, не вкладывается ли предок в нас (alpha <| beta).
            # Это сигнал опасности (бесконечный рост).
            dangerous_alpha = self._find_embedding_ancestor(beta)

            if dangerous_alpha:
                # ОПАСНОСТЬ! Делаем обобщение (MSG).
                self._generalize(dangerous_alpha, beta, unprocessed)
                # Текущий узел beta больше не нужен, мы перестроили дерево сверху.
                continue

            # --- 3. Драйвинг - вычисляем, если все спокойно ---
            self._drive_node(beta, unprocessed)

    def _create_node(self, expr: Expr, var_types: Dict[str, TypeExpr]) -> Node:
        """Создает узел и сразу считает мешок тегов, если нужно."""
        node = Node(expr, var_types)
        if self.strategy == 'TAG':
            node.bag = TagBag.collect(expr)
        return node

    def _drive_node(self, node: Node, unprocessed: list):
        """Выполняет шаг прогонки и добавляет детей в дерево."""
        step = self.driver.drive(node.expr, node.var_types)

        new_children = []
        match step:
            case StopStep():
                pass  # Лист

            case TransientStep(next_expr):
                child = self._create_node(next_expr, var_types=node.var_types.copy())
                node.add_child(child)
                new_children.append(child)

            case DecomposeStep(parts):
                for part in parts:
                    child = self._create_node(part, var_types=node.var_types.copy())
                    node.add_child(child)
                    new_children.append(child)

            case VariantStep(branches):
                for expr_branch, contraction, branch_types in branches:
                    child = self._create_node(expr_branch, var_types=branch_types)
                    node.add_child(child, contraction)
                    new_children.append(child)

        # Добавляем новых детей в конец (Breadth First), чтобы находить кратчайшие циклы.
        unprocessed.extend(new_children)

    def _find_embedding_ancestor(self, node: Node) -> Node | None:
        """Ищет предка, который гомеоморфно вложен в текущий узел."""
        # Мы проверяем свисток только для Вызовов Функций (FCall).
        # Конструкторы (Ctr) безопасны, мы их просто декомпозируем.
        # Если этого не сделать, add(a,b) свистнет на S(add(..)), и мы не дойдем до свертки.
        if not isinstance(node.expr, FCall):
            return None

        for alpha in node.ancestors():
            # Сравниваем только FCall с FCall
            if not isinstance(alpha.expr, FCall):
                continue

            is_dangerous = False

            if self.strategy == 'HE':
                if he(alpha.expr, node.expr):
                    is_dangerous = True

            elif self.strategy == 'TAG':
                # Сравниваем мешки
                if alpha.bag and node.bag:
                    if TagBag.is_dangerous(alpha.bag, node.bag):
                        is_dangerous = True

            if is_dangerous:
                return alpha
        return None

    def _generalize(self, alpha: Node, beta: Node, unprocessed: list):
        """
        Реализует стратегию обобщения:
        1. Считаем MSG(alpha, beta) -> gen.
        2. Заменяем alpha.expr на gen.
        3. Удаляем старых детей alpha (обрубаем ветку).
        4. Создаем новых детей для alpha из подстановки (let-binding).
        """
        # 1. Считаем MSG
        res = msg(alpha.expr, beta.expr)
        # res.gen - обобщенное выражение (с переменными v1, v2...)
        # res.sub1 - как получить alpha из gen (v1 -> expr1, ...)

        # Если обобщенное выражение совпадает с предком (с точностью до имен),
        # то нет смысла перестраивать дерево. Это просто цикл.
        if _is_renaming(alpha.expr, res.gen):
            # C' === C1
            # Превращаем это в свертку (Folding)
            beta.back_link = alpha
            return

        # 2. Обновляем узел alpha
        # print(f"GENERALIZATION: {alpha.expr} AND {beta.expr} -> {res.gen}")
        alpha.expr = res.gen
        if self.strategy == 'TAG':
            alpha.bag = TagBag.collect(alpha.expr)

        _remove_children_from_unprocessed(alpha, unprocessed)
        alpha.children = []  # Очищаем историю (забываем путь, который привел к beta)
        alpha.back_link = None

        # 3. Создаем новых детей для alpha из подстановки
        # Важно сохранить порядок переменных, чтобы потом правильно генерировать код.
        # msg генерирует v1, v2... по порядку.
        sorted_keys = sorted(res.sub1.keys())  # [('v', 1), ('v', 2)]

        for key in sorted_keys:
            val_expr = res.sub1[key]

            v_name = f"{key[0]}{key[1]}"
            # Создаем ребенка.
            child = Node(val_expr, var_types=alpha.var_types.copy())

            # Используем поле contraction, чтобы запомнить имя переменной let-связывания
            # (var_name='v1', pattern=None)
            let_info = Contraction(var_name=v_name, pattern=None)

            alpha.add_child(child, let_info)
            unprocessed.append(child)
