import sys
import os

# Хак для импортов (чтобы запускать файл напрямую)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from sll.parser import tokenize, parse, Parser
from sll.ast_nodes import IntLit
from sll.interpreter import step

print("=== ЗАПУСК ТЕСТОВ ПАРСЕРА (v2: line numbers & new comments) ===\n")

# ==========================================
# ТЕСТ 1: Токенизатор
# ==========================================
text = """
<< Это комментарий первой строки >>
(add 42 y) -> y     << тут число и переменная >>
type [List a] : Nil << тут ключевые слова >>
"""

print("--- 1. Токенизация ---")
tokens = tokenize(text)

print(text)
for t in tokens:
    print(t)

# Проверки:
# 1. Комментарии должны исчезнуть
assert "Это комментарий" not in [t[1] for t in tokens]
# 2. Число 42 должно быть типа INT
token_42 = next(t for t in tokens if t[1] == 42)
assert token_42[0] == 'INT'
assert token_42[2] > 1 # Оно не на первой строке
print("✅ Токенизация: ОК")


# ==========================================
# ТЕСТ 2: Полный парсинг и Номера строк
# ==========================================
code = """
type [Nat] : Z | S [Nat] .

fun (add [Nat] [Nat]) -> [Nat] :
    (add [Z] y) -> y
  | (add [S x] y) -> [S (add x y)].
"""

print("\n--- 2. Парсинг программы ---")
print(code)
program = parse(code)
print("Программа успешно считана!")
print(f"Количество типов: {len(program.types)}") # 1 (Nat)
print(f"Количество сигнатур: {len(program.signatures)}") # 1 (add)
print(f"Количество правил: {len(program.rules)}") # 2

# ПРОВЕРКА НОМЕРОВ СТРОК (Требование научника)
nat_type = program.types[0]
print(f"Тип Nat определен на строке: {nat_type.lineno}")
assert nat_type.lineno == 2 # "type [Nat]..." вторая строка (первая пустая)

add_sig = program.signatures[0]
print(f"Сигнатура add на строке: {add_sig.lineno}")
assert add_sig.lineno == 4

rule_1 = program.rules[0]
print(f"Первое правило на строке: {rule_1.lineno}")
assert rule_1.lineno == 5

print("✅ AST содержит корректные номера строк!")


# ==========================================
# ТЕСТ 3: Вычисление (Интеграция с интерпретатором)
# ==========================================
expr_text = "(add [S [Z]] [S [Z]])"
p = Parser(tokenize(expr_text))
expr = p.parse_expr()

print(f"\n--- 3. Вычисление: {expr} ---")

curr = expr
for i in range(10):
    next_expr = step(curr, program)
    if next_expr is None:
        break
    print(f"Step {i+1}: {next_expr}")
    curr = next_expr

# Ожидаем [S [S [Z]]]
result_str = str(curr)
print(f"Результат: {result_str}")
assert "[S [S [Z]]]" in result_str
print("✅ Интерпретатор работает!")


# ==========================================
# ТЕСТ 4: Проверка парсинга чисел
# ==========================================
print("\n--- 4. Тест чисел (IntLit) ---")
num_code = "42"
p_num = Parser(tokenize(num_code))
num_expr = p_num.parse_expr()

print(f"Строка '{num_code}' распарсилась в объект: {num_expr}")
print(f"Это класс IntLit? {isinstance(num_expr, IntLit)}")
print(f"Значение: {num_expr.value}")
assert num_expr.value == 42
print("✅ Числа парсятся корректно!")