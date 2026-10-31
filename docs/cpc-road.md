# The CPC road: spec

How the Amstrad CPC Chase H.Q. draws the playfield behind the sprites (sky, backdrop, ground, road, rumble
strips, lane lines) and the course model behind it. Read from the Z80 in BI2 and LV1-LV5 on 2026-10-31 and
checked in the harness (`tools/cpc.py`). The scripts are in `work/road/` (git-ignored): `model.py` and
`render2.py` are a Python re-implementation of everything below except the fork and the tunnel mouth.

**Verified** means the Python model produced the same bytes as the emulator. Over 2,500 game loops of stage 1
(both fork branches), every non-fork frame's 8,192 playfield bytes matched, except 5 frames that differ by one
lane pixel on the top road line (a stale carry, see Oddities). The fork (208 frames) and the tunnel mouth are
read from the code and not modelled.

## Summary

- **The road redraws the whole playfield every frame.** `&4895` writes all 8,192 bytes of lines 64-191 in the
  back buffer, bottom to top: road lines, then backdrop lines, then sky. Nothing is cleared first and nothing
  outside the playfield is written (checked over 1,500 loops, fork and tunnel included). Sprites go on top
  afterwards.
- **The course is a list of segments.** Each has a curve, a gradient, a lane layout and roadside objects,
  from six run-length streams in the stage block. The player's position is a segment number and a fraction
  (1/256 of a segment). A 32-segment window of decoded values sits in a ring at `&F700`.
- **Pseudo-3D over 21 segment boundaries.** Per frame: the screen line of each boundary (from an 8 × 22
  perspective table plus the summed gradients), then each boundary's X (the road converges on a vanishing
  point that the summed curvature moves), then per-line edges by Bresenham between boundaries.
- **The renderer draws each line as three runs of 2-byte cells** (grass, road, grass, by `PUSH`), then patches
  in rumble strips (3 bytes, pixel accurate) and up to three 1-pixel lane lines. Colours alternate every two
  segments and dither line by line.
- **Precision:** screen X in half-pixels, 16-bit signed (the road runs off both sides). Boundary lines are
  8-bit signed. Per-segment X steps are 8-bit. Projection only uses the top 3 bits of the fraction, so the
  geometry moves in 8 steps a segment.
- **Cost:** about 224,000 Z80 T a game loop, 56% of the 400,000 T loop. The renderer is 155,000 T and the
  edge and lane tables 58,000 T. It writes 8,664 bytes a frame on average.

## The data

### Stage block (`&59AB`-`&79AA`, one LVn file)
| Address | Bytes | What |
|---|---|---|
| `&59AB` | 528 | Backdrop: 24 rows × 22 bytes (44 pixels), MODE 0 bytes, **row 0 is the bottom row**. Tiles horizontally |
| `&5BBB` | 6 | Normal colours (below) |
| `&5BC1` | 6 | Alternative ground colours, same layout (S3 type `&C1`) |
| `&5BC7` | 3 | Tunnel road colours: P0 even line, P0 odd line, P1 (screen-line parity, below) |
| `&5BF3` | 14 | Header, copied to `&17A0`-`&17AD` at stage start: initial `&17A0` (16-bit), then the six stream pointers |
| from about `&5E1E` | | The streams |

Colour block at `&5BBB` (MODE 0 bytes; P0 and P1 are the two stripe phases, below):
| Offset | Use | Stage 1 |
|---|---|---|
| +0 | P0 grass, every line | `&03` (pen 8, 8) |
| +1 | P0 road, even screen lines | `&AA` (15, 0) |
| +2 | P0 road, odd screen lines | `&55` (0, 15) |
| +3 | P1 road, every line | `&FF` (15, 15) |
| +4 | P1 grass, even screen lines | `&02` (8, 0) |
| +5 | P1 grass, odd screen lines | `&01` (0, 8) |

Stages 2 and 5 use `&3C`/`&28`/`&14` (pen 6) for the grass, stage 3 `&F3`/`&A2`/`&51` (pen 13). The road
bytes are the same in all five. Stage 1 pens: 0 and 1 black, 2 white, 5 bright blue, 8 green, 14 dark red,
15 grey. MODE 0 byte layout: the left pixel's pen bits 0-3 are byte bits 7, 3, 5, 1, the right's 6, 2, 4, 0.

