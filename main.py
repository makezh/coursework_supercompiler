import argparse
import sys
import os

# Добавляем путь к пакету sll
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sll.parser import parse, Parser, tokenize
from sll.type_checker import check_program
from sll.supercompiler import Supercompiler
from sll.residualizer import Residualizer
from sll.exporter import to_dot
from sll.ast_nodes import TypeExpr

# Настройки папок
SAMPLES_DIR = "samples"
OUTPUT_DIR = "output"

try:
    import graphviz
    HAS_GRAPHVIZ = True
except ImportError:
    HAS_GRAPHVIZ = False

def main():
    parser = argparse.ArgumentParser(description="SLL Supercompiler")
    parser.add_argument("file", help="Filename of .sll program (looks in current dir or ./samples/)")
    parser.add_argument("expr", help="Expression to supercompile, e.g. '(add a b)'")
    parser.add_argument("-t", "--types", nargs="+", help="Variable types, e.g. 'a=Nat b=Nat'", default=[])
    parser.add_argument("-o", "--out", help="Output filename base (saved to ./output/)", default="graph")

    args = parser.parse_args()

    # --- 1. Поиск входного файла ---
    input_path = args.file
    # Если файл не найден по прямому пути, ищем в папке samples
    if not os.path.exists(input_path):
        alt_path = os.path.join(SAMPLES_DIR, args.file)
        if os.path.exists(alt_path):
            input_path = alt_path
        else:
            print(f"Error: File '{args.file}' not found (checked current dir and '{SAMPLES_DIR}/').")
            return

    print(f"--- Reading {input_path} ---")
    with open(input_path, 'r', encoding='utf-8') as f:
        code = f.read()

    # --- 2. Парсинг и Проверка ---
    print("--- Parsing & Type Checking ---")
    try:
        prog = parse(code)
        check_program(prog)
    except Exception as e:
        print(f"Error: {e}")
        return

    # --- 3. Парсинг выражения ---
    try:
        start_expr = Parser(tokenize(args.expr)).parse_expr()
    except Exception as e:
        print(f"Expression Parse Error: {e}")
        return

    # --- 4. Разбор типов переменных ---
    start_var_types = {}
    for t_str in args.types:
        if "=" not in t_str:
            print(f"Error: Invalid type format '{t_str}'. Use 'var=Type'")
            return
        vname, tname = t_str.split("=")
        start_var_types[vname] = TypeExpr(tname, [])

    # --- 5. Запуск Суперкомпилятора ---
    print(f"--- Supercompiling: {start_expr} ---")
    print(f"    Context: {start_var_types}")

    sc = Supercompiler(prog)
    sc.build_tree(start_expr, start_var_types)

    # --- 6. Экспорт (Graphviz) ---
    # Создаем папку output, если нет
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Формируем полный путь к выходному файлу (без расширения)
    out_path_base = os.path.join(OUTPUT_DIR, args.out)

    print(f"--- Exporting Graph to {OUTPUT_DIR}/ ---")
    dot_code = to_dot(sc.tree)

    # Сохраняем .dot
    with open(f"{out_path_base}.dot", 'w', encoding='utf-8') as f:
        f.write(dot_code)

    # Рисуем картинку
    if HAS_GRAPHVIZ:
        try:
            # graphviz сам добавит расширение .png к filename
            s = graphviz.Source(dot_code)
            # render(filename, directory, ...)
            output_file = s.render(filename=args.out, directory=OUTPUT_DIR, format="png", cleanup=True)
            print(f"✅ Graph saved: {output_file}")
        except Exception as e:
            print(f"Warning: Graphviz render failed: {e}")
    else:
        print(f"Saved .dot file. Install 'graphviz' to generate PNG automatically.")

    # --- 7. Резидуализация ---
    print("\n=== RESIDUAL PROGRAM ===")
    res = Residualizer(sc.tree)
    new_prog = res.residualize()
    print(new_prog)
    print("========================")

if __name__ == "__main__":
    main()