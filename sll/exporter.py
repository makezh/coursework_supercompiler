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

        case Let(vname, val, body):
            return f"let {vname}{t} = {to_tagged_str(val)} in {to_tagged_str(body)}"

        case _:
            return str(expr)

def to_dot(root: Node, dev_mode=False) -> str:
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

    while queue:
        node = queue.pop(0)
        uid = node_ids[id(node)]

        if id(node) in processed:
            continue
        processed.add(id(node))

        is_ref = getattr(node, 'is_basis_ref', False)

        style_attr = ""
        if is_ref:
            # Та самая синяя заливка
            style_attr = ', style="filled", fillcolor="lightcyan", color="blue", penwidth=2.0'

        # 1. Описание самого узла
        # Экранируем кавычки и скобки для DOT
        if dev_mode:
            label = to_tagged_str(node.expr).replace('"', '\\"')
        else:
            label = str(node.expr).replace('"', '\\"')

        lines.append(f'    {uid} [label="{label}", shape=box{style_attr}];')

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
                v = child.contraction.var_name
                if child.contraction.pattern:
                    # Ветвление: x = [S v1]
                    p = str(child.contraction.pattern)
                    edge_label = f"{v} -> {p}"
                else:
                    # Обобщение: let v = ...
                    edge_label = f"let {v} = {to_tagged_str(child.contraction.value)}"


            is_branch_edge = bool(child.contraction and child.contraction.pattern)
            from_id = uid

            if getattr(child, "driven_rule", None) is not None:
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
                aux_counter += 1
                gen_id = f"gen{aux_counter}"

                # Короткие строки (без тегов или с тегами — как тебе удобнее)
                if dev_mode:
                    a = to_tagged_str(child.gen_alpha) if child.gen_alpha else "?"
                    g = to_tagged_str(child.gen_result)
                else:
                    a = str(child.gen_alpha) if child.gen_alpha else "?"
                    g = str(child.gen_result)

                gen_label = (
                    "GEN\\n"
                    f"α: {a}\\n"
                    f"gen: {g}"
                ).replace('"', '\\"')

                # Ромбик Обобщения
                lines.append(
                    f'    {gen_id} [label="{gen_label}", shape=diamond, style="filled", '
                    f'fillcolor="lightyellow", color="orange"];'
                )

                branch_label = edge_label if is_branch_edge else ""
                lines.append(f'    {from_id} -> {gen_id} [label="{branch_label}"];')
                from_id = gen_id

            dup_label = edge_label if is_branch_edge else edge_label
            lines.append(f'    {from_id} -> {child_id} [label="{dup_label}"];')


    lines.append("}")
    return "\n".join(lines)