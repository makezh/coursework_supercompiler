from typing import List, Dict, Tuple
from sll.ast_nodes import Program, Rule, Pattern, Expr, Var, Ctr, FCall, IntLit
from sll.process_tree import Node
from sll.matching import substitute

class Residualizer:
    def __init__(self, tree_root: Node):
        self.root = tree_root
        self.rules: List[Rule] = []
        self.node_to_sig: Dict[Node, Tuple[str, List[Var]]] = {}
        self.f_count = 0
        self.g_count = 0

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
                body = self._transform(child)
                self.rules.append(Rule(pat, body))
        else:
            pat = Pattern(name, params)
            if not node.children:
                body = node.expr
            elif node.children[0].contraction and node.children[0].contraction.pattern is None:
                # Generalization case
                bindings = {}
                for child in node.children:
                    bindings[child.contraction.var_name] = self._transform(child)
                body = substitute(node.expr, bindings)
            elif isinstance(node.expr, Ctr):
                new_args = [self._transform(c) for c in node.children]
                body = Ctr(node.expr.name, new_args)
            elif len(node.children) == 1:
                body = self._transform(node.children[0])
            else:
                body = node.expr
            self.rules.append(Rule(pat, body))

    def _transform(self, node: Node) -> Expr:
        if node.back_link:
            target = node.back_link
            func_name, func_params = self.node_to_sig[target]
            return FCall(func_name, self._get_vars(node.expr))

        if node in self.node_to_sig:
            func_name, func_params = self.node_to_sig[node]
            return FCall(func_name, self._get_vars(node.expr))

        if isinstance(node.expr, Ctr) and node.children:
             new_args = [self._transform(c) for c in node.children]
             return Ctr(node.expr.name, new_args)

        if len(node.children) == 1:
             return self._transform(node.children[0])

        return node.expr

    def _get_vars(self, expr: Expr) -> List[Var]:
        vars_list = []
        seen = set()
        def visit(e):
            match e:
                case Var(name):
                    if name not in seen:
                        seen.add(name)
                        vars_list.append(e)
                case Ctr(_, args) | FCall(_, args):
                    for a in args: visit(a)
        visit(expr)
        return vars_list