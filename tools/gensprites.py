"""The sprites for the BBC, in their final form, from the CPC (docs/cpc-sprites.md).

    python tools/gensprites.py build/gen

writes sprites.6502 for the data's bank: each sprite as MODE 2 bytes, a column at a time (each column's lines
top first, as the plotter's Y runs down a character cell), and a table of them: SprW, SprH, SprStep (a
column's bytes less 8, signed), SprLo and SprHi (its bytes less 8). A tiled sprite's columns carry their first
7 lines again after their last (h + 7 bytes), so 8 lines read on from any of its rows wrap.

Colours (D7, D8): a transparent pixel (CPC pen 0) is logical 8; a byte below &40 is wholly opaque, the
screen's byte. The rest are coded for the plotter: &FF wholly transparent, &80 + c the left pixel
transparent and the right logical c, &88 + c the right transparent and the left c (MaskTab, OrTab). Opaque
pens take their D7 pairs over 2x2 blocks of the sprite's own pixels (its dither fixed to it): a pen on two of
a block's pixels takes its pair one colour each, otherwise each pixel its pair's by x + y parity.

The player's car (all of its frames, and each mirrored, since it's drawn every loop); the turbo icon (a list,
TurboIcon, that draw_turbos compiles into the code's bank); the stage's roadside
objects, as part lists by side, id and size (ObjPartLo, ObjPartHi: records of sprite, X offset, kind; kind 1
ends a list); its cars by size (CarSprite).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cpc import CPC, mode0_pens                     # noqa: E402
from cpcdsk import read_dsk                         # noqa: E402
from gendata import pair_for, mode2_byte            # noqa: E402

TRANSPARENT = 8


def cpc_pens(mem, ptr, w, h):
    """A CPC sprite's pens: [line][pixel], line 0 the bottom (as stored)."""
    rows = []
    for r in range(h):
        row = []
        for b in mem[ptr + r * w:ptr + r * w + w]:
            row += mode0_pens(b)
        rows.append(row)
    return rows


def colours(pens, inks):
    """The BBC colours of a sprite's pens, by 2x2 blocks of its own pixels (D7); pen 0 transparent."""
    h, w = len(pens), len(pens[0])
    out = [[TRANSPARENT] * w for _ in range(h)]
    for y0 in range(0, h, 2):
        for x0 in range(0, w, 2):
            cells = [(x0, y0), (x0 + 1, y0), (x0, y0 + 1), (x0 + 1, y0 + 1)]
            block = [pens[y][x] if y < h and x < w else 0 for x, y in cells]
            seen = {}
            for k, ((x, y), p) in enumerate(zip(cells, block)):
                if p == 0 or y >= h or x >= w:
                    continue
                a, b = pair_for(inks[p])
                if block.count(p) == 2:
                    out[y][x] = (a, b)[seen.get(p, 0)]
                    seen[p] = 1
                else:
                    out[y][x] = (a, b)[(x + y) & 1]
    return out


def code(b):
    """A MODE 2 byte (logical 8 transparent) as the plotter reads it: opaque as it is, else &FF, &80 + the
    right pixel's colour (the left transparent) or &88 + the left's (the right transparent)."""
    left, right = b >> 1 & 0x55, b & 0x55               # each pixel's bits, as a right pixel's
    pixel = lambda bits: (bits & 1) | (bits >> 1 & 2) | (bits >> 2 & 4) | (bits >> 3 & 8)
    lc, rc = pixel(left), pixel(right)
    if lc < 8 and rc < 8:
        return b
    if lc >= 8 and rc >= 8:
        return 0xFF
    return 0x80 + rc if lc >= 8 else 0x88 + lc


