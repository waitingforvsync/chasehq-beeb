"""The BBC's road model (src/road.6502, in py65) against the CPC's (tools/cpc.py), loop by loop.

    .venv/bin/python tools/check_road.py [loops] [right]

(right: the bot keeps the car right of centre, X about &D0, so it takes a fork's right branch)

Starts a game of stage 1 in the CPC (work/logic/game.py, its bot driving) and the road in the BBC code, then
each loop feeds the BBC the CPC's speed (at &4219) and the road's X (at &3FCF) and compares, at &4895: the
segment, the fraction, the horizon, the window's curves, gradients, flags and objects (S4-S6, the BBC's obstacle
spawn run after the compare, as the CPC's &3305 runs after its render), the boundaries' lines, the
edge tables over the entries the CPC pushed, and the lane tables over the same; at a fork the second road's
edge (&7F) and the fork's state too, and after each flip the BBC's commit (as the CPC's &4144). The backdrop's scroll is
reported but not counted: the CPC takes its speed band from a stale register (docs/cpc-road.md, Oddities).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, '..', 'work', 'logic'), os.path.join(HERE, '..', 'work', 'road')]
from game import start_game, bot, word, K     # noqa: E402
from machine import Machine                    # noqa: E402
from model import tables                       # noqa: E402


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def cpc_table(M, page, n):
    return [s16(M[page * 256 + 0xFE - 2 * k] | M[page * 256 + 0xFF - 2 * k] << 8) for k in range(n)]


def bbc_table(b, lo, hi, n):
    L, H = b.syms[lo], b.syms[hi]
    return [s16(b.ram[L + k] | b.ram[H + k] << 8) for k in range(n)]


def bbc_lanes(b, name, n):
    """A lane table from the code's bank (paged in under the call; the bank's copy otherwise)."""
    lo, hi = b.syms[name + 'Lo'], b.syms[name + 'Hi']
    mem = b.ram if b.paged == 0 else b.banks[0]
    off = 0 if b.paged == 0 else -0x8000
    return [s16(mem[lo + k + off] | mem[hi + k + off] << 8) for k in range(n)]


def right_bot(m):
    """The bot, but keeping X about &D0 (x grows to the left): a fork's right branch."""
    k = bot(m) - {K.left, K.right}
    x = word(m, 0x17A0)
    if x >= 0xD8:
        k.add(K.right)
    elif x < 0xC8:
        k.add(K.left)
    return k


