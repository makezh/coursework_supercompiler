from sll.ast_nodes import Program, Expr, Var, Ctr, FCall, IntLit, Let

class TagAllocator:
    def __init__(self):
        # Начинаем счетчик с 1 (0 оставим как резерв)
        self.current_tag = 1

    def get_new_tag(self) -> int:
        """Выдает следующий уникальный номер и увеличивает счетчик."""
        tag = self.current_tag
        self.current_tag += 1
        return tag

    def process_program(self, program: Program):
        """
        Проходит по всей программе и расставляет теги.
        """
        # Проходим по всем правилам (уравнениям) программы
        for rule in program.rules:
            # Тегируем правую часть уравнения (тело функции)
            self._process_expr(rule.body)

    def process_expr(self, expr: Expr):
        """
        Публичный метод, чтобы можно было потегировать отдельное выражение
        """
        self._process_expr(expr)

    def _process_expr(self, expr: Expr):
        """
        Рекурсивно обходит дерево выражения и ставит теги.
        """
        # 1. Ставим уникальный тег текущему узлу
        expr.tag = self.get_new_tag()

        # 2. Идем вглубь (к детям), если они есть
        match expr:
            case Ctr(_, args) | FCall(_, args):
                for arg in args:
                    self._process_expr(arg)

            case Let(_, val, body):
                self._process_expr(val)
                self._process_expr(body)

            case Var(_) | IntLit(_):
                # У переменных и чисел детей нет, просто выходим
                pass