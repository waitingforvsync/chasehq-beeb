"""The text system's data for the BBC, in its final form, from the CPC (docs/cpc-text.md).

    python tools/gentext.py build/gen [stage]

writes text.6502, and previews in the same directory, all drawn from the BBC bytes below as the 6502 would
draw them: text_font.png (the font at both sizes), text_faces.png, text_page_<name>.png for each page and
text_msg_<name>.png for a few messages and the static.

What text.6502 holds (English only):
- Font1, the message font (the CPC's &56BF: 41 glyphs, 2 bytes by 8 lines) as MODE 2 bytes. A glyph is its
  two character cells column by column (the left cell's 8 lines, then the right's), which is the screen's own
  order: on a row-aligned page entry it's 16 consecutive bytes. It's stored byte-planar, byte i of glyph g at
  Font1 + i * Glyphs1 + g, so with X the glyph a glyph is 16 `LDA Font1+i*Glyphs1,X : STA (dst),Y`, with no
  pointer to make for the source. The panel's message line straddles rows 6 and 7 at line 4: the same 16
  bytes go there through two destination pointers, lines 0-3 to row 6 (4 bytes on) and 4-7 to row 7 (4
  bytes back). A size-2 page entry doubles lines 1-6 at run time as the CPC does (&1424, &1436, &1416): white,
  0, 1, 1, 2, 2, 3, 3 in its top row and 4, 4, 5, 5, 6, 6, 7, white in the next, each source byte loaded once.
- Glyph numbers: 0-9 the digits (0 is the CPC's O, which it uses for zero), 10 space, then the letters without
  O, then . , ! ' -. A figure patched into a page is its digit, or GlyphSpace.
- The faces (Nancy &D600, the partner &DE00, and the stage's own (&5BCA) if it has one): 8 cells by 40 lines,
  as the panel's rows 1-5 hold them, 64 bytes a row (cells 43-50, 8 lines each): a row is one 64-byte copy.
- The message scripts as the CPC's (&1DB4), with the text as glyph numbers, its length first:
      segment:  face (0 the stage's, 1 Nancy, 2 the partner), then lines [n, n glyphs], then &FF (the end) or
                &FE and an address (static, then that script)
      choice:   &FC and three addresses: random < &55 the first, < &AA the second, else the third
- The pages (&139F), each entry's loop worked out from the CPC's delays:
      page:     its last loop (the request's loop is 1), entries, then 0
      entry:    the loop it appears, size (1, 2), offset (2 bytes: the box's left cell at the text's first line,
                row * 512 + cell * 8 from the playfield's start), n, n glyphs
  Labels mark the glyphs the game patches (the bonus page's figures, the continue page's countdown).
- The dissolve (&1337): the CPC's 19 masks of 8 lines x (even cell, odd cell), and its six patterns.

Colours (D5, D7): each pen takes its D7 pair over 2x2 blocks of the glyph's or face's own pixels, as the
sprites do (gensprites.py): a pen on two of a block's pixels gets its pair one colour each, otherwise each
pixel its pair's colour by x + y parity. Glyphs and faces sit at even pixels and even lines, so that parity
is the screen's. The text is opaque: no byte has bit 3 set.
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from cpc import CPC, mode0_pens                     # noqa: E402
from cpcdsk import read_dsk                         # noqa: E402
from gendata import pair_for, mode2_byte, BBC_RGB, siren_colours, panel_bytes   # noqa: E402

BASE = 0x59AB                                       # the stage block's address
FONT = 0x56BF                                       # the message font: 16 bytes a glyph, 2 bytes by 8 lines
CPC_GLYPHS = 41                                     # A-Z . , ! ' space 1-9 - (41 on is code)
WHITE_PEN = 2                                       # the boxes' and the message line's background (&0C)
CHARS = "0123456789 ABCDEFGHIJKLMNPQRSTUVWXYZ.,!'-"   # the BBC's glyph numbers; O is glyph 0
FACE_W, FACE_H = 8, 40                              # bytes, lines
FACE_ROW, FACE_CELL = 1, 43                         # where a face goes: panel rows 1-5, cells 43-50
MASKS, MASK_COUNT = 0xFEB0, 19                      # the dissolve's masks: 16 bytes each, to &FFCF
DOUBLE = (None, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, None)    # a size-2 entry's lines (None white)

# the scripts the game requests (&1DB4: HL the script, A its priority): label, CPC address, priority, where
MESSAGES = [
    ('MsgTurbo', 0x1AB0, 2, '&158A: a turbo starts'),
    ('MsgCrash', 0x1A97, 3, '&31A3: a traffic car hit'),
    ('MsgRam', 0x1A57, 5, '&3035: the criminal rammed'),
    ('MsgSlow', 0x1A83, 10, '&3879: 100 loops below speed 120'),
    ('MsgRam19', 0x1AC3, 10, '&3C9C: the 19th ram'),
    ('MsgForkRight', 0x1AF2, 20, '&4087: past the fork on the criminal\'s branch'),
    ('MsgForkWrong', 0x1A4D, 20, '&4087: past the fork on the other branch'),
    ('MsgTime15', 0x1A89, 21, '&202B: the clock reaches 15'),
    ('MsgStart', 0x1AF8, 255, '&035F: the stage starts, on a 64K CPC (no speech)'),
    ('MsgGameOver', 0x1AC9, 255, '&046D: the game over sequence starts'),
]
AIRBORNE = [                                        # only with a stage face, (&5BCA) <> 0: stages 2 and 4
    ('MsgAirLeft', 0x1A14, 15, '&32E3: the airborne patrol, the criminal turned left'),
    ('MsgAirRight', 0x1A24, 15, '&32E3: the airborne patrol, the criminal turned right'),
]
BRIEFING = ('MsgBriefing', 'brief', 255, '&04FB: the stage\'s briefing, in its intro (the stage record\'s (&5BDA))')

# the pages (&139F: HL the page): label, CPC address ('arrest': the stage record's), where
PAGES = [
    ('PageSighting', 0x11DE, '&3C68: the criminal sighted'),
    ('PageTimeUp', 0x1269, '&203F: time up, requested every loop while the car coasts'),
    ('PageContinue', 0x1277, '&209D: the continue offer, requested every loop'),
    ('PageGameOver', 0x1259, '&0478: the game over sequence, requested every loop'),
    ('PagePullOver', 0x1222, '&1185: the 20th ram'),
    ('PageArrest', 'arrest', '&1003: the stage end\'s state 3 (the stage record\'s (&5BDC))'),
    ('PageBonus', 0x118D, '&10B6: the stage end\'s state 4, its figures patched first'),
]
PATCHES = {                                         # a patched character's CPC address: label, glyphs
    0x12CB: ('PageContinueTime', 2),                # "TIME nn": tens or space, units (&20C7)
    0x11A1: ('PageBonusClear', 2),                  # the clear bonus's leading figures (&102F)
    0x11B9: ('PageBonusTime', 2),                   # seconds left: tens or space, units (&1042-&1077)
    0x11D4: ('PageBonusScore', 8),                  # the score, leading zeros as spaces (&107A)
}
EXAMPLE = {'PageContinueTime': ' 7', 'PageBonusClear': '10', 'PageBonusTime': '50',
           'PageBonusScore': '  455445'}            # for the previews: as run_b's bonus page had them

# the 6502's costs as estimated in docs/cpc-text.md (cycles): a size-1 glyph with its border bytes, a
# size-2 glyph doubled from Font1, and an entry's box and set-up
COST_GLYPH = {1: 257, 2: 350}
COST_ENTRY = {1: 265, 2: 390}


class Mem:
    """Main memory with a stage's block over &59AB."""

    def __init__(self, mem, block):
        self.mem, self.block = mem, block

    def rd(self, a):
        return self.block[a - BASE] if BASE <= a < BASE + len(self.block) else self.mem[a]

    def rw(self, a):
        return self.rd(a) | self.rd(a + 1) << 8

    def text(self, a):
        """A CPC string (bit 7 on its last character) and the address after it."""
        s = []
        while True:
            c = self.rd(a)
            s.append(chr(c & 0x7F))
            a += 1
            if c & 0x80:
                return ''.join(s), a


