"""A minimal CPC 6128 round Chase H.Q.'s code: the reference for the BBC port (P4).

The game runs with interrupts off and polls the hardware, so this models only what it touches: the gate
array (inks, mode, the 128K banks C0 and C4-C7), the CRTC's registers, the PPI (vsync on port B, the AY's
bus and the keyboard's row on port C) and the AY's registers (the keyboard read through register 14).
Disc access is skipped: BI3's loader at &0C5B becomes a RET and the LV files are put where it would load
them. The simulator starts at &BA00 with memory as BI4's start-up leaves it.

The Z80 is kosarev's (the z80 package): flat 64K of RAM, breakpoints, port callbacks. Time: it counts plain
Z80 T-states; the CPC rounds every memory cycle up to a microsecond, so its code runs about a fifth slower.
`stretch` scales the frame to suit (the frame is 79,872 T on a CPC).

    from cpc import CPC
    m = CPC()
    m.run_frames(100)            # game loops (each ends at the flip, &0DCD)
    m.screen_png('a.png')
"""
import os
import sys

import z80
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from cpcdsk import read_dsk                         # noqa: E402

DSK = os.path.join(os.path.dirname(__file__), '..', 'docs', 'chasehq.dsk')
FLIP = 0x0DCD                                       # the buffer flip, once a game loop
FRAME_T = 79872                                     # T-states a CPC frame (312 lines of 64 us at 4 MHz)

# hardware colour -> RGB (0, 128 or 255 a gun)
_H = [(1, 1, 1), (1, 1, 1), (0, 2, 1), (2, 2, 1), (0, 0, 1), (2, 0, 1), (0, 1, 1), (2, 1, 1),
      (2, 0, 1), (2, 2, 1), (2, 2, 0), (2, 2, 2), (2, 0, 0), (2, 0, 2), (2, 1, 0), (2, 1, 2),
      (0, 0, 1), (0, 2, 1), (0, 2, 0), (0, 2, 2), (0, 0, 0), (0, 0, 2), (0, 1, 0), (0, 1, 2),
      (1, 0, 1), (1, 2, 1), (1, 2, 0), (1, 2, 2), (1, 0, 0), (1, 0, 2), (1, 1, 0), (1, 1, 2)]
HWRGB = [tuple((0, 128, 255)[g] for g in c) for c in _H]

# CPC key numbers (row * 8 + bit)
KEYS = {'up': 0, 'right': 1, 'down': 2, 'left': 8, 'copy': 9, 'return': 18, 'shift': 21, 'ctrl': 23,
        'p': 27, 'o': 34, 'i': 35, 'l': 36, 'k': 37, 'm': 38, 'space': 47, 'q': 67, 'a': 69, 'z': 71,
        'x': 63, 'esc': 66, '1': 64, '2': 65, '3': 57, '4': 56, 'f1': 13, 'f2': 14,
        'joyup': 72, 'joydown': 73, 'joyleft': 74, 'joyright': 75, 'fire2': 76, 'fire1': 77}


def mode0_pens(b):
    """A MODE 0 byte's two pens, left then right."""
    left = (b >> 7 & 1) | (b >> 3 & 1) << 1 | (b >> 5 & 1) << 2 | (b >> 1 & 1) << 3
    right = (b >> 6 & 1) | (b >> 2 & 1) << 1 | (b >> 4 & 1) << 2 | (b & 1) << 3
    return left, right


def initial_memory(files):
    """Memory as BI4's start-up leaves it at &BA00, the 128K banks, and the loader stubbed."""
    mem = bytearray(65536)
    for name, addr in (('CHASEHQ.BI2', 0x0300), ('CHASEHQ.BI3', 0x0C5B), ('CHASEHQ.BI4', 0xA610),
                       ('CHASEHQ.BI1', 0xC000)):
        d = files[name]['data']
        mem[addr:addr + len(d)] = d
    mem[0xBA00:0xBA00 + 0x1D2] = mem[0x8680:0x8680 + 0x1D2]     # &0100's LDIR
    mem[0x7FFF:0xACC1] = mem[0x59AF:0x8671]                     # and its LDDR (&2CC2 bytes)
    assert len(mem) == 65536
    lv = [files[f'CHASEHQ.LV{i}']['data'] for i in range(1, 9)]
    banks = {5: bytearray(lv[0] + lv[1]), 6: bytearray(lv[2] + lv[3]), 7: bytearray(lv[4] + lv[5]),
             4: bytearray(lv[6] + lv[7])}
    mem[0x59AB:0x59AB + 0x2000] = lv[0]                         # the last load, on 64K and 128K alike
    mem[0x0C5B] = 0xC9                                          # BI3's loader: RET (all of it preloaded)
    return mem, banks