### The streams
The header points at the byte **before** each stream's first byte. Six streams, decoded one segment at a
time by `&4219`:

| | Pointer, counter | Format | Value written to the window |
|---|---|---|---|
| S1 curve | `&17A2`, `&1777` | nibble runs | `c = (v & 8 ? -(v & 7) : v) × 2`: -14..14, even (data: -6..6) |
| S2 gradient | `&17A4`, `&1778` | nibble runs | `h = v - 8`: -8..7 (data: 0, ±1, ±3, ±5, ±7) |
| S3 layout flags | `&17A6`, `&177C` | count, value pairs | flags (below) |
| S4 objects | `&17A8`, `&177A` | nibble runs, half rate | `v` (roadside object, for the sprite code) |
| S5 objects | `&17AA`, `&1779` | nibble runs, half rate | `v` |
| S6 objects | `&17AC`, `&177B` | counts plus codes, half rate | a sticky value set by codes 3-9 |

- **Nibble runs**: one byte a run, high nibble = length in segments (1-15, 0 means 16), low nibble `v`.
- **Count, value pairs** (S3): a count byte (1-255 segments) then the value. The first segment of a run gets
  the value with bit 3 cleared, the second with bit 2 cleared, the rest with both cleared. So bit 2 marks a
  run's first segment and bit 3 its second.
- **Half rate**: S4-S6 are parsed on alternate segments only. The segments between get 0.
- **Control** (a zero where a run byte or count is due), then:
  - `00 lo hi`: continue at that address. The byte **at** it is the next run.
  - `01`: continue at the branch chosen at the fork (the address is patched into `LD HL,0` at `&428A` etc.
    by `&4144`).
  - `02 a1 a2` (two little-endian addresses): a fork. `a1` is the left branch, `a2` the right. The stream
    switches to a hold sequence in BI2 (`&5971` S1: one 0 then -4 for ever; `&5977` S2: 0 for ever; `&597C`
    S3: 255 segments of `&ED`).
  - S6 also has codes 3-15 (object values and branch hints at `&1759`-`&175C`): left to the sprite spec.

Course shape (S3 walked through both branches): a main leg of 320 segments (stage 1) or 400 (stages 2-5)
ending at a fork. Each branch is 198-210 segments long, then they jump to a common section that ends in a
jump back into itself, so the course loops for ever (402-450 segments a loop). The stage ends by game
logic, not by the road.

### S3 layout flags
| Bits | Meaning |
|---|---|
| 0-1 `t` | 0: full road, 4 lanes. 1-3: left edge from table `&79+t` (`&7A` the edge, `&7B`-`&7D` the lane lines) |
| 7 | With `t` ≠ 0: right edge from table `&7C+t` (3 lanes, 2 lane lines), else `&7B+t` (2 lanes, 1 line) |
| 2, 3 | First / second segment of a run (above): start a taper |
| 5 | Taper the right side (else the left) |
| 4 | Taper direction: narrowing (1) or widening (0) |
| 6 (7 clear) | Tunnel. With bit 2: entrance. With bits 3+4: exit |
| 6+7 (5 clear) | Alternative ground colours (`&5BC1`), no lane lines |
| 7+6+5 (`&E1` set) | Fork hold |

Values in the data: `&00`, `&81` (3 lanes, left), `&82` (3 lanes, right), `&01`/`&03` (2 lanes), `&AD`,
`&BD`, `&8E`, `&9E`, `&2D`, `&3D`, `&0F`, `&1F` (tapers into and out of those), `&45`/`&59` (tunnel in/out),
`&C1` (red ground, stage 1 right branch), `&ED` (fork hold).

### Tables built at boot (in the screens' 512-byte gaps)
| Address | Size | What |
|---|---|---|
| `&FE00` | 8 × 22 | `base[f][j]`: screen line (below the horizon) of boundary `j` on flat road, `f` = fraction / 32. `base[f][0]` = 96. Near-1/z: row 0 is 96 74 60 50 43 37 33 30 27 24 22 21 19 18 17 16 15 14 13 12 11 10 |
| `&EE00` | 8 × 22 | `m[f][j]` ≈ 1024 × (1 − base[f][j+1] / base[f][j]): the perspective fraction a boundary step closes on the vanishing point |
| `&EEB0` | 8 × 22 | `n[f][j]` ≈ 3 × (base[f][j] − base[f][j+1]): how much the road narrows over segment `j` |
| `&F600` | 128 × 2 | `T[θ]` (θ even, 0-254) = 128 + 128 tan(π(θ − 128)/256), signed 16-bit (`T[0]` = 0). The vanishing point's X for a heading |
| `&D7A0` | 12 × 8 | Rumble patterns (below); 5 bytes of each 8 used |