def cpc_glyph(ch):
    """A character's glyph in the CPC's font, as &1F61 picks it."""
    c = ord(ch)
    if c >= 0x41:
        g = c - 0x41
    else:
        g = {'.': 26, ',': 27, '!': 28, "'": 29, ' ': 30, '-': 40, '0': 14}.get(ch, c - 0x12)
    assert 0 <= g < CPC_GLYPHS, f'{ch!r} has no glyph (&1F61 would give {g})'
    return g


def glyph(ch):
    return 0 if ch == 'O' else CHARS.index(ch)


def block_colours(pens, pairs):
    """Pens [line][pixel] -> BBC colours: D7 pairs over 2x2 blocks of the image's own pixels."""
    h, w = len(pens), len(pens[0])
    out = [[0] * w for _ in range(h)]
    for y0 in range(0, h, 2):
        for x0 in range(0, w, 2):
            cells = [(x, y) for x, y in ((x0, y0), (x0 + 1, y0), (x0, y0 + 1), (x0 + 1, y0 + 1)) if x < w and y < h]
            block = [pens[y][x] for x, y in cells]
            seen = {}
            for (x, y), p in zip(cells, block):
                a, b = pairs[p]
                if block.count(p) == 2:
                    out[y][x] = (a, b)[seen.get(p, 0)]
                    seen[p] = 1
                else:
                    out[y][x] = (a, b)[(x + y) & 1]
    return out


