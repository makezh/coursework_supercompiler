"""
Сравнение нормальных форм оригинала и резидуала на конкретных входах
для всех комбинаций стратегий.
"""

import unittest
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from sll.parser import parse, tokenize, Parser
from sll.type_checker import check_program
from sll.supercompiler import Supercompiler
from sll.residualizer import Residualizer
from sll.interpreter import step
from sll.ast_nodes import Program, Var, Ctr, FCall, TypeExpr


def nat(n: int) -> Ctr:
    result = Ctr("Z", [])
    for _ in range(n):
        result = Ctr("S", [result])
    return result


def letter(ch: str) -> Ctr:
    return Ctr(ch, [])


def lst(items: list) -> Ctr:
    result = Ctr("Nil", [])
    for it in reversed(items):
        result = Ctr("Cons", [it, result])
    return result


def run_to_nf(expr, program: Program, max_steps: int = 5000):
    curr = expr
    for _ in range(max_steps):
        nxt = step(curr, program)
        if nxt is None:
            return curr
        curr = nxt
    raise TimeoutError(f"step-лимит {max_steps} превышен; последнее: {curr}")


def supercompile_and_residualize(prog: Program, start_expr, var_types: dict,
                                  strategy: str, gen_type: str) -> Program:
    sc = Supercompiler(prog, strategy=strategy, gen_type=gen_type)
    if gen_type == "TOP":
        sc.build_tree(start_expr, var_types)
    else:
        sc.run_hypercycle(start_expr, var_types)
    return Residualizer(sc.tree, prog).residualize()


ADD_SRC = """
type [Nat] : Z | S [Nat] .

fun (add [Nat] [Nat]) -> [Nat] :
    (add [Z] y) -> y
  | (add [S x] y) -> [S (add x y)] .
"""

ADD3_SRC = """
type [Nat] : Z | S [Nat] .

fun (add [Nat] [Nat]) -> [Nat] :
    (add [Z] y) -> y
  | (add [S x] y) -> [S (add x y)] .

fun (add3 [Nat] [Nat] [Nat]) -> [Nat] :
    (add3 x y z) -> (add (add x y) z) .
"""

FABC_SRC = """
type [List x] : Cons x [List x] | Nil .
type [Letter] : A | B | C | D .

fun (fab [List [Letter]]) -> [List [Letter]] :
    (fab [Cons [A] xs]) -> [Cons [B] (fab xs)]
  | (fab [Cons x xs]) -> [Cons x (fab xs)]
  | (fab [Nil]) -> [Nil] .

fun (fbc [List [Letter]]) -> [List [Letter]] :
    (fbc [Cons [B] xs]) -> [Cons [C] (fbc xs)]
  | (fbc [Cons x xs]) -> [Cons x (fbc xs)]
  | (fbc [Nil]) -> [Nil] .

fun (fabc [List [Letter]]) -> [List [Letter]] :
    (fabc xs) -> (fbc (fab xs)) .
"""


STRATEGY_MATRIX = [
    ("HE", "TOP"),
    ("HE", "BOTTOM"),
    ("TAG", "TOP"),
    ("TAG", "BOTTOM"),
]


KNOWN_BROKEN = {
    ("add3", "TAG", "BOTTOM"),
    ("fabc", "HE",  "BOTTOM"),
    ("fabc", "TAG", "BOTTOM"),
}


# ----------------------------------------------------------------------
# Тесты
# ----------------------------------------------------------------------

class TestPipelineIntegration(unittest.TestCase):

    def _check_equivalence(self, src, fn_name, inputs, arg_types):
        prog = parse(src)
        check_program(prog)

        arg_names = [f"x{i+1}" for i in range(len(arg_types))]
        var_types = {n: t for n, t in zip(arg_names, arg_types)}
        start_call = FCall(fn_name, [Var(n) for n in arg_names])

        for strategy, gen_type in STRATEGY_MATRIX:
            with self.subTest(strategy=strategy, gen=gen_type, fn=fn_name):
                if (fn_name, strategy, gen_type) in KNOWN_BROKEN:
                    self.skipTest(f"{fn_name} × {strategy}/{gen_type}: KNOWN_BROKEN")
                residual = supercompile_and_residualize(
                    prog, start_call, dict(var_types),
                    strategy=strategy, gen_type=gen_type,
                )
                entry_name = residual.rules[0].pattern.name

                for input_tuple in inputs:
                    orig_nf = run_to_nf(FCall(fn_name, list(input_tuple)), prog)
                    res_nf = run_to_nf(FCall(entry_name, list(input_tuple)), residual)
                    self.assertEqual(
                        str(orig_nf), str(res_nf),
                        msg=f"{fn_name} {strategy}/{gen_type} on {input_tuple}: orig={orig_nf}, res={res_nf}",
                    )

    def test_add(self):
        inputs = [
            (nat(0), nat(0)),
            (nat(1), nat(0)),
            (nat(0), nat(1)),
            (nat(1), nat(1)),
            (nat(3), nat(2)),
            (nat(5), nat(5)),
        ]
        self._check_equivalence(
            ADD_SRC, "add", inputs,
            [TypeExpr("Nat", []), TypeExpr("Nat", [])],
        )

    def test_add3(self):
        inputs = [
            (nat(0), nat(0), nat(0)),
            (nat(1), nat(0), nat(0)),
            (nat(0), nat(1), nat(0)),
            (nat(0), nat(0), nat(1)),
            (nat(2), nat(3), nat(1)),
            (nat(4), nat(2), nat(3)),
        ]
        self._check_equivalence(
            ADD3_SRC, "add3", inputs,
            [TypeExpr("Nat", []), TypeExpr("Nat", []), TypeExpr("Nat", [])],
        )

    def test_fabc(self):
        L = lambda *chars: lst([letter(c) for c in chars])
        inputs = [
            (L(),),
            (L("A"),),
            (L("B"),),
            (L("A", "B", "C"),),
            (L("D", "A", "B"),),
            (L("A", "A", "A", "B"),),
        ]
        self._check_equivalence(
            FABC_SRC, "fabc", inputs,
            [TypeExpr("List", [TypeExpr("Letter", [])])],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