`m` and `n` match the formulas within 1 except `m[7][20]` (85, formula 171) and `n[7][20]` (3, formula 6).
Copy the tables rather than regenerate them.

Code tables: `&3E03`: three bytes, 255, 127, 85: fraction units per horizon step for `|h/2|` = 1, 2, 3.
`&3E03 + 4|c| + s`: backdrop scroll (period in loops, step in bytes) for `|c|` = 2, 4, 6 and speed band `s`:
`|c|`=2: (4,1) (3,1) (2,1) (1,1); 4 and 6: (3,1) (2,1) (1,1) (1,2).

## The model

### Order in the game loop (`&0362`)
| Call | Does |
|---|---|
| `&4219` | Advance by the speed, decode a segment for each one entered, per-segment horizon and drift (`&3EAD`) |
| `&5260` | Boundary lines: `&8E01`-`&8E15`, clipped copy `&8E36`-`&8E4A` |
| `&3E23` | Backdrop scroll `&4CC4`, horizon progress within the segment |
| `&3FCF` | Boundary X steps, per-line edge tables `&7A`/`&7E`, lane tables `&7B`-`&7D`; the fork's two roads |
| `&4895` | Draw the playfield into the back buffer |
| `&238C`... | Sprites (the tunnel mouth is drawn among them, `&455B`) |
| `&4144` | After the flip: resolve a fork once it's passed |

The attract mode (`&08DC`) calls the same routines.

### State
| Address | Units, range | What |
|---|---|---|
| `&1774` | 1/256 segment | Fraction. Projection uses `f = frac >> 5` (0-7) |
| `&1775` | segment, mod 256 | Ring position `seg`; `&1776` = `&F7`. Course segment = `seg` − 32 (+ 256k) |
| `&177E` | 9-bit, 1/256 segment a loop | Speed: `frac += speed & 255`; carry, and bit 8, each add a segment. Low gear tops out at 231 (measured) |
| `&1788` | count | Segments entered this loop |
| `&17A0` | 16-bit signed, half-pixels | Road's right edge X on the bottom line. Left edge = `&17A0` − 295. Stage 1 starts at 234. Steering writes it (`&3A62`, `&3AF5`, `&3B25`) |
| `&1693` | 16-bit signed, lines | Horizon height `H`: the line, counted up from the playfield's bottom, where backdrop row 0 sits. Starts at 84 |
| `&178C`, `&178E`, `&178F` | | Gradient rate of segment 2 (`h/2`), steps and fraction used so far this segment |
| `&1790`, `&1791`, `&1792` | | Curve under the player (`c` of segment 0, negated on the right fork branch), 4·`|c|`, scroll countdown |
| `&4CC4` | bytes, 0-21 | Backdrop scroll `s` (an operand inside the renderer) |
| `&8E00`-`&8E16` | lines, signed | `y[0..21]` (`y[0]` = 96) and a terminator `&A0` (-96) |
| `&8E20`-`&8E35` | half-pixels, signed | `d[j] + n[j]` after `&3FCF` |
| `&8E36`-`&8E4A`, `&8E4C`-`&8E60` | | Running-minimum `y` and lines per segment, for the sprite code |
| `&7A00`-`&7FFF` | 16-bit | Per-line X tables, below |
| `&179A`-`&179D`, `&177D`, `&168F` | | Fork state, below |

### The window (`&F700`-`&F7FF`)
For relative segment `i` = 0-31 (0 under the player), with 8-bit wrap on the low byte:

| Address | Stream |
|---|---|
| `&F7(seg + i)` | S1 curve `c[i]` |
| `&F7(seg + &20 + i)` | S2 gradient `h[i]` |
| `&F7(seg + &40 + i)` | S3 flags |
| `&F7(seg + &60 + i)`, `+&80`, `+&A0` | S4, S5, S6 |

