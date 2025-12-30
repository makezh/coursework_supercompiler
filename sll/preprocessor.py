from sll.ast_nodes import Program, Expr, Ctr, FCall, Let

class Tagger:
    def __init__(self):
        self.counter = 0

    def _new_tag(self) -> int:
        self.counter += 1
        return self.counter

    def preprocess(self, program: Program):
        """
        Проходит по всем правилам программы и назначает уникальные теги
        всем узлам в правых частях (body).
        """
        self.counter = 0
        for rule in program.rules:
            self._tag_expr(rule.body)

    def _tag_expr(self, expr: Expr):
        # 1. Ставим тег текущему узлу
        expr.tag = self._new_tag()

        # 2. Рекурсивно идем вглубь
        match expr:
            case Ctr(_, args):
                for arg in args:
                    self._tag_expr(arg)

            case FCall(_, args):
                for arg in args:
                    self._tag_expr(arg)

            case Let(_, val, body):
                self._tag_expr(val)
                self._tag_expr(body)

            # Var и IntLit — листья, они получили тег в шаге 1, детей нет
            case _:
                pass

def add_tags(program: Program):
    """Удобная функция-обертка."""
    Tagger().preprocess(program)