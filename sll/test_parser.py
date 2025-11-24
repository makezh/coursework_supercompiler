from parser import tokenize, parse

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