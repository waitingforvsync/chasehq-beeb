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


STAGES = (1, 2, 3, 4, 5)
CAR_SPRITES = 24                                    # the player's car's, the same in every stage: 0-23


def stage_sprites(stage, files, mem, inks):
    """A stage's sprites (the player's car first), its objects' kinds, part lists and records, its cars."""
    sprites = []                                    # (name, w bytes, h, data)
    for kind, table, count in (('Body', 0x53D3, 9), ('Wheels', 0x53F7, 3)):
        for i in range(count):
            w, h, lo, hi = mem[table + 4 * i:table + 4 * i + 4]
            cols = colours(cpc_pens(mem, lo | hi << 8, w, h), inks)
            sprites.append((f'Car{kind}{i}', w, h, columns(cols)))
            sprites.append((f'Car{kind}{i}M', w, h, columns(cols, mirror=True)))
    assert len(sprites) == CAR_SPRITES

    # the stage's objects: side 0 right, 1 left; ids 0-9; sizes 1-10
    st = Stage(mem, files[f'CHASEHQ.LV{stage}']['data'], inks)
    st.sprites = sprites
    kinds, lists, records = [], [], []
    seen = {}
    for side, ptr in ((0, 0x5BCE), (1, 0x5BD4)):
        table = st.rw(ptr)
        for i in range(10):
            desc, handler = (st.rw(table + 7 * i), st.rw(table + 7 * i + 2)) if i else (0, 0)
            kind = KINDS.get(handler, 0) if desc else 0
            if kind == 4 and (side, i) != (1, 2):
                # (stage 3's right id 8, never placed: from the right the CPC's beam would end at the next row's
                # left edge, before it starts. Its pylon alone)
                kind = 3
            kinds.append(kind)
            for size in range(1, 11):
                parts = tuple(st.parts(3 if kind == 4 else kind, desc, size)) if kind in (1, 2, 3, 4) else ()
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
    # the airborne patrol's helicopter (docs/cpc-stages.md), if the stage has one: its frame lists at (&5BDE)
    # and (&5BE0), odd loops' the first's images mirrored; each two parts, an x offset then a header: the
    # helicopter at x + 0, its shadow at x + 8. Four sprites from HeliSprite: each frame's two parts
    heli = 0
    lists2 = [st.rw(0x5BDE), st.rw(0x5BE0)]
    if all(a >= BASE for a in lists2):
        heli = len(sprites)
        for k, fl in enumerate(lists2):
            for part, xoff in ((0, 0), (1, 8)):
                p = st.rw(fl + 2 * part)
                assert st.rd(p) == xoff, f'stage {stage}: the helicopter\'s part {part} at x + {st.rd(p)}'
                n = st.sprite(p + 1, 'Heli')
                assert n == heli + 2 * k + part, 'the helicopter\'s sprites one after another'
    assert len(sprites) <= 256
    # the gantry's beam (left id 2, kind 4: the CPC's &2474), if the stage has one: by size, its pylon's x
    # (at its first part's descriptor + 2 + 2(size - 1)), its height and a colour byte a line from the bottom
    # (+ 22 + 3(size - 1)), each line's as its fill byte for the line's parity (the pens' D7 pairs by x + y
    # parity): a list's line k from the bottom, line bottom - k on the screen, in GantryEven for an even bottom
    # and GantryOdd for an odd one
    beam = None
    table = st.rw(0x5BD4)
    desc, handler = st.rw(table + 7 * 2), st.rw(table + 7 * 2 + 2)
    if KINDS.get(handler) == 4:
        pd = st.rw(desc + 1)
        heights, lists_ = [], {}
        xoffs = [st.rd(pd + 2 + 2 * (s - 1)) for s in range(1, 11)]
        assert all(x > 0 for x in xoffs), 'the beam\'s right end: 0 only with a carry (gantry_beam)'
        for s in range(1, 11):
            h, at = st.rd(pd + 22 + 3 * (s - 1)), st.rw(pd + 23 + 3 * (s - 1))
            heights.append((h, at))
            lists_[at] = max(lists_.get(at, 0), h)
        beam_bytes, offsets = [], {}
        for at, h in sorted(lists_.items()):
            offsets[at] = len(beam_bytes)
            for k in range(h):
                lp, rp = mode0_pens(st.rd(at + k))
                fill = [mode2_byte(pair_for(inks[lp])[(0 + y) & 1], pair_for(inks[rp])[(1 + y) & 1]) for y in (0, 1)]
                beam_bytes.append((fill[k & 1], fill[(1 + k) & 1]))   # (the bottom even, odd)
        assert all(h for h, _ in heights), 'a beam of 0 lines (the CPC would draw 256)'
        beam = ([h for h, _ in heights], [offsets[at] for _, at in heights], xoffs, beam_bytes)
    return sprites, kinds, lists, records, cars, heli, beam


