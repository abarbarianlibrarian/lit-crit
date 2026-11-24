"""Line numbers for poems and passages, shared by the site (build.py) and the practice-test
PDF builder (claude/practice-test-tools/build.py in the Lit Crit App project). Keep both copies the same.

Rules come from the Style Guide's "Line numbers" section and claude/line-numbers-plan.md
(215 numbered passages in 12 released UIL PDFs, 2012-2026).

Text format (Poems and Passages, Text):
  - no title line and no numbers
  - a blank line is a stanza break; leading spaces are indentation
  - "+ "  continues the line before it (a turnover or dropped half-line); not counted. It prints with a
          hanging indent; extra spaces after "+ " indent it further (a dropped half-line)
  - "* "  a gloss or footnote; not counted
  - "# "  a label (section numeral, epigraph, poet and date); not counted
Record fields: Line Start (blank = 1), Line Numbering (Auto, Every 3/4/5/6, Every line, None),
Layout (Verse, Prose (UIL lines), Prose (paragraphs)).

Transition: a text that still carries UIL's printed numbers at line ends (two or more spaces, then
the number) is shown with those printed numbers, moved into the number column, until the record
is migrated.

    rows = number(text, numbering="Auto", start=None, layout=None)

returns one Row per input line (trailing blank lines dropped), so callers can zip rows with
per-line data such as the essay page's glosses.
"""
import re
from collections import namedtuple

# kind: "line" (a counted line), "cont" (+ turnover), "gloss" (*), "label" (#), "gap" (blank line)
# text: the line without its marker and leading spaces; indent: the number of leading spaces
# n: the counted line's number (cont rows carry their line's number); show: the number to print, or ""
Row = namedtuple("Row", "kind text indent n show")

EVERY = {"Every 3": 3, "Every 4": 4, "Every 5": 5, "Every 6": 6, "Every line": 1, "None": 0}
LEGACY = re.compile(r"^(.*?\S)(?:[ \t]{2,}|\t)(\d{1,3})\s*$")   # "Was unfamiliar but, truth is, the man     4"


def _split(text):
    lines = (text or "").replace("\r", "").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    while lines and not lines[0].strip():
        lines.pop(0)
    return lines


def _parse(line):
    """(kind, text, indent) for one source line."""
    if not line.strip():
        return "gap", "", 0
    body = line.rstrip()
    ind = len(body) - len(body.lstrip(" "))
    s = body.lstrip(" ")
    for mark, kind in (("+", "cont"), ("*", "gloss"), ("#", "label")):
        if s == mark or s.startswith(mark + " "):
            rest = s[1:]
            if rest.startswith(" "):
                rest = rest[1:]
            sub = len(rest) - len(rest.lstrip(" "))   # for "+", the spaces after the marker set the indent
            return kind, rest.strip(), sub if kind == "cont" else ind
    return "line", s, ind


def legacy_numbers(text):
    """{source line index: printed number} when the text still carries UIL's printed numbers, else {}."""
    found = {}
    for i, line in enumerate(_split(text)):
        m = LEGACY.match(line)
        if m and line.strip() and not line.lstrip().startswith(("* ", "# ")):
            found[i] = int(m.group(2))
    # A single stray match (e.g. "Psalm  23" in a heading) is not a numbering run.
    return found if len(found) >= 2 or (found and max(found.values()) in (3, 4, 5, 6)) else {}


def stanza_lengths(kinds):
    """Counted lines per stanza; a gap or a label ends a stanza."""
    out, cur = [], 0
    for k in kinds:
        if k == "line":
            cur += 1
        elif k in ("gap", "label") and cur:
            out.append(cur); cur = 0
    if cur:
        out.append(cur)
    return out


def auto_interval(kinds, layout=None, excerpt=False):
    """The Auto rule. 0 means no numbers. Short pieces get none, but an excerpt keeps its numbering."""
    count = sum(1 for k in kinds if k == "line")
    if layout == "Prose (paragraphs)":
        return 0
    if layout == "Prose (UIL lines)":
        return 1 if count <= 12 else 5
    if count <= 5 and not excerpt:
        return 0
    st = stanza_lengths(kinds)
    if len(st) == 1:
        return 4 if count <= 16 else 5
    body = st[:-1]
    if len(set(body)) == 1:
        L = body[0]
        if L % 4 == 0:
            return 4
        if L % 3 == 0:
            return 3
        return 5
    return 5


