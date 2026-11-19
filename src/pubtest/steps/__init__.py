"""pubtest's steps, one module per family of GRAMMAR.md."""

from __future__ import annotations

import re
from typing import Any

from pytest_bdd import parsers

__all__ = ["phrase"]

# A value in quotes is any text, empty too, read as cucumber's {string} reads
# one: \" is a quote and \\ a backslash. It is read strictly first, with no
# bare quote inside, so a shorter step never swallows a longer one's text
# (`… asked "GET /a" with the header "H" set to "V"`). When no step of
# pubtest's reads the text strictly, a value may hold bare quotes
# (`holding "{"kind": "utility"}"`, `mentions ""tags" must be true"`), read
# to the step's last quote. {name:d} is a whole number; a bare {name} is words.
_FIELD = re.compile(r'"\{(?P<quoted>\w+)\}"|\{(?P<whole>\w+):d\}|\{(?P<bare>\w+)\}')
_STRICT = r'(?:[^"\\]|\\.)*'
_LOOSE = r'(?:\\.|[^\\])*?'
_ESCAPE = re.compile(r'\\(["\\])')


def _pattern(template: str, quoted: str) -> str:
    out, pos = [], 0
    for field in _FIELD.finditer(template):
        out.append(re.escape(template[pos:field.start()]))
        if field["quoted"]:
            out.append(f'"(?P<{field["quoted"]}>{quoted})"')
        elif field["whole"]:
            out.append(rf"(?P<{field['whole']}>-?\d+)")
        else:
            out.append(f"(?P<{field['bare']}>.+)")
        pos = field.end()
    out.append(re.escape(template[pos:]))
    return "".join(out)


class phrase(parsers.re):  # noqa: N801 - read as a parser, like parsers.parse
    """A step's words, its values in braces as parsers.parse writes them
    (`'the file "{path}" holds "{text}"'`), matched so that a quoted value
    may be empty (`""`), its escapes read as cucumber reads them, and a
    shorter step's pattern never swallows a longer one's text. `{n:d}` is a
    whole number. Its name stays the words, so a suite's own step of the
    same words takes its place, as with parsers.parse."""

    every: list["phrase"] = []

    def __init__(self, template: str) -> None:
        super().__init__(_pattern(template, _STRICT), re.S)
        self.loose = re.compile(_pattern(template, _LOOSE), re.S)
        self.name = template
        self.whole = [f["whole"] for f in _FIELD.finditer(template) if f["whole"]]
        self.quoted = [f["quoted"] for f in _FIELD.finditer(template) if f["quoted"]]
        phrase.every.append(self)

    def is_matching(self, name: str) -> bool:
        if self.regex.fullmatch(name):
            return True
        return bool(self.loose.fullmatch(name)) and not any(p.regex.fullmatch(name) for p in phrase.every)

    def parse_arguments(self, name: str) -> dict[str, Any] | None:
        found = self.regex.fullmatch(name) or self.loose.fullmatch(name)
        if found is None:
            return None
        values: dict[str, Any] = found.groupdict()
        for key in self.whole:
            values[key] = int(values[key])
        for key in self.quoted:
            values[key] = _ESCAPE.sub(r"\1", values[key])
        return values
