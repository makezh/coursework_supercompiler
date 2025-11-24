from parser import tokenize

text = """
-- Это комментарий
(add [Z] y) -> y -- первое правило
(add [S x] y) -> [S (add x y)] -- второе правило
"""

print(tokenize(text))