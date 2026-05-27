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


SAMPLES = os.path.join(parent_dir, "samples")


def _load(name):
    with open(os.path.join(SAMPLES, name), "r", encoding="utf-8") as f:
        return f.read()


def _run(src, entry, gen_type, strategy="HE", level="PARAM"):
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
    return sc


def _start_basis(sc):
    if sc.hypercycle_roots:
        first = sc.tree.children[0] if sc.tree.children else None
        return first
    return sc.tree


def _all_formats(sc):
    if sc.hypercycle_roots:
        return [r.output_format for r in sc.hypercycle_roots.values()
                if r.output_format is not None]
    return [sc.tree.output_format] if sc.tree.output_format else []


class TestParamFormats(unittest.TestCase):
    def test_proj_param_frozen(self):
        sc = _run(_load("format_proj_param.sll"), "wrapS", "TOP")
        fmt = _start_basis(sc).output_format
        self.assertEqual(str(fmt), "[S #x1]")
        self.assertIn("x1", fmt.frozen_params)

    def test_drop_param_constant(self):
        sc = _run(_load("format_drop_param.sll"), "constY", "TOP")
        fmt = _start_basis(sc).output_format
        self.assertEqual(str(fmt), "[S [Z]]")
        self.assertEqual(fmt.frozen_params, set())
        self.assertEqual(fmt.output_vars, set())

    def test_append_canonical(self):
        sc = _run(_load("format_append.sll"), "main", "BOTTOM")
        formats = [str(f) for f in _all_formats(sc)]
        self.assertIn("[Cons #x1 [Cons #x2 v1]]", formats)
        self.assertIn("[Cons #x2 v1]", formats)

    def test_simple_unchanged_under_param(self):
        sc_s = _run(_load("format_sum.sll"), "main", "BOTTOM", level="SIMPLE")
        sc_p = _run(_load("format_sum.sll"), "main", "BOTTOM", level="PARAM")
        s = [str(f) for f in _all_formats(sc_s)]
        p = [str(f) for f in _all_formats(sc_p)]
        self.assertEqual(s, p)

    def test_append_residual_semantics(self):
        def nat(n):
            r = Ctr("Z", [])
            for _ in range(n):
                r = Ctr("S", [r])
            return r

        def lst(*items):
            r = Ctr("Nil", [])
            for it in reversed(items):
                r = Ctr("Cons", [it, r])
            return r

        def nf(e, p, m=5000):
            for _ in range(m):
                n = step(e, p)
                if n is None:
                    return e
                e = n
            return None

        src = _load("format_append.sll")
        prog = parse(src)
        check_program(prog)
        sc = Supercompiler(prog, strategy="HE", gen_type="BOTTOM",
                            format_level="PARAM")
        sc.run_hypercycle(
            FCall("main", [Var("x1"), Var("x2"), Var("x3"), Var("x4")]),
            {"x1": TypeExpr("Nat", []),
             "x2": TypeExpr("Nat", []),
             "x3": TypeExpr("List", [TypeExpr("Nat", [])]),
             "x4": TypeExpr("List", [TypeExpr("Nat", [])])},
        )
        residual = Residualizer(sc.tree, prog).residualize()
        entry = residual.rules[0].pattern.name

        cases = [
            (nat(1), nat(2), lst(), lst()),
            (nat(0), nat(1), lst(nat(3)), lst(nat(4), nat(5))),
            (nat(2), nat(3), lst(nat(4), nat(5)), lst()),
        ]
        for inp in cases:
            orig = nf(FCall("main", list(inp)), prog)
            res = nf(FCall(entry, list(inp)), residual)
            self.assertEqual(str(orig), str(res),
                              msg=f"append на {inp}: orig={orig} res={res}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