Entering a segment writes the newly parsed values at its `i` = 31 (`&F7(seg + &1F + &20k)`, new `seg`). Just before
that, it ORs the S4 and S5 of the segment just left into `&1771`/`&1772`. Stage start (`&15B8`) zeroes the
page, sets `seg` = 0, copies the header, and advances 32 times to fill the window.

### Advance (`&4219`)
`frac += speed & 255`; on a carry, or if speed bit 8 is set (once more), enter a segment: `seg += 1`, decode
S1-S6 into the window, then `&3EAD`:
- Horizon: during a segment `H` moves `h2` lines, where `h2` is the gradient two segments ahead when the
  segment was entered, halved: `h ≥ 0 ? h >> 1 : (h >> 1) + 1`, so -3..3. `&3E23` takes one step (of
  `h2`'s sign) each time the fraction passes another `&3E03[|h2|]` units (255, 127, 85); entering the next
  segment settles the remainder, then latches the new `h2` in `&178C`.
- `&1790 = c[0]`, the scroll period and the car's drift terms (`&1793`, `&3D31`), which belong to the game logic.

### Backdrop scroll (`&3E23`, every loop with speed ≠ 0)
If `c[0]` ≠ 0: count `&1792` down; at 0, reload it with the period and move `s` by the step: `s −= step`
for `c > 0`, `s += step` for `c < 0`, mod 22. The table index is `4|c| + s_band`, where `s_band` is
`(speed >> 7) × 2`. In `&3E23` bit 7 of the speed is taken from a stale `A'` (see Oddities).

### Boundary lines (`&5260`)
With `rnd8(v)` = `(S >> 3) + ((S >> 2) & 1)` for `S = s8(v)` (S/8 rounded half up):
```
C = s8(−rnd8(f × h[0]))
for j = 1..21:
    C = s8(C + h[j−1])
    y[j] = s8(base[f][j] + ((4 × base[f][j] × C) >> 8))     ; = base·(1 + C/64), floor
y[0] = 96, y[22] = −96
```
`y` counts lines below the flat horizon: screen line = 95 + `y`, so `y` = 96 is the bottom line, 191.
`C` is the road's height relative to the camera in gradient units; the camera is 64 units up. The
clipped copy is `min(96, y[1..j])` running. Verified.

### Boundary X and per-line edges (`&50FC`, `&51CE`)
```
θ = (128 − rnd8(7 × c[0])) & &FE        ; 7, not f: see Oddities
x = &17A0
for j = 0..21:
    θ = (θ + c[j]) & 255
    P = ((T[θ] − x) × (m[f][j] >> 2)) & &FFFF      ; 16-bit wrap
    d[j] = s8((P >> 8) + ((P >> 7) & 1))           ; P/256 rounded
    x += d[j]
```
This is perspective: `x[j+1] − T ≈ (x[j] − T) · y[j+1] / y[j]`, with each segment heading toward the
vanishing point of the summed curvature.

Per-line X, pushed into a table from the bottom line up (`&51CE`), for the right edge from `x0` = `&17A0`
with steps `d[j]`, then the left edge from `x0` − 295 with `s8(d[j] + n[f][j])`:
```
x = x0; def = 0
for j = 0..20:
    N = y[j] − y[j+1]; a = def + N
    if a >= 2:                        ; normal segment: N lines (N, not a: see Oddities)
        emit N values stepping x by d[j] (stepper below); def = 0
    else:                             ; flat or hidden: one entry
        x += d[j]; emit x; def = (a <= 0) ? a : 0
```
Stepper (Bresenham, `D = |d|`, `σ` = sign):
- `N ≥ D`: `acc = N >> 1`; each line `acc += D`; if `acc ≥ N` then `acc −= N`, `x += σ`; emit `x`.
- `N < D`: `acc = 0`; each line repeat `x += σ`, `acc += N` until `acc` overflows 8 bits or `acc ≥ D`;
  `acc −= D` (8-bit); emit `x`.

Table layout: entry `k` (k = 0 for line 191) is the 16-bit word at index `&FE − 2k` of its page; a line `y`
below the horizon is index `2y + &3E`. `&7E` = right edge, `&7A` = left edge. Up to 107 entries are pushed
(the road can climb above the horizon, `y` down to about -10).

Lane lines (`&3FCF`, indices `&30` to `&FE`, far to near, every frame): `h = (R − L − carry) >> 1`,
`&7C = L + h`, `&7D = L + h + (h >> 1)`, `&7B = &7D − h − carry`. The carries chain from line to line (±1
half-pixel). Verified.

### The fork
- `&3FCF` scans `i` = 0-21 for flags with `&E1` all set. If none, the above. If found at `i` = `jf`, it builds
  **two** roads: the normal one (`&50FC`: edges `&7A`, `&7E`) and a mirrored one (`&50F4`: every `c`
  negated, edges `&7D`, `&7F`). On the left branch (`&177D` = 0) the normal road is at `&17A0` and the
  mirrored one at `&17A0 + sep`. On the right branch the mirrored road is at `&17A0` and the normal one at
  `&17A0 − sep`. The hold curve of -4 makes them bend apart.
- For lines from `y[jf]` up: `&7C = (L1 + R1)/2`, `&7B = (&7C + L1)/2`, `&7D = (L2 + R2)/2`,
  `&7E = (&7D + R2)/2`. So the left half of road 1 (`&7A`-`&7C`, lane line `&7B`) and the right half of road
  2 (`&7D`-`&7F`, lane line `&7E`) are drawn: two 2-lane roads. Lines nearer than the fork get the normal
  lane tables.
- `sep` (`&179B`, 16-bit): 0 until the player passes the first hold segment. Then the branch is fixed once
  (`&177D` = 1, right, if `&17A0` < 268) and `sep` grows by 16 every 2 segments, interpolated by the fraction:
  `sep = &179B + (((&168F & 1) << 3) | f) − 16`, about 8 half-pixels a segment.
- When `sep` ≥ 256, `&4144` switches the streams to the branch, refills the window (32 curves of -4 (left) or
  +4 (right), 32 flags `&01` (left half) or `&03` (right half), clears S4 or S5) and points the streams at
  short lead-ins (`&5988` etc.: 36 straight segments, a widening taper back to 4 lanes) before the branch.

## The renderer (`&4895`)

### Per frame
- Line address starts at line 191 and steps up a scanline (`−&800`, or `+&3800 − &40` across a character row).
  The back buffer's base is patched in by the flip (`&0E1C`/`&0E3C` lists).
- Stripe phase for relative segment `i` = bit 1 of `(seg + i)`: 1 is P1, 0 is P0. It toggles after every
  second segment end. Hidden segments (below) don't count.
- Rumble level, counting segment ends (zero-height segments included): segments 0-2 level 0, 3-7 level 1,
  8 on level 2. The right rumble only picks up a new level at the next phase toggle (see Oddities).
- Dither parity: screen-line parity. The colour table's "even" entries go on even screen lines.

### Per segment (bottom up, `j` = 0, 1, ...)
`N = y[j] − y[j+1]` lines. At the segment's start its flags select (sticky until the next `t` = 0 segment
restores the normal set):

