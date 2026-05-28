from dataclasses import dataclass, field
from typing import Optional, List, Dict
import subprocess
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sll.parser import parse, Parser, tokenize
from sll.type_checker import check_program
from sll.supercompiler import Supercompiler
from sll.residualizer import Residualizer
from sll.exporter import to_dot
from sll.ast_nodes import TypeExpr, Var, FCall, Expr, Ctr, FCall as _FCall


LEVELS = ("OFF", "SIMPLE", "PARAM", "ACTIVE")
STRATEGIES = ("HE", "TAG")
GENS = ("TOP", "BOTTOM")


@dataclass
class FormatRow:
    basis_expr: str
    format_str: str
    frozen_params: List[str] = field(default_factory=list)
    output_vars: List[str] = field(default_factory=list)
    decomposed: bool = False


@dataclass
class CompileResult:
    level: str
    strategy: str
    gen_type: str
    entry: str
    residual_sll: str = ""
    dot: str = ""
    svg: Optional[str] = None
    formats: List[FormatRow] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None


def render_svg(dot_text: str) -> Optional[str]:
    if not dot_text:
        return None
    try:
        p = subprocess.run(
            ["dot", "-Tsvg"],
            input=dot_text.encode("utf-8"),
            capture_output=True,
            timeout=20,
        )
        if p.returncode != 0:
            return None
        return p.stdout.decode("utf-8", errors="replace")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _parse_entry_call(src: str, entry: str):
    prog = parse(src)
    check_program(prog)
    sig = next((s for s in prog.signatures if s.name == entry), None)
    if sig is None:
        raise ValueError(f"Функция '{entry}' не найдена в сигнатурах.")
    arg_names = [f"x{i+1}" for i in range(len(sig.arg_types))]
    start = FCall(entry, [Var(n) for n in arg_names])
    var_types = {n: t for n, t in zip(arg_names, sig.arg_types)}
    return prog, start, var_types


def _collect_formats(sc: Supercompiler) -> List[FormatRow]:
    rows: List[FormatRow] = []
    if sc.hypercycle_roots:
        bases = list(sc.hypercycle_roots.values())
    else:
        bases = [sc.tree] if sc.tree is not None else []
    for b in bases:
        if b.output_format is None:
            continue
        rows.append(FormatRow(
            basis_expr=str(b.expr),
            format_str=str(b.output_format),
            frozen_params=sorted(b.output_format.frozen_params),
            output_vars=sorted(b.output_format.output_vars),
            decomposed=bool(b.decomposed),
        ))
    return rows


def _residual_stats(prog) -> Dict[str, int]:
    num_rules = len(prog.rules)
    fn_arities: Dict[str, int] = {}
    callers: Dict[str, set] = {}
    for r in prog.rules:
        name = r.pattern.name
        fn_arities[name] = max(fn_arities.get(name, 0), len(r.pattern.params))
        callers.setdefault(name, set()).update(_called_names(r.body))
    num_functions = len(fn_arities)
    max_arity = max(fn_arities.values()) if fn_arities else 0

    recursive = _recursive_functions(callers)
    rec_arity = max(
        (fn_arities[n] for n in recursive if n in fn_arities),
        default=0,
    )

    return {
        "num_functions": num_functions,
        "num_rules": num_rules,
        "max_arity": max_arity,
        "recursion_arity": rec_arity,
    }


def _called_names(body: Expr) -> set:
    out: set = set()
    def walk(e):
        match e:
            case _FCall(n, args):
                out.add(n)
                for a in args: walk(a)
            case Ctr(_, args):
                for a in args: walk(a)
    walk(body)
    return out


def _recursive_functions(callers: Dict[str, set]) -> set:
    reach: Dict[str, set] = {n: set(callers.get(n, ())) for n in callers}
    changed = True
    while changed:
        changed = False
        for n in reach:
            new = set(reach[n])
            for m in list(reach[n]):
                new.update(reach.get(m, ()))
            if new != reach[n]:
                reach[n] = new
                changed = True
    return {n for n in reach if n in reach[n]}


def compile_one(src: str, entry: str, strategy: str, gen_type: str,
                level: str, with_svg: bool = True) -> CompileResult:
    res = CompileResult(level=level, strategy=strategy,
                        gen_type=gen_type, entry=entry)
    try:
        prog, start, var_types = _parse_entry_call(src, entry)
        sc = Supercompiler(prog, strategy=strategy, gen_type=gen_type,
                            format_level=level)
        if gen_type == "TOP":
            sc.build_tree(start, var_types)
        else:
            sc.run_hypercycle(start, var_types)

        residual = Residualizer(sc.tree, prog).residualize()
        res.residual_sll = str(residual)
        res.dot = to_dot(sc.tree, dev_mode=False, start_expr=start)
        if with_svg:
            res.svg = render_svg(res.dot)
        res.formats = _collect_formats(sc)
        res.stats = _residual_stats(residual)
    except Exception as e:
        res.error = f"{type(e).__name__}: {e}"
    return res


def compile_all_levels(src: str, entry: str, strategy: str = "HE",
                        gen_type: str = "BOTTOM",
                        with_svg: bool = True) -> Dict[str, CompileResult]:
    return {
        lvl: compile_one(src, entry, strategy, gen_type, lvl, with_svg=with_svg)
        for lvl in LEVELS
    }


def auto_detect_entry(src: str) -> Optional[str]:
    try:
        prog = parse(src)
    except Exception:
        return None
    names = [s.name for s in prog.signatures]
    for preferred in ("main", "entry", "start"):
        if preferred in names:
            return preferred
    return names[-1] if names else None


def summarize_effect(results: Dict[str, CompileResult]) -> Dict[str, str]:
    off = results.get("OFF")
    active = results.get("ACTIVE")
    summary = {}
    if off and active and not off.error and not active.error:
        if off.stats.get("recursion_arity", 0) != active.stats.get("recursion_arity", 0):
            summary["arity_change"] = (
                f"Местность рекурсивной функции: "
                f"{off.stats['recursion_arity']} → {active.stats['recursion_arity']}"
            )
        if off.residual_sll != active.residual_sll:
            summary["residual_change"] = "Активная декомпозиция изменила остаточную программу."
        if active.formats and any(f.decomposed for f in active.formats):
            decomposed_n = sum(1 for f in active.formats if f.decomposed)
            summary["active_decomp"] = f"Активирована декомпозиция на {decomposed_n} конфигурациях."
    return summary