def main(loops=200, right=False):
    m = start_game()
    b = Machine()
    b.call('road_start')
    bad = s6diff = badcar = badrows = badbounce = 0
    for i in range(loops):
        m.keys = right_bot(m) if right else bot(m)
        assert m.run_to(0x4219)
        speed = word(m, 0x177E)
        assert m.run_to(0x3FCF)
        x = word(m, 0x17A0)
        assert m.run_to(0x4895)
        M = bytes(m.mem)
        b.poke('RoadSpeed', [speed & 255, speed >> 8])
        b.call('road_advance')
        b.poke('RoadX', [x & 255, x >> 8])
        b.call('road_frame')

        seg, frac = M[0x1775], M[0x1774]
        y, d, R, L = tables(M)
        n = len(R)
        got = {
            'seg': (b.peek('RoadSeg'), seg),
            'frac': (b.peek('RoadFrac'), frac),
            'H': (s16(b.peek('RoadH') | b.peek('RoadH+1' if False else b.syms['RoadH'] + 1) << 8),
                  s16(M[0x1693] | M[0x1694] << 8)),
            'window': ([b.ram[b.syms['RoadWindow'] + ((b.peek('RoadSeg') + k * 32 + j) & 255)]
                        for k in range(6) for j in range(32)],
                       [M[0xF700 + ((seg + k * 32 + j) & 255)] for k in range(6) for j in range(32)]),
            'y': (list(b.peek('RoadY', 23)), [M[0x8E00 + j] for j in range(23)]),
            'edgeR': (bbc_table(b, 'EdgeRLo', 'EdgeRHi', n), cpc_table(M, 0x7E, n)),
            'edgeL': (bbc_table(b, 'EdgeLLo', 'EdgeLHi', n), cpc_table(M, 0x7A, n)),
        }
        fork = any((M[0xF700 + ((seg + 0x40 + j) & 255)] & 0xE1) == 0xE1 for j in range(22))
        if fork:
            got['edgeR2'] = (bbc_table(b, 'EdgeR2Lo', 'EdgeR2Hi', n), cpc_table(M, 0x7F, n))
        got['fork'] = ([b.peek('ForkSeen'), b.peek('ForkDecided'), b.peek('ForkBranch'), b.peek('ForkHalf'),
                        b.peek('ForkSep') | b.peek('ForkSep', 2)[1] << 8],
                       [M[0x1799], M[0x179D], M[0x177D], M[0x168F], M[0x179B] | M[0x179C] << 8])
        if fork:
            got['forkrow'] = (b.peek('ForkRow'), M[0x179A])
        nl = min(n, 104)
        for name, page in (('Lane1', 0x7B), ('Lane2', 0x7C), ('Lane3', 0x7D)):
            got[name] = (bbc_lanes(b, name, nl)[:-1], cpc_table(M, page, nl)[:-1])  # (the top entry: a carry
            # from the stale entries above it, which differ in the two)
        wrong = [k for k, (u, v) in got.items() if u != v]
        if wrong:
            bad += 1
            if bad <= 5:
                print(f'loop {i} seg {seg} frac {frac} speed {speed}: differ in {wrong}')
                for k in wrong[:2]:
                    u, v = got[k]
                    if isinstance(u, list):
                        diff = [(j, u[j], v[j]) for j in range(min(len(u), len(v))) if u[j] != v[j]][:6]
                        print(f'    {k}: (index, BBC, CPC) {diff}')
                    else:
                        print(f'    {k}: BBC {u}, CPC {v}')
        s6 = ([b.ram[b.syms['RoadWindow'] + ((b.peek('RoadSeg') + 0xA0 + j) & 255)] for j in range(32)],
              [M[0xF700 + ((seg + 0xA0 + j) & 255)] for j in range(32)])
        if s6[0] != s6[1]:                      # (S6, reported only: the CPC's obstacles (&3305) clear its
            s6diff += 1                         # entries for values 3 and 6, not ported yet)
        scroll = (b.peek('RoadScroll'), M[0x4CC4])
        if i % 50 == 0 or (fork and i % 10 == 0):
            print(f'loop {i}: seg {seg} speed {speed} H {got["H"][1]} entries {n} scroll BBC/CPC {scroll}'
                  + (f' fork row {M[0x179A]} sep {M[0x179B] | M[0x179C] << 8} branch {M[0x177D]}' if fork else ''))
        b.call('obstacles')                     # (after the render, as the CPC's &3305: S6 two and four rows on
        #                                         cleared for values 3 and 6)
        assert m.run_to(0x2C94)                 # the car's tests: its anchors then, CarOff at the flip
        A = bytes(m.mem)
        m.run_to(0x0DCD)
        b.poke('back', 0x40)
        b.call('road_draw')                     # (its tapers go into the tables, as the CPC's)
        b.poke('CarBounce', 0)
        b.call('car_offroad')
        if not A[0x3A9B]:                       # a bounce started by the tests (roadside, barrier, divider), the
            bounce = ((b.peek('CarBounce'), b.peek('CarBounceSide') if b.peek('CarBounce') else 0),   # CPC's
                      (m.mem[0x3A9B], m.mem[0x3AE4] if m.mem[0x3A9B] else 0))         # by the flip
            if bounce[0] != bounce[1]:
                badbounce += 1
                if badbounce <= 5:
                    print(f'loop {i} seg {seg}: a bounce and its side (BBC, CPC): {bounce}, anchors (CPC L, R) '
                          f'{s16(A[0x7CFE] | A[0x7CFF] << 8)}, {s16(A[0x7CFC] | A[0x7CFD] << 8)}')
        sparking = m.mem[0x3B51] != 0           # (the CPC's bounce sparks clear its CarOff: not compared)
        rows = ([[s16(b.peek('RowXLLo', 22)[r] | b.peek('RowXLHi', 22)[r] << 8),
                  s16(b.peek('RowXRLo', 22)[r] | b.peek('RowXRHi', 22)[r] << 8)] for r in range(1, 21)],
                [[s16(A[0x7CB0 + 4 * (20 - r) + 2] | A[0x7CB0 + 4 * (20 - r) + 3] << 8),
                  s16(A[0x7CB0 + 4 * (20 - r)] | A[0x7CB0 + 4 * (20 - r) + 1] << 8)] for r in range(1, 21)])
        #                                         (rows 1-20, which objects are drawn in: 21's entry is past the
        #                                          last written, stale in both)
        onscreen = lambda rr: [[v if 0 <= v <= 255 else 'off' for v in lr] for lr in rr]
        rows = (onscreen(rows[0]), onscreen(rows[1]))   # (an anchor off the screen drops its object, whatever
        #                                                  it is: entries past the tables' are stale on the CPC)
        if rows[0] != rows[1] and i > 0:
            badrows += 1
            if badrows <= 3:
                d = [(r + 1, rows[0][r], rows[1][r]) for r in range(20) if rows[0][r] != rows[1][r]][:4]
                print(f'loop {i}: the rows\' anchors differ (row, BBC [L, R], CPC [L, R]): {d}')
        anchors = ([s16(b.peek('CarAnchorL') | b.peek('CarAnchorL', 2)[1] << 8),
                    s16(b.peek('CarAnchorR') | b.peek('CarAnchorR', 2)[1] << 8), b.peek('CarOff')],
                   [s16(A[0x7CFE] | A[0x7CFF] << 8), s16(A[0x7CFC] | A[0x7CFD] << 8), m.mem[0x1773]])
        if sparking:
            anchors[0][2] = anchors[1][2]
        if anchors[0] != anchors[1] and i > 0:
            badcar += 1
            if badcar <= 5:
                print(f'loop {i}: the car\'s anchors and CarOff (BBC, CPC): {anchors}')
        b.call('road_commit')
    print(f'{bad} loops of {i + 1} differ (S6, not counted: {s6diff} differ); the car\'s anchors and CarOff: {badcar}; the rows\' anchors: {badrows}; bounces: {badbounce}')


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200, 'right' in sys.argv[2:])