| Flags | Left table | Right table | Lane tables | Colours |
|---|---|---|---|---|
| `t` = 0 | `&7A` | `&7E` | `&7B`, `&7C`, `&7D` | `&5BBB` |
| `t` ≠ 0, bit 7 | `&79+t` | `&7C+t` | the 2 between | unchanged |
| `t` ≠ 0, no bit 7 | `&79+t` | `&7B+t` | the 1 between | unchanged |
| `&C1` type | `&7A` | unchanged | none | `&5BC1` |
| tunnel | `&79+t` | `&7D` | none | road from `&5BC7`, walls and sky `&C0` (black) |
| fork | separate renderer, below | | | |

**Taper** (`&4724`; `t` ≠ 0, bit 2 or 3 set, `j` ≤ 17): before drawing, overwrite one edge table over the
taper's lines with a straight Bresenham line, so the edge slides across one lane:
- `P` = bit 5 ? (bit 7 ? `&7E` : `&7D`) : the left table. Written page `W` = bit 5 ? `P − 1` : `P`.
- `j` = 0 with bit 2: lines `y[0]` to `y[2]`, `off = f × 4`. `j` = 0 with bit 3: `y[0]` to `y[1]`,
  `off = f × 4 + 32`. `j` ≥ 1: bit 2 only, `y[j]` to `y[j+2]`, `off` = 0. (Over two segments the taper moves
  64 half-pixels; `off` is how much of it is already behind the player.)
- Bit 4 set: from `P[y_near] − off` to `(P−1)[y_far]`. Clear: from `(P−1)[y_near] + off` to `P[y_far]`.
- The X difference is clamped to 8 bits by its low byte's sign (±127), then stepped as above.

