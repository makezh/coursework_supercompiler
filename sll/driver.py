from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

from sll.ast_nodes import Expr, Var, Ctr, FCall, Program, Pattern, IntLit, TypeExpr, Let
from sll.matching import match as match_term, substitute, \
    MatchSuccess, MatchNarrowing, MatchFail
from sll.process_tree import Contraction


def _instantiate_type(type_expr: TypeExpr, subst: dict) -> TypeExpr:
    """Подставляет конкретные типы вместо типовых параметров.
    Например, TypeExpr("x",[]) при subst={"x": TypeExpr("Letter",[])} → TypeExpr("Letter",[])
    """
    if not type_expr.params:
        return subst.get(type_expr.name, type_expr)
    new_params = [_instantiate_type(p, subst) for p in type_expr.params]
    return TypeExpr(type_expr.name, new_params, lineno=type_expr.lineno)


# --- Генератор имен ---
class NameGen:
    def __init__(self):
        self.counter = 0

    def fresh_var(self, prefix="v") -> str:
        self.counter += 1
        return f"{prefix}{self.counter}"


# --- Результаты шага драйвинга ---
# TransientStep (Транзитный шаг) — шаг вычисления, при котором вызов функции
# однозначно заменяется на её тело без ветвления.

# DecomposeStep (Декомпозиция) — шаг разбиения пассивного конструктора (например, [Cons x xs])
# на составные части-аргументы для их независимой обработки.

# VariantStep (Ветвление) — шаг разбора случаев, при котором выполнение расщепляется
# на несколько веток в зависимости от всех конструкторов типа этой переменной

# StopStep (Остановка) — терминальный шаг, означающий, что выражение (свободная переменная или литерал)
# не может быть вычислено или преобразовано дальше.

@dataclass
class DriveStep: pass


@dataclass
class LetStep(DriveStep):
    bindings: List[Tuple[str, Expr]]
    body: Expr


@dataclass
class TransientStep(DriveStep):
    next_expr: Expr
    rule_pat: Optional[Pattern] = None


@dataclass
class DecomposeStep(DriveStep):
    parts: List[Expr]


@dataclass
class VariantStep(DriveStep):
    # Возвращаем не только выражение ветки, но и новые типы для нее
    branches: List[Tuple[Expr, Contraction, Dict[str, TypeExpr], Optional[Pattern]]]


@dataclass
class StopStep(DriveStep):
    pass


# --- Драйвер ---

