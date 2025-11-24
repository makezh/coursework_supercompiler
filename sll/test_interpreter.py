from ast_nodes import Var, Ctr, FCall, Pattern, Rule, Program
from interpreter import step

# 1. Строим язык
# (add [Z] y) -> y
# (add [S x] y) -> [S (add x y)]

var_x = Var("x")
var_y = Var("y")

# Правило 1: (add [Z] y) = y
p1 = Pattern("add", [Ctr("Z", []), var_y])
r1 = Rule(p1, var_y)

# Правило 2: (add [S x] y) = [S (add x y)]
p2 = Pattern("add", [Ctr("S", [var_x]), var_y])
body2 = Ctr("S", [FCall("add", [var_x, var_y])])
r2 = Rule(p2, body2)

prog = Program([r1, r2])

# 2. Выражение: (add [S [Z]] [S [Z]])

one = Ctr("S", [Ctr("Z", [])])
expr = FCall("add", [one, one])

print(f"Исходное выражение: {expr}")

# 3. Запускаем цикл
current_expr = expr
step_count = 0

while True:
    next_expr = step(current_expr, prog)
    if next_expr is None:
        break
    current_expr = next_expr
    step_count += 1
    print(f"Шаг {step_count}: {current_expr}")

print(f"Результат: {current_expr}")