from sll.ast_nodes import Program, Expr, FCall
from sll.he import he
from sll.msg import msg
from sll.process_tree import Node, Contraction
from sll.driver import Driver, TransientStep, DecomposeStep, VariantStep, StopStep
from sll.matching import match


def _find_embedding_ancestor(node: Node) -> Node | None:
    """Ищет предка, который гомеоморфно вложен в текущий узел."""
    # Мы проверяем свисток только для Вызовов Функций (FCall).
    # Конструкторы (Ctr) безопасны, мы их просто декомпозируем.
    # Если этого не сделать, add(a,b) свистнет на S(add(..)), и мы не дойдем до свертки.
    if not isinstance(node.expr, FCall):
        return None

    for alpha in node.ancestors():
        # Сравниваем только с "опасными" предками (тоже FCall).
        if isinstance(alpha.expr, FCall) and he(alpha.expr, node.expr):
            return alpha
    return None


def _is_renaming(t1: Expr, t2: Expr) -> bool:
    """
    Проверяет, является ли t1 переименованием t2.
    Эквивалентно: t1 <= t2 И t2 <= t1.
    """
    return (match(t2, t1) is not None) and (match(t1, t2) is not None)


def _find_renaming_ancestor(node: Node) -> Node | None:
    """Ищет предка, который совпадает с точностью до переименования."""
    for alpha in node.ancestors():
        if _is_renaming(node.expr, alpha.expr):
            return alpha
    return None


def _generalize(alpha: Node, beta: Node, unprocessed: list):
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

    # 2. Обновляем узел alpha
    # print(f"GENERALIZATION: {alpha.expr} AND {beta.expr} -> {res.gen}")
    alpha.expr = res.gen
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


class Supercompiler:
    def __init__(self, program: Program):
        self.program = program
        self.driver = Driver(program)
        self.tree = None

    def build_tree(self, start_expr: Expr):
        """Строит дерево процессов для заданного выражения."""
        self.tree = Node(start_expr)

        # Очередь необработанных узлов
        unprocessed = [self.tree]

        while unprocessed:
            # Берем первый узел (стратегия в ширину/глубину зависит от pop(0) или pop())
            beta = unprocessed.pop(0)

            # 1. Проверка на зацикливание (Folding)
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
            dangerous_alpha = _find_embedding_ancestor(beta)

            if dangerous_alpha:
                # ОПАСНОСТЬ! Делаем обобщение (MSG).
                _generalize(dangerous_alpha, beta, unprocessed)
                # Текущий узел beta больше не нужен, мы перестроили дерево сверху.
                continue

            # --- 3. Драйвинг - вычисляем, если все спокойно ---
            self._drive_node(beta, unprocessed)

    def _drive_node(self, node: Node, unprocessed: list):
        """Выполняет шаг драйвинга и добавляет детей в дерево."""
        step = self.driver.drive(node.expr)

        new_children = []
        match step:
            case StopStep():
                pass  # Лист

            case TransientStep(next_expr):
                child = Node(next_expr)
                node.add_child(child)
                new_children.append(child)

            case DecomposeStep(parts):
                for part in parts:
                    child = Node(part)
                    node.add_child(child)
                    new_children.append(child)

            case VariantStep(branches):
                for expr_branch, contraction in branches:
                    child = Node(expr_branch)
                    node.add_child(child, contraction)
                    new_children.append(child)

        # Добавляем новых детей в конец (Breadth First), чтобы находить кратчайшие циклы.
        unprocessed.extend(new_children)
