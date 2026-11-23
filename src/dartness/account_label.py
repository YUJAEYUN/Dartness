"""Reduce a financial statement account label to its core name (docs/cash-table-extraction.md).

Statements decorate account names with outline markers in front ("(5)", "5.", "Ⅴ.", "가.",
"①") and note references behind ("(주4,29)"). Neither changes what the account is, so they are
removed. Words are never removed: "제한된 현금및현금성자산" keeps its meaning and stays different
from "현금및현금성자산". Extractors compare the core name with the account they look for.
"""

import re

# Outline markers, one or more in a row. Each is a number, Roman numeral, single Latin letter
# or single Hangul syllable wrapped in parentheses or followed by a period, or a circled
# number. "주" is excluded because "(주)" is a note or company mark, not an outline position.
_TOKEN = "(?:[0-9]+|[Ⅰ-Ⅻⅰ-ⅻ]+|[A-Za-z]|[\uac00-\uc8fb\uc8fd-\ud7a3])"
_MARKERS = re.compile(rf"^(?:\({_TOKEN}\)|{_TOKEN}\.|[①-⑳])+")
# One note reference at the end, e.g. "(주4,29)".
_NOTE = re.compile(r"\(주[0-9]+(?:,[0-9]+)*\)$")


def core_account_name(label: str) -> str:
    """Return the label without whitespace, leading outline markers and a trailing note."""
    text = "".join(label.split())
    text = _NOTE.sub("", text, count=1)
    return _MARKERS.sub("", text, count=1)
