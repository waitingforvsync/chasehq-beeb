"""Make build/gen/ from the CPC disc: the BBC's data, in its final form (MODE 2 bytes, character cells).

    python tools/gendata.py build/gen

writes
    gen.6502    PenEven, PenOdd: each CPC game pen's dithered MODE 2 byte on even and odd lines
    panel.bin   the dashboard, 8 rows of 512 bytes, dithered
    panel.png   a preview of it, at the BBC's aspect
    siren.6502  SirenPal: the sirens' two palettes (for main RAM)
    (in gen.6502) PanelGlyphs: the dashboard's font (HI, LO, then 0-9), each 2 bytes by 8 lines as 16 bytes,
                its left column's 8 lines then its right's: a glyph's two character cells in a row, as the
                panel has them

Colours (D5, D7): each CPC channel is 0, half or full, so every CPC colour is the average of two BBC
colours; of the pairs that average to it, the two closest in brightness (Rec. 601 luma) are taken. A pixel
at (x, y) shows the pair's first colour where x + y is even, the second where it's odd. The palette is the
identity (logical 0-7 are physical 0-7), so the bytes hold BBC colours.

The sirens (the panel's two lights) flash by swapping (the CPC swaps their bytes in one of its two buffers).
Here each light pixel takes a logical colour 8-15 standing for its pair of colours, its own and the other
light's there, and the flash is a palette: no bytes move. Logical 8-15 are free (nothing drawn has bit 3 set).
"""
import os
import sys
from itertools import combinations_with_replacement

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from cpc import CPC, mode0_pens                     # noqa: E402

LUMA = (0.299, 0.587, 0.114)
BBC_RGB = [((c & 1) * 255, (c >> 1 & 1) * 255, (c >> 2 & 1) * 255) for c in range(8)]   # BBC colour c


def cpc_levels(hw):
    """A CPC hardware colour's guns as 0, 1 (half) or 2 (full)."""
    from cpc import HWRGB
    return tuple({0: 0, 128: 1, 255: 2}[g] for g in HWRGB[hw])


def bbc_bits(c):
    return (c & 1, c >> 1 & 1, c >> 2 & 1)


def luma(c):
    return sum(w * b for w, b in zip(LUMA, bbc_bits(c)))


def pair_for(hw):
    """A CPC colour's BBC pair (D7): the darker first."""
    want = cpc_levels(hw)
    best = None
    for a, b in combinations_with_replacement(range(8), 2):
        if all(x + y == w for x, y, w in zip(bbc_bits(a), bbc_bits(b), want)):
            key = (abs(luma(a) - luma(b)), a, b)
            best = key if best is None or key < best else best
    _, a, b = best
    return (a, b) if luma(a) <= luma(b) else (b, a)


def right_pixel(c):
    return (c & 1) | (c & 2) << 1 | (c & 4) << 2 | (c & 8) << 3


def mode2_byte(left, right):
    return right_pixel(left) << 1 | right_pixel(right)


def dither(pairs, pen, x, y):
    a, b = pairs[pen]
    return a if (x + y) & 1 == 0 else b


def cpc_after_init():
    """The CPC as the game starts (&0300): the panel drawn at &C000, the game's inks set."""
    m = CPC()
    assert m.run_to(0x0300)
    return m


LIGHTS = (2, 56)                                    # the lights' first bytes, 6 wide, on lines 8-39
LIGHT_W = 6
LIGHT_LINES = range(8, 40)


def panel_colour(m, pairs, x, y):
    """The dashboard's BBC colour at pixel (x, y), dithered."""
    pens = mode0_pens(m.mem[0xC000 + (y >> 3) * 64 + (y & 7) * 0x800 + (x >> 1)])
    return dither(pairs, pens[x & 1], x, y)


def siren_colours(m, pairs):
    """The lights' pixels: {(x, y): logical colour}, and the 8 (normal, swapped) pairs that 8-15 stand for.
    A pixel whose pair is one colour twice keeps it. More than 8 pairs: the rarest take the commonest with
    their normal colour (only the flash is approximate)."""
    want = {}
    for i, first in enumerate(LIGHTS):
        other = LIGHTS[1 - i]
        for y in LIGHT_LINES:
            for dx in range(2 * LIGHT_W):
                x = 2 * first + dx
                want[(x, y)] = (panel_colour(m, pairs, x, y), panel_colour(m, pairs, 2 * other + dx, y))
    counts = {}
    for pair in want.values():
        if pair[0] != pair[1]:
            counts[pair] = counts.get(pair, 0) + 1
    kept = sorted(counts, key=lambda p: -counts[p])[:8]
    out = {}
    for xy, pair in want.items():
        if pair[0] == pair[1]:
            out[xy] = pair[0]
            continue
        if pair not in kept:
            pair = max((k for k in kept if k[0] == pair[0]), key=lambda k: counts[k])
        out[xy] = 8 + kept.index(pair)
    return out, kept


