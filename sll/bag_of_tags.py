from collections import Counter
from typing import Optional

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
    def collect(node: Node) -> Counter:
        """
        Возвращает tag-bag для конфигурации узла (heap/focus/stack).
        """
        bag = Counter()

        # focus root tag: 3 * tag(focus)
        TagBag._add_tag(bag, getattr(node.expr, "tag", None), TagBag.W_FOCUS)

        # heap root tags: 2 * tag(rhs)
        for hb in getattr(node, "heap", []):
            TagBag._add_tag(bag, getattr(hb.expr, "tag", None), TagBag.W_HEAP)

        # stack root tags: 5 * tag(frame)
        for fr in getattr(node, "stack", []):
            TagBag._add_tag(bag, getattr(fr, "tag", None), TagBag.W_STACK)

        return bag

    @staticmethod
    def is_dangerous(old, new):
        if not old:
            return False
        if set(old.keys()) != set(new.keys()):
            return False
        return sum(new.values()) >= sum(old.values())