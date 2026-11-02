"""Make the speech's bank from the CPC disc: its five phrases (CHASEHQ.BI1, the 128K CPC's bank 4), each
nibble an AY volume, mapped to the SN76489's attenuation.

    python tools/genspeech.py build/gen

writes
    speech1.bin .. speech5.bin
                  the phrases, two samples a byte (high nibble first), each the SN76489 attenuation for the
                  AY volume the CPC wrote
    speechstore.6502
                  for the store's bank (src/store.6502): each phrase packed on its own by ZX02, at SpeechPack1-5
                  (decisions D17: speak unpacks one into the hidden playfield, then plays it)
    speech.6502   SpeechPackLo/Hi and SpeechLenLo/Hi: phrase n (1-5) at index n - 1, its packed bytes in the
                  store's bank and its unpacked length

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
    lengths = []
    for n in range(1, PHRASES + 1):
        e = TABLE + 4 * n
        length = m.mem[e] | m.mem[e + 1] << 8
        addr = m.mem[e + 2] | m.mem[e + 3] << 8
        raw = bank[addr - WINDOW:addr - WINDOW + length]
        assert len(raw) == length, f'phrase {n} past the bank'
        assert length <= 0x2000, f'phrase {n} is more than a playfield'
        lengths.append(length)
        with open(os.path.join(out, f'speech{n}.bin'), 'wb') as f:
            f.write(bytes(attenuation(b >> 4) << 4 | attenuation(b & 15) for b in raw))
    with open(os.path.join(out, 'speechstore.6502'), 'w') as f:
        f.write('\\\\ speechstore.6502 - made by tools/genspeech.py from the CPC disc: do not edit.\n\n')
        f.write('\\\\ the phrases (1-5), each packed on its own (speak unpacks one into the hidden playfield)\n')
        for n in range(1, PHRASES + 1):
            f.write(f'\n.SpeechPack{n}\n    SECTION SpeechPhrase{n}, transform = "zx02"\n'
                    f'        INCBIN "speech{n}.bin"\n    ENDSECTION\n')
    with open(os.path.join(out, 'speech.6502'), 'w') as f:
        f.write('\\\\ speech.6502 - made by tools/genspeech.py from the CPC disc: do not edit.\n\n')
        f.write('\\\\ the phrases (1-5 at 0-4): their packed bytes in the store\'s bank, and their unpacked '
                'length\n\n')
        packs = [f'SpeechPack{n}' for n in range(1, PHRASES + 1)]
        for lab, vals in (('SpeechPackLo', [f'LO({p})' for p in packs]),
                          ('SpeechPackHi', [f'HI({p})' for p in packs]),
                          ('SpeechLenLo', [f'&{n & 255:02X}' for n in lengths]),
                          ('SpeechLenHi', [f'&{n >> 8:02X}' for n in lengths])):
            f.write(f'.{lab}\n    EQUB ' + ', '.join(vals) + '\n')
    data = sum(lengths)
    print(f'{PHRASES} phrases, {data} bytes')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'build/gen')
