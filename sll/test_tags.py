from sll.parser import parse  # Используем твою функцию
from sll.tagging import TagAllocator
from sll.ast_nodes import Expr, Ctr, FCall, Let, Var, IntLit

def print_tree_with_tags(expr: Expr, indent: int = 0):
    """
    Рекурсивно печатает дерево выражения, показывая теги.
    """
    indent_str = "  " * indent
    tag_value = expr.tag if expr.tag is not None else "None"
    print(f"{indent_str}- [{type(expr).__name__}] TAG={tag_value}  ::  {expr}")

    match expr:
        case Ctr(_, args) | FCall(_, args):
            for arg in args:
                print_tree_with_tags(arg, indent + 1)
        case Let(_, val, body):
            print_tree_with_tags(val, indent + 1)
            print_tree_with_tags(body, indent + 1)
        case _:
            pass

source_code = """
type [Nat] : Z | S [Nat].

fun (add [Nat] [Nat]) -> [Nat] :
  (add [Z] y) -> y
| (add [S x] y) -> [S (add x y)].
"""

print("--- 1. Парсинг программы ---")
program = parse(source_code)

print("--- 2. Разметка тегами ---")
allocator = TagAllocator()
allocator.process_program(program)

print("--- 3. Проверка тегов в правилах ---")

for i, rule in enumerate(program.rules):
    print(f"\nПравило №{i+1}: {rule.pattern}")
    print_tree_with_tags(rule.body)