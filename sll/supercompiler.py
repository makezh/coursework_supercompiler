from typing import Dict, Optional, List

from sll.ast_nodes import Program, Expr, FCall, TypeExpr, Var, IntLit, Ctr, Let
from sll.he import he
from sll.msg import msg, natural_key
from sll.process_tree import Node, Contraction
from sll.driver import Driver, TransientStep, DecomposeStep, VariantStep, StopStep, DriveStep, LetStep
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
            while isinstance(step, TransientStep):
                self._drive_node_with_step(beta, step, unprocessed)
                step = self.driver.drive(beta.expr, beta.var_types)
                print(f"[DRIVE*] at {beta.expr}  step={type(step).__name__}")
                if self.strategy == "TAG":
                    print(f"[BAG] expr={beta.expr} bag={beta.bag} heap={len(beta.heap)} stack={len(beta.stack)}")

            ancestor = _find_renaming_ancestor(beta)
            if ancestor:
                beta.back_link = ancestor
                print(f"[FOLD*] beta={beta.expr}  -> alpha={ancestor.expr}")
                continue

            # --- Шаг В: Свисток (Whistle) ---
            # Здесь происходит выбор: HE или TAG
            dangerous_alpha = self._find_embedding_ancestor(beta)
            if dangerous_alpha:
                print(f"[WHISTLE] alpha={dangerous_alpha.expr}  beta={beta.expr}  strategy={self.strategy}")
                if self.gen_type == 'TOP':
                    print(f"[GEN] alpha={dangerous_alpha.expr}  beta={beta.expr} gen_type={self.gen_type}")
                    did_gen = self._generalize(dangerous_alpha, beta, unprocessed)
                else:
                    print(f"[GEN] alpha={dangerous_alpha.expr}  beta={beta.expr} gen_type={self.gen_type}")
                    self._generalize_bottom(dangerous_alpha, beta, unprocessed)
                    did_gen = True
                if did_gen:
                    continue
                # did_gen=False: обобщение отложено, прогоняем beta нормально

            self._drive_node_with_step(beta, step, unprocessed)

    def _create_node(self, expr: Expr, var_types: Dict[str, TypeExpr]) -> Node:
        """Создает узел и сразу считает мешок тегов, если нужно."""
        node = Node(expr, var_types)
        if self.strategy == 'TAG':
            node.bag = TagBag.collect(node)
        return node

    def _drive_node_with_step(self, node: Node, step: DriveStep, unprocessed: list):
        """Выполняет уже вычисленный шаг драйвинга."""
        new_children = []
        match step:
            case StopStep():
                return

            case LetStep(bindings, body):
                node.extend_heap(bindings)
                node.expr = body
                if self.strategy == "TAG":
                    node.bag = TagBag.collect(node)
                return

            case TransientStep(next_expr, rule_pat):
                node.driven_from = node.expr
                node.driven_rule = rule_pat
                node.expr = next_expr

                if self.strategy == "TAG":
                    node.bag = TagBag.collect(node)

            case DecomposeStep(parts):
                # NEW: контекст вырос у node
                node.push_frame(getattr(node.expr, "tag", None), kind="DECOMP")
                if self.strategy == "TAG":
                    node.bag = TagBag.collect(node)

                for part in parts:
                    child = self._create_node(part, var_types=node.var_types.copy())
                    node.add_child(child)
                    if self.strategy == "TAG":
                        child.bag = TagBag.collect(child)
                    new_children.append(child)

            case VariantStep(branches):
                node.push_frame(getattr(node.expr, "tag", None), kind="CASE")
                if self.strategy == "TAG":
                    node.bag = TagBag.collect(node)

                for expr_branch, contraction, branch_types, applied_pat in branches:
                    child = self._create_node(expr_branch, var_types=branch_types)
                    child.driven_rule = applied_pat
                    node.add_child(child, contraction)
                    if self.strategy == "TAG":
                        child.bag = TagBag.collect(child)
                    new_children.append(child)

        unprocessed.extend(new_children)

    def _find_embedding_ancestor(self, node: Node) -> Node | None:
    # эвристика: не свистим на конструкторах (можно оставить)
        if isinstance(node.expr, Ctr):
            return None

        for alpha in node.ancestors():
            if getattr(alpha.expr, "name", None) == "PROGRAM_FOREST":
                continue

            if self.strategy == "HE":
                if not isinstance(alpha.expr, FCall):
                    continue
                if he(alpha.expr, node.expr):
                    return alpha

            elif self.strategy == "TAG":
                # страховка: TAG не должен побеждать renaming
                if _is_renaming(alpha.expr, node.expr):
                    continue
                if alpha.bag is not None and node.bag is not None:
                    if TagBag.is_dangerous(alpha.bag, node.bag):
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

        # если TOP не даёт прогресса, уходим в BOTTOM
        if isinstance(res.gen, Var):
            self._generalize_bottom(alpha, beta, unprocessed)
            return

        # если gen равен alpha по переименованию:
        # - если beta тоже переименование alpha → fold (стандартная свёртка)
        # - если beta имеет БОЛЬШЕ структуры (напр. Cons вместо переменной) →
        #   НЕ сворачиваем сейчас: beta нужно прогнать дальше, fold наступит
        #   в рекурсивном подвызове (например, fbc(fab(v2)) вместо fbc(fab(Cons v1 v2)))
        if _is_renaming(alpha.expr, res.gen):
            if _is_renaming(beta.expr, alpha.expr):
                beta.back_link = alpha
                return True
            return False  # сигнал: обобщение не выполнено, прогнать beta нормально

        old_alpha_expr = alpha.expr
        if any(_is_renaming(old_alpha_expr, v) for v in res.sub1.values()):
            self._generalize_bottom(alpha, beta, unprocessed)
            return True

        alpha.gen_alpha = old_alpha_expr
        alpha.gen_beta = beta.expr
        alpha.gen_result = res.gen

        # 2. Обновляем узел alpha
        # print(f"GENERALIZATION: {alpha.expr} AND {beta.expr} -> {res.gen}")
        alpha.expr = res.gen
        if self.strategy == 'TAG':
            alpha.bag = TagBag.collect(alpha)

        # Пробрасываем типы для свежих переменных MSG в var_types alpha.
        # Тип v_i = тип выражения sub1[v_i] в контексте alpha.
        # Если sub1[v_i] — переменная, берём её тип напрямую.
        for v_name, val_expr in res.sub1.items():
            if isinstance(val_expr, Var) and val_expr.name in alpha.var_types:
                alpha.var_types[v_name] = alpha.var_types[val_expr.name]

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
        unprocessed.insert(0, alpha)
        return True

    def _generalize_bottom(self, alpha: Node, beta: Node, unprocessed: list):
        """
        Обобщение снизу.
        Если MSG(alpha,beta) вырождается в дырку и beta = FCall(...),
        строим Let по beta-контексту и возвращаем beta в очередь,
        чтобы driver разложил Let на детей.
        """
        res = msg(alpha.expr, beta.expr)

        # Книжный случай: разные головы -> MSG дырка -> делаем контекстный Let по beta
        if isinstance(res.gen, Var) and isinstance(beta.expr, FCall):
            f_name = beta.expr.name
            args = beta.expr.args

            bindings = []
            hole_vars = []
            for i, arg in enumerate(args, start=1):
                h = f"h{i}"
                bindings.append((h, arg))
                hole_vars.append(Var(h))

            beta.gen_alpha = alpha.expr
            beta.gen_beta = beta.expr
            beta.gen_result = Let(bindings=bindings, body=FCall(f_name, hole_vars))

            beta.expr = beta.gen_result
            if self.strategy == "TAG":
                beta.bag = TagBag.collect(beta)

            unprocessed.insert(0, beta)
            return

        # Обычный путь (MSG сохраняет структуру)
        beta.gen_alpha = alpha.expr
        beta.gen_beta = beta.expr
        beta.gen_result = res.gen

        bindings = []
        for v_name in sorted(res.sub2.keys(), key=natural_key):
            bindings.append((v_name, res.sub2[v_name]))

        beta.expr = Let(bindings=bindings, body=res.gen)

        if self.strategy == "TAG":
            beta.bag = TagBag.collect(beta)

        unprocessed.insert(0, beta)
        return

    def run_hypercycle(self, start_expr, start_var_types):
        """
        Гиперцикл Абрамова:
        строим деревья процессов для множества базисных конфигураций.
        Ключевой момент: конфигурации идентифицируются по КАНОНИЧЕСКОМУ корню
        (после нормализации/прогонки внутри build_tree).
        """

        processed_configs: dict[str, Node] = {}

        queue: list[tuple[Expr, dict]] = [(start_expr, start_var_types)]

        start_canon: str | None = None

        while queue:
            current_expr, current_types = queue.pop(0)

            # 1) Строим дерево для текущего выражения
            self.build_tree(current_expr, current_types)

            # 2) Канонический ключ = фактический корень после прогонки/нормализации
            canon = str(self.tree.expr)

            # запоминаем канон старта (важно для add3!)
            if start_canon is None and _is_renaming(self.tree.expr, start_expr):
                start_canon = canon

            # 3) Если уже обработано — ничего не делаем
            if canon in processed_configs:
                continue

            print(f"  Hypercycle: processing config {canon}")
            processed_configs[canon] = self.tree

            # 4) Собираем базисные конфигурации (цели backlink'ов) и добавляем в очередь
            for base_node in self._find_all_backlink_targets(self.tree):
                b_canon = str(base_node.expr)
                if b_canon not in processed_configs:
                    queue.append((base_node.expr, base_node.var_types))

        # 5) Фиксируем лес
        self.hypercycle_roots = processed_configs

        # 6) Выбираем стартовый корень корректно:
        # если start_canon не нашёлся (редко), берём корень по канону после build_tree(start_expr)
        if start_canon is None:
            # пересоберём один раз, чтобы узнать канон старта
            self.build_tree(start_expr, start_var_types)
            start_canon = str(self.tree.expr)

        self.tree = self.hypercycle_roots[start_canon]

        # 7) Обрезаем ссылки на другие корни и собираем PROGRAM_FOREST
        self._prune_forest()
        forest_root = Node(FCall("PROGRAM_FOREST", []), {})

        # (порядок можно сохранить как в processed_configs, но лучше стабилизировать)
        for _, root_node in self.hypercycle_roots.items():
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
            node.is_basis_ref = True  # объявлено в Node
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