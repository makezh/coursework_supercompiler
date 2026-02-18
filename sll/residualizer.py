from typing import List, Dict, Tuple
from sll.ast_nodes import Program, Rule, Pattern, Expr, Var, Ctr, FCall, IntLit, Let
from sll.process_tree import Node
from sll.matching import substitute, match, MatchSuccess


class Residualizer:
    def __init__(self, tree_root: Node):
        self.root = tree_root
        self.rules: List[Rule] = []
        self.node_to_sig: Dict[Node, Tuple[str, List[Var]]] = {}
        self.f_count = 0
        self.g_count = 0
        self.k_count = 0
        self.let_cache: Dict[str, str] = {}

    def _rewrite_expr(self, expr: Expr) -> Expr:
        match expr:
            case Var(_) | IntLit(_):
                return expr

            case Ctr(name, args):
                return Ctr(name, [self._rewrite_expr(a) for a in args], lineno=expr.lineno, tag=expr.tag)

            case FCall(_, _):
                for target in self.node_to_sig.keys():
                    if not isinstance(target.expr, FCall):
                        continue
                    if isinstance(expr, FCall) and target.expr.name != expr.name:
                        continue
                    m = match(target.expr, expr)

                    if isinstance(m, MatchSuccess):
                        return self._call_registered(target, expr)

                return FCall(expr.name, [self._rewrite_expr(a) for a in expr.args], lineno=expr.lineno, tag=expr.tag)

            case Let(bindings, body):
                # 1) сначала резидуализируем значения биндингов (важно: тут применятся folding→g...)
                new_bindings = [(name, self._rewrite_expr(val)) for name, val in bindings]

                # 2) резидуализируем body
                new_body = self._rewrite_expr(body)

                # 3) кэш, чтобы одинаковые let не плодили 100 функций
                key = str(Let(new_bindings, new_body))
                if key in self.let_cache:
                    kname = self.let_cache[key]
                else:
                    self.k_count += 1
                    kname = f"k{self.k_count}"
                    self.let_cache[key] = kname

                    # k(h1,h2,...) -> body
                    params = [Var(name) for name, _ in new_bindings]
                    self.rules.append(Rule(Pattern(kname, params), new_body))

                # 4) let ... in ... заменяем на вызов k(e1,e2,...)
                args = [val for _, val in new_bindings]
                return FCall(kname, args, lineno=getattr(expr, "lineno", 0), tag=getattr(expr, "tag", None))

            case _:
                return expr


    def _call_registered(self, target: Node, current_expr: Expr) -> Expr:
        func_name, params = self.node_to_sig[target]

        m = match(target.expr, current_expr)
        if not isinstance(m, MatchSuccess):
            return FCall(func_name, self._get_vars(current_expr))

        args = [m.bindings.get(v.name, v) for v in params]  # важен порядок params
        return FCall(func_name, args)

    def residualize(self) -> Program:
        self._find_functions(self.root)

        # Сортировка для детерминизма (по id узла или порядку добавления)
        nodes = list(self.node_to_sig.keys())
        # Можно отсортировать по именам функций для красоты, но не обязательно

        for node in nodes:
            self._generate_definition(node)
        return Program(self.rules, [], [])

    def _find_functions(self, node: Node):
        must_be_function = False
        if node is self.root:
            must_be_function = True

        # G-функция (Ветвление)
        if len(node.children) > 1:
            # Проверяем, что это не MSG (где pattern is None)
            if any(c.contraction and c.contraction.pattern is not None for c in node.children):
                must_be_function = True

        if must_be_function and node not in self.node_to_sig:
            self._register_func(node)

        for child in node.children:
            self._find_functions(child)
            if child.back_link:
                self._register_func(child.back_link)

    def _register_func(self, node: Node):
        if node in self.node_to_sig: return
        vars_in_expr = self._get_vars(node.expr)

        is_g = False
        if node.children:
            if node.children[0].contraction and node.children[0].contraction.pattern is not None:
                is_g = True

        if is_g:
            self.g_count += 1
            name = f"g{self.g_count}"
        else:
            self.f_count += 1
            name = f"f{self.f_count}"
        self.node_to_sig[node] = (name, vars_in_expr)

    def _generate_definition(self, node: Node):
        name, params = self.node_to_sig[node]

        is_g = False
        if node.children:
             if node.children[0].contraction and node.children[0].contraction.pattern is not None:
                 is_g = True

        if is_g:
            for child in node.children:
                if not child.contraction: continue
                lhs_params = []
                for var in params:
                    if var.name == child.contraction.var_name:
                        lhs_params.append(child.contraction.pattern)
                    else:
                        lhs_params.append(var)

                pat = Pattern(name, lhs_params)
                body = self._rewrite_expr(self._transform(child))
                self.rules.append(Rule(pat, body))
        else:
            pat = Pattern(name, params)
            if not node.children:
                body = self._rewrite_expr(node.expr)
            elif node.children[0].contraction and node.children[0].contraction.pattern is None:
                # Generalization case
                bindings = {}
                for child in node.children:
                    bindings[child.contraction.var_name] = self._transform(child)
                body = self._rewrite_expr(substitute(node.expr, bindings))
            elif isinstance(node.expr, Ctr):
                new_args = [self._transform(c) for c in node.children]
                body = Ctr(node.expr.name, new_args)
            elif len(node.children) == 1:
                body = self._transform(node.children[0])
            else:
                body = self._rewrite_expr(node.expr)
            self.rules.append(Rule(pat, body))

    def _transform(self, node: Node) -> Expr:
        if node.back_link:
            return self._call_registered(node.back_link, node.expr)

        if node in self.node_to_sig:
            return self._call_registered(node, node.expr)

        if isinstance(node.expr, Ctr) and node.children:
             new_args = [self._transform(c) for c in node.children]
             return Ctr(node.expr.name, new_args)

        if node.children and node.children[0].contraction and node.children[0].contraction.pattern is None:
            bindings = {}
            for c in node.children:
                bindings[c.contraction.var_name] = self._transform(c)
            return self._rewrite_expr(substitute(node.expr, bindings))

        if len(node.children) == 1:
             return self._transform(node.children[0])

        return self._rewrite_expr(node.expr)

    def _get_vars(self, expr: Expr) -> List[Var]:
        vars_list = []
        seen = set()
        def visit(e, bound: set):
            match e:
                case Var(name):
                    if name in bound:
                        return
                    if name not in seen:
                        seen.add(name)
                        vars_list.append(e)
                case Ctr(_, args) | FCall(_, args):
                    for a in args: visit(a, bound)
                case Let(bindings, body):
                    for _, val in bindings:
                        visit(val, bound)
                    new_bound = set(bound)
                    for name, _ in bindings:
                        new_bound.add(name)
                    visit(body, new_bound)
        visit(expr, set())
        return vars_list