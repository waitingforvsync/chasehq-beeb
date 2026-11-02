"""The road's data for the BBC, in its final form, from the CPC (docs/cpc-road.md).

    python tools/genroad.py build/gen [stage]

writes road.6502: the perspective tables (copied from the CPC: base, m, n, T), the stage's streams (relocated:
the hold and lead-in sequences from BI2, then the stage's own), its start X, the backdrop as MODE 2 bytes, and
the fills, rumbles and lane pixels as final MODE 2 bytes, so the renderer only stores.

Colours (D7): a fill alternates two CPC bytes by line, so its 2x2 block has four pens. A pen on two or four
of them takes its D7 pair, one colour each (a whole block by x + y parity): so the CPC's own checkers (grey
and black on P0's road) keep their pens' pairs. Otherwise the block takes the four BBC colours with its average and the least
spread of brightness (Rec. 601 luma). Single pens in art (the backdrop, rumbles, lanes) take D7's pair by
x + y parity.
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cpc import CPC, HWRGB, mode0_pens          # noqa: E402
from cpcdsk import read_dsk                       # noqa: E402
from gendata import pair_for, mode2_byte, luma    # noqa: E402

BASE = 0x59AB                                     # the stage block's address
HOLD = (0x5960, 0x59AB)                           # BI2's hold and lead-in sequences
# the sequences the code switches streams to (their first bytes): lead-ins after a fork (&4144), holds at
# one (S6's from &4461; S1-S3's from the fork's parse). Kinds: n nibble runs, s3 count-value pairs, s6
LEADINS = {'S1': (0x5989, 'n'), 'S2': (0x598E, 'n'), 'S3L': (0x5993, 's3'), 'S3R': (0x599F, 's3'),
           'S4L': (0x5981, 'n'), 'S4R': (0x5985, 'n'), 'S5L': (0x5985, 'n'), 'S5R': (0x5981, 'n'),
           'S6': (0x597E, 's6'), 'HoldS1': (0x5971, 'n'), 'HoldS2': (0x5977, 'n'), 'HoldS3': (0x597C, 's3'),
           'HoldS4': (0x596C, 'n'), 'HoldS5': (0x596B, 'n'), 'HoldS6': (0x5963, 's6')}


def levels(hw):
    return tuple({0: 0, 128: 1, 255: 2}[g] for g in HWRGB[hw])


def bbc_bits(c):
    return (c & 1, c >> 1 & 1, c >> 2 & 1)


def block_for(pens, inks):
    """Four CPC pens (left even, right even, left odd, right odd) -> four BBC colours, same order. A pen on
    two or four of the pixels takes its D7 pair, one colour each, by x + y parity (so the CPC's own checkers
    keep their pens' pairs); otherwise the set of four with the block's average and the least spread of
    brightness."""
    counts = [pens.count(p) for p in pens]
    if all(c % 2 == 0 for c in counts):
        out, seen = [], {}
        for k, p in enumerate(pens):
            if counts[k] == 4:
                out.append(pair_for(inks[p])[(k & 1) ^ (k >> 1)])     # a whole block: its checker
            else:
                out.append(pair_for(inks[p])[seen.get(p, 0)])         # two on a diagonal: one colour each
                seen[p] = 1
        return tuple(out)
    want = [sum(levels(inks[p])[ch] for p in pens) for ch in range(3)]    # half-units, 0-8
    assert all(w % 2 == 0 for w in want), 'a block with an odd half-unit sum'
    best = None
    for combo in itertools.combinations_with_replacement(range(8), 4):
        if all(sum(bbc_bits(c)[ch] for c in combo) * 2 == want[ch] for ch in range(3)):
            ls = [luma(c) for c in combo]
            mean = sum(ls) / 4
            key = (sum((l - mean) ** 2 for l in ls), combo)
            best = key if best is None or key < best else best
    c = sorted(best[1], key=lambda k: (luma(k), k))
    return (c[0], c[2], c[3], c[1])               # diagonals: c0 with c1, c2 with c3


def fill_bytes(even, odd, inks):
    """A fill's CPC bytes on even and odd lines -> its MODE 2 bytes on even and odd lines."""
    le, re = mode0_pens(even)
    lo, ro = mode0_pens(odd)
    a, b, c, d = block_for((le, re, lo, ro), inks)
    return mode2_byte(a, b), mode2_byte(c, d)


def pixel(pen, x, y, inks):
    a, b = pair_for(inks[pen])
    return a if (x + y) & 1 == 0 else b


def emit(f, label, data, per=16):
    f.write(f'.{label}\n')
    for i in range(0, len(data), per):
        f.write('    EQUB ' + ', '.join(f'&{v:02X}' for v in data[i:i + per]) + '\n')


class Streams:
    """The stage's six streams and BI2's holds and lead-ins, walked from their starts so every address
    in them is found and relocated."""

    def __init__(self, stage, main):
        self.stage, self.main = stage, main
        self.ptrs = [self.rd(0x5BF5 + 2 * i) | self.rd(0x5BF6 + 2 * i) << 8 for i in range(6)]
        self.touched, self.words = set(), set()
        kinds = ['n', 'n', 's3', 'n', 'n', 's6']
        for p, k in zip(self.ptrs, kinds):
            self.walk(p + 1, k)
        for a, kind in LEADINS.values():
            self.walk(a, kind)
        inside = sorted(a for a in self.touched if a >= BASE)
        self.lo, self.hi = inside[0], inside[-1] + 1

    def rd(self, a):
        return self.stage[a - BASE] if a >= BASE else self.main[a]

    def walk(self, p, kind, seen=None):
        seen = set() if seen is None else seen
        todo = [p]
        while todo:
            p = todo.pop()
            while p not in seen:
                seen.add(p)
                b = self.rd(p)
                self.touched.add(p)
                if b == 0:
                    c = self.rd(p + 1)
                    self.touched.update((p, p + 1))
                    if c == 0:
                        self.words.add(p + 2)
                        self.touched.update((p + 2, p + 3))
                        todo.append(self.rd(p + 2) | self.rd(p + 3) << 8)
                        break
                    if c == 1:
                        break
                    if c == 2:
                        self.words.update((p + 2, p + 4))
                        self.touched.update(range(p + 2, p + 6))
                        todo += [self.rd(p + 2) | self.rd(p + 3) << 8, self.rd(p + 4) | self.rd(p + 5) << 8]
                        break
                    assert kind == 's6', f'control code {c} in a {kind} stream at &{p:04X}'
                    p += 2                          # an S6 code: no operand
                    continue
                if kind == 's3':
                    self.touched.add(p + 1)
                    p += 2
                else:
                    p += 1

    def where(self, a):
        """A CPC address in the streams -> (label, offset)."""
        if HOLD[0] <= a < HOLD[1]:
            return 'RoadHold', a - HOLD[0]
        assert self.lo <= a <= self.hi, f'&{a:04X} outside the streams'
        return 'RoadStreams', a - self.lo

    def write(self, f):
        for label, lo, hi in (('RoadHold', *HOLD), ('RoadStreams', self.lo, self.hi)):
            f.write(f'.{label}\n')
            a = lo
            while a < hi:
                if a in self.words:
                    t, o = self.where(self.rd(a) | self.rd(a + 1) << 8)
                    f.write(f'    EQUW {t} + {o}\n')
                    a += 2
                else:
                    run = []
                    while a < hi and a not in self.words and len(run) < 16:
                        run.append(self.rd(a))
                        a += 1
                    f.write('    EQUB ' + ', '.join(f'&{v:02X}' for v in run) + '\n')
        f.write('.RoadStreamStarts                          ; S1-S6: the byte before each one\'s first\n')
        for p in self.ptrs:
            t, o = self.where(p + 1)
            f.write(f'    EQUW {t} + {o} - 1\n')
        for name, (a, _) in LEADINS.items():
            t, o = self.where(a)
            f.write(f'RoadLead{name} = {t} + {o} - 1          ; (a stream pointer: the byte before its first)\n')


def main(out, stage=1):
    os.makedirs(out, exist_ok=True)
    files = read_dsk(os.path.join(os.path.dirname(__file__), '..', 'docs', 'chasehq.dsk'))
    m = CPC()
    assert m.run_to(0x0300)
    inks = list(m.inks)
    mem = bytes(m.mem)
    blk = files[f'CHASEHQ.LV{stage}']['data']
    st = lambda a: blk[a - BASE]

    with open(os.path.join(out, 'road.6502'), 'w') as f:
        f.write('\\\\ road.6502 - made by tools/genroad.py from the CPC disc: do not edit.\n\n')

        f.write('\\\\ the perspective tables, as the CPC builds them (docs/cpc-road.md): 8 fractions x 22\n')
        f.write('\\\\ boundaries each, and T, the vanishing point\'s X by heading (lo, hi at even indices)\n\n')
        emit(f, 'RoadBase', mem[0xFE00:0xFE00 + 176])
        emit(f, 'RoadM', mem[0xEE00:0xEE00 + 176])
        emit(f, 'RoadN', mem[0xEEB0:0xEEB0 + 176])

        f.write('\n\\\\ &3E03: fraction units a horizon step for |h2| 1-3, then at 4|c| + speed band a backdrop scroll\n')
        f.write('\\\\ (period in loops, step in bytes) for |c| 2, 4, 6\n\n')
        emit(f, 'RoadScrollTab', mem[0x3E03:0x3E23])
        f.write(f'\nCrimDodgeGap = {st(0x5BF1)}             ; the criminal\'s dodge count\'s reload, at least (&5BF1)\n')
        f.write(f'CrimSprintGap = {st(0x5BF2)}            ; loops between the criminal\'s sprints, at least (&5BF2)\n')
        f.write(f'\nTrafficGap = {st(0x5BF0)}                ; segments between traffic, at least (the CPC\'s &5BF0)\n')
        f.write(f'\nStageStartX = {st(0x5BF3) | st(0x5BF4) << 8}            ; the right edge\'s X at the start, half-pixels\n\n')
        # the roadside objects' collisions: by type 0-15, (bound C, bound E, the bounce's end); S4 (the right
        # side's) from (&5BD0), S5 (the left's) from (&5BD6), 7 bytes a type
        f.write('\\\\ the roadside objects\' collisions by type (0-15; S4 the right side\'s, S5 the left\'s): the bounds\n')
        f.write('\\\\ C and E for the middle lane line\'s X at the car (S4: E < x < C; S5: C <= x < E) and the bounce\'s end\n\n')
        t = st(0x5BCC) | st(0x5BCD) << 8
        f.write('\\\\ the obstacles: their widths by kind (cones, barriers; the CPC\'s (&5BCC)); a flight\'s heights\n')
        f.write('\\\\ (&3446), and its start and loops by the speed\'s bucket (&346E)\n\n')
        f.write('.ObstacleWidth\n    EQUB ' + ', '.join(str(st(t + 3 * k)) for k in range(2)) + '\n')
        emit(f, 'ObstacleHeights', mem[0x3446:0x346E])
        emit(f, 'ObstacleFlights', mem[0x346E:0x3478])
        f.write('\n')
        f.write('\\\\ the fork\'s divider, by branch (left, right): its bounds C and E (left: E < x < C; right: C <= x < E)\n\n')
        divs = []
        for ptr in (0x5BD2, 0x5BD8):
            t = st(ptr) | st(ptr + 1) << 8
            divs.append((st(t), st(t + 1)))
        f.write('.ForkDivC\n    EQUB ' + ', '.join(str(d[0]) for d in divs) + '\n')
        f.write('.ForkDivE\n    EQUB ' + ', '.join(str(d[1]) for d in divs) + '\n\n')
        for side, ptr in (('R', 0x5BD0), ('L', 0x5BD6)):
            t = st(ptr) | st(ptr + 1) << 8
            recs = [tuple(st(t + 7 * v + k) for k in range(3)) if v < 10 else (0, 0, 0) for v in range(16)]
            for k, name in enumerate(('C', 'E', 'End')):
                f.write(f'.Roadside{side}{name}\n    EQUB ' + ', '.join(str(r[k]) for r in recs) + '\n')
        f.write('\n')
        Streams(blk, mem).write(f)

        # the backdrop: 24 rows (row 0 the bottom) of 22 bytes, its dither fixed to it (x + row parity)
        bd = bytearray()
        for r in range(24):
            for xb in range(22):
                lp, rp = mode0_pens(st(0x59AB + 22 * r + xb))
                bd.append(mode2_byte(pixel(lp, 2 * xb, r, inks), pixel(rp, 2 * xb + 1, r, inks)))
        f.write('\n\\\\ the backdrop by columns: column k\'s 24 rows (row 0 the bottom) at BackPlanar + 24k\n\n')
        planar = bytearray()
        for xb in range(22):
            planar += bytes(bd[22 * r + xb] for r in range(24))
        emit(f, 'BackPlanar', planar, 24)

        # the fills: per colour set, P0 grass, P0 road, P1 road, P1 grass, each even then odd
        # (the tunnel's: its road from &5BC7, P0 even, P0 odd, P1; its walls &C0, black)
        sets = {'Normal': [st(0x5BBB + i) for i in range(6)], 'Alt': [st(0x5BC1 + i) for i in range(6)],
                'Tunnel': [0xC0, st(0x5BC7), st(0x5BC8), st(0x5BC9), 0xC0, 0xC0]}
        f.write('\n\\\\ fills: P0 grass, P0 road, P1 road, P1 grass, each on even then odd lines\n\n')
        for name, c in sets.items():
            fills = []
            for even, odd in ((c[0], c[0]), (c[1], c[2]), (c[3], c[3]), (c[4], c[5])):
                fills += fill_bytes(even, odd, inks)
            emit(f, f'Fill{name}', fills)
        sky = mode2_byte(pixel(5, 0, 0, inks), pixel(5, 1, 0, inks))
        f.write(f'SkyByte = &{sky:02X}\n')
        black = fill_bytes(0xC0, 0xC0, inks)
        assert black[0] == black[1]
        f.write(f'SkyTunnel = &{black[0]:02X}                ; (the CPC\'s &C0: a tunnel\'s sky and walls)\n')
        f.write('\n\\\\ the tunnel mouth\'s colours, even line then odd: the entrance\'s band (&3F), the exit\'s (&C0), the\n')
        f.write('\\\\ sky above an entrance (&F0)\n\n')
        emit(f, 'MouthFills', list(fill_bytes(0x3F, 0x3F, inks)) + list(black) + [sky, sky])

        # rumbles: set, phase, parity, level, x AND 2, side -> 3 bytes, final (the fill under them known: the
        # left's first byte is over grass and its last over road; the right's the other way round)
        rum = mem[0xD7A0:0xD800]
        out = [[], [], []]
        outrr = [[], [], []]                        # the fork's: road under both ends (normal colours)
        lanes = []
        for name, c in sets.items():
            cpcfill = {(0, 0): (c[0], c[1]), (0, 1): (c[0], c[2]), (1, 0): (c[4], c[3]), (1, 1): (c[5], c[3])}
            for ph in (0, 1):
                for par in (0, 1):
                    grass, road = cpcfill[(ph, par)]
                    bgrass, broad = fill_bytes(*((grass, grass) if True else ()), inks), None
                    gblock = block_for(mode0_pens(cpcfill[(ph, 0)][0]) + mode0_pens(cpcfill[(ph, 1)][0]), inks)
                    rblock = block_for(mode0_pens(cpcfill[(ph, 0)][1]) + mode0_pens(cpcfill[(ph, 1)][1]), inks)
                    def under(block, k):
                        return block[par * 2 + k]
                    for level in range(3):
                        for xb in (0, 1):
                            pat = rum[32 * level + (0 if ph else 16) + xb * 8:][:5]
                            for side in (0, 1):
                                first, last = (gblock, rblock) if side == 0 else (rblock, gblock)
                                trio = []
                                for k3, (mask, orb, blk) in enumerate(((pat[0], pat[1], first), (0, pat[2], None),
                                                                      (pat[3], pat[4], last))):
                                    cols = []
                                    for k in (0, 1):
                                        keep = mask & (0xAA if k == 0 else 0x55)
                                        if keep:
                                            cols.append(under(blk, k))
                                        else:
                                            pen = mode0_pens(orb)[k]
                                            cols.append(pixel(pen, k, par, inks))
                                    trio.append(mode2_byte(*cols))
                                for i in range(3):
                                    out[i].append(trio[i])
                                if name == 'Normal':
                                    trio = []
                                    for k3, (mask, orb) in enumerate(((pat[0], pat[1]), (0, pat[2]), (pat[3], pat[4]))):
                                        cols = []
                                        for k in (0, 1):
                                            if mask & (0xAA if k == 0 else 0x55):
                                                cols.append(under(rblock, k))
                                            else:
                                                cols.append(pixel(mode0_pens(orb)[k], k, par, inks))
                                        trio.append(mode2_byte(*cols))
                                    for i in range(3):
                                        outrr[i].append(trio[i])
                    # lanes (drawn on P1 lines only): the road's byte with its left or right pixel white
                    for k in (0, 1):
                        cols = [under(rblock, 0), under(rblock, 1)]
                        cols[k] = 7
                        lanes.append(mode2_byte(*cols))
        f.write('\n\\\\ rumbles: index ((((set * 2 + phase) * 2 + parity) * 3 + level) * 2 + x AND 2) * 2 + side\n\n')
        for i, lab in enumerate(('RumbleA', 'RumbleB', 'RumbleC')):
            emit(f, lab, out[i])
        f.write('\n\\\\ and the fork\'s first road\'s end, its last byte over road too (normal colours only, the same\n')
        f.write('\\\\ index)\n\n')
        for i, lab in enumerate(('RumbleRRA', 'RumbleRRB', 'RumbleRRC')):
            emit(f, lab, outrr[i])
        f.write('\n\\\\ lane pixels: index ((set * 2 + phase) * 2 + parity) * 4 + (x AND 2), x the pixel\'s\n')
        f.write('\\\\ half-pixel (the odd ones between unused)\n\n')
        emit(f, 'LaneBytes', [lanes[i // 2] if i % 2 == 0 else 0 for i in range(16 * len(sets))])

        # T last, on the bank's last page before its workspace: the data's own spare bytes in front of it (the
        # code's are in front of the data, CodeDataOrg)
        f.write('\n\\\\ T, on the code bank\'s last page: the data\'s spare bytes before it\n\n')
        f.write('    PADTO CodeVarsOrg - &100\n')
        emit(f, 'RoadT', mem[0xF600:0xF700])

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'build/gen', int(sys.argv[2]) if len(sys.argv) > 2 else 1)
