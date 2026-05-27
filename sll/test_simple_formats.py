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
from sll.ast_nodes import TypeExpr, Var, FCall
from sll.output_format import match_value


SAMPLES = os.path.join(parent_dir, "samples")


def _load(name):
    with open(os.path.join(SAMPLES, name), "r", encoding="utf-8") as f:
        return f.read()


def _run(src, entry, gen_type, strategy="HE"):
    prog = parse(src)
    check_program(prog)
    sig = next(s for s in prog.signatures if s.name == entry)
    arg_names = [f"x{i+1}" for i in range(len(sig.arg_types))]
    start = FCall(entry, [Var(n) for n in arg_names])
    var_types = {n: t for n, t in zip(arg_names, sig.arg_types)}
    sc = Supercompiler(prog, strategy=strategy, gen_type=gen_type,
                        format_level="SIMPLE")
    if gen_type == "TOP":
        sc.build_tree(start, var_types)
    else:
        sc.run_hypercycle(start, var_types)
    return sc


def _basis_format(sc):
    if sc.hypercycle_roots:
        for root in sc.hypercycle_roots.values():
            if root.output_format is not None:
                return root.output_format
    return sc.tree.output_format


class TestSimpleFormats(unittest.TestCase):
    def test_const(self):
        from sll.ast_nodes import Ctr
        sc = _run(_load("format_const.sll"), "constSZ", "TOP")
        fmt = _basis_format(sc)
        self.assertEqual(str(fmt), "[S [Z]]")
        self.assertTrue(match_value(fmt, Ctr("S", [Ctr("Z", [])])))
        self.assertFalse(match_value(fmt, Ctr("Z", [])))

    def test_sum_canonical(self):
        from sll.ast_nodes import Ctr
        sc = _run(_load("format_sum.sll"), "main", "BOTTOM")
        fmt = _basis_format(sc)
        zero = Ctr("Z", [])
        s = lambda e: Ctr("S", [e])
        self.assertTrue(match_value(fmt, s(s(zero))))
        self.assertTrue(match_value(fmt, s(s(s(zero)))))
        self.assertTrue(match_value(fmt, s(s(s(s(zero))))))
        self.assertFalse(match_value(fmt, zero))
        self.assertFalse(match_value(fmt, s(zero)))

    def test_proj_trivial(self):
        from sll.ast_nodes import Ctr, Var
        sc = _run(_load("format_proj.sll"), "idnat", "TOP")
        fmt = _basis_format(sc)
        self.assertTrue(isinstance(fmt.expr, Var))
        self.assertTrue(match_value(fmt, Ctr("Z", [])))
        self.assertTrue(match_value(fmt, Ctr("S", [Ctr("Z", [])])))

    def test_branchy_lifts_to_S_var(self):
        from sll.ast_nodes import Ctr
        sc = _run(_load("format_branchy.sll"), "pick", "TOP")
        fmt = _basis_format(sc)
        z = Ctr("Z", [])
        s = lambda e: Ctr("S", [e])
        self.assertTrue(match_value(fmt, s(z)))
        self.assertTrue(match_value(fmt, s(s(z))))
        self.assertFalse(match_value(fmt, z))


if __name__ == "__main__":
    unittest.main(verbosity=2)
