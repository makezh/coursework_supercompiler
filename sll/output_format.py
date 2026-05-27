from dataclasses import dataclass, field
from typing import Optional, Set

from sll.ast_nodes import Expr, Var, Ctr, FCall, IntLit
from sll.matching import match, MatchSuccess
from sll.msg import msg


@dataclass
class OutputFormat:
    expr: Optional[Expr] = None
    output_vars: Set[str] = field(default_factory=set)
    frozen_params: Set[str] = field(default_factory=set)
    is_bottom: bool = False

    def __str__(self):
        if self.is_bottom:
            return "⊥"
        return _render(self.expr, self.frozen_params)


BOTTOM = OutputFormat(is_bottom=True)


def _render(expr: Expr, frozen: Set[str]) -> str:
    match expr:
        case Var(name) if name in frozen:
            return f"#{name}"
        case Var(name):
            return name
        case IntLit(v):
            return str(v)
        case Ctr(name, args):
            if not args:
                return f"[{name}]"
            return f"[{name} {' '.join(_render(a, frozen) for a in args)}]"
        case FCall(name, args):
            return f"({name} {' '.join(_render(a, frozen) for a in args)})"
        case _:
            return str(expr)


def _collect_vars(expr: Expr) -> Set[str]:
    seen: Set[str] = set()
    def walk(e):
        match e:
            case Var(n):
                seen.add(n)
            case Ctr(_, args) | FCall(_, args):
                for a in args:
                    walk(a)
    walk(expr)
    return seen


def _frozen_match(pattern: Expr, value: Expr, frozen: Set[str]) -> bool:
    match pattern:
        case Var(name) if name in frozen:
            return isinstance(value, Var) and value.name == name
        case Var(_):
            return True
        case IntLit(pv):
            return isinstance(value, IntLit) and value.value == pv
        case Ctr(pn, pa):
            if not isinstance(value, Ctr) or value.name != pn or len(pa) != len(value.args):
                return False
            return all(_frozen_match(p, v, frozen) for p, v in zip(pa, value.args))
        case FCall(pn, pa):
            if not isinstance(value, FCall) or value.name != pn or len(pa) != len(value.args):
                return False
            return all(_frozen_match(p, v, frozen) for p, v in zip(pa, value.args))
        case _:
            return False


def match_value(fmt: OutputFormat, value: Expr) -> bool:
    if fmt.is_bottom:
        return False
    if fmt.frozen_params:
        return _frozen_match(fmt.expr, value, fmt.frozen_params)
    return isinstance(match(fmt.expr, value), MatchSuccess)


def gen_format(fmt: OutputFormat, value: Expr,
               frozen_params: Optional[Set[str]] = None) -> OutputFormat:
    frozen = set(frozen_params) if frozen_params else set(fmt.frozen_params)
    if fmt.is_bottom:
        new_expr = value
    else:
        new_expr = msg(fmt.expr, value).gen
    all_vars = _collect_vars(new_expr)
    return OutputFormat(
        expr=new_expr,
        output_vars=all_vars - frozen,
        frozen_params=frozen & all_vars,
        is_bottom=False,
    )


def coarity(fmt: OutputFormat) -> int:
    return len(fmt.output_vars)


def arity_with_p(fmt: OutputFormat) -> int:
    return coarity(fmt) + len(fmt.frozen_params)