class CPC:
    def __init__(self, dsk=DSK, stretch=1.2):
        self.files = read_dsk(dsk)
        self.mem, self.banks = initial_memory(self.files)
        self.window = 0                                         # the bank at &4000 (0: main RAM's own)
        self.saved = None                                       # main RAM's &4000-&7FFF while a bank's there
        self.frame_t = int(FRAME_T / stretch)
        self.pen = 0
        self.inks = [20] * 17                                   # (hardware colours; 20 black)
        self.mode = 1
        self.crtc = [0] * 32
        self.crtcsel = 0
        self.ppi = [0xFF, 0, 0, 0]                              # A, B, C, control
        self.psgsel = 0
        self.psg = [0] * 16
        self.psglog = []                                        # (T, register, value)
        self.keys = set()
        self.z = z80.Z80Machine()
        self.z.set_memory_block(0, self.mem)
        self.mem = self.z.memory                                # (the machine's own: everything uses it)
        self.z.pc = 0xBA00
        self.z.sp = 0x0300
        self.z.set_input_callback(self.read_port)
        self.z.set_output_callback(self.write_port)
        self.t = 0                                              # T-states run before the current run()
        self.budget = 0                                         # the current run()'s ticks_to_stop at its start
        self.flips = []                                         # T at each flip's vsync
        self.work = []                                          # T each game loop worked, its vsync wait left out

    # the hardware

    def page(self, cfg):
        want = cfg & 7 if cfg & 4 else 0
        assert cfg & 7 in (0, 4, 5, 6, 7), f'RAM config &{cfg:02X} not modelled'
        if want == self.window:
            return
        if self.window:
            self.banks[self.window][:] = self.mem[0x4000:0x8000]
            self.mem[0x4000:0x8000] = self.saved
        if want:
            self.saved = bytes(self.mem[0x4000:0x8000])
            self.mem[0x4000:0x8000] = self.banks[want]
        self.window = want

    def now(self):
        return self.t + self.budget - self.z.ticks_to_stop

    def write_port(self, port, value):
        if port & 0xC000 == 0x4000:                             # gate array
            f = value >> 6
            if f == 0:
                self.pen = 16 if value & 0x10 else value & 15
            elif f == 1:
                self.inks[self.pen] = value & 31
            elif f == 2:
                self.mode = value & 3
            else:
                self.page(value)
        if port & 0x4000 == 0:                                  # CRTC
            f = port >> 8 & 3
            if f == 0:
                self.crtcsel = value & 31
            elif f == 1:
                self.crtc[self.crtcsel] = value
        if port & 0x0800 == 0:                                  # PPI
            f = port >> 8 & 3
            if f == 3:
                if value & 0x80:
                    self.ppi[3] = value
                else:
                    bit = 1 << (value >> 1 & 7)
                    self.ppi[2] = self.ppi[2] | bit if value & 1 else self.ppi[2] & ~bit
                    self.psg_bus()
            else:
                self.ppi[f] = value
                if f == 2:
                    self.psg_bus()

    def psg_bus(self):
        f = self.ppi[2] >> 6
        if f == 3:
            self.psgsel = self.ppi[0] & 15
        elif f == 2:
            self.psg[self.psgsel] = self.ppi[0]
            self.psglog.append((self.now(), self.psgsel, self.ppi[0]))

    def read_port(self, port):
        if port & 0x0800 == 0:
            f = port >> 8 & 3
            if f == 0:
                if self.ppi[2] >> 6 == 1:
                    if self.psgsel == 14:
                        row = self.ppi[2] & 15
                        return 0xFF & ~sum(1 << (k & 7) for k in self.keys if k >> 3 == row)
                    return self.psg[self.psgsel]
                return 0xFF
            if f == 1:
                vsync = self.now() % self.frame_t < 8 * 256
                return 0x5E | vsync
            if f == 2:
                return self.ppi[2]
        return 0xFF

    # running

    def run_to(self, addr, max_t=50 * FRAME_T):
        """Run until PC is addr (one instruction at least). False if max_t T-states pass first."""
        z = self.z
        z.set_breakpoint(addr)
        z.step_over_breakpoint() if z.pc == addr else None
        hit = False
        left = max_t
        while left > 0 and not hit:
            self.budget = min(left, 1 << 24)
            z.ticks_to_stop = self.budget
            events = z.run()
            ran = self.budget - z.ticks_to_stop
            self.t += ran
            left -= ran
            self.budget = 0
            hit = bool(events & z._BREAKPOINT_HIT) and z.pc == addr
        z.clear_breakpoint(addr)
        return hit

    def run_frames(self, n, keys_for=None):
        """Run n game loops, each to the flip; keys_for(i) gives the keys held in loop i."""
        for i in range(n):
            if keys_for:
                self.keys = {KEYS.get(k, k) for k in keys_for(i)}
            start = self.t
            if not self.run_to(FLIP, 40 * FRAME_T):
                raise RuntimeError(f'no flip within 40 frames: PC &{self.z.pc:04X}')
            self.work.append(self.t - start)                    # the loop's work, its vsync wait left out
            self.run_to(0x0DD5)                                 # past its vsync wait
            self.flips.append(self.t)

    def frames_per_loop(self):
        t = self.flips
        return [round((b - a) / self.frame_t) for a, b in zip(t, t[1:])]

    # looking

    def screen_base(self, r12=None):
        r12 = self.crtc[12] if r12 is None else r12
        ma = r12 << 8 | self.crtc[13]
        return (ma >> 12 & 3) * 0x4000, (ma & 0x3FF) * 2

    def screen_image(self, r12=None, scale=2):
        base, offset = self.screen_base(r12)
        width = self.crtc[1] * 2
        rows = self.crtc[6] or 25
        img = Image.new('RGB', (width * 4, rows * 8))
        px = img.load()
        mem = self.mem
        rgb = [HWRGB[self.inks[p]] for p in range(16)]
        for y in range(rows * 8):
            a = base + (y & 7) * 0x800
            for x in range(width):
                left, right = mode0_pens(mem[a + ((offset + (y >> 3) * width + x) & 0x7FF)])
                px[x * 4, y] = px[x * 4 + 1, y] = rgb[left]
                px[x * 4 + 2, y] = px[x * 4 + 3, y] = rgb[right]
        return img.resize((img.width * scale // 2, img.height * scale), Image.NEAREST)

    def screen_png(self, path, r12=None):
        self.screen_image(r12).save(path)


if __name__ == '__main__':
    m = CPC()
    m.run_frames(int(sys.argv[1]) if len(sys.argv) > 1 else 50)
    print('frames per loop', m.frames_per_loop()[-20:])
    m.screen_png(sys.argv[2] if len(sys.argv) > 2 else 'build/cpc.png')
