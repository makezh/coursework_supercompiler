from sll.ast_nodes import Var, Ctr, FCall, Program, Rule, Pattern

##############################
# ПРИМЕР 1: (append [Cons x xs] ys)
var_x = Var("x")
var_xs = Var("xs")
var_ys = Var("ys")

cons_expr = Ctr("Cons", [var_x, var_xs])

program = FCall("append", [cons_expr, var_ys])

print(program)
print(repr(program))

print()
##############################
# ПРИМЕР 2:
# (add [Z] y) -> y
# (add [S x] y) -> [S (add x y)]
var_y = Var("y")

cons_Z = Ctr("Z", [])
cons_S_x = Ctr("S", [var_x])

pattern_1 = Pattern("add", [cons_Z, var_y])
pattern_2 = Pattern("add", [cons_S_x, var_y])

rule_1 = Rule(pattern_1, var_y)  # Правило: (add Z y) -> y
rule_2 = Rule(pattern_2, Ctr("S", [FCall("add", [var_x, var_y])]))  # Правило: (add Z(x) y) -> S(add x y)
program_1 = Program([rule_1, rule_2])

print(program_1)
print(repr(program_1))
