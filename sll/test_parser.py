from parser import tokenize, parse, Parser, IntLit
from interpreter import step

# ==========================================
# ТЕСТ 1: Токенизатор (проверка чисел и спецсимволов)
# ==========================================
text = """
-- Это комментарий
(add 42 y) -> y     -- тест чисел
type [List a] : Nil -- тест ключевых слов
"""

print("--- 1. Токенизация ---")
tokens = tokenize(text)
print(tokens)
# Ожидаем: ['(', 'add', '42', 'y', ')', '->', 'y', 'type', '[', 'List', 'a', ']', ':', 'Nil']


# ==========================================
# ТЕСТ 2: Полный парсинг (Новая грамматика)
# ==========================================
# Здесь мы используем новый синтаксис:
# 1. Объявление типа (должно пропуститься)
# 2. Сигнатура функции с типами (должны пропуститься)
code = """
type [Nat] : Z | S [Nat] .

fun (add [Nat] [Nat]) -> [Nat] :
    (add [Z] y) -> y
  | (add [S x] y) -> [S (add x y)].
"""

print("\n--- 2. Парсинг программы ---")
program = parse(code)
print("Программа успешно считана!")
print(f"Количество типов: {len(program.types)}")
print(f"Количество сигнатур: {len(program.signatures)}")
print(f"Количество правил: {len(program.rules)}")
print(program)



# ==========================================
# ТЕСТ 3: Вычисление (Интеграционный тест)
# ==========================================
# Проверяем, что, несмотря на усложнение парсера,
# логика 1 + 1 всё ещё работает.

expr_text = "(add [S [Z]] [S [Z]])"
# Создаем временный парсер для одного выражения
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

print(f"Результат: {curr}")


# ==========================================
# ТЕСТ 4: Проверка парсинга чисел
# ==========================================
print("\n--- 4. Тест чисел (IntLit) ---")
num_code = "42"
p_num = Parser(tokenize(num_code))
num_expr = p_num.parse_expr()

print(f"Строка '{num_code}' распарсилась в объект: {num_expr}")
print(f"Это класс IntLit? {isinstance(num_expr, IntLit)}")
# Если парсер работает верно, тут будет True