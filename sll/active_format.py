from dataclasses import dataclass, field
from typing import List, Optional

from sll.ast_nodes import Expr, Var, Ctr, FCall, IntLit, Pattern, Rule, Let
from sll.output_format import OutputFormat


@dataclass
class Decomposition:
    fmt_name: str
    unfmt_name: str
    fmt_rule: Rule
    unfmt_rule: Rule
    output_vars: List[str]
    frozen_params: List[str]


def is_unfmt_constructor_expressible(fmt: OutputFormat) -> bool:
    if fmt.is_bottom or fmt.expr is None:
        return False

    def pure(e: Expr) -> bool:
        match e:
            case Var(_):
                return True
            case Ctr(_, args):
                return all(pure(a) for a in args)
            case _:
                return False

    return pure(fmt.expr)


def should_activate(basis_fmt: OutputFormat, ancestor_decomposed: bool) -> bool:
    if basis_fmt is None or basis_fmt.is_bottom:
        return False
    if not basis_fmt.frozen_params:
        return False
    if ancestor_decomposed:
        return False
    return is_unfmt_constructor_expressible(basis_fmt)


def build_rules(fmt: OutputFormat, fmt_name: str, unfmt_name: str) -> Decomposition:
    output_vars = sorted(fmt.output_vars)
    frozen_params = sorted(fmt.frozen_params)

    fmt_params = [Var(v) for v in output_vars] + [Var(p) for p in frozen_params]
    fmt_rule = Rule(
        pattern=Pattern(fmt_name, fmt_params),
        body=fmt.expr,
    )

    unfmt_rule = Rule(
        pattern=Pattern(unfmt_name, [_expr_to_pattern_atom(fmt.expr)]),
        body=_unfmt_body(output_vars),
    )

    return Decomposition(
        fmt_name=fmt_name,
        unfmt_name=unfmt_name,
        fmt_rule=fmt_rule,
        unfmt_rule=unfmt_rule,
        output_vars=output_vars,
        frozen_params=frozen_params,
    )


def _expr_to_pattern_atom(e: Expr) -> Expr:
    match e:
        case Var(name):
            return Var(name)
        case Ctr(name, args):
            return Ctr(name, [_expr_to_pattern_atom(a) for a in args])
        case _:
            return e


def _unfmt_body(output_vars: List[str]) -> Expr:
    if not output_vars:
        return Ctr("Unit", [])
    if len(output_vars) == 1:
        return Var(output_vars[0])
    return Ctr("Tuple" + str(len(output_vars)),
               [Var(v) for v in output_vars])


def build_decomposed_call(decomp: Decomposition,
                           original_call: Expr) -> Expr:
    return FCall(
        decomp.fmt_name,
        [FCall(decomp.unfmt_name, [original_call])]
        + [Var(p) for p in decomp.frozen_params],
    )
