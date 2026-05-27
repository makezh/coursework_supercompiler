import unittest
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from sll.parser import parse
from sll.type_checker import check_program
from sll.supercompiler import Supercompiler
from sll.residualizer import Residualizer
from sll.interpreter import step
from sll.ast_nodes import Var, FCall, Ctr, TypeExpr
from sll.output_format import OutputFormat
from sll.active_format import (
    should_activate, is_unfmt_constructor_expressible, build_rules,
)


SAMPLES = os.path.join(parent_dir, "samples")


def _load(name):
    with open(os.path.join(SAMPLES, name), "r", encoding="utf-8") as f:
        return f.read()


def _run(src, entry, gen_type, level="ACTIVE", strategy="HE"):
    prog = parse(src)
    check_program(prog)
    sig = next(s for s in prog.signatures if s.name == entry)
    arg_names = [f"x{i+1}" for i in range(len(sig.arg_types))]
    start = FCall(entry, [Var(n) for n in arg_names])
    var_types = {n: t for n, t in zip(arg_names, sig.arg_types)}
    sc = Supercompiler(prog, strategy=strategy, gen_type=gen_type,
                        format_level=level)
    if gen_type == "TOP":
        sc.build_tree(start, var_types)
    else:
        sc.run_hypercycle(start, var_types)
    return sc, prog


def _nat(n):
    r = Ctr("Z", [])
    for _ in range(n):
        r = Ctr("S", [r])
    return r


def _lst(*items):
    r = Ctr("Nil", [])
    for it in reversed(items):
        r = Ctr("Cons", [it, r])
    return r


def _nf(e, p, m=5000):
    for _ in range(m):
        n = step(e, p)
        if n is None:
            return e
        e = n
    return None


class TestActivationLogic(unittest.TestCase):
    def test_pure_constructor_pattern_expressible(self):
        fmt = OutputFormat(
            expr=Ctr("Cons", [Var("a"), Var("v1")]),
            output_vars={"v1"}, frozen_params={"a"},
        )
        self.assertTrue(is_unfmt_constructor_expressible(fmt))

    def test_fcall_in_format_not_expressible(self):
        fmt = OutputFormat(
            expr=Ctr("Cons", [FCall("square", [Var("y")]), Var("v1")]),
            output_vars={"v1"}, frozen_params={"y"},
        )
        self.assertFalse(is_unfmt_constructor_expressible(fmt))

    def test_no_frozen_params_no_activation(self):
        fmt = OutputFormat(
            expr=Ctr("S", [Var("v1")]),
            output_vars={"v1"}, frozen_params=set(),
        )
        self.assertFalse(should_activate(fmt, ancestor_decomposed=False))

    def test_ancestor_decomposed_no_activation(self):
        fmt = OutputFormat(
            expr=Ctr("Cons", [Var("a"), Var("v1")]),
            output_vars={"v1"}, frozen_params={"a"},
        )
        self.assertFalse(should_activate(fmt, ancestor_decomposed=True))
        self.assertTrue(should_activate(fmt, ancestor_decomposed=False))

    def test_build_rules_shape(self):
        fmt = OutputFormat(
            expr=Ctr("Cons", [Var("a"), Var("v1")]),
            output_vars={"v1"}, frozen_params={"a"},
        )
        d = build_rules(fmt, "fmt_X", "unfmt_X")
        self.assertEqual(d.fmt_name, "fmt_X")
        self.assertEqual(d.unfmt_name, "unfmt_X")
        self.assertEqual(d.output_vars, ["v1"])
        self.assertEqual(d.frozen_params, ["a"])
        self.assertEqual(str(d.fmt_rule), "(fmt_X v1 a) -> [Cons a v1]")
        self.assertEqual(str(d.unfmt_rule), "(unfmt_X [Cons a v1]) -> v1")


class TestActivationIntegration(unittest.TestCase):
    def test_simple_active_residual_semantics(self):
        sc, prog = _run(_load("active_simple.sll"), "main", "BOTTOM")
        decomposed = [b for b in sc.hypercycle_roots.values() if b.decomposed]
        self.assertTrue(decomposed, "Должна быть хотя бы одна decomposed-конфигурация")

        residual = Residualizer(sc.tree, prog).residualize()
        names = {r.pattern.name for r in residual.rules}
        self.assertIn("fmt_1", names)

        entry = residual.rules[0].pattern.name
        cases = [(_nat(1), _nat(2), _lst(), _lst()),
                  (_nat(0), _nat(1), _lst(_nat(3)), _lst(_nat(4), _nat(5))),
                  (_nat(2), _nat(3), _lst(_nat(4)), _lst())]
        for inp in cases:
            o = _nf(FCall("main", list(inp)), prog)
            r = _nf(FCall(entry, list(inp)), residual)
            self.assertEqual(str(o), str(r),
                              msg=f"active_simple {inp}: orig={o} res={r}")

    def test_no_trigger_for_format_without_frozen(self):
        sc, _ = _run(_load("active_no_trigger.sll"), "main", "BOTTOM")
        decomposed = [b for b in sc.hypercycle_roots.values() if b.decomposed]
        self.assertFalse(decomposed,
                          "Без #p ни одна конфигурация не должна активироваться")

    def test_anti_recurrence_only_outer_decomposed(self):
        sc, _ = _run(_load("active_simple.sll"), "main", "BOTTOM")
        decomposed = [b for b in sc.hypercycle_roots.values() if b.decomposed]
        self.assertEqual(len(decomposed), 1,
                          "Должен быть decomposed ровно один базис (анти-рекурсия)")

    def test_deforestation_drops_frozen_from_main_body(self):
        sc, prog = _run(_load("active_simple.sll"), "main", "BOTTOM")
        residual = Residualizer(sc.tree, prog).residualize()
        main_rule = next(r for r in residual.rules if r.pattern.name == "main")
        decomp = next(b.active_decomp for b in sc.hypercycle_roots.values()
                      if b.decomposed)
        fmt_call = main_rule.body
        self.assertIsInstance(fmt_call, FCall)
        self.assertEqual(fmt_call.name, decomp.fmt_name)
        inner = fmt_call.args[0]
        self.assertNotIsInstance(inner, FCall,
                                  msg="Дефорестация должна была убрать unfmt-обёртку, но inner = "
                                      f"{type(inner).__name__}: {inner}") if not isinstance(inner, FCall) else \
            self.assertNotEqual(inner.name, decomp.unfmt_name,
                                 msg=f"main.body должна вызывать дефорестованную функцию, а не {decomp.unfmt_name}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
