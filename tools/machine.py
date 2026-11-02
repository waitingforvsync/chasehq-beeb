"""py65 with the game's sideways RAM banks: what the logic checks run the BBC code on.

    m = Machine()                  # the build's files unpacked as !BOOT and the loader would leave them,
                                   # the loader's tables made
    m.call('road.frame')           # a routine by symbol (or address), run to its RTS
    m.mem[a]                       # main RAM (and the paged bank at &8000)

Banks are paged by writes to ROMSEL (&FE30), its value the bank's index here (0 code, 1 data, 2 the store,
3 the stages): bankcode, bankdata, bankstore and bankstages are set to 0-3. py65 never runs the IRQ: anything
timed is jsbeeb's.
"""
import json
import os

from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, '..', 'build')
SENTINEL = 0xFFF0                                   # a return address that ends a call


def ssd_files(path):
    """An .ssd's files: {name: (load, exec, bytes)}."""
    d = open(path, 'rb').read()
    files = {}
    for i in range(d[0x105] // 8):
        name = d[8 + i * 8:15 + i * 8].decode('latin1').rstrip()
        e = d[0x108 + i * 8:0x110 + i * 8]
        mixed = e[6]
        load = e[0] | e[1] << 8 | (mixed >> 2 & 3) << 16
        exe = e[2] | e[3] << 8 | (mixed >> 6 & 3) << 16
        length = e[4] | e[5] << 8 | (mixed >> 4 & 3) << 16
        sector = e[7] | (mixed & 3) << 8
        files[name] = (load, exe, d[sector * 256:sector * 256 + length])
    return files


def unzx02(src, pos=0):
    """Unpack a ZX02 stream, step for step as src/dzx02.6502 does (its bit reservoir included).
    Returns (the bytes, the position after the stream)."""
    out = bytearray()
    st = {'bitr': 0x80, 'pos': pos}

    def asl():                                      # ASL bitr: the carry out
        c = st['bitr'] >> 7
        st['bitr'] = st['bitr'] << 1 & 0xFF
        return c

    def get_elias(x, c=None):
        """get_elias with X = x (or elias_skip1 with the carry c): the value, 8-bit (0 for 256)."""
        while True:
            if c is None:
                c = asl()
                if st['bitr'] == 0:                 # a new byte of bits; the sentinel's 1 rolls in
                    a = src[st['pos']]
                    st['pos'] += 1
                    c = a >> 7
                    st['bitr'] = (a << 1 | 1) & 0xFF
            if not c:
                return x
            a = (x << 1 | asl()) & 0xFF             # elias_get: the next data bit into the result
            x = a
            c = None

    offset = 1
    state = 'literal'
    while True:
        if state == 'literal':
            n = get_elias(1) or 256                 # decode_literal: a run of bytes
            out += src[st['pos']:st['pos'] + n]
            st['pos'] += n
            if asl():
                state = 'new_offset'
                continue
            n = get_elias(1) or 256                 # a repeat of the last offset
        else:
            x = get_elias(1)                        # new_offset
            if x == 0:
                return bytes(out), st['pos']
            lo = src[st['pos']]
            st['pos'] += 1
            offset = (x - 1) * 128 + (lo >> 1) + 1
            n = (get_elias(1, lo & 1) + 1) & 0xFF or 256
        for _ in range(n):                          # copy
            out.append(out[-offset])
        state = 'new_offset' if asl() else 'literal'


def symbols(path=os.path.join(BUILD, 'chasehq.json')):
    """Every symbol in the build, scoped names as Baron writes them."""
    syms = {}
    for asm in json.load(open(path))['assemblies']:
        for section in asm['sections']:
            for kind in ('labels', 'za_autos', 'assignments'):
                for k, v in (section.get(kind) or {}).items():
                    syms[k] = v['value'] if isinstance(v, dict) else v
    return syms


def store_labels(path=os.path.join(BUILD, 'chasehq.json')):
    """The labels in the store's bank (SwramStore): its routines and the text's data."""
    out = set()
    for asm in json.load(open(path))['assemblies']:
        for section in asm['sections']:
            if section.get('name') == 'SwramStore':
                out.update(section.get('labels') or {})
    return out


class Machine:
    """py65 over 64K, the banks paged in at &8000 by writes to ROMSEL."""

    def __init__(self, ssd=os.path.join(BUILD, 'chasehq.ssd'), stage=1):
        self.syms = symbols()
        self.store = store_labels()
        files = ssd_files(ssd)
        self.banks = [bytearray(unzx02(files[n][2])[0].ljust(0x4000, b'\0')) for n in ('CHASEC', 'CHASED')]
        self.ram = bytearray(0x10000)
        load, _, chase2 = files['CHASE2']
        load &= 0xFFFF
        for image, org in (('maincode_image', 'MainCodeOrg'), ('panel_image', 'PanelAddr')):
            body, _ = unzx02(chase2, self.syms[image] - load)
            a = self.syms[org]
            self.ram[a:a + len(body)] = body
        self.ram[0], self.ram[1] = 0, 1                 # bankcode, bankdata
        for i, n in ((2, 'CHASES'), (3, 'CHASEL')):     # bankstore and bankstages, if the build has them
            if n in files:
                self.banks.append(bytearray(unzx02(files[n][2])[0].ljust(0x4000, b'\0')))
                self.ram[i] = i
        self.paged = 0
        self.ram[0x8000:0xC000] = self.banks[0]
        mem = ObservableMemory(subject=self.ram)
        mem.subscribe_to_write([0xFE30], self._romsel)
        self.mem = mem
        self.mpu = MPU(memory=mem)
        # the loader's tables in the code's bank: its make_tables run where CHASE2 loads (playfield A, drawn
        # over), then the playfield cleared
        self.ram[load:load + len(chase2)] = chase2
        self.call('make_tables')
        self.ram[load:load + len(chase2)] = bytes(len(chase2))
        if 'stage_load' in self.syms:                   # the stage's own data put in place, as stage_start does
            self.poke('back', 0x40)
            self.poke('Stage', stage)
            self.call('stage_load', max_steps=20_000_000)

    def _romsel(self, address, value):
        if value != self.paged:
            self.banks[self.paged][:] = self.ram[0x8000:0xC000]
            self.ram[0x8000:0xC000] = self.banks[value]
            self.paged = value
        return value

    def addr(self, name):
        return name if isinstance(name, int) else self.syms[name]

    def call(self, name, a=0, x=0, y=0, max_steps=5_000_000):
        """Run a routine to its RTS (one in the store's bank with it paged in, as its stubs do). Returns the
        cycles it took."""
        if name in self.store:
            back = self.paged
            self._romsel(0xFE30, 2)
            try:
                return self.call(self.syms[name], a, x, y, max_steps)
            finally:
                self._romsel(0xFE30, back)
        mpu = self.mpu
        mpu.a, mpu.x, mpu.y = a, x, y
        mpu.sp = 0xFF
        ret = SENTINEL - 1
        mpu.memory[0x1FF] = ret >> 8
        mpu.memory[0x1FE] = ret & 0xFF
        mpu.sp = 0xFD
        mpu.pc = self.addr(name)
        start = mpu.processorCycles
        for _ in range(max_steps):
            if mpu.pc == SENTINEL:
                return mpu.processorCycles - start
            mpu.step()
        raise RuntimeError(f'{name}: no RTS within {max_steps} steps, PC &{mpu.pc:04X}')

    def _mem(self, name):
        """The memory a name's in, and its offset there: the store's bank's own copy unless it's paged."""
        a = self.addr(name)
        if name in self.store and self.paged != 2:
            return self.banks[2], a - 0x8000
        return self.ram, a

    def peek(self, name, n=1):
        m, a = self._mem(name)
        return bytes(m[a:a + n]) if n > 1 else m[a]

    def poke(self, name, data):
        m, a = self._mem(name)
        data = bytes([data]) if isinstance(data, int) else bytes(data)
        m[a:a + len(data)] = data
