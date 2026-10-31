"""Make the speech's bank from the CPC disc: its five phrases (CHASEHQ.BI1, the 128K CPC's bank 4), each
nibble an AY volume, mapped to the SN76489's attenuation.

    python tools/genspeech.py build/gen

writes
    speech.bin    the phrases, one after another, two samples a byte (high nibble first), each the SN76489
                  attenuation for the AY volume the CPC wrote
    speech.6502   SpeechAddrLo/Hi and SpeechLenLo/Hi: phrase n (1-5) at index n - 1, its address in the bank
                  (&8000 on) and its bytes

The CPC plays a phrase (&0B75) a nibble at a time, high first, into AY volume registers 8 and 9, about 414 T
a sample (9.7 kHz). The AY's volume steps are about 3 dB apart, the SN76489's attenuation 2 dB: volume v (15
loudest) becomes attenuation round((15 - v) * 3 / 2), 15 (silent) beyond. The table's at &0B5D, 4 bytes a
phrase from phrase 0: its length, then its address in bank 4's window at &4000.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cpc import CPC                                 # noqa: E402
from cpcdsk import read_dsk                         # noqa: E402

TABLE = 0x0B5D
PHRASES = 5
WINDOW = 0x4000                                     # where the CPC pages its bank 4


def attenuation(v):
    """An AY volume (0-15) as the SN76489's attenuation (0 loudest, 15 off)."""
    return 15 if v == 0 else min(15, round((15 - v) * 1.5))


def main(out):
    os.makedirs(out, exist_ok=True)
    m = CPC()
    assert m.run_to(0x0300)
    bank = read_dsk(os.path.join(os.path.dirname(__file__), '..', 'docs', 'chasehq.dsk'))['CHASEHQ.BI1']['data']
    data = bytearray()
    places = []
    for n in range(1, PHRASES + 1):
        e = TABLE + 4 * n
        length = m.mem[e] | m.mem[e + 1] << 8
        addr = m.mem[e + 2] | m.mem[e + 3] << 8
        raw = bank[addr - WINDOW:addr - WINDOW + length]
        assert len(raw) == length, f'phrase {n} past the bank'
        places.append((0x8000 + len(data), length))
        data += bytes(attenuation(b >> 4) << 4 | attenuation(b & 15) for b in raw)
    assert len(data) <= 0x4000, 'the phrases fill more than a bank'
    with open(os.path.join(out, 'speech.bin'), 'wb') as f:
        f.write(data)
    with open(os.path.join(out, 'speech.6502'), 'w') as f:
        f.write('\\\\ speech.6502 - made by tools/genspeech.py from the CPC disc: do not edit.\n\n')
        f.write('\\\\ the phrases (1-5 at 0-4): their places in the speech\'s bank and their bytes\n\n')
        for lab, vals in (('SpeechAddrLo', [a & 255 for a, _ in places]), ('SpeechAddrHi', [a >> 8 for a, _ in places]),
                          ('SpeechLenLo', [n & 255 for _, n in places]), ('SpeechLenHi', [n >> 8 for _, n in places])):
            f.write(f'.{lab}\n    EQUB ' + ', '.join(f'&{v:02X}' for v in vals) + '\n')
    print(f'{PHRASES} phrases, {len(data)} bytes')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'build/gen')
