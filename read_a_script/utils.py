from enum import Enum

import jouvence.document


class ElementType(Enum):

    ACTION = jouvence.document.TYPE_ACTION
    CENTERED_ACTION = jouvence.document.TYPE_CENTEREDACTION
    CHARACTER = jouvence.document.TYPE_CHARACTER
    DIALOG = jouvence.document.TYPE_DIALOG
    PARENTHETICAL = jouvence.document.TYPE_PARENTHETICAL
    TRANSITION = jouvence.document.TYPE_TRANSITION
    LYRICS = jouvence.document.TYPE_LYRICS
    PAGE_BREAK = jouvence.document.TYPE_PAGEBREAK
    SECTION = jouvence.document.TYPE_SECTION
    SYNOPSIS = jouvence.document.TYPE_SYNOPSIS


def mixrange(s):
    """
    Expand a range which looks like "1-3,6,8-10" to [1, 2, 3, 6, 8, 9, 10]
    """
    r = []
    for i in s.split(","):
        if "-" not in i:
            r.append(int(i))
        else:
            l, h = list(map(int, i.split("-")))
            r += list(range(l, h + 1))
    return r


def merge(dict_1, dict_2):
    """Merge two dictionaries.

    Values that evaluate to true take priority over falsy values.
    `dict_1` takes priority over `dict_2`.

    """
    return dict((str(key), dict_1.get(key) or dict_2.get(key))
                for key in set(dict_2) | set(dict_1))
