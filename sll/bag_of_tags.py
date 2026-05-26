from collections import Counter
from typing import Optional

from sll.ast_nodes import Ctr, FCall, Let
from sll.process_tree import Node


class TagBag:
    W_HEAP = 2
    W_FOCUS = 3
    W_STACK = 5

    @staticmethod
    def _add_tag(bag: Counter, tag: Optional[int], weight: int):
        if tag is None:
            return
        bag[tag] += weight

    @staticmethod
    def _walk_expr(bag: Counter, expr, weight: int):
        TagBag._add_tag(bag, getattr(expr, "tag", None), weight)
        match expr:
            case Ctr(_, args) | FCall(_, args):
                for a in args:
                    TagBag._walk_expr(bag, a, weight)
            case Let(bindings, body):
                for _, val in bindings:
                    TagBag._walk_expr(bag, val, weight)
                TagBag._walk_expr(bag, body, weight)

    @staticmethod
    def collect(node: Node) -> Counter:
        bag = Counter()
        TagBag._walk_expr(bag, node.expr, TagBag.W_FOCUS)
        for hb in getattr(node, "heap", []):
            TagBag._walk_expr(bag, hb.expr, TagBag.W_HEAP)
        for fr in getattr(node, "stack", []):
            TagBag._add_tag(bag, getattr(fr, "tag", None), TagBag.W_STACK)
        return bag

    @staticmethod
    def is_dangerous(old, new):
        if not old:
            return False
        for tag, count in old.items():
            if new.get(tag, 0) < count:
                return False
        return True