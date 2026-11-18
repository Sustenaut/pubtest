"""pubtest's steps, one module per family of GRAMMAR.md."""

from __future__ import annotations

import re
from typing import Any

from pytest_bdd import parsers

__all__ = ["phrase"]

# A value in quotes is any text with no unescaped quote, empty too, as
# cucumber's {string} is; {name:d} is a whole number; a bare {name} is words.
_FIELD = re.compile(r'"\{(?P<quoted>\w+)\}"|\{(?P<whole>\w+):d\}|\{(?P<bare>\w+)\}')
_QUOTED = r'(?:[^"\\]|\\.)*'


class phrase(parsers.re):  # noqa: N801 - read as a parser, like parsers.parse
    """A step's words, its values in braces as parsers.parse writes them
    (`'the file "{path}" holds "{text}"'`), matched so that a quoted value
    may be empty (`""`) and never runs past its closing quote: a shorter
    step's pattern cannot swallow a longer one's text. `{n:d}` is a whole
    number. Its name stays the words, so a suite's own step of the same
    words takes its place, as with parsers.parse."""

    def __init__(self, template: str) -> None:
        pattern, pos, self.whole = [], 0, []
        for field in _FIELD.finditer(template):
            pattern.append(re.escape(template[pos:field.start()]))
            if field["quoted"]:
                pattern.append(f'"(?P<{field["quoted"]}>{_QUOTED})"')
            elif field["whole"]:
                pattern.append(rf"(?P<{field['whole']}>-?\d+)")
                self.whole.append(field["whole"])
            else:
                pattern.append(f"(?P<{field['bare']}>.+)")
            pos = field.end()
        pattern.append(re.escape(template[pos:]))
        super().__init__("".join(pattern), re.S)
        self.name = template

    def parse_arguments(self, name: str) -> dict[str, Any] | None:
        found: dict[str, Any] | None = super().parse_arguments(name)
        if found is not None:
            for key in self.whole:
                found[key] = int(found[key])
        return found
