from typing import List, Dict, Tuple, Optional
from sll.ast_nodes import (Program, Rule, Pattern, Expr, Var, Ctr, FCall,
                           IntLit, Let, TypeExpr, FunSig)
from sll.process_tree import Node
from sll.matching import substitute, match, MatchSuccess
from sll.supercompiler import _is_renaming
from sll.type_checker import TypeContext, infer_type, resolve_type


class Residualizer:
    def __init__(self, tree_root: Node, original_program=None):
        self.root = tree_root
        self.original_program = original_program
        self.rules: List[Rule] = []
        self.node_to_sig: Dict[Node, Tuple[str, List[Var]]] = {}
        self.f_count = 0
        self.g_count = 0
        self.k_count = 0
        self.let_cache: Dict[str, str] = {}
        self._entry_node: Optional[Node] = None
        self._entry_name: Optional[str] = None
        self._fresh_n = 0

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
        if isinstance(self.root.expr, FCall) and self.root.expr.name == "PROGRAM_FOREST":
            roots = self.root.children
            if not roots:
                return Program([], self._original_types(), [])

            for r in roots:
                if r not in self.node_to_sig:
                    self._register_func(r)
                self._find_functions(r)

            for node in list(self.node_to_sig.keys()):
                self._generate_definition(node)

            start_root = roots[0]
            if hasattr(self, "start_expr"):
                for r in roots:
                    if _is_renaming(r.expr, self.start_expr):
                        start_root = r
                        break

            entry_name = "main"
            start_sig_name, start_params = self.node_to_sig[start_root]

            for r in roots:
                decomp = getattr(r, "active_decomp", None)
                if decomp is not None:
                    self.rules.append(decomp.fmt_rule)
                    self.rules.append(decomp.unfmt_rule)

            start_decomp = getattr(start_root, "active_decomp", None)
            if start_decomp is not None:
                orig_call = FCall(start_sig_name, list(start_params))
                deforested = self._deforest_unfmt(start_decomp, orig_call)
                inner = deforested if deforested is not None \
                    else FCall(start_decomp.unfmt_name, [orig_call])
                fmt_args = [inner] + [Var(p) for p in start_decomp.frozen_params]
                entry_body = FCall(start_decomp.fmt_name, fmt_args)
            else:
                entry_body = FCall(start_sig_name, list(start_params))

            self.rules.insert(
                0,
                Rule(Pattern(entry_name, start_params), entry_body)
            )

            self._pull_unresolved_originals()
            self._drop_unreachable(entry_name)
            self._entry_node = start_root
            self._entry_name = entry_name
            return Program(self.rules, self._original_types(), self._infer_signatures())

        # обычный режим
        self._find_functions(self.root)
        for node in list(self.node_to_sig.keys()):
            self._generate_definition(node)
        self._generate_root_entry()
        self._pull_unresolved_originals()
        self._entry_node = self.root
        self._entry_name = self.rules[0].pattern.name if self.rules else None
        return Program(self.rules, self._original_types(), self._infer_signatures())

    def _drop_unreachable(self, entry_name: str):
        called = set()

        def collect(e):
            match e:
                case FCall(name, args):
                    called.add(name)
                    for a in args:
                        collect(a)
                case Ctr(_, args):
                    for a in args:
                        collect(a)
                case Let(bindings, body):
                    for _, v in bindings:
                        collect(v)
                    collect(body)

        live = {entry_name}
        changed = True
        while changed:
            changed = False
            for r in self.rules:
                if r.pattern.name not in live:
                    continue
                before = len(called)
                collect(r.body)
                if len(called) > before:
                    for c in called:
                        if c not in live:
                            live.add(c)
                            changed = True
        self.rules = [r for r in self.rules if r.pattern.name in live]

    def _deforest_unfmt(self, decomp, basis_call: FCall) -> Optional[Expr]:
        inner_rules = [r for r in self.rules if r.pattern.name == basis_call.name]
        if len(inner_rules) != 1:
            return None
        inner_rule = inner_rules[0]
        params = inner_rule.pattern.params
        if not all(isinstance(p, Var) for p in params):
            return None
        sub = {p.name: a for p, a in zip(params, basis_call.args)}
        inner_body = substitute(inner_rule.body, sub)

        unfmt_pat = decomp.unfmt_rule.pattern.params[0]
        m = match(unfmt_pat, inner_body)
        if not isinstance(m, MatchSuccess):
            return None
        return substitute(decomp.unfmt_rule.body, m.bindings)

    def _pull_unresolved_originals(self):
        if self.original_program is None:
            return
        defined = {r.pattern.name for r in self.rules}
        called = set()

        def collect(e):
            match e:
                case FCall(name, args):
                    called.add(name)
                    for a in args:
                        collect(a)
                case Ctr(_, args):
                    for a in args:
                        collect(a)
                case Let(bindings, body):
                    for _, v in bindings:
                        collect(v)
                    collect(body)

        for r in self.rules:
            collect(r.body)

        queue = list(called - defined)
        while queue:
            name = queue.pop()
            if name in defined:
                continue
            orig_rules = [r for r in self.original_program.rules if r.pattern.name == name]
            if not orig_rules:
                continue
            self.rules.extend(orig_rules)
            defined.add(name)
            for r in orig_rules:
                new_called = set()
                old_called = called.copy()
                collect(r.body)
                for c in called - old_called:
                    if c not in defined:
                        queue.append(c)

    @staticmethod
    def _is_pattern_contraction(c) -> bool:
        """True если контракция представляет ветвление по паттерну (g-функция)."""
        return (c.pattern is not None or
                c.narrowings is not None or
                c.is_default)

    @staticmethod
    def _expr_to_pattern(expr):
        """Рекурсивно преобразует Ctr-выражение в Pattern для LHS правила."""
        if isinstance(expr, Ctr):
            return Pattern(expr.name, [Residualizer._expr_to_pattern(a) for a in expr.args])
        return expr  # Var остаётся Var

    def _find_functions(self, node: Node):
        if isinstance(node.expr, FCall) and node.expr.name == "PROGRAM_FOREST":
            # forest — это контейнер, функции не создаём
            for ch in node.children:
                self._find_functions(ch)
                if ch.back_link:
                    self._register_func(ch.back_link)
            return
        must_be_function = False
        if node is self.root:
            must_be_function = True

        # G-функция (Ветвление)
        if len(node.children) > 1:
            # Проверяем, что это не MSG (где pattern is None, narrowings is None, not is_default)
            if any(c.contraction and self._is_pattern_contraction(c.contraction)
                   for c in node.children):
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

        is_g = any(
            c.contraction and self._is_pattern_contraction(c.contraction)
            for c in node.children
        )

        if is_g:
            self.g_count += 1
            name = f"g{self.g_count}"
        else:
            self.f_count += 1
            name = f"f{self.f_count}"
        self.node_to_sig[node] = (name, vars_in_expr)

    def _generate_definition(self, node: Node):
        name, params = self.node_to_sig[node]

        is_g = any(
            c.contraction and self._is_pattern_contraction(c.contraction)
            for c in node.children
        )

        if is_g:
            for child in node.children:
                if not child.contraction: continue
                if not self._is_pattern_contraction(child.contraction): continue
                lhs_params = []

                if child.contraction.narrowings is not None or child.contraction.is_default:
                    # Multi-narrowing или default branch
                    narrowings = child.contraction.narrowings or {}
                    for var in params:
                        if var.name in narrowings:
                            lhs_params.append(self._expr_to_pattern(narrowings[var.name]))
                        else:
                            lhs_params.append(var)
                else:
                    # Одиночное сужение (обратная совместимость)
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
            elif node.children[0].contraction and not self._is_pattern_contraction(node.children[0].contraction):
                # Generalization case (MSG let-binding)
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

    def _generate_root_entry(self):
        """
        Если корень — g-функция с let-binding детьми (от TOP MSG),
        генерирует обёртку-точку входа: f(orig_vars) -> g(val1, val2, ...).
        """
        if self.root not in self.node_to_sig:
            return
        root_name, root_params = self.node_to_sig[self.root]
        is_root_g = any(
            c.contraction and self._is_pattern_contraction(c.contraction)
            for c in self.root.children
        )
        if not is_root_g:
            return
        let_children = [
            c for c in self.root.children
            if c.contraction and not self._is_pattern_contraction(c.contraction)
            and c.contraction.value is not None
        ]
        if not let_children:
            return
        # Строим подстановку: имя свежей var → residualized выражение
        let_sub = {c.contraction.var_name: self._transform(c) for c in let_children}
        entry_args = [let_sub.get(v.name, v) for v in root_params]
        entry_vars = self._get_vars(FCall("__entry_aux__", entry_args))
        if not entry_vars:
            return
        self.f_count += 1
        entry_name = f"f{self.f_count}"
        entry_pat = Pattern(entry_name, entry_vars)
        entry_body = FCall(root_name, entry_args)
        self.rules.insert(0, Rule(entry_pat, entry_body))

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

    def _original_types(self):
        if self.original_program is not None:
            return self.original_program.types
        return []

    def _fresh_type(self) -> TypeExpr:
        self._fresh_n += 1
        return TypeExpr(f"t{self._fresh_n}", [])

    def _build_ctx(self) -> TypeContext:
        ctx = TypeContext()
        prog = self.original_program
        for t in prog.types:
            ctx.defined_types[t.name] = t
            for c in t.constructors:
                ctx.constructors[c.name] = (t, c.arg_types)
        for s in prog.signatures:
            ctx.functions[s.name] = s
        return ctx

    def _bind_pattern(self, pat: Expr, t: TypeExpr, ctx: TypeContext, scope: dict):
        if isinstance(pat, Var):
            scope[pat.name] = t
            return
        name = getattr(pat, "name", None)
        if name and name in ctx.constructors and getattr(pat, "params", None) is not None:
            type_def, templates = ctx.constructors[name]
            mapping = {}
            if t.name == type_def.name and len(t.params) == len(type_def.params):
                mapping = dict(zip(type_def.params, t.params))
            for sub, tmpl in zip(pat.params, templates):
                self._bind_pattern(sub, resolve_type(tmpl, mapping), ctx, scope)

    def _arg_types(self, clauses, arity, ctx, node, params):
        out = []
        unknown = set()
        for pos in range(arity):
            t = None
            if node is not None and params is not None and pos < len(params):
                pv = params[pos]
                if isinstance(pv, Var):
                    t = node.var_types.get(pv.name)
            if t is None:
                for cl in clauses:
                    p = cl.pattern.params[pos]
                    cn = getattr(p, "name", None)
                    if cn and cn[:1].isupper() and cn in ctx.constructors:
                        type_def, _ = ctx.constructors[cn]
                        t = TypeExpr(type_def.name,
                                     [self._fresh_type() for _ in type_def.params])
                        break
            if t is None:
                t = self._fresh_type()
                unknown.add(pos)
            out.append(t)
        return out, unknown

    def _find_calls(self, expr, nm, acc):
        match expr:
            case FCall(name, args):
                if name == nm:
                    acc.append(args)
                for a in args:
                    self._find_calls(a, nm, acc)
            case Ctr(_, args):
                for a in args:
                    self._find_calls(a, nm, acc)
            case Let(bindings, body):
                for _, e in bindings:
                    self._find_calls(e, nm, acc)
                self._find_calls(body, nm, acc)

    def _refine_args_from_calls(self, nm, ctx, sigs, unknown):
        if not unknown:
            return False
        for cl in self.rules:
            if cl.pattern.name == nm:
                continue
            caller_sig = sigs.get(cl.pattern.name)
            if caller_sig is None:
                continue
            calls = []
            self._find_calls(cl.body, nm, calls)
            for args in calls:
                scope = {}
                try:
                    for p, at in zip(cl.pattern.params, caller_sig.arg_types):
                        self._bind_pattern(p, at, ctx, scope)
                except Exception:
                    continue
                changed = False
                for pos in list(unknown):
                    if pos >= len(args):
                        continue
                    try:
                        at = infer_type(args[pos], ctx, dict(scope))
                    except Exception:
                        continue
                    if at is not None and at.name in ctx.defined_types:
                        sigs[nm].arg_types[pos] = at
                        ctx.functions[nm].arg_types[pos] = at
                        unknown.discard(pos)
                        changed = True
                if changed:
                    return True
        return False

    def _infer_ret(self, name, node, ctx) -> Optional[TypeExpr]:
        if node is not None:
            try:
                return infer_type(node.expr, ctx, dict(node.var_types))
            except Exception:
                pass
        sig = ctx.functions.get(name)
        if sig is None:
            return None
        for cl in [r for r in self.rules if r.pattern.name == name]:
            scope = {}
            try:
                for p, at in zip(cl.pattern.params, sig.arg_types):
                    self._bind_pattern(p, at, ctx, scope)
                return infer_type(cl.body, ctx, scope)
            except Exception:
                continue
        return None

    def _infer_signatures(self) -> List[FunSig]:
        if self.original_program is None:
            return []

        ctx = self._build_ctx()

        name_node: Dict[str, Tuple[Node, List[Var]]] = {}
        for nd, (nm, params) in self.node_to_sig.items():
            name_node.setdefault(nm, (nd, params))
        if self._entry_name is not None and self._entry_name not in name_node \
                and self._entry_node is not None:
            entry_params = None
            for r in self.rules:
                if r.pattern.name == self._entry_name:
                    entry_params = r.pattern.params
                    break
            name_node[self._entry_name] = (self._entry_node, entry_params)

        order = []
        seen = set()
        for r in self.rules:
            if r.pattern.name not in seen:
                seen.add(r.pattern.name)
                order.append(r.pattern.name)

        sigs: Dict[str, FunSig] = {}
        unknowns: Dict[str, set] = {}
        for nm in order:
            clauses = [r for r in self.rules if r.pattern.name == nm]
            arity = len(clauses[0].pattern.params)
            node, params = name_node.get(nm, (None, None))
            arg_types, unknown = self._arg_types(clauses, arity, ctx, node, params)
            sigs[nm] = FunSig(nm, arg_types, self._fresh_type())
            ctx.functions[nm] = sigs[nm]
            unknowns[nm] = unknown

        for _ in range(len(order) + 2):
            changed = False
            for nm in order:
                if self._refine_args_from_calls(nm, ctx, sigs, unknowns[nm]):
                    changed = True
                node, _ = name_node.get(nm, (None, None))
                rt = self._infer_ret(nm, node, ctx)
                if rt is not None and str(rt) != str(sigs[nm].ret_type):
                    sigs[nm].ret_type = rt
                    ctx.functions[nm].ret_type = rt
                    changed = True
            if not changed:
                break

        return [sigs[nm] for nm in order]

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