def columns(cols, mirror=False):
    """Colours [line][pixel] -> the bytes, coded, column by column, each column's lines top first."""
    h, w = len(cols), len(cols[0])
    if mirror:
        cols = [row[::-1] for row in cols]
    data = bytearray()
    for bx in range(w // 2):
        for y in reversed(range(h)):
            data.append(code(mode2_byte(cols[y][2 * bx], cols[y][2 * bx + 1])))
    return data


def tile(data, h):
    """A tiled sprite's columns, each followed by its first 7 lines again (cyclically)."""
    out = bytearray()
    for c in range(0, len(data), h):
        col = data[c:c + h]
        out += bytes(col[i % h] for i in range(h + 7))
    return out


BASE = 0x59AB                                       # the stage block's address
KINDS = {0x26BA: 1, 0x26B5: 1, 0x2723: 2, 0x26E0: 2, 0x25D9: 3, 0x25D4: 3, 0x2474: 4}   # raised, ground, composite, gantry


class Stage:
    """A stage's objects and cars, from its block and the main memory."""

    def __init__(self, mem, block, inks):
        self.mem, self.block, self.inks = mem, block, inks
        self.sprites = []                           # (name, w, h, data)
        self.index = {}                             # (data, w, h, mirrored) -> sprite number

    def rd(self, a):
        return self.block[a - BASE] if BASE <= a < BASE + len(self.block) else self.mem[a]

    def rw(self, a):
        return self.rd(a) | self.rd(a + 1) << 8

    def sprite(self, header, name):
        """The sprite for a CPC header (w, flags, h, data), converted once (mirrored ones on their own)."""
        w, fl, h, data = self.rd(header), self.rd(header + 1), self.rd(header + 2), self.rw(header + 3)
        key = (data, w, h, fl & 1)
        if key not in self.index:
            pens = [[] for _ in range(h)]
            for r in range(h):
                for b in range(w):
                    pens[r] += mode0_pens(self.rd(data + r * w + b))
            self.index[key] = len(self.sprites)
            self.sprites.append((f'{name}{len(self.sprites)}', w, h, columns(colours(pens, self.inks), bool(fl & 1))))
        return self.index[key]

    def parts(self, kind, desc, s):
        """An object's parts at size s (1-10): (sprite, X offset, kind) with kind 0 single, 2 fixed, 3-10 tiled."""
        if kind in (1, 2):
            base = self.rw(desc)
            xoff, hoff = self.rd(desc + 2 * s), self.rd(desc + 2 * s + 1)
            return [(self.sprite(base + hoff, 'Obj'), xoff, 0)]
        out = []
        p = desc
        while self.rd(p) != 1:
            t, pd = self.rd(p), self.rw(p + 1)
            base = self.rw(pd)
            xoff, off = self.rd(pd + 2 * s), self.rd(pd + 2 * s + 1)
            out.append((self.sprite(base + off - 2, 'Obj'), xoff, t))
            p += 3
        return out


def main(out, stage=1):
    os.makedirs(out, exist_ok=True)
    m = CPC()
    assert m.run_to(0x0300)
    mem = bytes(m.mem)
    inks = list(m.inks)
    sprites = []                                    # (name, w bytes, h, data)
    for kind, table, count in (('Body', 0x53D3, 9), ('Wheels', 0x53F7, 3)):
        for i in range(count):
            w, h, lo, hi = mem[table + 4 * i:table + 4 * i + 4]
            cols = colours(cpc_pens(mem, lo | hi << 8, w, h), inks)
            sprites.append((f'Car{kind}{i}', w, h, columns(cols)))
            sprites.append((f'Car{kind}{i}M', w, h, columns(cols, mirror=True)))
    turbo = columns(colours(cpc_pens(mem, 0x8FBD, 4, 16), inks))   # the icon (&2193), compiled by draw_turbos

    # the stage's objects: side 0 right, 1 left; ids 0-9; sizes 1-10
    files = read_dsk(os.path.join(os.path.dirname(__file__), '..', 'docs', 'chasehq.dsk'))
    st = Stage(mem, files[f'CHASEHQ.LV{stage}']['data'], inks)
    st.sprites = sprites
    kinds, lists, records = [], [], []
    seen = {}
    for side, ptr in ((0, 0x5BCE), (1, 0x5BD4)):
        table = st.rw(ptr)
        for i in range(10):
            desc, handler = (st.rw(table + 7 * i), st.rw(table + 7 * i + 2)) if i else (0, 0)
            kind = KINDS.get(handler, 0) if desc else 0
            kinds.append(kind)
            for size in range(1, 11):
                parts = tuple(st.parts(kind, desc, size)) if kind in (1, 2, 3) else ()
                if parts not in seen:
                    seen[parts] = len(records)
                    records += list(parts) + [(0, 0, 1)]
                lists.append(seen[parts])
    assert all(0 <= x < 128 for _, x, _ in records), 'draw_objects takes X offsets of 0-127'
    tiled = {sp for sp, _, k in records if k >= 3}
    for n in tiled:
        name, w, h, data = sprites[n]
        sprites[n] = (name, w, h, tile(data, h))
    # the cars: criminal first, each six sizes (0-5)
    cars = []
    for c in range(5):
        desc = st.rw(0x5BE6 + 2 * c)
        cars += [st.sprite(desc + 5 * k, 'CarImg') for k in range(6)]
    obst = st.rw(0x5BCC)                            # the obstacles (cones, barriers) as models 5 and 6
    for k in range(2):
        desc = st.rw(obst + 3 * k + 1)
        cars += [st.sprite(desc + 5 * s, 'CarImg') for s in range(6)]

    with open(os.path.join(out, 'sprites.6502'), 'w') as f:
        f.write('\\\\ sprites.6502 - made by tools/gensprites.py from the CPC disc: do not edit.\n\n')
        for n, (name, w, h, data) in enumerate(sprites):
            if name.startswith('Car') and not name.startswith('CarImg'):
                f.write(f'Spr{name} = {n}\n')
        f.write(f'SpriteCount = {len(sprites)}\n\n')
        f.write('TurboIcon = {' + ', '.join(f'&{v:02X}' for v in turbo) + '}   ; 4 x 16, coded: draw_turbos compiles it\n\n')
        assert len(sprites) <= 256
        steps = [len(x[3]) // x[1] - 8 & 255 for x in sprites]   # a column's bytes less 8, signed
        for lab, vals in (('SprW', [x[1] for x in sprites]), ('SprH', [x[2] for x in sprites]), ('SprStep', steps)):
            for i in range(0, len(vals), 32):
                f.write((f'.{lab}\n' if i == 0 else '') + '    EQUB ' + ', '.join(str(v) for v in vals[i:i + 32]) + '\n')
        for lab, fn in (('SprLo', 'LO'), ('SprHi', 'HI')):         # each sprite's bytes, less 8
            for i in range(0, len(sprites), 8):
                f.write((f'.{lab}\n' if i == 0 else '') + '    EQUB ' + ', '.join(f'{fn}(SprData{x[0]} - 8)' for x in sprites[i:i + 8]) + '\n')
        f.write('\n\\\\ the stage\'s roadside objects: kind by side * 10 + id (0 none, 1 raised, 2 on the ground, 3 parts,\n')
        f.write('\\\\ 4 the gantry); part lists by (side * 10 + id) * 10 + size - 1\n\n')
        f.write('.ObjKind\n    EQUB ' + ', '.join(str(k) for k in kinds) + '\n')
        for lab, fn in (('ObjPartLo', 'LO'), ('ObjPartHi', 'HI')):
            for i in range(0, len(lists), 10):
                f.write((f'.{lab}\n' if i == 0 else '') + '    EQUB ' + ', '.join(f'{fn}(ObjParts + {3 * x})' for x in lists[i:i + 10]) + '\n')
        f.write('.ObjParts                                   ; sprite, X offset (quarter-bytes), kind (1 the end)\n')
        for i in range(0, len(records), 6):
            f.write('    EQUB ' + ', '.join(f'{a}, {b}, {c}' for a, b, c in records[i:i + 6]) + '\n')
        f.write('\n.CarSprite                                  ; the stage\'s cars (the criminal first), then its obstacles, by size 0-5\n')
        f.write('    EQUB ' + ', '.join(str(c) for c in cars) + '\n\n')
        for name, w, h, data in sprites:
            f.write(f'.SprData{name}                                   ; {w} x {h}, a column at a time, top first\n')
            for i in range(0, len(data), 16):
                f.write('    EQUB ' + ', '.join(f'&{v:02X}' for v in data[i:i + 16]) + '\n')
    print(len(sprites), 'sprites,', sum(len(x[3]) for x in sprites), 'bytes,', len(records), 'part records')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'build/gen')