Verified (tapers into and out of 3-lane sections).

### Per line (`&49F2`)
With `Lx`, `Rx` the line's entries from the left and right tables:
1. Cells (2 bytes each, 32 a line): `E` = `Lx` < 0 ? 0 : `Lx` > 255 ? 32 : `(Lx >> 3) + 1`;
   `R` = `Rx` < 0 ? 0 : `Rx` > 255 ? 32 : `Rx >> 3`. Grass in cells `[0, E)` and `[R, 32)`, road in `[E, R)`.
   Drawn right to left as three unrolled `PUSH` runs entered by patched `JR` offsets.
   - P0: grass `+0` every line; road `+1` on even, `+2` on odd screen lines.
   - P1: road `+3`; grass `+4` on even, `+5` on odd screen lines.
   - Tunnel: grass becomes `&C0`.
2. Left rumble, if 0 ≤ `Lx` < 248: at byte `b = Lx >> 2`.
3. Lane lines, P1 only: for each lane table, if 0 ≤ `x` ≤ 255, one pixel of pen 2 at pixel `x >> 1`: byte
   `x >> 2`, `AND &55 OR &08` if bit 1 of `x` is clear, else `AND &AA OR &04`.
4. Right rumble, if 0 ≤ `Rx` ≤ 255 and `b = (Rx >> 2) − 2` is 0-61: at byte `b`.

A rumble writes 3 bytes from a pattern `p` = `&D7A0 + 32 × level + (P0 ? 16 : 0) + (x & 2) × 4`:
`[b] = [b] AND p0 OR p1`, `[b+1] = p2`, `[b+2] = [b+2] AND p3 OR p4`.

| Level | `x & 2` | p0 p1, p2, p3 p4 (white; red is the same with `&3F`/`&2A`/`&15`) | Pixels from `2b` |
|---|---|---|---|
| 0 | 0 | `00 0C`, `0C`, `55 08` | 0-4 |
| 0 | 2 | `AA 04`, `0C`, `00 0C` | 1-5 |
| 1 | 0 | `AA 04`, `0C`, `55 08` | 1-4 |
| 1 | 2 | `FF 00`, `0C`, `00 0C` | 2-5 |
| 2 | 0 | `FF 00`, `0C`, `FF 00` | 2-3 |
| 2 | 2 | `FF 00`, `04`, `55 08` | 3-4, and pixel 2 black |

White (pen 2) in P1, dark red (pen 14) in P0.

### Segment end and hidden segments (`&4B68`, `&4B9F`)
- After each drawn segment: phase and rumble bookkeeping, then `N' = y[j+1] − y[j+2]`.
- `N'` = 0: skip one table entry, do the segment-end bookkeeping, look at the next.
- `N'` < 0 (behind a crest): accumulate `a = N' + N'' + ...`, skipping one entry per segment, with no
  bookkeeping, until `a` > 0; then draw that segment with `a` lines.
- Stop when a span is 80-223 (as a byte): the terminator `&A0` gives `y[21] + 96`.

Verified, including crests.

### Backdrop and sky (`&4C70`, `&4D39`)
`B` = road lines drawn. Backdrop rows `C`: 0 if `H` < 0; 24 if `H` ≥ `B`; else `max(0, H − B + 24)`. Then
`C = min(C, 127 − B)`. Skipped in a tunnel. From the line above the road, upwards, draw rows `24 − C` to 23:
screen byte `x` of row `r` = `backdrop[22r + (x − s) mod 22]` (four `LDI` chains: `s` + 22 + 22 +
(20 − `s`) bytes). Then fill every line up to line 64 with `&F0` (pen 5), or `&C0` in a tunnel. Verified.

### The fork, from the code (`&3FCF`-`&4141`, `&4144`)
Each frame, in the edge builder (`&3FCF`):
- **Detect**: `i` = 0-21, the first window row whose flags have `&E1` all set is `jf` (`&179A` = `jf`,
  `&1799` = `&60`). None: the normal road (`&50FC`) and the normal lane tables, and that's all.
- **Count**: `B = y[jf] + 8` (`&8E00 + jf`, computed as `NOT(&60 − y) + &69`): the edge entries from index
  `&30` (line −7) down to line `y[jf]`, which get the split lanes.