def main(out):
    os.makedirs(out, exist_ok=True)
    m = CPC()
    assert m.run_to(0x0300)
    mem = bytes(m.mem)
    inks = list(m.inks)
    files = read_dsk(os.path.join(os.path.dirname(__file__), '..', 'docs', 'chasehq.dsk'))
    turbo = columns(colours(cpc_pens(mem, 0x8FBD, 4, 16), inks))   # the icon (&2193), compiled by draw_turbos
    per = {s: stage_sprites(s, files, mem, inks) for s in STAGES}
    cars = per[1][0][:CAR_SPRITES]
    for s in STAGES:
        assert per[s][0][:CAR_SPRITES] == cars, f'stage {s}: the player\'s car differs'
    most = max(len(per[s][0]) for s in STAGES)      # the tables' entries: the most sprites a stage has
    var = {s: 3 * len(per[s][3]) + sum(len(x[3]) for x in per[s][0][CAR_SPRITES:]) for s in STAGES}
    helis = [s for s in STAGES if per[s][5]]
    room = max(var.values())                        # the parts and the stage's own sprites
    # the helicopter's four sprites, the same in every stage that has one: kept once (heli.6502's pack) at
    # the slot's end, HeliData, the stage's own below it
    heli_sprites = [per[s][0][per[s][5]:per[s][5] + 4] for s in helis]
    assert all([x[1:] for x in hs] == [x[1:] for x in heli_sprites[0]] for hs in heli_sprites), 'the helicopters differ'
    heli_bytes = sum(len(x[3]) for x in heli_sprites[0]) if helis else 0
    own_room = max(var[s] - (heli_bytes if per[s][5] else 0) for s in STAGES)  # the parts' piece

    with open(os.path.join(out, 'sprites.6502'), 'w') as f:
        f.write('\\\\ sprites.6502 - made by tools/gensprites.py from the CPC disc: do not edit. The player\'s car;\n')
        f.write('\\\\ the stages\' slot at the bank\'s end is spriteslot.6502.\n\n')
        for n, (name, w, h, data) in enumerate(cars):
            f.write(f'Spr{name} = {n}\n')
        f.write(f'SprTableSize = {most}                    ; the sprite tables\' entries: the most sprites a stage has\n\n')
        f.write('TurboIcon = {' + ', '.join(f'&{v:02X}' for v in turbo) + '}   ; 4 x 16, coded: draw_turbos compiles it\n\n')
        for name, w, h, data in cars:
            f.write(f'.SprData{name}                                   ; {w} x {h}, a column at a time, top first\n')
            for i in range(0, len(data), 16):
                f.write('    EQUB ' + ', '.join(f'&{v:02X}' for v in data[i:i + 16]) + '\n')
        beams = [per[s][6] for s in STAGES if per[s][6]]
        beam_lines = max((len(b[3]) for b in beams), default=0)
        assert 2 * beam_lines <= 256 and max((max(b[0]) for b in beams), default=0) <= 32, 'BeamBuf: 32 lines'

        slot = 20 + 2 * 200 + 42 + 1 + 30 + 2 * beam_lines + room  # (the five sprite tables in main RAM, GameVars)
    with open(os.path.join(out, 'spriteslot.6502'), 'w') as f:
        f.write('\\\\ spriteslot.6502 - made by tools/gensprites.py: the stages\' slot at the data bank\'s end.\n')
        f.write('\n\\\\ the stage\'s sprite tables, in main RAM (decisions D22): SprW, SprH, SprStep (a column\'s bytes less\n')
        f.write('\\\\ 8, signed), SprLo and SprHi (its bytes less 8) by sprite\n\n')
        f.write('SECTION GameVars\n')
        for lab in ('SprW', 'SprH', 'SprStep', 'SprLo', 'SprHi'):
            f.write(f'.{lab}\n    SKIP {most}\n')
        f.write('ENDSECTION\n')
        f.write('\n\\\\ the stage\'s slot (spritestageN.6502\'s Stage<n>Data and Parts, filled whole): its roadside objects\' kinds by\n')
        f.write('\\\\ side * 10 + id (0 none, 1 raised, 2 on the ground, 3 parts, &80 the gantry); their part lists by\n')
        f.write('\\\\ (side * 10 + id) * 10 + size - 1; its cars (the criminal first) then its obstacles, by size 0-5;\n')
        f.write('\\\\ its helicopter\'s first sprite (0 none; then its shadow, then both mirrored); then its parts and its\n')
        f.write('\\\\ own sprites\n\n')
        f.write(f'DataSlotBytes = {slot}\n')
        f.write(f'HeliData = DataVarsOrg - {heli_bytes}            ; the helicopter\'s sprites, the slot\'s last (heli.6502)\n')
        f.write('    PADTO DataVarsOrg - DataSlotBytes\n')
        for lab, n in (('ObjKind', 20), ('ObjPartLo', 200), ('ObjPartHi', 200), ('CarSprite', 42),
                       ('HeliSprite', 1), ('GantryX', 10), ('GantryHeight', 10), ('GantryAt', 10),
                       ('GantryEven', beam_lines), ('GantryOdd', beam_lines), ('DataSlotParts', room)):
            f.write(f'.{lab}\n    SKIP {n}\n')

    for s in STAGES:
        sprites, kinds, lists, records, carsp, heli, beam = per[s]
        n = len(sprites)
        pad = lambda vals, fill=0: vals + [fill] * (most - len(vals))
        steps = [len(x[3]) // x[1] - 8 & 255 for x in sprites]   # a column's bytes less 8, signed
        with open(os.path.join(out, f'spritestage{s}.6502'), 'w') as f:
            f.write(f'\\\\ spritestage{s}.6502 - made by tools/gensprites.py: stage {s}\'s slot in the data\'s bank\n')
            f.write('\\\\ (sprites.6502\'s), rephased to its place: its sprite tables, objects, cars, parts and sprites.\n\n')
            f.write(f'.Stage{s}Sprites                             ; (its packs: Stage{s}Sprites.DataPack, .PartsPack)\n{{\n')
            f.write('.DataPack\n')
            f.write(f'    SECTION Stage{s}DataPacked, transform = "zx02"\n')
            f.write(f'SECTION Stage{s}Data, org = SprW\n')
            for lab, vals in (('SprW', [x[1] for x in sprites]), ('SprH', [x[2] for x in sprites]), ('SprStep', steps)):
                vals = pad(vals)
                f.write(f'    ASSERT P% == {lab}\n')
                for i in range(0, len(vals), 32):
                    f.write('    EQUB ' + ', '.join(str(v) for v in vals[i:i + 32]) + '\n')
            for lab, fn in (('SprLo', 'LO'), ('SprHi', 'HI')):          # each sprite's bytes, less 8
                f.write(f'    ASSERT P% == {lab}\n')
                vals = [f'{fn}(SprData{"Heli" + str(i - heli) if heli and heli <= i < heli + 4 else x[0]} - 8)'
                        for i, x in enumerate(sprites)] + ['0'] * (most - n)
                for i in range(0, len(vals), 8):
                    f.write('    EQUB ' + ', '.join(vals[i:i + 8]) + '\n')
            f.write('    ASSERT P% == SprHi + SprTableSize\n')
            f.write('ENDSECTION\n')
            f.write(f'SECTION Stage{s}Data2, org = ObjKind\n')
            f.write('    EQUB ' + ', '.join(str(k if k != 4 else 0x80) for k in kinds) + '\n')   # (the gantry's bit 7)
            for lab, fn in (('ObjPartLo', 'LO'), ('ObjPartHi', 'HI')):
                f.write(f'    ASSERT P% == {lab}\n')
                for i in range(0, len(lists), 10):
                    f.write('    EQUB ' + ', '.join(f'{fn}(ObjParts + {3 * x})' for x in lists[i:i + 10]) + '\n')
            f.write('    ASSERT P% == CarSprite\n')
            f.write('    EQUB ' + ', '.join(str(c) for c in carsp) + '\n')
            f.write('    ASSERT P% == HeliSprite\n')
            f.write(f'    EQUB {heli}\n')
            f.write('    ASSERT P% == GantryX                        ; (the gantry\'s beam by size: its pylon\'s x, its lines less 1,\n')
            f.write('                                                ; its first line\'s fill in GantryEven for an even\n')
            f.write('                                                ; bottom line, GantryOdd an odd, a line\'s from it up)\n')
            if beam:
                f.write('    EQUB ' + ', '.join(map(str, beam[2])) + '\n')
                f.write('    EQUB ' + ', '.join(str(h - 1) for h in beam[0]) + '\n')
                f.write('    EQUB ' + ', '.join(map(str, beam[1])) + '\n')
                for p in (0, 1):
                    f.write(f'    ASSERT P% == Gantry{("Even", "Odd")[p]}\n')
                    fills = [x[p] for x in beam[3]] + [0] * (beam_lines - len(beam[3]))
                    for i in range(0, len(fills), 16):
                        f.write('    EQUB ' + ', '.join(f'&{v:02X}' for v in fills[i:i + 16]) + '\n')
            f.write('    SKIPTO DataSlotParts                        ; (none, or the rest)\n')
            f.write('    ASSERT P% == DataSlotParts\n')
            f.write('ENDSECTION\n')
            f.write('    ENDSECTION\n')
            f.write('.PartsPack                                  ; (its own pack: the slot is more than a playfield)\n')
            f.write(f'    SECTION Stage{s}PartsPacked, transform = "zx02"\n')
            f.write(f'SECTION Stage{s}Parts, org = DataSlotParts\n')
            f.write('.ObjParts                                   ; sprite, X offset (quarter-bytes), kind (1 the end)\n')
            for i in range(0, len(records), 6):
                f.write('    EQUB ' + ', '.join(f'{a}, {b}, {c}' for a, b, c in records[i:i + 6]) + '\n')
            for i, (name, w, h, data) in enumerate(sprites[CAR_SPRITES:], CAR_SPRITES):
                if heli and heli <= i < heli + 4:
                    continue                        # (heli.6502's)
                f.write(f'.SprData{name}                                   ; {w} x {h}, a column at a time, top first\n')
                for i in range(0, len(data), 16):
                    f.write('    EQUB ' + ', '.join(f'&{v:02X}' for v in data[i:i + 16]) + '\n')
            f.write(f'    ASSERT P% <= {"HeliData" if heli else "DataSlotParts + " + str(room)}\n')
            f.write('ENDSECTION\n')
            f.write('    ENDSECTION\n')
            f.write('}\n')
    with open(os.path.join(out, 'spritepieces.6502'), 'w') as f:
        f.write('\\\\ spritepieces.6502 - made by tools/gensprites.py: the pieces a stage fills in the data\'s bank (its\n')
        f.write('\\\\ slot, spritestageN.6502\'s two packs, as the slot is more than a playfield): each its address and\n')
        f.write('\\\\ bytes, then 0\n\n')
        f.write('.SpriteTablePieces                          ; (the first in main RAM, D22)\n')
        f.write('    EQUW SprW, 5 * SprTableSize\n')
        f.write('    EQUW ObjKind, DataSlotParts - ObjKind\n')
        f.write('    EQUW 0\n')
        f.write('.SpritePartPieces\n')
        f.write(f'    EQUW DataSlotParts, {own_room}\n')
        f.write('    EQUW 0\n')
        f.write('.HeliPieces                                 ; (filled after SpritePartPieces: theirs can reach it)\n')
        f.write(f'    EQUW HeliData, {heli_bytes}\n')
        f.write('    EQUW 0\n')
        f.write(f'    ASSERT 5 * SprTableSize + DataSlotParts - ObjKind <= PlayBytes AND {own_room} <= PlayBytes, '
                '"a pack unpacks into a playfield"\n')
        f.write('    ASSERT SprH == SprW + SprTableSize AND SprHi == SprW + 4 * SprTableSize, "the tables one after another"\n')
    with open(os.path.join(out, 'heli.6502'), 'w') as f:
        f.write('\\\\ heli.6502 - made by tools/gensprites.py: the helicopter\'s four sprites (stages ' +
                ', '.join(map(str, helis)) + '), packed once,\n')
        f.write('\\\\ rephased to the slot\'s end (HeliData): its two parts, then both mirrored.\n\n')
        f.write('.HeliPack\n    SECTION HeliPacked, transform = "zx02"\nSECTION Heli, org = HeliData\n')
        for k, (name, w, h, data) in enumerate(heli_sprites[0]):
            f.write(f'.SprDataHeli{k}                                   ; {w} x {h}, a column at a time, top first\n')
            for i in range(0, len(data), 16):
                f.write('    EQUB ' + ', '.join(f'&{v:02X}' for v in data[i:i + 16]) + '\n')
        f.write('    ASSERT P% == DataVarsOrg\nENDSECTION\n    ENDSECTION\n')
    print(f'sprites: {", ".join(str(len(per[s][0])) for s in STAGES)} a stage (tables of {most}); parts and own '
          f'sprites {var} in {room}; the slot {5 * most + 20 + 400 + 42 + 1 + room} bytes; helicopters in {helis}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'build/gen')
