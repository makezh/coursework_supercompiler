from parser import tokenize, parse, Parser
from interpreter import step

### Тест 1: Токенизатор
text = """
-- Это комментарий
(add [Z] y) -> y -- первое правило
(add [S x] y) -> [S (add x y)] -- второе правило
"""

print("--- Токенизация ---")
print(tokenize(text))
print()

### Тест 2: Парсер
code = """
fun add x y :
    (add [Z] y) -> y
  | (add [S x] y) -> [S (add x y)].
"""

print("--- Парсинг ---")
program = parse(code)
print(program)


expr_text = "(add [S [Z]] [S [Z]])"
p = Parser(tokenize(expr_text))
expr = p.parse_expr()

print(f"\n--- Вычисление: {expr} ---")

curr = expr
for i in range(10):
    next_expr = step(curr, program)
    if next_expr is None:
        break
    print(f"Step {i+1}: {next_expr}")
    curr = next_expr

print(f"Результат: {curr}")