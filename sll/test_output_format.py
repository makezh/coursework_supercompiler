import unittest
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from sll.ast_nodes import Var, Ctr
from sll.output_format import (
    OutputFormat, BOTTOM, match_value, gen_format, coarity, arity_with_p,
)


def nat(n):
    r = Ctr("Z", [])
    for _ in range(n):
        r = Ctr("S", [r])
    return r


def ssx():
    return Ctr("S", [Ctr("S", [Var("x")])])


class TestMatchValue(unittest.TestCase):
    def test_bottom_matches_nothing(self):
        self.assertFalse(match_value(BOTTOM, Var("x")))
        self.assertFalse(match_value(BOTTOM, nat(0)))

    def test_const_matches_itself(self):
        fmt = OutputFormat(expr=nat(2))
        self.assertTrue(match_value(fmt, nat(2)))
        self.assertFalse(match_value(fmt, nat(1)))
        self.assertFalse(match_value(fmt, nat(3)))

    def test_template_matches_instances(self):
        fmt = OutputFormat(expr=ssx(), output_vars={"x"})
        self.assertTrue(match_value(fmt, nat(2)))
        self.assertTrue(match_value(fmt, nat(3)))
        self.assertFalse(match_value(fmt, nat(0)))
        self.assertFalse(match_value(fmt, nat(1)))

    def test_trivial_matches_everything(self):
        fmt = OutputFormat(expr=Var("x"), output_vars={"x"})
        self.assertTrue(match_value(fmt, nat(0)))
        self.assertTrue(match_value(fmt, nat(5)))


class TestGenFormat(unittest.TestCase):
    def test_gen_from_bottom_takes_value(self):
        new_fmt = gen_format(BOTTOM, nat(2))
        self.assertEqual(str(new_fmt.expr), "[S [S [Z]]]")
        self.assertFalse(new_fmt.is_bottom)

    def test_gen_widens_to_template(self):
        fmt = OutputFormat(expr=nat(2))
        new_fmt = gen_format(fmt, nat(3))
        self.assertTrue(match_value(new_fmt, nat(2)))
        self.assertTrue(match_value(new_fmt, nat(3)))

    def test_gen_idempotent(self):
        fmt = OutputFormat(expr=ssx(), output_vars={"x"})
        new_fmt = gen_format(fmt, nat(2))
        self.assertTrue(match_value(new_fmt, nat(2)))
        self.assertTrue(match_value(new_fmt, nat(3)))
        self.assertFalse(match_value(new_fmt, nat(0)))

    def test_gen_monotonic(self):
        f0 = BOTTOM
        f1 = gen_format(f0, nat(2))
        f2 = gen_format(f1, nat(1))
        self.assertTrue(match_value(f2, nat(2)))
        self.assertTrue(match_value(f2, nat(1)))

    def test_frozen_param_marked(self):
        v = Ctr("Cons", [Var("ys"), Var("x")])
        new_fmt = gen_format(BOTTOM, v, frozen_params={"ys"})
        self.assertIn("ys", new_fmt.frozen_params)
        self.assertIn("x", new_fmt.output_vars)
        self.assertEqual(str(new_fmt), "[Cons #ys x]")


class TestArity(unittest.TestCase):
    def test_const_format_zero_arity(self):
        fmt = OutputFormat(expr=nat(2))
        self.assertEqual(coarity(fmt), 0)
        self.assertEqual(arity_with_p(fmt), 0)

    def test_trivial_format_one_arity(self):
        fmt = OutputFormat(expr=Var("x"), output_vars={"x"})
        self.assertEqual(coarity(fmt), 1)
        self.assertEqual(arity_with_p(fmt), 1)

    def test_param_format_counts_both(self):
        fmt = OutputFormat(
            expr=Ctr("Cons", [Var("ys"), Var("x")]),
            output_vars={"x"},
            frozen_params={"ys"},
        )
        self.assertEqual(coarity(fmt), 1)
        self.assertEqual(arity_with_p(fmt), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