class Driver:
    def __init__(self, program: Program):
        self.program = program
        self.name_gen = NameGen()

        # Словарь: Имя типа -> Определение (TypeDef)
        # Пример: 'List' -> TypeDef(name='List', constructors=[...])
        self.type_map = {t.name: t for t in program.types}

    def drive(self, expr: Expr, var_types: Dict[str, TypeExpr]) -> DriveStep:
        """
        Главная функция.
        Принимает выражение И известные типы переменных (var_types).
        """
        match expr:
            # 0. Let узлы
            case Let(bindings, body):
                print("[DRIVE] LET matched")
                parts = [val for (_, val) in bindings] + [body]
                return DecomposeStep(parts=parts)

            # 1. Конструктор (Пассивные данные)
            case Ctr(_, args):
                return DecomposeStep(parts=args)

            # 2. Переменная или Число (Лист)
            case Var(_) | IntLit(_):
                return StopStep()

            # 3. Вызов функции
            case FCall(_, _):
                # Здесь будет основная логика (Transient / Variant / Nested)
                return self._drive_call(expr, var_types)

            case _:
                return StopStep()

    def _apply_sub_fully(self, expr: Expr, sub: Dict[str, Expr]) -> Expr:
        """Применяет подстановку транзитивно (до стабилизации)."""
        result = expr
        for _ in range(200):
            new_result = substitute(result, sub)
            if new_result == result:
                return result
            result = new_result
        return result

    def _get_call_vars(self, expr: FCall) -> List[Var]:
        """Возвращает переменные из аргументов вызова (в порядке первого вхождения)."""
        result = []
        seen = set()

        def collect(e):
            match e:
                case Var(name):
                    if name not in seen:
                        seen.add(name)
                        result.append(e)
                case Ctr(_, args) | FCall(_, args):
                    for a in args:
                        collect(a)
        for arg in expr.args:
            collect(arg)
        return result

    def _compute_full_rule_narrowing(
        self, rule, expr: FCall, var_types: Dict[str, TypeExpr]
    ) -> Optional[Tuple[Dict[str, Expr], Dict[str, Expr], Dict[str, TypeExpr]]]:
        """
        Вычисляет полную подстановку, нужную для применения правила к expr.
        Возвращает (running_sub, rule_bindings, new_var_types) или None при MatchFail.
        - running_sub:    все сужения переменных (включая промежуточные)
        - rule_bindings:  переменные паттерна правила → значения (для тела правила)
        - new_var_types:  типы свежих переменных
        """
        pat_args = rule.pattern.params
        if len(pat_args) != len(expr.args):
            return None

        running_sub: Dict[str, Expr] = {}
        rule_bindings: Dict[str, Expr] = {}
        new_var_types = dict(var_types)

        # Worklist: (pat_arg, orig_call_arg)
        # Храним оригинальные выражения; running_sub применяем при каждом извлечении.
        work = list(zip(pat_args, list(expr.args)))

        max_iters = 500
        iters = 0
        while work:
            iters += 1
            if iters > max_iters:
                return None

            pat, e_orig = work.pop(0)
            e_subst = self._apply_sub_fully(e_orig, running_sub)

            res = match_term(pat, e_subst)

            if isinstance(res, MatchFail):
                return None
            elif isinstance(res, MatchSuccess):
                rule_bindings.update(res.bindings)
            elif isinstance(res, MatchNarrowing):
                var_name = res.var_name
                constr_name = res.constr_name

                if var_name not in new_var_types:
                    return None

                var_type_expr = new_var_types[var_name]
                type_name = var_type_expr.name
                if type_name not in self.type_map:
                    return None

                type_def = self.type_map[type_name]
                constr_def = next((c for c in type_def.constructors if c.name == constr_name), None)
                if not constr_def:
                    return None

                type_param_subst = {
                    param: arg
                    for param, arg in zip(type_def.params, var_type_expr.params)
                }

                fresh_vars = []
                for arg_type in constr_def.arg_types:
                    v = Var(self.name_gen.fresh_var())
                    fresh_vars.append(v)
                    new_var_types[v.name] = _instantiate_type(arg_type, type_param_subst)

                running_sub[var_name] = Ctr(constr_name, fresh_vars)
                # Повторяем для той же пары с обновлённым running_sub
                work.insert(0, (pat, e_orig))

        return running_sub, rule_bindings, new_var_types

    def _is_default_redundant(self, branches, var_types: Dict[str, TypeExpr]) -> bool:
        """
        Возвращает True, если catch-all ветка недостижима:
        специфические ветки уже покрывают ВСЕ конструкторы единственной
        дискриминируемой переменной.
        Работает только для случая, когда во всех ветках сужается ровно одна
        и та же переменная (остальные остаются как есть).
        """
        if not branches:
            return False

        really_narrowed_sets = []
        for _, contraction, _, _ in branches:
            narrowings = contraction.narrowings or {}
            really_narrowed = frozenset(
                v for v, e in narrowings.items()
                if not (isinstance(e, Var) and e.name == v)
            )
            really_narrowed_sets.append(really_narrowed)

        # Пересечение: переменная, которая сужается в КАЖДОЙ ветке
        common = really_narrowed_sets[0]
        for s in really_narrowed_sets[1:]:
            common = common & s

        # Только если ровно одна общая переменная
        if len(common) != 1:
            return False

        disc_var = next(iter(common))
        if disc_var not in var_types:
            return False

        type_name = var_types[disc_var].name
        if type_name not in self.type_map:
            return False

        all_ctrs = {c.name for c in self.type_map[type_name].constructors}

        # Какие конструкторы disc_var покрыты на верхнем уровне
        covered = set()
        for _, contraction, _, _ in branches:
            narrowings = contraction.narrowings or {}
            e = narrowings.get(disc_var)
            if isinstance(e, Ctr):
                covered.add(e.name)

        return covered >= all_ctrs

    def _drive_call(self, expr: FCall, var_types: Dict[str, TypeExpr]) -> DriveStep:
        """
        Rule-Based Driving для вызова функции.
        Использует полное сужение (full narrowing) по каждому правилу:
        одна ветка = одно правило = все нужные сужения сразу.
        """
        rules = [r for r in self.program.rules if r.pattern.name == expr.name]

        # Если аргумент — FCall в позиции, где правило ожидает конструктор — nested driving.
        for rule in rules:
            for i, p in enumerate(rule.pattern.params):
                if not isinstance(p, Var) and i < len(expr.args) and isinstance(expr.args[i], FCall):
                    return self._drive_nested(expr, var_types)

        branches = []
        seen_keys: List[str] = []   # дедупликация веток

        for rule in rules:
            result = self._compute_full_rule_narrowing(rule, expr, var_types)

            if result is None:
                continue  # MatchFail — правило неприменимо

            running_sub, rule_bindings, new_var_types = result

            # Финальная подстановка для оригинальных переменных вызова
            orig_vars = self._get_call_vars(expr)
            final_narrowing: Dict[str, Expr] = {}
            for v in orig_vars:
                final_narrowing[v.name] = self._apply_sub_fully(Var(v.name), running_sub)

            body = substitute(rule.body, rule_bindings)

            has_real_narrowing = any(
                not isinstance(final_narrowing[v.name], Var) or final_narrowing[v.name].name != v.name
                for v in orig_vars
            )

            if not has_real_narrowing:
                # Пустое сужение = catch-all правило совпало напрямую
                if not branches:
                    return TransientStep(next_expr=body, rule_pat=rule.pattern)
                else:
                    # Catch-all после специфических веток → default branch,
                    # но только если специфические ветки НЕ покрывают все конструкторы.
                    if not self._is_default_redundant(branches, var_types):
                        contraction = Contraction(var_name="", pattern=None, is_default=True)
                        branches.append((body, contraction, var_types.copy(), rule.pattern))
                    return VariantStep(branches=branches)
            else:
                # Специфическая ветка с сужением
                key = str(sorted(
                    (k, str(v)) for k, v in final_narrowing.items()
                    if not (isinstance(v, Var) and v.name == k)
                ))
                if key in seen_keys:
                    continue
                seen_keys.append(key)

                contraction = Contraction(var_name="", pattern=None, narrowings=final_narrowing)
                branches.append((body, contraction, new_var_types, rule.pattern))

        if branches:
            return VariantStep(branches=branches)

        return self._drive_nested(expr, var_types)

    def _create_branch(self, expr: FCall, var_name: str, constr_name: str, var_types: Dict[str, TypeExpr]) -> Optional[
        Tuple[Expr, Contraction, Dict[str, TypeExpr], Optional[Pattern]]]:
        """
        Создает одну ветку для VariantStep.
        заменяет переменную var_name в expr на конструктор constr_name с новыми переменными.
        """

        # Находим тип переменной
        if var_name not in var_types:
            return None  # Переменная не имеет типа

        type_name = var_types[var_name].name
        if type_name not in self.type_map:
            return None  # Неизвестный тип

        type_def = self.type_map[type_name]

        # Находим конструктор в типе
        constr_def = next((c for c in type_def.constructors if c.name == constr_name), None)
        if not constr_def:
            return None  # Неизвестный конструктор

        # Строим подстановку типовых параметров, например {"x": TypeExpr("Letter",[])}
        var_type_expr = var_types[var_name]
        type_param_subst = {
            param: arg
            for param, arg in zip(type_def.params, var_type_expr.params)
        }

        # Создаем новые переменные для аргументов конструктора
        fresh_vars = []
        new_branch_types = var_types.copy()

        for arg_type in constr_def.arg_types:
            v = Var(self.name_gen.fresh_var())
            fresh_vars.append(v)
            new_branch_types[v.name] = _instantiate_type(arg_type, type_param_subst)

        # Создаем новый конструктор с этими переменными
        fresh_ctr = Ctr(constr_name, fresh_vars)
        bindings = {var_name: fresh_ctr}

        # Делаем подстановку в исходное выражение
        new_expr = substitute(expr, bindings)

        final_expr = new_expr

        contraction = Contraction(var_name, Pattern(constr_name, fresh_vars))
        return final_expr, contraction, new_branch_types, None


    def _drive_nested(self, expr: FCall, var_types: Dict[str, TypeExpr]) -> DriveStep:
        for i, arg in enumerate(expr.args):
            if isinstance(arg, FCall):
                inner_step = self.drive(arg, var_types)

                match inner_step:
                    case TransientStep(next_expr=nested_next):
                        new_args = list(expr.args)
                        new_args[i] = nested_next
                        return TransientStep(FCall(expr.name, new_args, lineno=expr.lineno, tag=expr.tag))

                    case VariantStep(branches):
                        new_branches = []
                        for branch_expr, contraction, branch_var_types, applied_pat in branches:

                            if contraction.narrowings is not None:
                                # Полное сужение: применяем все сужения к внешнему выражению
                                global_branch_expr = substitute(expr, contraction.narrowings)
                            elif contraction.is_default:
                                # Catch-all: заменяем внутренний FCall его результатом
                                new_args = list(expr.args)
                                new_args[i] = branch_expr
                                global_branch_expr = FCall(expr.name, new_args,
                                                           lineno=expr.lineno, tag=expr.tag)
                            else:
                                # Одиночное сужение (обратная совместимость)
                                v_name = contraction.var_name
                                pat = contraction.pattern
                                constr_expr = Ctr(pat.name, pat.params)
                                global_branch_expr = substitute(expr, {v_name: constr_expr})

                            new_branches.append((global_branch_expr, contraction, branch_var_types, applied_pat))

                        return VariantStep(branches=new_branches)
        return StopStep()
