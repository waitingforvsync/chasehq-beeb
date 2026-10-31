"""Put trailing ; comments on column 40 (style.md), or 44 where the code runs past it, in Baron files.

    python tools/aligncomments.py src/irq.6502 ...

Whole-line comments, comments inside strings, and cycle counts (a comment starting with a digit, as in the
vsync sync loop) are left as they are.
"""
import sys


def split(line):
    """The line's code and its trailing comment (from the ;), or None."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in '"\'':
            quote = ch
        elif ch == ';':
            return line[:i].rstrip(), line[i:]
        elif ch == '\\' and line[i:i + 2] == '\\\\':
            return None
    return None


def align(line):
    parts = split(line)
    if not parts:
        return line
    code, comment = parts
    if not code.strip() or comment[1:].lstrip()[:1].isdigit():
        return line
    col = 40 if len(code) < 39 else 44 if len(code) < 43 else len(code) + 1
    return code.ljust(col) + comment


for path in sys.argv[1:]:
    with open(path) as f:
        lines = f.read().split('\n')
    with open(path, 'w') as f:
        f.write('\n'.join(align(line) for line in lines))
