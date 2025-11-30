from sll.ast_nodes import (
    Var, Ctr, FCall, Program, Rule, Pattern,
    IntLit, TypeExpr, ConstrDef, TypeDef, FunSig
)

print("=== 1. Проверка чисел (IntLit) ===")
num = IntLit(42)
print(f"Число: {num}")
print(f"Repr:  {repr(num)}")

print("\n=== 2. Сборка Типов (TypeDef) вручную ===")
# type [Nat] : Z | S [Nat] .

nat_type_expr = TypeExpr("Nat", [])
def_Z = ConstrDef("Z", [])
def_S = ConstrDef("S", [nat_type_expr])
def_Nat = TypeDef(
    name="Nat",
    params=[],
    constructors=[def_Z, def_S]
)

print(f"Тип Nat собран: {def_Nat}")

print("\n=== 3. Сборка Сигнатуры (FunSig) вручную ===")
# fun (add [Nat] [Nat]) -> [Nat]

sig_add = FunSig(
    name="add",
    arg_types=[nat_type_expr, nat_type_expr],
    ret_type=nat_type_expr
)
print(f"Сигнатура add: {sig_add}")

print("\n=== 4. Сборка полной Программы ===")
var_x = Var("x")
var_y = Var("y")

# (add [Z] y) -> y
pat1 = Pattern("add", [Ctr("Z", []), var_y])
rule1 = Rule(pat1, var_y)

# (add [S x] y) -> [S (add x y)]
pat2 = Pattern("add", [Ctr("S", [var_x]), var_y])
body2 = Ctr("S", [FCall("add", [var_x, var_y])])
rule2 = Rule(pat2, body2)

prog = Program(
    rules=[rule1, rule2],
    types=[def_Nat],
    signatures=[sig_add]
)

print("Печать всей программы (str):")
print("-" * 20)
print(prog)
print("-" * 20)
