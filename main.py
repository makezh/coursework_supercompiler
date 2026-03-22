import argparse
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sll.parser import parse, Parser, tokenize
from sll.type_checker import check_program
from sll.supercompiler import Supercompiler
from sll.residualizer import Residualizer
from sll.exporter import to_dot
from sll.ast_nodes import TypeExpr, Var

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
    parser.add_argument("-g", "--gen", choices=['TOP', 'BOTTOM'], default='TOP',
                    help="Generalization type: TOP (rewrite ancestor) or BOTTOM (rewrite current)")
    parser.add_argument("-d", "--dev", choices=['ON', 'OFF'], default='OFF',
                    help="Developer mode: ON (show tags in graph) or OFF (hide tags)")

    args = parser.parse_args()
    DEV_MODE = (args.dev == 'ON')

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
    if "(" not in args.expr and ")" not in args.expr:
        func_name = args.expr

        sig = next((s for s in prog.signatures if s.name == func_name), None)
        if not sig:
            print(f"Error: Function '{func_name}' not found in signatures.")
            return

        arg_names = [f"x{i+1}" for i in range(len(sig.arg_types))]
        start_expr_str = f"({func_name} {' '.join(arg_names)})"

        for i, t_expr in enumerate(sig.arg_types):
            start_var_types[arg_names[i]] = t_expr

        print(f"--- Auto-inferred call: {start_expr_str} ---")

        # Парсим уже эту строку
        try:
            start_expr = Parser(tokenize(start_expr_str)).parse_expr()
        except Exception as e:
            print(f"Expression Parse Error: {e}")
            return

    else:
        try:
            start_expr = Parser(tokenize(args.expr)).parse_expr()
        except Exception as e:
            print(f"Expression Parse Error: {e}")
            return

    # --- 4. Разбор типов переменных (если переданы вручную через -t) ---
    for t_str in args.types:
        if "=" not in t_str:
            print(f"Error: Invalid type format '{t_str}'. Use 'var=[Type]' or 'var=Type'")
            return
        vname, tname = t_str.split("=", 1)
        tname = tname.strip()
        if tname.startswith('['):
            try:
                type_tokens = list(tokenize(tname))
                p = Parser(type_tokens)
                parsed_type = p.parse_type_expr()
                start_var_types[vname] = parsed_type
            except Exception as e:
                print(f"Error parsing type '{tname}': {e}")
                return
        else:
            start_var_types[vname] = TypeExpr(tname, [])

    # --- 5. Запуск Суперкомпилятора ---
    print(f"--- Supercompiling: {start_expr} ---")
    print(f"    Strategy: {args.strategy}")
    print(f"    Generalize type: {args.gen}")
    print(f"    Context: {start_var_types}")

    sc = Supercompiler(prog, strategy=args.strategy, gen_type=args.gen)
    if args.gen == 'TOP':
        print("Running Classical TOP-down Supercompilation...")
        sc.build_tree(start_expr, start_var_types)
    else:
        print("Running Abramov's BOTTOM-up Supercompilation with Hypercycle...")
        sc.run_hypercycle(start_expr, start_var_types)

    # --- 6. Экспорт (Graphviz) ---
    # Создаем папку output, если нет
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    out_path_base = os.path.join(OUTPUT_DIR, args.out)

    print(f"--- Exporting Graph to {OUTPUT_DIR}/ ---")
    dot_code = to_dot(sc.tree, dev_mode=DEV_MODE)

    graph_label = (
        f"Expression: {args.expr}\\n"
        f"Whistle Strategy: {args.strategy} | Gen Type: {args.gen}"
    )

    header_settings = (
        f'\n  label="{graph_label}";\n'
        f'  labelloc="t";\n'      # Расположить сверху (top)
        f'  fontsize=20;\n'       # Размер шрифта
        f'  fontname="Arial";\n'
    )
    dot_code = dot_code.replace('{', '{' + header_settings, 1)

    # Сохраняем .dot
    with open(f"{out_path_base}.dot", 'w', encoding='utf-8') as f:
        f.write(dot_code)

    # Рисуем граф
    if HAS_GRAPHVIZ:
        try:
            s = graphviz.Source(dot_code)
            output_file = s.render(filename=args.out, directory=OUTPUT_DIR, format="png", cleanup=True)
            print(f"✅ Graph saved: {output_file}")
        except Exception as e:
            print(f"Warning: Graphviz render failed: {e}")
    else:
        print(f"Saved .dot file. Install 'graphviz' to generate PNG automatically.")

    # --- 7. Резидуализация ---
    print("\n=== RESIDUAL PROGRAM ===")
    res = Residualizer(sc.tree, prog)
    new_prog = res.residualize()
    print(new_prog)
    print("========================")

if __name__ == "__main__":
    main()