from typing import Dict, Optional, List

from sll.ast_nodes import Program, Expr, FCall, TypeExpr, Var, IntLit, Ctr
from sll.he import he
from sll.msg import msg, natural_key
from sll.process_tree import Node, Contraction
from sll.driver import Driver, TransientStep, DecomposeStep, VariantStep, StopStep, DriveStep
from sll.matching import match, MatchSuccess
from sll.preprocessor import add_tags, Tagger
from sll.bag_of_tags import TagBag
from sll.tagging import TagAllocator


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
    def __init__(self, program: Program, strategy: str = "HE", gen_type: str = "TOP"):
        self.program = program
        self.driver = Driver(program)
        self.hypercycle_roots: Dict[str, Node] = {}
        self.tree: Optional[Node] = None
        self.strategy = strategy
        self.gen_type = gen_type

        # Если выбрана стратегия TAG, нам нужно один раз разметить всю программу
        self.tag_allocator = None
        if self.strategy == 'TAG':
            self.tag_allocator = TagAllocator()
            self.tag_allocator.process_program(self.program)

    def _find_global_root(self, node: Node) -> Node | None:
        """
        Ищет, совпадает ли узел с одним из корней в лесу базисных конфигураций.
        """
        for root in self.hypercycle_roots.values():
            if node is root:
                continue

            if _is_renaming(node.expr, root.expr):
                return root
        return None

    def build_tree(self, start_expr: Expr, start_var_types: Dict[str, TypeExpr], max_steps:int = 100):
        """Строит дерево процессов для заданного выражения.
        start_expr: Начальное выражение для суперкомпиляции.
        start_var_types: Типы переменных начального выражения.
        """
        if self.strategy == 'TAG' and self.tag_allocator is not None:
            # Размечаем и входное выражение тоже, чтобы у него появились теги
            self.tag_allocator.process_expr(start_expr)

        self.tree = self._create_node(start_expr, start_var_types)

        # Очередь необработанных узлов
        unprocessed = [self.tree]
        steps = 0
        while unprocessed:
            steps += 1
            if steps > max_steps:
                print(f"[STOP] step limit reached: {max_steps}")
                print(f"[STOP] queue size={len(unprocessed)}")
                print(f"[STOP] next node would be: {unprocessed[0].expr}")
                break
            beta = unprocessed.pop(0)

            # --- Шаг А: Свертка (Folding/Renaming) ---
            # Одинаково для обеих стратегий
            ancestor = _find_renaming_ancestor(beta)
            if ancestor:
                beta.back_link = ancestor
                print(f"[FOLD] beta={beta.expr}  -> alpha={ancestor.expr}")
                continue

            # --- Шаг Б: Прогонка (Driving) ---
            step = self.driver.drive(beta.expr, beta.var_types)
            print(f"[DRIVE] at {beta.expr}  step={type(step).__name__}")

            # Если это простое упрощение (TransientStep) — делаем его сразу
            if isinstance(step, TransientStep):
                self._drive_node_with_step(beta, step, unprocessed)
                continue

            # --- Шаг В: Свисток (Whistle) ---
            # Здесь происходит выбор: HE или TAG
            dangerous_alpha = self._find_embedding_ancestor(beta)
            if dangerous_alpha:
                print(f"[WHISTLE] alpha={dangerous_alpha.expr}  beta={beta.expr}  strategy={self.strategy}")
                if self.gen_type == 'TOP':
                    # Классика: рубим дерево сверху
                    print(f"[GEN] alpha={dangerous_alpha.expr}  beta={beta.expr} gen_type={self.gen_type}")
                    self._generalize(dangerous_alpha, beta, unprocessed)
                else:
                    # Абрамов: перестраиваем текущий узел снизу
                    print(f"[GEN] alpha={dangerous_alpha.expr}  beta={beta.expr} gen_type={self.gen_type}[pe]adeijf;jwern")
                    self._generalize_bottom(dangerous_alpha, beta, unprocessed)
                continue

            self._drive_node_with_step(beta, step, unprocessed)

    def _create_node(self, expr: Expr, var_types: Dict[str, TypeExpr]) -> Node:
        """Создает узел и сразу считает мешок тегов, если нужно."""
        node = Node(expr, var_types)
        if self.strategy == 'TAG':
            node.bag = TagBag.collect(expr)
        return node

    def _drive_node_with_step(self, node: Node, step: DriveStep, unprocessed: list):
        """Выполняет уже вычисленный шаг драйвинга."""
        new_children = []
        match step:
            case StopStep():
                return
            case TransientStep(next_expr, rule_pat):
                child = self._create_node(next_expr, var_types=node.var_types.copy())
                child.driven_from = node.expr
                child.driven_rule = rule_pat
                node.add_child(child)
                new_children.append(child)
            case DecomposeStep(parts):
                for part in parts:
                    child = self._create_node(part, var_types=node.var_types.copy())
                    node.add_child(child)
                    new_children.append(child)
            case VariantStep(branches):
                for expr_branch, contraction, branch_types, applied_pat in branches:
                    child = self._create_node(expr_branch, var_types=branch_types)
                    child.driven_rule = applied_pat
                    node.add_child(child, contraction)
                    new_children.append(child)

        unprocessed.extend(new_children)

    def _find_embedding_ancestor(self, node: Node) -> Node | None:
        """Ищет предка, который гомеоморфно вложен в текущий узел."""
        # Конструкторы (Ctr) безопасны, мы их просто декомпозируем.
        # Если этого не сделать, add(a,b) свистнет на S(add(..)), и мы не дойдем до свертки.
        if isinstance(node.expr, Ctr):
            return None

        for alpha in node.ancestors():
            if getattr(alpha.expr, "name", None) == "PROGRAM_FOREST":
                continue
            # Сравниваем только FCall с FCall
            if not isinstance(alpha.expr, FCall):
                continue

            is_dangerous = False

            if self.strategy == 'HE':
                if he(alpha.expr, node.expr):
                    is_dangerous = True

            elif self.strategy == 'TAG':
                # Сравниваем мешки
                if isinstance(node.expr, FCall) and alpha.bag and node.bag:
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

        # Если обобщенное выражение совпадает с предком (с точностью до имен),
        # то нет смысла перестраивать дерево. Это просто цикл.
        if _is_renaming(alpha.expr, res.gen):
            # C' === C1
            # Превращаем это в свертку (Folding)
            beta.back_link = alpha
            return

        old_alpha_expr = alpha.expr
        alpha.gen_alpha = old_alpha_expr
        alpha.gen_beta = beta.expr
        alpha.gen_result = res.gen

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
        sorted_vnames = sorted(res.sub1.keys(), key=natural_key)

        for v_name in sorted_vnames:
            val_expr = res.sub1[v_name]

            # Создаем ребенка.
            child = self._create_node(val_expr, var_types=alpha.var_types.copy())

            let_info = Contraction(var_name=v_name, pattern=None, value=val_expr)

            alpha.add_child(child, let_info)
            unprocessed.append(child)

    def _generalize_bottom(self, alpha: Node, beta: Node, unprocessed: list):
        """
        Стратегия Абрамова (снизу):
        Обобщаем текущий узел beta относительно предка alpha.
        """
        res = msg(alpha.expr, beta.expr)

        old_beta_expr = beta.expr
        beta.gen_alpha = alpha.expr
        beta.gen_beta = old_beta_expr
        beta.gen_result = res.gen

        # Обновляем выражение в ТЕКУЩЕМ узле beta
        beta.expr = res.gen
        if self.strategy == 'TAG':
            beta.bag = TagBag.collect(beta.expr)

        # Создаем детей для beta из того, что попало в подстановку (v1 -> expr1, ...)
        sorted_vnames = sorted(res.sub2.keys(), key=natural_key) # sub2 - подстановка для beta

        for v_name in sorted_vnames:
            val_expr = res.sub2[v_name]
            child = self._create_node(val_expr, var_types=beta.var_types.copy())

            # Помечаем ребро как let-связывание
            let_info = Contraction(var_name=v_name, pattern=None, value=val_expr)
            beta.add_child(child, let_info)
            unprocessed.append(child)

    def run_hypercycle(self, start_expr, start_var_types):
        """
        Реализация Гиперцикла Абрамова.
        Итеративно строит графы для всех базисных конфигураций.
        """
        # Набор выражений, которые мы уже суперкомпилировали (базисные конфигурации)
        processed_configs = {}

        # Очередь на суперкомпиляцию. Первым идет стартовое выражение.
        queue = [(start_expr, start_var_types)]

        while queue:
            current_expr, current_types = queue.pop(0)
            expr_str = str(current_expr)
            if expr_str in processed_configs:
                continue

            print(f"  Hypercycle: processing config {expr_str}")

            # Строим дерево
            self.build_tree(current_expr, current_types)

            # Сохраняем корень этого дерева
            processed_configs[expr_str] = self.tree

            # Ищем новые базисные конфигурации
            new_bases = self._find_all_backlink_targets(self.tree)
            for base_node in new_bases:
                b_str = str(base_node.expr)
                if b_str not in processed_configs:
                    queue.append((base_node.expr, base_node.var_types))

        self.hypercycle_roots = processed_configs
        self.tree = processed_configs[str(start_expr)]

        self._prune_forest()
        forest_root = Node(FCall("PROGRAM_FOREST", []), {})

        for expr_str, root_node in self.hypercycle_roots.items():
            forest_root.add_child(root_node)

        self.tree = forest_root

    def _prune_forest(self):
        """
        Проходит по всем построенным деревьям и обрезает ветки,
        которые совпадают с корнями других деревьев.
        """
        print("--- Pruning Forest ---")
        for root_node in self.hypercycle_roots.values():
            self._prune_node_recursive(root_node)

    def _prune_node_recursive(self, node: Node):
        if node.back_link:
            return
        global_root = self._find_global_root(node)

        if global_root:
            node.is_basis_ref = True
            node.children = []
            return

        for child in list(node.children):
            self._prune_node_recursive(child)

    def _find_all_backlink_targets(self, root: Node) -> List[Node]:
        """Собирает все узлы, на которые КТО-ТО ссылается через back_link."""
        targets = set()

        def collect(node: Node):
            if node.back_link:
                targets.add(node.back_link)
            for child in node.children:
                collect(child)

        collect(root)
        return list(targets)