- **Decide** (unless row `jf`'s flags have bit 2, the run's first segment; once, `&179D` 0 → 1): the branch
  `&177D` = 1 (right) if `&17A0` < `&10C`, else 0 (left). Branch + 1 compared with the criminal's (`&175B`):
  the same → message `&1AF2` (priority `&14`); different → the criminal's velocity low byte (`&16C5`) = `&5F`,
  score + (stage + 4) × 10,000, message `&1A4D` (priority `&14`).
- **Grow** (skipped with the decision when bit 2's set): `c = &168F + entered`; if `c ≥ 2`: `c −= 2`, `sep += 16`;
  `&168F = c`. Then `sep' = sep + (((&168F & 1) << 3) | (RoadFrac >> 5)) − 16` (16-bit, signed).
- **Two roads**: left branch (0): the normal road (`&50FC`, edges `&7A`/`&7E`) at `&17A0`, then the mirrored
  one (`&50F4`: the same builder with a `NEG` patched in at `&5147`, so every `c` is negated; edges `&7D`/`&7F`)
  at `&17A0 + sep'`. Right branch (1): the mirrored one at `&17A0`, the normal one at `&17A0 − sep'`. `&17A0`
  is restored after.
- **Lanes**: for the B entries from index `&30`: `&7C = (L1 + R1) >> 1`, `&7B = (&7C + L1) >> 1`,
  `&7D = (L2 + R2) >> 1`, `&7E = (&7D + R2) >> 1` (arithmetic shifts; `&7A` = L1, `&7F` = R2 kept). Then, if
  any entries are left, the normal lane loop (with its chained carries) from the next index to `&FE`.
- **Commit** (`&4144`, after the flip, when `&179C` ≠ 0: `sep` has passed 255): every stream pointer to a
  lead-in, by branch. Left: S3 `&5992`, S4 `&5980`, S5 `&5984`; right: S3 `&599E`, S4 `&5984`, S5 `&5980`;
  both: S1 `&5988`, S2 `&598D`, S6 `&597D`. The six branch continuations (the `01` code's targets) set from
  the addresses the fork codes recorded for that branch. The window's 32 rows from the car's: curve −4 (left) or
  +4 (right), flags `&01` or `&03`; S5 (left) or S4 (right) zeroed; gradients kept. Then the six run counters
  `&1777`-`&177C`, `&179D`, `&177D`, `&1799`, `sep` (and `&179C`) = 0; `&16B5` (the half-rate toggle) and
  `&168F` = 1.

### Fork renderer (`&4DCE`-`&50F3`; from the code, not modelled)
From the first fork-hold segment to the top, every line is five runs:
`[0, E1)` grass, `[E1, E2)` road, `[E2, E3)` grass, `[E3, R2)` road, `[R2, 32)` grass, where
`E1 = E(&7A)`, `E2 = E(&7C)`, `E3 = E(&7D)` (left rounding, `+1`) and `R2 = R(&7F)`. Rumbles at `&7A`
(left type), `&7C` (bytes `(x>>2)−1` to `+1`), `&7D` (left type), `&7F` (right type). Lane lines `&7B`, `&7E`
in P1. Normal colours only, no flag types. Zero and negative spans both skip one entry and count as a
segment end. It doesn't add its lines to `B`.

### Tunnel mouth (`&455B`-`&4723`; partly decoded)
`&44E1` (after the road) patches `CALL &455B` into the sprite plotter at `&23A9`/`&23CB` while a tunnel is
in view, so the mouth is drawn at its depth among the sprites. The mouth is a full-width band of `&3F`
(dark red, entrance) or `&C0` (black, exit) from the tunnel segment's line upwards, scaled with distance,
with a black opening over the 3-lane road (`&7A` to `&7D`), sky above (see `work/road/tunmouth.png`). The
renderer has already drawn the tunnel's black sky, black walls and blue road (`&5BC7`) beyond it.

## Costs (measured)
Plain Z80 T from the harness over 1,480 game loops of stage 1 (a real CPC takes about 20% longer). The
whole loop is about 400,000 T.

| Routine | Min | Mean | Max |
|---|---|---|---|
| `&4219` advance, decode | 703 | 1,620 | 3,951 |
| `&5260` boundary lines | 4,493 | 6,421 | 9,743 |
| `&3E23` scroll | 119 | 242 | 645 |
| `&3FCF` edges and lanes | 54,741 | 60,619 | 105,334 (fork) |
| of which boundary X | | 8,851 | |
| of which right edge, left edge | | 13,844, 9,356 | 17,026, 13,945 |
| of which lane tables (all 104 lines) | 24,819 | 24,819 | 24,819 |
| `&4895` render (non-tunnel) | 120,318 | 155,063 | 202,446 |
| of which road lines | 95,759 | 123,373 | 163,039 |
| of which backdrop | 138 | 21,053 | 31,981 |
| of which sky | 583 | 10,637 | 24,421 |
| **Total** | | **about 224,000** | |

- Road lines drawn: mean 83, max 107; about 1,490 T a road line (352 of it the 32 `PUSH`es).
- Backdrop: mean 16 rows, about 1,300 T a row (64 `LDI`s). Sky: about 365 T a line.
- Bytes written to the playfield by `&4895`: 8,496-9,049, mean 8,664: 8,192 fill plus rumbles (6 a line) and
  lane pixels (up to 3 a line, read-modify-write).

## Oddities and waste
Bugs and quirks (all verified unless marked):
- **The curve's fractional offset is always 7/8** (`&5126`: `A` = `&EE`, not the fraction, at the
  `CALL &52F2`). The hill uses `f/8` properly. So curves step sideways once a segment instead of sliding.
- Lane tables: the first entry (`&30`) takes a stale carry: one lane pixel on the top line can be one
  half-pixel off (the 5 unmatched frames).
- After a crest the edge pusher emits the segment's raw line count while the renderer draws the accumulated
  one, so edges beyond a crest are read a few entries out of step. Hidden segments also skip the stripe
  bookkeeping, so stripes beyond a crest are out of phase.
- The right rumble's width level lags the left's by up to 2 segments (`&4B43` only updates on a phase toggle).
- Rumble level 2, odd position, writes a black pixel left of the strip (an unmasked `LDI` of `&04`).
- `&3E23` takes speed bit 7 for the scroll band from a stale `A'` (`&3EAD` uses `LD A,L` first; this
  doesn't). Unverified effect.
- The scroll table has entries only for `|c|` ≤ 6; larger curves would read code. The data never uses them.
- 8-bit and 16-bit wraps: the gradient sum `C` (the data reaches ±135 over 21 segments), `d + n`, and
  `(T − x) × m` at extreme headings (the curve sum reaches ±132 over 22 segments, past `T`'s ends). Effects
  unverified; a port should clamp.
- The fork renderer doesn't count its lines into `B`, so backdrop placement during a fork uses the
  pre-fork lines only. Unverified effect.

Waste:
- The whole playfield is redrawn every frame, sky and backdrop included, though they rarely change. The sky
  above the backdrop only changes when `B + C` changes; the backdrop only when `s`, `C` or `B` changes. Per
  buffer bookkeeping could skip them (about 31,700 T mean).
- The three lane tables are computed for all 104 lines every frame (24,800 T), but lane pixels are drawn
  only on P1 lines, 3 a line. One shift and add per pixel from `L` and `R` would do.
- Per-line X goes through 16-bit tables with clamping and shifting per line. Edges could step in cell and
  pixel units per segment directly.
- The fork renderer is a full second copy of the line loop.
- Every road line writes 64 bytes; only the grass and road colours and the edges change between lines.

## For the BBC
- Full redraw, no erase: the sprite code can draw on whatever the road left. 8,192 bytes a frame minimum.
- The maths is small: 21 boundaries a frame, 8-bit lines, 16-bit X in half-pixels, one 8 × 8 and one
  16 × 6-bit multiply per boundary. Everything per line is interpolation.
- Data to carry: per stage 528 + 18 bytes plus the streams (header at `&5BF3`); shared tables
  3 × 176 + 256 + 60 bytes.

## Open questions
- The tunnel mouth's exact shape and height (`&455B`-`&4723`).
- The fork renderer and the fork tables, checked against the emulator.
- S4-S6 object codes (sprite spec), and the branch hints at `&1759`-`&175C` (game logic).
- Are the inks the same in every stage? (Pens are given here; inks belong to the palette code.)
- The emulator isn't deterministic across different breakpoint patterns (frames-per-loop shifts), so frame
  numbers in `work/road/` only reproduce with the same script.