def column_bytes(cols, lines):
    """BBC colours [line][pixel] -> bytes, a 2-pixel column at a time, each column's given lines."""
    out = bytearray()
    for bx in range(len(cols[0]) // 2):
        for y in lines:
            out.append(mode2_byte(cols[y][2 * bx], cols[y][2 * bx + 1]))
    return out


def cpc_pens(m, a, w, h):
    """A CPC image of w bytes by h lines at a: pens [line][pixel]."""
    rows = []
    for y in range(h):
        row = []
        for b in range(w):
            row += mode0_pens(m.rd(a + w * y + b))
        rows.append(row)
    return rows


class Text:
    """The font, the scripts and the pages, read from the CPC."""

    def __init__(self, m, pairs):
        self.m, self.pairs = m, pairs
        assert pairs[WHITE_PEN] == (7, 7), 'the boxes are white'
        self.white = mode2_byte(7, 7)
        self.font = [column_bytes(block_colours(cpc_pens(m, FONT + 16 * cpc_glyph(ch), 2, 8), pairs), range(8))
                     for ch in CHARS]
        self.nodes = {}                             # CPC address: ('choice', targets) or ('seg', face, lines, next)
        self.pages = []                             # (label, last loop, entries, where)

    def node(self, a):
        """Read the script at a, and everything it leads to, into self.nodes."""
        if a in self.nodes:
            return
        m = self.m
        if m.rd(a) == 0xFC:
            targets = [m.rw(a + 1 + 2 * k) for k in range(3)]
            self.nodes[a] = ('choice', targets)
            for t in targets:
                self.node(t)
            return
        lines, p, nxt = [], a + 1, None
        while True:
            if lines and m.rd(p) == 0xFF:           # (a segment's first line is read whatever its first byte
                break                               # is, at &1E79: "OH, NO!" at &18FF shows)
            if lines and m.rd(p) == 0xFE:
                nxt = m.rw(p + 1)
                break
            s, _ = m.text(m.rw(p))
            assert 1 <= len(s) <= 31 and '"' not in s, f'a line of {len(s)}: {s!r}'
            lines.append(s)
            p += 4
        self.nodes[a] = ('seg', m.rd(a), lines, nxt)
        if nxt is not None:
            self.node(nxt)

    def page(self, label, a, where):
        """A CPC page: [d0] then [d][size][offset][text] ... [d][0]. The delay before an entry is loaded as
        it appears (&1378) and counts that loop, so entry i + 1 appears d_i - 1 loops after entry i, and
        the page ends as the next would appear."""
        m = self.m
        at, p, entries = m.rd(a), a + 1, []
        while True:
            d, size = m.rd(p), m.rd(p + 1)
            if size == 0:
                break
            assert d >= 1, 'a delay of 0 would be 256 loops'
            off = m.rw(p + 2)
            line, cpcrow, cell = off >> 11, (off & 0x7FF) >> 6, off & 63
            assert line == (7 if size == 1 else 0), 'size 1 starts the line above a row, size 2 a row'
            row = cpcrow - 8 + (size == 1)          # the text's first row in the playfield
            s, nxt = m.text(p + 4)
            assert len(s) >= 1, 'page_draw counts an entry\'s glyphs down from at least 1'
            assert (row >= 1 or size == 2) and row + 1 <= 15 and cell + 1 + 2 * len(s) <= 63, 'off the playfield'
            patches = {i: PATCHES[p + 4 + i] for i in range(len(s)) if p + 4 + i in PATCHES}
            entries.append((at, size, row, cell, s, patches))
            at += d - 1
            p = nxt
        self.pages.append((label, at, entries, where))


# drawing from the BBC bytes, as the 6502 would (for the previews)

def draw_entry(t, play, size, row, cell, s):
    """A page entry into a playfield (16 rows of 512 bytes): its box, then its glyphs."""
    w, wl, wr = t.white, mode2_byte(7, 0), mode2_byte(0, 7)

    def at(r, c, ln):
        return r * 512 + c * 8 + ln

    def over(a, keep, ink):
        play[a] = play[a] & keep | ink
    right = cell + 1 + 2 * len(s)
    if size == 1:                                   # lines -1 to 8: the left column's left pixel 0-7 only
        over(at(row - 1, cell, 7), 0xAA, wr)
        over(at(row + 1, cell, 0), 0xAA, wr)
        for ln in range(8):
            play[at(row, cell, ln)] = w
            over(at(row, right, ln), 0x55, wl)
    else:                                           # lines 0-15: both columns' outer pixel 2-13 only
        for ln in range(16):
            a = at(row + ln // 8, cell, ln & 7)
            if 2 <= ln < 14:
                play[a] = w
                over(at(row + ln // 8, right, ln & 7), 0x55, wl)
            else:
                over(a, 0xAA, wr)
    for k, ch in enumerate(s):
        c, g = cell + 1 + 2 * k, t.font[glyph(ch)]
        for col in (0, 1):
            if size == 1:
                play[at(row - 1, c + col, 7)] = w
                play[at(row + 1, c + col, 0)] = w
                for ln in range(8):
                    play[at(row, c + col, ln)] = g[8 * col + ln]
            else:
                for ln, src in enumerate(DOUBLE):
                    play[at(row + ln // 8, c + col, ln & 7)] = w if src is None else g[8 * col + src]


def draw_line(t, panel, s):
    """A whole message line into the panel: cleared to white, then its glyphs from column 0."""
    for c in range(1, 63):
        for ln in range(4, 8):
            panel[6 * 512 + 8 * c + ln] = t.white
        for ln in range(4):
            panel[7 * 512 + 8 * c + ln] = t.white
    for k, ch in enumerate(s):
        base = 8 * (1 + 2 * k)
        g = t.font[glyph(ch)]
        for i in range(16):
            if i & 4:
                panel[7 * 512 - 4 + base + i] = g[i]    # glyph lines 4-7: row 7, lines 0-3
            else:
                panel[6 * 512 + 4 + base + i] = g[i]    # glyph lines 0-3: row 6, lines 4-7


def draw_face(panel, face):
    for r in range(5):
        a = (FACE_ROW + r) * 512 + FACE_CELL * 8
        panel[a:a + 64] = face[64 * r:64 * r + 64]


def render(buf, rows, path, siren=()):
    """MODE 2 character rows (512 bytes each) -> a PNG at the BBC's aspect (4 x 2 a pixel); logical 8-15
    as the sirens' normal colours."""
    img = Image.new('RGB', (512, rows * 16))
    px = img.load()
    for y in range(rows * 8):
        for xb in range(64):
            b = buf[(y >> 3) * 512 + xb * 8 + (y & 7)]
            for k, shift in ((0, 1), (1, 0)):
                c = sum((b >> (shift + 2 * i) & 1) << i for i in range(4))
                c = siren[c - 8][0] if c >= 8 else c
                for dx in range(4):
                    for dy in range(2):
                        px[(2 * xb + k) * 4 + dx, y * 2 + dy] = BBC_RGB[c & 7]
    img.save(path)


def backdrop(pairs):
    """Something to draw the pages over: the sky's blue above, grass below, each dithered."""
    play = bytearray(16 * 512)
    for y in range(128):
        a, b = pairs[5 if y < 64 else 8]
        for xb in range(64):
            play[(y >> 3) * 512 + xb * 8 + (y & 7)] = mode2_byte(a, b) if y & 1 == 0 else mode2_byte(b, a)
    return play


def static_bytes(white):
    """The face box's static from the CPC's generator as it powers on: each byte the first of its two calls
    (the CPC's &C000 buffer's), AND &0C."""
    s0, s1, s2 = 0x7B, 0x2D, 0xE9
    out = bytearray()
    for i in range(640):
        s0, s1 = (s0 - 0x8D) & 255, (s1 + 3) & 255
        a = (s0 + s1) & 255
        s2 = ((s2 >> 1 | s2 << 7) & 255) + (a >> 1 | a << 7) & 255
        if i & 1 == 0:
            out.append((0, mode2_byte(0, 7), mode2_byte(7, 0), white)[(s2 & 0x0C) >> 2])
    return out


# writing

class Out:
    """Baron source with trailing comments on column 40 (44 past it), and a count of the bytes."""

    def __init__(self):
        self.lines, self.bytes = [], 0

    def __call__(self, code='', comment=None):
        if comment is not None:
            col = 40 if len(code) < 39 else 44 if len(code) < 43 else len(code) + 1
            code = code.ljust(col) + '; ' + comment.rstrip()
        self.lines.append(code)

    def equb(self, values, comment=None, per=16):
        values = list(values)
        for i in range(0, len(values), per):
            self('    EQUB ' + ', '.join(values[i:i + per]), comment if i == 0 else None)
        self.bytes += len(values)


def hexes(data):
    return [f'&{v:02X}' for v in data]


def main(out, stage=1):
    os.makedirs(out, exist_ok=True)
    cpc = CPC()
    assert cpc.run_to(0x0300)
    files = read_dsk(os.path.join(os.path.dirname(__file__), '..', 'docs', 'chasehq.dsk'))
    m = Mem(bytes(cpc.mem), files[f'CHASEHQ.LV{stage}']['data'])
    pairs = [pair_for(cpc.inks[p]) for p in range(16)]
    t = Text(m, pairs)

    faces = [('FaceNancy', 1, m.rw(0x17AE)), ('FacePartner', 2, m.rw(0x17B0))]
    stage_face = m.rw(0x5BCA)
    if stage_face:
        faces.insert(0, ('FaceStage', 0, stage_face))
    face_bytes = {}
    for name, _, a in faces:
        cols = block_colours(cpc_pens(m, a, FACE_W, FACE_H), pairs)
        face_bytes[name] = b''.join(column_bytes(cols[8 * r:8 * r + 8], range(8)) for r in range(5))

    roots = MESSAGES + (AIRBORNE if stage_face else []) + [BRIEFING[:1] + (m.rw(0x5BDA),) + BRIEFING[2:]]
    for _, a, _, _ in roots:
        t.node(a)
    for a, n in t.nodes.items():
        assert n[0] == 'choice' or n[1] != 0 or stage_face, f'&{a:04X} shows a stage face stage {stage} lacks'
    names = {a: name for name, a, _, _ in roots}
    for label, a, where in PAGES:
        t.page(label, m.rw(0x5BDC) if a == 'arrest' else a, where)

    def label(a):
        return names.get(a, f'Msg{a:04X}')

    w = Out()
    sizes = {}
    w('\\\\ text.6502 - made by tools/gentext.py from the CPC disc: do not edit.')
    w(f'\\\\ The message window\'s, the pages\' and the dissolve\'s data, stage {stage}, English (docs/cpc-text.md).')
    w()
    w('\\\\ the glyphs\' numbers: 0-9 the digits (the O is 0), 10 space, the letters, then . , ! \' -; TextGlyphs maps')
    w('\\\\ a string to them (Baron\'s FIND errs on a character with no glyph), and GLYPHS puts down its length,')
    w('\\\\ then them')
    w()
    w(f'TextChars = "{CHARS}"')
    w('GlyphSpace = FIND(TextChars, " ")')
    w('Glyphs1 = LEN(TextChars)', 'Font1\'s glyphs: the stride of its planes')
    w('FUNCTION TextGlyphs(s) = FIND(CODES(TextChars), WHERE(CODES(s) == \'O\', \'0\', CODES(s)))')
    w()
    w('MACRO GLYPHS s')
    w('    EQUB LEN(s), TextGlyphs(s)')
    w('ENDMACRO')
    w()
    w('\\\\ the boxes\' bytes: white (the CPC\'s pen 2, &0C) whole, on one pixel, and the masks keeping the other')
    w()
    w(f'TextWhite = &{t.white:02X}')
    w(f'TextWhiteL = &{mode2_byte(7, 0):02X}', 'the left pixel white, after AND TextKeepR')
    w(f'TextWhiteR = &{mode2_byte(0, 7):02X}', 'the right pixel white, after AND TextKeepL')
    w('TextKeepL = &AA', 'keeps the left pixel')
    w('TextKeepR = &55', 'keeps the right pixel')
    w()
    w('\\\\ where the message window draws: the face (panel rows 1-5, cells 43-50, each row\'s 64 bytes a run) and')
    w('\\\\ the line (lines 52-59, cells 1-62: row 6 from line 4, row 7 to line 3). Glyph byte i (cell i DIV 8,')
    w('\\\\ line i AND 7) of column c goes to MsgLineTop + 8 * (1 + 2c) + i for lines 0-3, MsgLineBottom +')
    w('\\\\ 8 * (1 + 2c) + i for lines 4-7')
    w()
    w(f'MsgFaceAt = PanelAddr + {FACE_ROW} * RowBytes + {FACE_CELL} * 8')
    w('MsgFaceRows = 5')
    w('MsgLineTop = PanelAddr + 6 * RowBytes + 4')
    w('MsgLineBottom = PanelAddr + 7 * RowBytes - 4')
    w('MsgLineCell = 1', 'column c\'s left cell is 1 + 2c')
    w('MsgColumns = 31')
    w('MsgStaticLoops = 4', 'static before a face, and before the face goes')
    w('MsgPauseLoops = 10', 'a finished line stays, counting its last glyph\'s')
    w()
    w('\\\\ the static\'s bytes by the CPC\'s random byte AND &0C, read in place (4 apart): bit 3 the left pixel')
    w('\\\\ white, bit 2 the right (the CPC\'s pens 0 and 2)')
    w()
    w('    INPAGE 13')
    w('.MsgStaticBytes')
    spread = [0] * 13
    for k, b in enumerate((0, mode2_byte(0, 7), mode2_byte(7, 0), t.white)):
        spread[4 * k] = b
    w.equb(hexes(spread))
    w()

    n0 = w.bytes
    w('\\\\ Font1: the message font (the CPC\'s &56BF), byte-planar: byte i of glyph g at Font1 + i * Glyphs1 + g;')
    w('\\\\ bytes 0-7 the left cell\'s lines 0-7, 8-15 the right cell\'s; glyphs in TextChars\' order')
    w()
    w('.Font1')
    for i in range(16):
        w.equb(hexes(g[i] for g in t.font), f'byte {i}')
    sizes['Font1'] = w.bytes - n0
    w()

    n0 = w.bytes
    w('\\\\ the faces: 5 rows of 64 bytes (cells 43-50, 8 lines each) for panel rows 1-5; by the scripts\' face')
    w('\\\\ byte (0 the stage\'s, 1 Nancy, 2 the partner)')
    if not stage_face:
        w(f'\\\\ (stage {stage} has no face of its own: (&5BCA) is 0 and no script shows face 0; 0 points at Nancy)')
    w()
    lab = {n: name for name, n, _ in faces}
    w('.FaceLo')
    w.equb([f'LO({lab.get(n, "FaceNancy")})' for n in range(3)])
    w('.FaceHi')
    w.equb([f'HI({lab.get(n, "FaceNancy")})' for n in range(3)])
    for name, n, a in faces:
        w(f'.{name}', f'the CPC\'s &{a:04X}')
        w.equb(hexes(face_bytes[name]))
    sizes['faces'] = w.bytes - n0
    w()

    n0 = w.bytes
    w('\\\\ the message scripts (&1DB4). A choice: &FC and three addresses (random < &55, < &AA, else). A segment:')
    w('\\\\ its face, its lines (length, glyphs), then &FF (the end) or &FE and the next\'s address (static first)')
    w()
    for name, a, prio, why in roots:
        w(f'{name}Prio = {prio}', why)
    w()
    order = []
    for _, a, _, _ in roots:                        # each root, then what it leads to
        todo = [a]
        while todo:
            x = todo.pop(0)
            if x in order:
                continue
            order.append(x)
            n = t.nodes[x]
            todo += n[1] if n[0] == 'choice' else [n[3]] if n[3] is not None else []
    for a in order:
        n = t.nodes[a]
        w(f'.{label(a)}', f'the CPC\'s &{a:04X}')
        if n[0] == 'choice':
            w('    EQUB &FC:EQUW ' + ', '.join(label(x) for x in n[1]))
            w.bytes += 7
            continue
        _, face, ls, nxt = n
        w.equb([str(face)], ('the stage\'s face', 'Nancy', 'the partner')[face])
        for s in ls:
            w(f'    GLYPHS "{s}"')
            w.bytes += 1 + len(s)
        if nxt is None:
            w.equb(['&FF'])
        else:
            w(f'    EQUB &FE:EQUW {label(nxt)}')
            w.bytes += 3
    sizes['scripts'] = w.bytes - n0
    w()

    n0 = w.bytes
    w('\\\\ the pages (&139F): the last loop drawn (the request\'s loop is 1), then the entries: the loop it')
    w('\\\\ appears, its size, its offset (the box\'s left cell at the text\'s first line: row * 512 + cell * 8')
    w('\\\\ from the playfield\'s start; a size-1 box takes the line above and below too), its length and glyphs;')
    w('\\\\ then 0. A request starts a page again')
    w()
    for name, last, entries, where in t.pages:
        w(f'.{name}', where)
        w.equb([str(last)], 'its last loop')
        for at, size, row, cell, s, patches in entries:
            w(f'    EQUB {at}, {size}:EQUW {row} * RowBytes + {cell} * 8', f'appears on loop {at}; size {size}, row {row}, cell {cell}')
            w.bytes += 4 + 1 + len(s)
            if not patches:
                w(f'    GLYPHS "{s}"')
                continue
            w(f'    EQUB {len(s)}')
            i = 0
            for c in sorted(patches) + [len(s)]:
                if c > i:
                    w(f'    EQUB TextGlyphs("{s[i:c]}")')
                if c in patches:
                    lab_, cnt = patches[c]
                    w(f'.{lab_}', f'{cnt} glyphs, patched')
                    w(f'    EQUB TextGlyphs("{s[c:c + cnt]}")')
                    i = c + cnt
        w.equb(['0'])
    sizes['pages'] = w.bytes - n0
    w()

    with open(os.path.join(out, 'text.6502'), 'w') as f:
        f.write('\n'.join(w.lines) + '\n')
    w.lines = ['\\\\ dissolve.6502 - made by tools/gentext.py from the CPC disc: do not edit.', '']

    n0 = w.bytes
    recs = [cpc.mem[MASKS + 16 * k:MASKS + 16 * k + 16] for k in range(MASK_COUNT)]
    w('\\\\ the dissolve (&1337): 19 masks for a pair of cells (even, odd), the same for every pair in the playfield,')
    w('\\\\ in the screen\'s order: byte i for cell i DIV 8 of the pair, line i AND 7 (the CPC has them by line, even')
    w('\\\\ then odd byte). A pattern ANDs one into the back playfield each loop for its count of loops, stepping,')
    w('\\\\ and draws its last one twice (no step on its last loop). Out (the CPC\'s A >= 0) steps +1, in steps -1.')
    w('\\\\ Pattern 1 + (random AND 3), 0 taken as 1')
    w()
    w('.DissolveMasks')
    for k, r in enumerate(recs):
        w.equb(hexes(r[2 * (i & 7) + (i >> 3)] for i in range(16)), f'{k}: the CPC\'s &{MASKS + 16 * k:04X}')
    pats = []
    for sign, table in ((1, 0x5305), (-1, 0x530E)):
        for p in (1, 2, 3):
            count, ptr = m.rd(table + 3 * p), m.rw(table + 3 * p + 1)
            first = (ptr - MASKS) // 16 + sign
            pats.append((first, count, [first + sign * min(i, count - 2) for i in range(count)]))
            assert all(0 <= k < MASK_COUNT for k in pats[-1][2])
    w('.DissolveFirst', 'the first mask: out patterns 1-3, then in 1-3')
    w.equb([str(f) for f, _, _ in pats])
    w('.DissolveCount', 'its loops')
    w.equb([str(c) for _, c, _ in pats])
    sizes['dissolve'] = w.bytes - n0

    with open(os.path.join(out, 'dissolve.6502'), 'w') as f:  # (its own file: it goes where there's room)
        f.write('\n'.join(w.lines) + '\n')

    # previews
    lights, siren = siren_colours(cpc, pairs)
    panel0 = panel_bytes(cpc, pairs, lights)
    font_preview(t, os.path.join(out, 'text_font.png'))
    face_preview(face_bytes, os.path.join(out, 'text_faces.png'))
    for name, last, entries, where in t.pages:
        play = backdrop(pairs)
        for at, size, row, cell, s, patches in entries:
            s = list(s)
            for c, (lab_, cnt) in patches.items():
                s[c:c + cnt] = EXAMPLE[lab_]
            draw_entry(t, play, size, row, cell, ''.join(s))
        render(bytes(panel0) + bytes(play), 24, os.path.join(out, f'text_page_{name[4:].lower()}.png'), siren)
    for tag, face, s in (('briefing', 'FaceNancy', 'THIS IS NANCY AT CHASE H.Q.'), ('ohno', 'FacePartner', 'OH, NO!'),
                         ('slow', 'FacePartner', "LET'S GET MOVIN' MAN!"),
                         ('wrongjob', 'FaceNancy', 'BETTER CHECK THE CLASSIFIED ADS')):
        panel = bytearray(panel0)
        draw_face(panel, face_bytes[face])
        draw_line(t, panel, s)
        render(bytes(panel), 8, os.path.join(out, f'text_msg_{tag}.png'), siren)
    panel = bytearray(panel0)
    draw_face(panel, static_bytes(t.white))
    render(bytes(panel), 8, os.path.join(out, 'text_msg_static.png'), siren)

    # what it comes to
    print(f'stage {stage}: {len(t.font)} glyphs, {len(faces)} faces, {len(order)} script nodes, {len(t.pages)} pages')
    print('bytes:', sizes, 'total', sum(sizes.values()))
    for name, last, entries, where in t.pages:
        g1 = sum(len(e[4]) for e in entries if e[1] == 1)
        g2 = sum(len(e[4]) for e in entries if e[1] == 2)
        cyc = sum(COST_ENTRY[e[1]] + COST_GLYPH[e[1]] * len(e[4]) for e in entries)
        print(f'  {name:13s} {last:3d} loops, {len(entries)} entries, {g1:2d} glyphs size 1, {g2:2d} size 2:'
              f' about {cyc:6,d} cycles a loop with all shown')
    for k, r in enumerate(recs):
        ff, zero = r.count(0xFF), r.count(0)
        print(f'  mask {k:2d}: {ff:2d} keep, {zero:2d} clear, {16 - ff - zero:2d} AND:'
              f' about {512 * (5 * zero + 11 * (16 - ff - zero)) + 512 * 6:6,d} cycles skipping and clearing')
    for i, (first, count, seq) in enumerate(pats):
        print(f'  {"out" if i < 3 else "in"} pattern {i % 3 + 1}: masks {seq}')


def font_preview(t, path):
    """The font on white: a row at size 1, then the same doubled as a size-2 entry draws it."""
    buf = bytearray([t.white]) * (6 * 512)
    for g, f in enumerate(t.font):
        r, c = 2 * (g // 21), 1 + 3 * (g % 21)
        for col in (0, 1):
            for ln in range(8):
                buf[r * 512 + 8 * (c + col) + ln] = f[8 * col + ln]
    for g in range(11, 32):
        c, f = 1 + 3 * (g - 11), t.font[g]
        for col in (0, 1):
            for ln, src in enumerate(DOUBLE):
                if src is not None:
                    buf[(4 + ln // 8) * 512 + 8 * (c + col) + (ln & 7)] = f[8 * col + src]
    render(bytes(buf), 6, path)


def face_preview(face_bytes, path):
    buf = bytearray(5 * 512)
    for k, data in enumerate(face_bytes.values()):
        for r in range(5):
            a = r * 512 + (4 + 12 * k) * 8
            buf[a:a + 64] = data[64 * r:64 * r + 64]
    render(bytes(buf), 5, path)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'build/gen', int(sys.argv[2]) if len(sys.argv) > 2 else 1)