def panel_bytes(m, pairs, lights):
    """The dashboard: the CPC's top 64 lines at &C000, as BBC character cells, dithered; the lights' pixels
    their logical colours."""
    out = bytearray(8 * 512)
    for y in range(64):
        for xb in range(64):
            c = [lights.get((x, y), None) for x in (2 * xb, 2 * xb + 1)]
            c = [panel_colour(m, pairs, x, y) if v is None else v for x, v in zip((2 * xb, 2 * xb + 1), c)]
            out[(y >> 3) * 512 + xb * 8 + (y & 7)] = mode2_byte(*c)
    return out


def preview(cells, rows, path, siren=()):
    """A PNG of MODE 2 character cells (64 bytes a line), 4 x 2 a pixel as the BBC shows them; logical 8-15
    as siren's first colours (the palette's normal state)."""
    img = Image.new('RGB', (128 * 4, rows * 8 * 2))
    px = img.load()
    for y in range(rows * 8):
        for xb in range(64):
            b = cells[(y >> 3) * 512 + xb * 8 + (y & 7)]
            for k, shift in ((0, 1), (1, 0)):
                c = sum((b >> (shift + 2 * i) & 1) << i for i in range(4))
                c = siren[c - 8][0] if c >= 8 else c
                for dx in range(4):
                    for dy in range(2):
                        px[(2 * xb + k) * 4 + dx, y * 2 + dy] = BBC_RGB[c]
    img.save(path)


def main(out):
    os.makedirs(out, exist_ok=True)
    m = cpc_after_init()
    pairs = [pair_for(m.inks[p]) for p in range(16)]
    even = [mode2_byte(a, b) for a, b in pairs]
    odd = [mode2_byte(b, a) for a, b in pairs]
    lights, siren = siren_colours(m, pairs)
    panel = panel_bytes(m, pairs, lights)
    with open(os.path.join(out, 'siren.6502'), 'w') as f:
        f.write('\\\\ siren.6502 - made by tools/gendata.py from the CPC disc: do not edit.\n\n')
        f.write('\\\\ the lights\' logical colours 8-15 as video ULA palette writes: normal, then swapped\n\n')
        f.write('.SirenPal\n')
        for state in (0, 1):
            f.write('    EQUB ' + ', '.join(f'&{(8 + k) << 4 | (p[state] ^ 7):02X}' for k, p in enumerate(siren))
                    + '\n')
    with open(os.path.join(out, 'panel.bin'), 'wb') as f:
        f.write(panel)
    preview(panel, 8, os.path.join(out, 'panel.png'), siren)
    with open(os.path.join(out, 'gen.6502'), 'w') as f:
        f.write('\\\\ gen.6502 - made by tools/gendata.py from the CPC disc: do not edit.\n\n')
        f.write('\\\\ each CPC game pen\'s dithered MODE 2 byte (D7), on even and odd lines\n\n')
        f.write('.PenEven\n    EQUB ' + ', '.join(f'&{b:02X}' for b in even) + '\n')
        f.write('.PenOdd\n    EQUB ' + ', '.join(f'&{b:02X}' for b in odd) + '\n')
        f.write('\n\\\\ the damage meter\'s bars (the CPC\'s &1553, by hits / 5): bytes 2 and 3 on even lines, then odd\n\n')
        f.write('.MeterBars\n')
        assert mode0_pens(0xC0) == (1, 1) and pairs[1] == (0, 0), 'the meter\'s black: 0'
        for level in range(5):
            cpc = m.mem[0x1553 + 2 * level:0x1555 + 2 * level]
            out_ = []
            for y in (0, 1):
                for xb, byte in zip((2, 3), cpc):
                    pl, pr = mode0_pens(byte)
                    out_.append(mode2_byte(dither(pairs, pl, 2 * xb, y), dither(pairs, pr, 2 * xb + 1, y)))
            f.write('    EQUB ' + ', '.join(f'&{b:02X}' for b in out_) + '\n')
        f.write('\n\\\\ the dashboard\'s font: HI, LO, then 0-9, each its two columns of 8 lines\n\n.PanelGlyphs\n')
        for g in range(14):
            cells = []
            for col in (0, 1):
                for line in range(8):
                    left, right = mode0_pens(m.mem[0xE600 + 16 * g + 2 * line + col])
                    x = 2 * col
                    cells.append(mode2_byte(dither(pairs, left, x, line), dither(pairs, right, x + 1, line)))
            f.write('    EQUB ' + ', '.join(f'&{b:02X}' for b in cells) + '\n')
    names = 'black red green yellow blue magenta cyan white'.split()
    for p, (a, b) in enumerate(pairs):
        print(f'pen {p:2d}: hardware {m.inks[p]:2d} -> {names[a]}/{names[b]}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'build/gen')
