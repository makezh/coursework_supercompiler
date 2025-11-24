from ast_nodes import Var, Ctr
from matching import match

# Подготовка деталек
var_x = Var("x")
var_xs = Var("xs")

# Паттерн: [Cons x xs]
pat = Ctr("Cons", [var_x, var_xs])

# --- Тест 1: Идеальное совпадение ---
# Вызов: [Cons [Z] [Nil]]
arg1 = Ctr("Cons", [Ctr("Z", []), Ctr("Nil", [])])

print("Тест 1:", match(pat, arg1))
# Ожидание: {'x': [Z], 'xs': [Nil]}


# --- Тест 2: Не совпало имя ---
# Вызов: [Nil]
arg2 = Ctr("Nil", [])

print("Тест 2:", match(pat, arg2))
# Ожидание: None (потому что ждали Cons, а пришел Nil)


# --- Тест 3: Вложенность ---
# Паттерн: [S x]
pat_num = Ctr("S", [var_x])

# Вызов: [S [S [Z]]] (число 2)
arg3 = Ctr("S", [Ctr("S", [Ctr("Z", [])])])

print("Тест 3:", match(pat_num, arg3))
# Ожидание: {'x': [S [Z]]} - обрати внимание, x захватил всё, что внутри