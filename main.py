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
from sll.ast_nodes import TypeExpr, Var

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
    parser.add_argument("-s", "--strategy", choices=['HE', 'TAG'], default='HE',
                        help="Whistle strategy: HE (Homeomorphic Embedding) or TAG (Bag of Tags)")

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

    # --- 3. Парсинг выражения и Авто-определение сигнатуры ---
    start_var_types = {}

    # Если введено просто имя (например, 'add3'), а не выражение со скобками
    if "(" not in args.expr and ")" not in args.expr:
        func_name = args.expr

        # Ищем сигнатуру функции
        sig = next((s for s in prog.signatures if s.name == func_name), None)

        if sig:
            # Пытаемся взять имена аргументов из первого правила этой функции
            first_rule = next((r for r in prog.rules if r.pattern.name == func_name), None)

            arg_names = []
            if first_rule:
                for i, p in enumerate(first_rule.pattern.params):
                    # Если в паттерне переменная — берем её имя, если конструктор — генерируем v...
                    if isinstance(p, Var):
                        arg_names.append(p.name)
                    else:
                        arg_names.append(f"v{i+1}")
            else:
                # Если правил почему-то нет, просто генерируем v1, v2...
                arg_names = [f"v{i+1}" for i in range(len(sig.arg_types))]

            # Формируем итоговое выражение: (func x y z)
            args.expr = f"({func_name} {' '.join(arg_names)})"

            # Автоматически заполняем типы из сигнатуры
            for i, t_expr in enumerate(sig.arg_types):
                start_var_types[arg_names[i]] = t_expr

            print(f"--- Auto-inferred signature: {args.expr} ---")
        else:
            print(f"Error: Function '{func_name}' not found in signatures.")
            return

    # Парсим уже готовое (или введенное вручную) выражение
    try:
        start_expr = Parser(tokenize(args.expr)).parse_expr()
    except Exception as e:
        print(f"Expression Parse Error: {e}")
        return

    # --- 4. Разбор типов переменных (если переданы вручную через -t) ---
    # Ручные типы имеют приоритет над автоматическими
    for t_str in args.types:
        if "=" not in t_str:
            print(f"Error: Invalid type format '{t_str}'. Use 'var=Type'")
            return
        vname, tname = t_str.split("=")
        start_var_types[vname] = TypeExpr(tname, [])

    # --- 5. Запуск Суперкомпилятора ---
    print(f"--- Supercompiling: {start_expr} ---")
    print(f"    Strategy: {args.strategy}")
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