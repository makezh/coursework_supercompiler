from sll.process_tree import Node

def to_dot(root: Node) -> str:
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

        # 1. Описание самого узла
        # Экранируем кавычки и скобки для DOT
        label = str(node.expr).replace('"', '\\"')
        lines.append(f'    {uid} [label="{label}", shape=box];')

        # 2. Ссылка назад (Folding)
        if node.back_link:
            target_id = node_ids.get(id(node.back_link))
            if target_id:
                lines.append(f'    {uid} -> {target_id} [style=dashed, color=red, label="Folding"];')
            continue # Детей у свернутого узла нет

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
                    edge_label = f"let {v}"

            lines.append(f'    {uid} -> {child_id} [label="{edge_label}"];')

    lines.append("}")
    return "\n".join(lines)