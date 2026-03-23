from sll.process_tree import Node
from sll.ast_nodes import Var, Ctr, FCall, IntLit, Let, Expr

def to_tagged_str(expr: Expr) -> str:
    """
    Вспомогательная функция для отображения тегов в графе.
    Рисует тег в фигурных скобках рядом с именем.
    """
    # Обработка виртуального корня гиперцикла
    if isinstance(expr, FCall) and expr.name == "PROGRAM_FOREST":
        return "PROGRAM_FOREST"

    # Формируем строку тега, если он есть
    t = f"{{{expr.tag}}}" if expr.tag is not None else ""

    match expr:
        case Var(name):
            return f"{name}{t}"

        case IntLit(val):
            return f"{val}{t}"

        case Ctr(name, args):
            if not args:
                return f"[{name}{t}]"
            args_str = " ".join(to_tagged_str(arg) for arg in args)
            return f"[{name}{t} {args_str}]"

        case FCall(name, args):
            args_str = " ".join(to_tagged_str(arg) for arg in args)
            return f"({name}{t} {args_str})"

        case Let(bindings, body):
            # Книжный вид: let ... in ...
            binds = "; ".join(f"{name} = {to_tagged_str(val)}" for name, val in bindings)
            return f"(let{t} {binds} in {to_tagged_str(body)})"

        case _:
            return str(expr)

def to_dot(root: Node, dev_mode=False, start_expr=None) -> str:
    """
    Генерирует описание графа в формате DOT (Graphviz).
    """
    lines = [
        "digraph ProcessTree {",
        "    node [fontname=\"Courier New\"];",
        "    edge [fontname=\"Courier New\"];"
    ]

    # Карта: Объект Node -> Уникальный ID (строка "n1", "n2"...)
    # Используем id() объекта, чтобы различать узлы
    node_ids = {}
    counter = 0
    aux_counter = 0

    # Очередь для обхода (BFS)
    queue = [root]
    processed = set()

    # Присваиваем ID корню
    node_ids[id(root)] = f"n{counter}"
    counter += 1

    # --- Стартовый узел ---
    has_start = start_expr is not None
    has_root_gen = getattr(root, "gen_result", None) is not None and root.parent is None
    root_gen_rendered = has_root_gen  # пометим, чтобы не рисовать повторно в BFS

    if has_start:
        start_label = str(start_expr).replace('"', '\\"')
        lines.append(
            f'    start [label="{start_label}", shape=box, style="filled", '
            f'fillcolor="lightgreen", color="darkgreen", penwidth=2.0];'
        )

    root_uid = node_ids[id(root)]
    if has_start and has_root_gen:
        # Информация об обобщении — подпись на стрелке, без отдельного ромба
        a = to_tagged_str(root.gen_alpha) if root.gen_alpha else "?"
        g = to_tagged_str(root.gen_result)
        edge_label = f"MSG\\nα: {a}\\n→ {g}".replace('"', '\\"')
        lines.append(f'    start -> {root_uid} [label="{edge_label}", color="darkorange", fontcolor="black", fontsize=10];')
    elif has_start:
        lines.append(f'    start -> {root_uid} [];')

    while queue:
        node = queue.pop(0)
        uid = node_ids[id(node)]

        if id(node) in processed:
            continue
        processed.add(id(node))

        is_ref = getattr(node, 'is_basis_ref', False)

        style_attr = ""
        if is_ref:
            style_attr = ', style="filled", fillcolor="lightcyan", color="blue", penwidth=2.0'
        elif isinstance(node.expr, Let):
            # Let-узлы подсвечиваем как в книжке
            style_attr = ', style="filled", fillcolor="lightyellow", color="orange", penwidth=2.0'

        # 1. Описание самого узла
        # Экранируем кавычки и скобки для DOT
        if dev_mode:
            label = to_tagged_str(node.expr).replace('"', '\\"')
        else:
            label = str(node.expr).replace('"', '\\"')

        lines.append(f'    {uid} [label="{label}", shape=box{style_attr}];')

        # GEN-ромб корня рендерится в блоке до BFS (как подпись на стрелке start→root)

        # 2. Ссылка назад (Folding)
        if node.back_link:
            target_id = node_ids.get(id(node.back_link))
            if target_id:
                lines.append(f'    {uid} -> {target_id} [style=dashed, color=red, label="Folding"];')
            continue

        # 3. Дети
        for child in node.children:
            # Присваиваем ID ребенку, если еще нет
            if id(child) not in node_ids:
                node_ids[id(child)] = f"n{counter}"
                counter += 1
                queue.append(child)

            child_id = node_ids[id(child)]

            # Подпись на ребре (если это ветвление или обобщение)
            edge_label = ""
            if child.contraction:
                c = child.contraction
                if c.narrowings is not None:
                    # Полное сужение нескольких переменных
                    parts = [f"{k} -> {v}" for k, v in c.narrowings.items()
                             if not (hasattr(v, 'name') and v.name == k)]
                    edge_label = ", ".join(parts) if parts else "default"
                elif c.is_default:
                    edge_label = "default"
                elif c.pattern is not None:
                    # Одиночное ветвление: x = [S v1]
                    edge_label = f"{c.var_name} -> {c.pattern}"
                elif c.value is not None:
                    # Обобщение: let v = ...
                    edge_label = f"let {c.var_name} = {to_tagged_str(c.value)}"

            is_branch_edge = bool(
                child.contraction and (
                    child.contraction.pattern is not None or
                    child.contraction.narrowings is not None or
                    child.contraction.is_default
                )
            )
            from_id = uid

            if dev_mode and getattr(child, "driven_rule", None) is not None:
                aux_counter += 1
                drive_id = f"drv{aux_counter}"

                # подпись: DRIVE + левая часть правила
                drive_label = f"DRIVE\\n{str(child.driven_rule)}".replace('"', '\\"')

                lines.append(
                    f'    {drive_id} [label="{drive_label}", shape=ellipse, style="filled", '
                    f'fillcolor="lavender"];'
                )

                branch_label = edge_label if is_branch_edge else ""
                lines.append(f'    {uid} -> {drive_id} [label="{branch_label}"];')
                from_id = drive_id

            if getattr(child, "gen_result", None) is not None:
                if dev_mode:
                    a = to_tagged_str(child.gen_alpha) if child.gen_alpha else "?"
                    g = to_tagged_str(child.gen_result)
                else:
                    a = str(child.gen_alpha) if child.gen_alpha else "?"
                    g = str(child.gen_result)
                gen_part = f"MSG\\nα: {a}\\n→ {g}".replace('"', '\\"')
                combined = f"{edge_label}\\n{gen_part}" if edge_label else gen_part
                lines.append(
                    f'    {from_id} -> {child_id} [label="{combined}", '
                    f'color="darkorange", fontcolor="black", fontsize=10];'
                )
            else:
                dup_label = edge_label if is_branch_edge else edge_label
                lines.append(f'    {from_id} -> {child_id} [label="{dup_label}"];')


    lines.append("}")
    return "\n".join(lines)