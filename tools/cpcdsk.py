"""Read the files from an AMSDOS data-format .DSK image (standard CPCEMU format).

    python tools/cpcdsk.py docs/chasehq.dsk [outdir]

lists the files and, given outdir, writes each one's body (the AMSDOS header removed).
read_dsk(path) returns {name: {'load', 'exec', 'data'}} for other tools.
"""
import os
import struct
import sys


def _sectors(img):
    ntracks, nsides = img[0x30], img[0x31]
    tsize = struct.unpack('<H', img[0x32:0x34])[0]
    tracks = {}
    for t in range(ntracks * nsides):
        base = 0x100 + t * tsize
        ti = img[base:base + 0x100]
        assert ti[:10] == b'Track-Info', t
        size = 128 << ti[0x14]
        secs = {}
        off = base + 0x100
        for s in range(ti[0x15]):
            secs[ti[0x18 + s * 8 + 2]] = img[off:off + size]
            off += size
        tracks[t] = secs
    return tracks


def read_dsk(path):
    """The disc's files: {name: {'load', 'exec', 'data'}}, data without its AMSDOS header."""
    img = open(path, 'rb').read()
    tracks = _sectors(img)

    def block(b):                                   # data format: 1K blocks, sectors &C1-&C9, no reserved tracks
        out = b''
        for lin in (b * 2, b * 2 + 1):
            t, s = divmod(lin, 9)
            out += tracks[t][0xC1 + s]
        return out

    directory = block(0) + block(1)
    extents = {}
    for i in range(64):
        e = directory[i * 32:(i + 1) * 32]
        if e[0] == 0xE5:
            continue
        name = bytes(c & 0x7F for c in e[1:9]).decode('latin1').rstrip()
        ext = bytes(c & 0x7F for c in e[9:12]).decode('latin1').rstrip()
        key = f'{name}.{ext}' if ext else name
        extents.setdefault(key, []).append((e[12], e[15], [b for b in e[16:32] if b]))
    files = {}
    for key, exts in extents.items():
        data = b''
        for _, records, blocks in sorted(exts):
            data += b''.join(block(b) for b in blocks)[:records * 128]
        head = data[:128]
        if len(data) >= 128 and sum(head[:67]) & 0xFFFF == struct.unpack('<H', head[67:69])[0]:
            length = head[64] | head[65] << 8 | head[66] << 16
            files[key] = {'load': struct.unpack('<H', head[21:23])[0],
                          'exec': struct.unpack('<H', head[26:28])[0],
                          'data': data[128:128 + length]}
        else:
            files[key] = {'load': None, 'exec': None, 'data': data}
    return files


if __name__ == '__main__':
    files = read_dsk(sys.argv[1])
    for name, f in sorted(files.items()):
        load = f'&{f["load"]:04X}' if f['load'] is not None else '-'
        print(f'{name:14s} {len(f["data"]):6d} bytes  load {load}')
        if len(sys.argv) > 2:
            with open(os.path.join(sys.argv[2], name), 'wb') as out:
                out.write(f['data'])
