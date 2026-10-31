"""The BBC's playfield (src/roaddraw.6502 in py65) beside the CPC's, after the road and before the sprites.

    .venv/bin/python tools/compare_road.py [loops] [out.png] [--objects] [--right]

(--right: the bot keeps right of centre, to take a fork's right branch)

Runs stage 1 in both as tools/check_road.py does (the CPC's bot driving, the BBC fed its speed and X), then
draws the BBC's playfield and renders both, the CPC's left, the BBC's right, at the BBC's aspect.
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, '..', 'work', 'logic')]
from game import start_game, bot, word        # noqa: E402
from check_road import right_bot               # noqa: E402
from machine import Machine                    # noqa: E402
from cpc import HWRGB, mode0_pens              # noqa: E402

BBC_RGB = [((c & 1) * 255, (c >> 1 & 1) * 255, (c >> 2 & 1) * 255) for c in range(8)]


def bbc_image(ram, base):
    img = Image.new('RGB', (128, 128))
    px = img.load()
    for y in range(128):
        for xb in range(64):
            b = ram[base + (y >> 3) * 512 + xb * 8 + (y & 7)]
            for k, shift in ((0, 1), (1, 0)):
                c = sum((b >> (shift + 2 * i) & 1) << i for i in range(3))
                px[2 * xb + k, y] = BBC_RGB[c]
    return img


def cpc_image(m, base):
    img = Image.new('RGB', (128, 128))
    px = img.load()
    rgb = [HWRGB[m.inks[p]] for p in range(16)]
    for y in range(128):
        sy = y + 64
        for xb in range(64):
            left, right = mode0_pens(m.mem[base + (sy >> 3) * 64 + (sy & 7) * 0x800 + xb])
            px[2 * xb, y] = rgb[left]
            px[2 * xb + 1, y] = rgb[right]
    return img


def main(loops=40, out='build/compare.png', objects=False, right=False):
    m = start_game()
    b = Machine()
    b.call('road_start')
    for i in range(loops):
        m.keys = right_bot(m) if right else bot(m)
        assert m.run_to(0x4219)
        speed = word(m, 0x177E)
        assert m.run_to(0x3FCF)
        x = word(m, 0x17A0)
        assert m.run_to(0x4895)
        b.poke('RoadSpeed', [speed & 255, speed >> 8])
        b.call('road_advance')
        b.poke('RoadX', [x & 255, x >> 8])
        b.call('road_frame')
        assert m.run_to(0x03A1 if objects else 0x238C)   # the road drawn (and the objects), the car not yet
        if i < loops - 1:
            m.run_to(0x0DCD)
            b.call('road_commit')
    back = m.mem[0x1645]
    b.poke('back', 0x40)
    cycles = b.call('road_draw')
    if objects:
        b.call('road_rows')                         # (the rows' anchors, after the road as the CPC's)
        ocycles = b.call('plot_objects')
        print(f'plot_objects {ocycles} cycles (py65)')
    left = cpc_image(m, back << 8)
    right = bbc_image(b.ram, 0x4000)
    sheet = Image.new('RGB', (256 + 8, 128))
    sheet.paste(left, (0, 0))
    sheet.paste(right, (136, 0))
    sheet.resize((sheet.width * 4, sheet.height * 4), Image.NEAREST).save(out)
    print(f'loop {loops}: seg {m.mem[0x1775]} H {word(m, 0x1693)} scroll BBC {b.peek("RoadScroll")} '
          f'CPC {m.mem[0x4CC4]}; road_draw {cycles} cycles (py65)')


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 40, sys.argv[2] if len(sys.argv) > 2 else 'build/compare.png',
         '--objects' in sys.argv, '--right' in sys.argv)