def number(text, numbering=None, start=None, layout=None, blank="Auto"):
    """Rows for a poem or passage. See the module docstring. `blank` is the setting used when
    Line Numbering is empty (the site passes "None" until every record has been migrated)."""
    lines = _split(text)
    # Only an unconverted record (Line Numbering still blank) can hold printed numbers.
    legacy = {} if numbering else legacy_numbers(text)
    rows = []
    if legacy:
        # Old text: keep UIL's printed numbers where they were printed; count nothing.
        for i, line in enumerate(lines):
            if i in legacy:
                line = LEGACY.match(line).group(1)
            kind, body, ind = _parse(line)
            if kind == "cont":
                kind = "line"
            shown = str(legacy[i]) if i in legacy else ""
            rows.append(Row(kind, body, ind, legacy.get(i), shown))
        return rows

    parsed = [_parse(l) for l in lines]
    kinds = [k for k, _, _ in parsed]
    try:
        n = int(start) - 1 if start not in (None, "") else 0
    except (TypeError, ValueError):
        n = 0
    numbering = numbering or blank
    if numbering in EVERY:
        every = EVERY[numbering]
    else:  # "Auto" or blank
        every = auto_interval(kinds, layout, excerpt=n > 0)
    if layout == "Prose (paragraphs)":
        every = 0
    # Count lines; a line's number prints on its last physical row (after any + turnovers).
    counted = []
    for kind, body, ind in parsed:
        if kind == "line":
            n += 1
        counted.append(n if kind in ("line", "cont") else None)
    last_row = {}
    for i, (kind, _, _) in enumerate(parsed):
        if kind in ("line", "cont") and counted[i]:
            last_row[counted[i]] = i
    for i, (kind, body, ind) in enumerate(parsed):
        num = counted[i]
        show = ""
        if every and num and last_row.get(num) == i and num % every == 0:
            show = str(num)
        rows.append(Row(kind, body, ind, num, show))
    return rows


def has_numbers(rows):
    return any(r.show for r in rows)


def plain(rows):
    """The text without markers or numbers (for search, previews and copy)."""
    return "\n".join((" " * r.indent + r.text) if r.kind != "gap" else "" for r in rows)


# ---------------------------------------------------------------- self-test

def _check():
    def shown(rows):
        return [(r.text, r.show) for r in rows if r.show]

    sonnet = "\n".join(f"line {i}" for i in range(1, 15))
    assert [s for _, s in shown(number(sonnet))] == ["4", "8", "12"]
    quatrains = "\n\n".join("\n".join(f"s{j} l{i}" for i in range(4)) for j in range(4))
    assert [s for _, s in shown(number(quatrains))] == ["4", "8", "12", "16"]
    villanelle = "\n\n".join(["a\nb\nc"] * 5 + ["a\nb\nc\nd"])
    assert [s for _, s in shown(number(villanelle))] == ["3", "6", "9", "12", "15", "18"]
    blank = "\n".join(f"line {i}" for i in range(1, 23))
    assert [s for _, s in shown(number(blank))] == ["5", "10", "15", "20"]
    assert shown(number("one\ntwo\nthree")) == []                         # short piece
    assert [s for _, s in shown(number("a\nb\nc\nd", start=9))] == ["12"]  # excerpt: London, 2026 S
    turn = "one\ntwo\nthree\n+     turned over\nfour\nfive"
    r = number(turn, numbering="Every 4")
    assert [(x.kind, x.show) for x in r][2:4] == [("line", ""), ("cont", "")] and r[4].show == "4"
    turn2 = "one\ntwo\nthree\nfour that wraps\n+   over"
    r = number(turn2, numbering="Every 4")
    assert r[3].show == "" and r[4].show == "4" and r[4].indent == 2
    glossed = "one\ntwo\nthree\n* spar: pole\nfour"
    assert number(glossed, numbering="Every 4")[4].show == "4"
    labelled = "# I\na\nb\nc\nd\n\n# II\ne\nf\ng\nh"
    assert [s for _, s in shown(number(labelled))] == ["4", "8"]
    prose = "\n".join(f"prose {i}" for i in range(1, 13))
    assert len(shown(number(prose, layout="Prose (UIL lines)"))) == 12
    assert shown(number(prose, layout="Prose (paragraphs)")) == []
    assert shown(number(blank, numbering="None")) == []
    assert shown(number(blank, blank="None")) == [] and len(shown(number(blank, "Every 4", blank="None"))) == 5
    # Transition: printed numbers in old text are kept and stripped from the line.
    old = ("            The Illiterate\n\nTouching your goodness, I am like a man\nWho turns a letter over in his hand\n"
           "And you might think that this was because the\n    hand\nWas unfamiliar but, truth is, the man             4\n"
           "Has never had a letter from anyone;\nAnd now he is both afraid of what it means\nAnd ashamed because he has no other means\n"
           "To find out what it says            8")
    r = number(old)
    assert shown(r) == [("Was unfamiliar but, truth is, the man", "4"), ("To find out what it says", "8")]
    print("linenums: all checks passed")


if __name__ == "__main__":
    _check()
