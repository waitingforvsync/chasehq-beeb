# CPC Chase H.Q.: sprites and objects

From the code of the CPC disc version, checked in the harness (`tools/cpc.py`) on 2026-10-31. Scripts and PNG sheets
are in `work/sprites/` (git-ignored). Addresses are the running game's. "Row" means one of the road's 20 object
rows, not a screen line. T-states are plain Z80 T as the harness counts them; a real CPC is about 1.2× slower.
Anything not checked in the harness is marked *unverified*.

## Summary

- **One plotter, masked, no stored masks.** Every sprite byte is drawn `(screen AND mask[b]) OR b`, with the mask
  looked up from a 256-byte table at `&8700` by the sprite byte (pen 0 transparent). Rows are unrolled up to 16
  bytes and entered part-way by `JP (IX)`. Mirrored sprites go through a pixel-swap table at `&8600` and are plotted
  right to left. There is no opaque or pre-shifted sprite path; the only opaque drawing is the gantry beam (a span
  fill) and the attract-mode text boxes.
- **Sprites move in whole bytes** (2 pixels) across and whole lines down. x is held in quarter-bytes (0-255 across
  the 64-byte screen) and truncated with `AND &FC`.
- **Data is stored bottom row first** and plotted upwards from the sprite's bottom line, which is where objects
  stand on the road.
- **Pre-scaled sizes only.** Roadside objects have 10 size slots, size = `min(row, 10)`, usually holding 5
  distinct images (sizes 1-2, 3-4, 5-6, 7-8, 9-10; 38 of 134 parts have only 3, 14 have a sixth at size 10). Cars
  have 6 slots holding 4 images. Rows 10-20 all use the smallest image.
- **Tall things are stretched by tiling**: a short pattern (often 1-2 bytes × 4 lines) is repeated up to a height
  of `scale(row) × factor`. Trees, poles, lamp posts, buildings, rock columns and pylons are stacks of fixed and
  tiled parts.
- **The object pass draws rows far to near** (row 20 to row 1). In each row: cars on that row, then the right-hand
  object, then the left-hand one. The player's car is drawn last, always the same size at the same place.
- **Cost**: in play, 20-30 sprite draws a game loop, about 1,000-2,000 bytes plotted (peak seen 3,195) over
  190-340 lines, taking 94-148K T a loop (26-36% of it). 55-80% of the bytes plotted are wholly opaque and 9-20%
  wholly transparent, yet all of them are masked.

## Formats

### Pixels and data

- CPC MODE 0 bytes: left pixel in bits 7,3,5,1 (pen bits 0-3), right pixel in bits 6,2,4,0. This is the BBC MODE 2
  layout. Pen 0 is transparent.
- A sprite is `h` rows of `w` bytes, row 0 the **bottom** line, packed with no padding. Width 1-16 bytes (the
  plotter's limit: 16 even, 15 odd), height 1-40 lines.
- `&8700`: mask table, `mask[b] = (left pen = 0 ? &AA : 0) OR (right pen = 0 ? &55 : 0)`. `&8600`: swap table,
  `swap[b]` = `b` with its two pixels exchanged. Both built at start-up (verified against all 256 values).

### Header (5 bytes): used by everything that goes through the clipper

| Offset | Meaning |
|---|---|
| +0 | width `w`, bytes |
| +1 | flags: bit 0 = draw mirrored |
| +2 | height `h`, lines |
| +3,+4 | data pointer |

Mirrored and plain headers share data. The direct entry `&2860` takes the same five values in registers.

### Sized descriptor (roadside objects drawn by `&26B5`/`&26BA`/`&26E0`/`&2723`)

`+0,+1` base address; then for size `s` = 1-10, at `+2s`: `xoff` (quarter-bytes) and `hoff`. The header is at
`base + hoff`. Size = `min(row, 10)`.

### Composite descriptor (`&25D4`/`&25D9`)

A list of `(type, partdesc)` triples ended by type 1. Parts are stacked from the ground up.

- `partdesc`: `+0,+1` base; for size `s`, at `+2s`: `xoff`, `off`. The part's header is at `base + off - 2` (the
  offset points at the header's height byte, which the stacking code reads first).
- Type 2: a fixed part; its `h` is added to the stack height `C`.
- Types 3-10: a tiled (stretched) part, height `max(1, k × scale - C)`, with `k` = 1.5, 0.5, 1.125, 0.375, 0.75,
  0.25, 1, 2 for types 3-10 (done with shifts: `a + a>>1`, `a>>1`, `a + a>>3`, `a>>1 - a>>3`, `a>>1 + a>>2`,
  `a>>2`, `a`, `2a`). Its pattern is the header's `h` lines, repeated from the bottom; the last repeat is cut short
  (only its bottom rows drawn).
- **Gantry extension** (id 2 on the left, stages 3 and 5): after the first part's 10 `(xoff, off)` pairs, at
  `partdesc + 22 + 3(s-1)`: beam height in lines and a pointer to one colour byte per line. See Plotting.

### Car descriptor

Six consecutive 5-byte headers, sizes 0-5, size = `min(row - 1, 10) >> 1`. Slots 2/3 and 4/5 share images: 4
images a car (for example 12×29, 8×22, 4×10, 3×6).

### Player-car tables (main block)

| Table | Entry | Contents |
|---|---|---|
| `&53D3` | 4 bytes × 9 | body: `w, h, ptr` |
| `&53F7` | 4 bytes × 3 | wheels and shadow: `w, h, ptr` |
| `&5403` | 6 bytes × 2 | tyre smoke: `w, h, xoff mirrored, xoff plain, ptr` |
| `&5484` | 4 bytes × 6 | effects: `w, h, ptr` |
| `&540F` | 3 bytes × 39 | effect placements: `dy, dx, 4 × effect index` |

## Catalogue

Sheets (sprites drawn upright, mirrored where the header says so, pen 0 shown as pink check):
`work/sprites/sheet_player.png`, `sheet_crim-extra.png`, `sheet_smoke.png`, `sheet_misc.png`, `sheet_obj5578.png`,
`sheet_lamp55AC.png`, `sheet_car56A1.png`, `sheet_stage1.png`-`sheet_stage5.png`. Whole objects assembled as the
game stacks them, at rows 1 and 5: `objects_stage1.png`-`objects_stage5.png`.

### Common to all stages (in the screen gaps unless noted)

| What | Table / header | Images (w×h, data) | Bytes |
|---|---|---|---|
| Player body: 3 pitches × 3 steering | `&53D3` | 12×29 `&8E61`, 12×29 `&9600`, 13×29 `&9E00`; 12×30 `&A600`, 12×30 `&AE00`, 13×30 `&B600`; 12×27 `&BE00`, 12×27 `&C600`, 13×27 `&CE00` | 3,182 |
| Player wheels and shadow, by steering | `&53F7` | 13×13 `&BF44`, `&C744`, `&DF40` | 507 |
| Tyre smoke, 2 frames | `&5403` | 8×15 `&B786`, `&9F79` | 240 |
| Player effects: the roof light and its flare, the bounce's burst (see Effects below) | `&5484` | 2×6 `&9FF1` light, 6×17 `&CF5F` flare, 6×20 `&975C` burst, 2×4 `&CFC5`, 3×8 `&CFCD`, 2×11 `&CFE5` lights | 288 |
| Turbo (nitro) icon | direct, `&2193` | 4×16 `&8FBD` | 64 |
| Debris from ramming | direct, `&3CEA` | 2×5 `&C7ED` | 10 |
| Smoke puff, 6 sizes | `&5550` | 4×13 `&E7B8`, 4×11 `&97D4`, 3×9 `&FFE0`, 3×7 `&DFE9`, 2×5 `&C7ED`, 1×3 `&9FFD` | 157 |
| Flames on the criminal's car: 3 heights × plain/mirrored × 6 sizes | `&549C`, `&54BA`, `&54D8`, `&54F6`, `&5514`, `&5532` | 6×16 `&D740`, 4×8 `&A7DD`, 6×11 `&D75E`, 4×6 `&A7E5`, 6×6 `&D77C`, 4×3 `&A7F1`, and 2×4..2×1 at `&C7F7`-`&C7FD` (each smaller one a suffix of the last) | 286 |
| Arrow: fork sign, and the marker over the criminal's car | `&556E`, `&5573` (mirrored) | 6×20 `&E740` | 120 |
| Lamp glow, raised (object id 1) | sized `&5578` | 4×14 `&A768`, 3×11 `&A7A0`, 2×8 `&A7C1`, 2×6 `&A7D1` | 117 |
| Bare post (object id 3) | composite `&55AC` | in the main block: foot 2×2 `&5673`, 1×1 `&567F`/`&5684`; post pattern 2×4 `&5677`, 1×4 `&5680`/`&5685` | 22 |
| Road barrier (a traffic-list object) | car `&56A1` | 8×20 `&EF60`, 6×15 `&AF68`, 4×10 `&AFC2`, 3×6 `&AFEA` | 308 |
| Briefing-screen lights | direct, `&0658` | 5×17 `&E6E0` | 85 |

Total in the gaps: 47 images, 5,354 bytes; in the main block, 46 bytes.

Not sprites, though in the gaps: dashboard portraits 8×40 at `&D600` and `&DE00` (stored top-down, drawn by the
panel code); `&8E00`-`&8E60` the object rows' arrays; `&F600`-`&F7FF` the track page (the object map is
`&F7C0`-`&F7FF`); `&FE00`-`&FEAF` the scale table; `&D7xx`, `&EE00`-`&EF5F` road tables (read by `&4B05`, `&515F`);
`&E600`-`&E6DF` read by `&2348`. `&D7A0`-`&D7FF` and `&FEB0`-`&FFDF` weren't seen read (*unverified*).

### Per stage (the stage block at `&59AB`)

Object ids index two 7-byte tables: right side `(&5BCE)`, left side `(&5BD4)`. An entry is `descriptor, handler`
and three bytes the object code doesn't read. The handler gives the kind: `&26BA`/`&26B5` sized and raised,
`&2723`/`&26E0` sized on the ground, `&25D9`/`&25D4` composite, `&2474` gantry (left only). Id 0 is empty. Left-side
descriptors are separate copies with their own `xoff`s and mirrored headers where the object isn't symmetric. Cars:
five words at `&5BE6`, the first being the criminal's (also shown on the briefing screen).

Sizes are the distinct images, largest first.

| Stage | Id | Descriptor R / L | Kind | What, parts (type: sizes) |
|---|---|---|---|---|
| all | 1 | `&5578` | sized, raised | lamp glow (above) |
| all | 3 | `&55AC` | composite | bare blue post: foot, then post ×0.5 |
| 1 | 4 | `&70B2` | composite | tree: shadow 16×5..6×1, trunk ×0.375 (4×4..2×2), foliage base 14×3, foliage ×1.125 (16×16..6×2), crown 14×12..4×2 |
| 1 | 5 | `&70C2` | composite | bush: base 14×3, foliage ×0.375 (16×16..), crown 14×12 |
| 1 | 6 | `&6E81` / `&6E8B` | composite | street lamp: foot, post ×1.125 (2×4), lamp head 8×7..3×4 |
| 1 | 7 | `&6F86` / `&6F90` | composite | telegraph pole: foot, pole ×1.125, crossbars 6×16..2×3 |
| 1 | 8, 9 | `&6B1A`, `&6B04` | sized, ground | curve warning sign, left-hand (mirrored) and right-hand: 8×40, 6×30, 4×20, 3×15, 2×13 |
| 2 | 4 | `&6F4E` / `&6FB3` | composite | rock column: base 16×8, body ×1.125 (14×8), 14×8, top 10×8 |
| 2 | 5 | `&74B3` / `&74C0` | composite | palm tree: base 10×5, trunk ×0.375 and ×0.75 (1-2 bytes wide), crown 9×25..4×7 |
| 2 | 6 | `&74BC` / `&74C9` | composite | low palm: crown 9×25 only |
| 2 | 7 | `&7816` / `&7820` | composite | post with a 10×8 board |
| 3 | 2 | `&7243` (R), `&729E` (L, gantry) | composite / gantry | lattice pylon ×1.5 (8×15 pattern), cap 8×24; the left one adds the beam |
| 3 | 4 | `&6B58` | composite | skyscraper: base 16×32..6×11, floors ×2 (16×8 pattern), roof 16×5 |
| 3 | 5, 6 | `&76FA` / `&7704` | composite | telegraph pole (as stage 1's 7) |
| 4 | 4, 5 | `&6E8A`, `&6ED6` | composite | brick pillar with a green top: base 14×5, body ×1.125 (10×8), top 14×10; 5 sits further out (`xoff` 80) |
| 4 | 6 | `&71A1` / `&71A8` | composite | rock pile: 12×15 and 9×15 |
| 4 | 7 | `&77F3` / `&77FD` | composite | double street lamp: foot, post ×1.125, head 10×8 |
| 4 | 8, 9 | `&7520`, `&750A` | sized, ground | curve warning signs (as stage 1) |
| 5 | 2 | `&70FC` (R), `&7157` (L, gantry) | composite / gantry | lattice pylon and beam (as stage 3) |
| 5 | 4 | `&751F` / `&752C` | composite | cactus: base 6×5, ×0.25 part, body 5×13, arm 2×9 |
| 5 | 5 | `&7742` / `&774C` | composite | street lamp (as stage 1's 6) |
| 5 | 6 | `&6B97` / `&6BFC` | composite | rock column (as stage 2's 4) |
| 5 | 7 | `&7847` / `&7851` | composite | telegraph pole |

Ids in use: right 1-9 in stages 1 and 4, 1-7 in 2 and 5, 1-6 in 3 (the tables are contiguous, so reading past the
last id runs into the left table). Id 2 is a null handler (`&0000`) in stages 1, 2 and 4.

| Stage | Cars at `&5BE6` (criminal first) | Images, largest |
|---|---|---|
| 1 | `&6366` blue sports car (the "blue British sports car"), `&632A` white saloon, `&6348` van | 12×31, 12×29, 11×38 |
| 2 | `&63DE` yellow sports car, `&641A` orange, `&63FC` green 4×4 | 11×30, 12×28, 12×29 |
| 3 | `&63C9`, `&6405`, `&63E7` | 12×29, 12×29, 12×29 |
| 4 | `&62E9`, `&6325`, `&6307` | 12×30, 12×31, 12×30 |
| 5 | `&63BF`, `&63FB`, `&63DD` | 12×29, 12×29, 11×38 |

| Stage | Distinct object images, bytes | Car images, bytes |
|---|---|---|
| 1 | 42 in the stage block (+16 common), 2,281 | 12, 1,920 |
| 2 | 51 (+10), 1,872 | 12, 1,770 |
| 3 | 29 (+16), 2,639 | 12, 1,845 |
| 4 | 36 (+10), 2,078 | 12, 1,819 |
| 5 | 60 (+16), 2,108 | 12, 1,918 |

## Object system and projection

### Order in a game loop (main loop `&0362`)

`&4895` draws the whole playfield (sky, ground, road) every loop, so nothing is ever erased. Of what concerns
sprites, in order: `&5260` (row lines `ya`, `yb`), `&4895`, `&2BEA` (row heights `hgt`), `&3305` (spawns traffic from the track page), `&350B` (projects the cars and
sorts them into `&7B00`), `&238C` (the object pass: rows 20 to 1, cars and roadside objects, then the fork arrow),
`&3A8D` (the player's car and its effects), `&216B` (turbo icons), `&12CF` (a screen effect, below), the flip.

### Rows and their variables

The road supplies 20 rows (row 1 nearest). Per frame they move smoothly through 8 phases; when the phase wraps, the
map index moves and every object steps one row (`&1774`/`&1775` look like one 16-bit track position, *unverified*).
The object code reads:

| Variable | Address | Meaning | Units, range |
|---|---|---|---|
| `ya[r]` | `&8E00 + r` | base line of row `r` | playfield line (0 top, 127 bottom); row 1 about 104-119, row 20 about 36-46 |
| `yb[r]` | `&8E35 + r` | `ya` clipped by any crest in front: `yb[r] = min(ya[1..r])` | as `ya` |
| `hgt[r]` | `&8E4B + r` | `128 - ya[r]` (`ya` after the fix-up below) | lines above the playfield's bottom |
| `XR[r]`, `XL[r]` | `&7CB0 + 4(20-r)`: `XR` lo, hi, `XL` lo, hi | right and left road edge at row `r`'s line (the same values as the road's per-line edge tables `&7Exx`/`&7Axx`) | quarter-bytes, 16-bit signed; on screen when the high byte is 0. Row 1 about −32 (left) and 193 (right); row 20 about 112 and 149 |
| `scale[r]` | `&FE00 + 22·phase + r`, `phase = (&1774) >> 5` | height unit at row `r`: a tiled part of factor `k` is `k × scale` lines tall. 74-93 at row 1, 11-12 at row 20 (static table, 8 × 22 bytes, entry 0 unused) | lines |
| object ids | right `&F7(&5F + P + r)`, left 32 bytes on (`&F7Ex`), `P = (&1775)` | which object stands at row `r` on each side | 0 none, 1-9 |

`&5260` writes `ya` and `yb` (`&52D5`, `&52ED`) 32 too small every loop; `&238C` adds 32 to all 21 bytes of both
before using them. `&2BEA` writes `hgt` as running sums.

### Roadside objects

For each row `r` (20 down to 1), right then left, if the id isn't 0:

- **Skip** if the anchor's high byte isn't 0 (`XR[r]` or `XL[r]` off-screen), except left id 2 (gantry), which is
  always processed.
- **Size** `s = min(r, 10)`; from the descriptor take `xoff` and the header.
- **x** (quarter-bytes, left edge): right side `XR + xoff` (`xoff` may be negative; skipped if the add carries
  when positive, or lands on exactly 0); left side `XL + 8 - xoff - 4w` (skipped if `XL + 8` carries or
  `XL + 8 - xoff < 0`). Byte column = `x >> 2`.
- **y**: the sprite's bottom line is `yb[r] + yoff`. `yoff` is 0 for ground objects; `-(scale - scale>>2)`
  (about −0.75 scale) for raised ones, which are drawn only in rows 1-15; `-C` for composite parts.
- **Crest**: if `ya ≠ yb`, `n = (ya - yb) - |yoff|`; if `n > 0`, the bottom `n` rows of the sprite are skipped and
  the rest drawn with its bottom at `yb`. A tiled part skips whole hidden repeats instead.
- **Top**: lines above playfield line 0 are not drawn (`lines = min(h, y + 1)`).

Composite: the parts are drawn in list order, bottom up, each with its own `xoff` against the same anchor and
`yoff = -C`, `C` growing by each part's height. A tiled part's height is also cut so it doesn't pass the top of the
playfield.

### Traffic, barriers and the criminal

Six slots of 20 bytes at `&16B8 + 20k`; slot 0 is the criminal (`+&0F` = `&FF`).

| Field | Meaning |
|---|---|
| +0 | active (bit 7, rotated each frame) |
| +1 | row, 1-22 (drawn if < 20; removed at 23) |
| +2,+3 | screen x of the sprite's left edge, quarter-bytes, 16-bit (written by `&350B`) |
| +4 | fraction of a row (0-255); the car is `frac/256` of the way from row `r` towards row `r-1` |
| +5 | lateral position across the road, 0-255 |
| +6 | lines below `ya[r]`, interpolated (written) |
| +9,+A | car descriptor |
| +B,+C | behaviour routine |
| +D,+E | relative speed, 8.8 rows a frame (subtracted from `+4`, carrying into `+1`) |
| +F | `&FF` criminal, `&80` ordinary, others when crashed |
| +10 | jump height, lines (tumbling after a hit; table at `&3446`) |
| +13 | draw upside down (toggles while tumbling) |

Projection (`&3529`), each frame:
- `h = hgt[r] - ((hgt[r] - hgt[r-1]) × frac >> 8)` lines above the bottom; `+6 = hgt[r] - h`.
- At that line, the road's left edge `L` and right edge `R` from the per-line tables; `x = L + ((R - L) × lat >> 8)`.
- Drawn in the object pass at row `r`, bottom line `yb[r] + (+6) - (+10)`, size `min(r - 1, 10) >> 1`, clipped
  left and right as roadside objects are.

The cars are kept in `&7B00` as 4-byte entries `row, frac, slot address`, sorted far to near, count in `&1757`;
`&363A` draws all entries for the current row.

The criminal, when drawn, also gets:
- the arrow `&556E` above it while damage (`&1767`) < 5 and its size < 4, offsets per size from `&531A`;
- damage 1-3: up to three smoke puffs (`&5550` sizes) cycling through 6 steps, positions from `&5347`, `&533A`,
  `&5354`;
- damage 4 and over: flames from the six sets at `&549C`, chosen by damage and frame.

The barrier `&56A1` is a traffic-list object too (each stage's data points at it); knocked, it tumbles and is drawn
upside down.

### The player's car

Always one size, at a fixed place, drawn by the direct entry (no clipping):
- **Wheels and shadow** `&53F7[steer]` at column 26 (25 when mirrored), bottom line 184.
- **Body** `&53D3[(pitch + steer + bounce) mod 9]` at column 26 (25 when on full lock and mirrored), bottom line
  `181 - (&3D1D)`. `steer` = `(&1784)` 0-2; `pitch` = `(&3D31)` 0 (flat), 3 or 6 by the road's slope; `bounce` 3 on
  alternate frames when bumping off the road. Mirrored (`&1785`) for the other direction.
- Everything is raised by `(&175F)` (jumps, crashes).
- The body covers the top 10 lines of the wheels: 517-546 bytes plotted every loop for about 410 visible.
- Tyre smoke: two 8×15 clouds (left one mirrored) at columns 21 and 36, bottom line 183, alternating frames, when
  skidding or off the road.
- Effects (`&3DC1`): sparks, crash flames and the turbo flame, placed by the `&540F` table relative to column 32,
  line 185.
- Debris (`&3CC7`): three 2×5 particles on paths from `&5361`, 9 frames, after a ram.

### Effects (`&3DC1`, decoded 2026-10-31)
`&3DC1` draws entry A of `&540F` (39 entries of 3 bytes: dy, dx signed, then the image's offset into `&5484`,
4 bytes an image: w, h, data): at playfield line `&79 + dy` less the body's lift `(&3D1D)`, the pitch's
(`(&3D31) >> 1`, less 2 if not 0) and the car's `(&175F)`, and x `&80 + dx` quarter-bytes (column 32), through
`&2860`. Its callers, and what the images are (rendered from the CPC's memory):
- **The bounce's burst** (`&3B50`, in `&3A8D`): while `(&3B51)` = S isn't 0, entry 3S + 24, plus 1 on full lock
  (2 when mirrored): entries 27-35, all the 6×20 burst (`&975C`, yellow and white). The bounce's start (`&2DB9`)
  puts its side + 1 in `&3B03` and 5 in `&3AFA`, and `&3AF9` copies it to `&3B51` for those 5 loops (then 0);
  the wall scrape (`&2D3D`) sets it too, the fork divider (`&2E2F`) and a stop (`&3A94`) clear it. The BBC's
  car_spark keeps the same state (CarSpark, CarSparkSide) but draws nothing yet.
- **The roof light** (`&3BD2`, car mode `(&1764)` 1, from the sighting): a counter `(&3BF2)` 0-6, a step every
  2 loops (3 at step 2), drawing entry 6 + C (13 + C on full lock, 20 + C mirrored), and C + 1 as well while
  C < 4: the light (red, 2×4 to 3×8 to 2×11) going onto the roof with its 6×17 flare. At 7, `(&1764)` = 0.
- **The arrest's flash** (car mode 2): entry 36, or 37 + mirrored on full lock: a 3×8 light.
- There is no turbo flame: the turbo is the whoosh alone.

### Overlays

- Fork arrow: `&556E` (left fork) at column 28 or `&5573` (right, mirrored) at column 30, bottom line 112, while
  `(&175C)` is 1 or 2.
- Turbo icons: `(&1692)` of them, 4×16, at columns 1, 5, 9, 13, bottom line 188; the last blinks while one is in
  use.
- Text: the attract and briefing text boxes (`&1393`/`&13B2`) are opaque, 2 bytes a character, framed, not sprites.
  They cost 29-58K T a loop in the attract mode.
- `&12CF` with `(&1766)` = 2 ANDs part of the playfield with patterns from `&FF80` (a crash effect, *unverified*).

## Plotting

### Entry points

| Entry | Use | Inputs |
|---|---|---|
| `&26E0` / `&2723` | sized object on the ground, left / right | `DE` descriptor, `B` row, `IX` anchor, `IY` row |
| `&26B5` / `&26BA` | sized object raised, left / right | as above |
| `&25D4` / `&25D9` | composite, left / right | as above |
| `&2474` | gantry (left id 2) | as above |
| `&2703` / `&26FB` | clip left and right, draw a header | `HL` header, `A` right edge (or `IX` anchor and `B` xoff at `&26FB`) |
| `&274B` / `&273E` | clip right only, draw a header | `HL` header, `A` left edge |
| `&2860` | direct: no clipping | `E` x, `D` y (bottom line), `B` h, `HL` data; alternate `E` w, `B` flags |
| `&288B` | direct with a ready screen address (briefing car) | |

`(&276D)` holds `yoff` and `(&27F5)` the variant (0 plain, 1 upside down, 2 tiled) for the clipper.

### Inner loops

| Loop | Rows | Per byte | Per line |
|---|---|---|---|
| plain, even width | `&28BC`: 8 × 13 bytes, entered at `&28BC + 13(8 - w/2)` | `POP BC` a pair; `LD E,C : LD A,(DE) : AND (HL) : OR C : LD (HL),A : INC L`: 38 T | 94 T, +32 at a character-row crossing |
| plain, odd width | `&2968`, last pair half used | 38 T | 94 T |
| mirrored, even | `&2A19`: 8 × 19 bytes | `LD L,C : LD L,(HL) : LD A,(DE) : INC H : AND (HL) : DEC H : OR L : LD (DE),A : DEC E`: 53 T | about 94 T |
| mirrored, odd | `&2AF7` | 53 T | about 94 T |

`SP` reads the sprite (saved and restored round the loop); the stride is the full `w`, so a clipped sprite just
plots fewer bytes a row from an offset pointer. The screen address steps up a line by `H -= 8`; below the buffer's
base (`CP &80`, patched to `&C0` by the flip) it becomes `H += &38`, `L -= &40` with borrow. Rows are plotted
bottom to top.

### Clipping

- **Horizontal**: left clip (skip `k` bytes at the start of each row, `k` taken from the right end instead when
  mirrored) only on the `&2703` path: left-side objects and cars left of centre. Right clip at column 64 on both
  paths. A sprite wholly off either side isn't drawn.
- **Vertical**: top at playfield line 0; bottom only by the crest rule. Nothing reaches the screen's bottom.
- **Not clipped**: the direct entry `&2860` (player's car, its effects, icons, arrow).

### Mirroring

Header flag bit 0: start at the row's right end, each byte through `&8600` (swap pixels), masked by
`&8700[swapped]`, stored leftwards. 6-15% of plotted bytes in play are mirrored.

### Variants

- **Upside down** (`(&27F5)` = 1, `&2B9D`): the data pointer starts at the last row and the stride is negated.
  Only tumbling cars and barriers.
- **Tiled** (`(&27F5)` = 2, `&2808`/`&282C`): the part's `h`-line pattern is plotted repeatedly, each repeat a
  separate call to the inner loop, until the total height `(&282D)` is drawn; the last repeat is short.

### The gantry beam (`&2474`)

The left pylon is drawn as a composite; then a horizontal bar spans the road: from column `(XL + 8 - xoff) >> 2`
(0 if off the left) to `(XR + xoff) >> 2` (64 if off the right), `xoff` being the pylon's at that size. Its bottom
line is `yb - 1.5·scale + hidden` and it has the per-size height from the descriptor. Each line is filled with one
byte (from a list, so the bar has coloured stripes) by an opaque unrolled run of `LD (HL),A : INC L` entered
part-way: 11 T a byte.

## Costs

Measured over 40 game loops a state (single-stepped, T attributed by code address), accelerating and steering.
`attract` is stage 1 in the attract mode from loop 30; the rest are in play.

| State | Loop T | Sprite T | Share | Draws | Tile repeats | Lines | Bytes | Opaque / mixed / transparent bytes | Inner loops T | Set-up and clip T |
|---|---|---|---|---|---|---|---|---|---|---|
| attract | 412,104 | 93,873 | 23% | 18 | 15 | 242 | 969 | 63 / 21 / 16% | 63,717 | 19,244 |
| stage 1 | 372,500-403,750 | 117,512-126,387 | 31-32% | 25 | 36 | 212-233 | 1,450-1,640 | 68-69 / 16-17 / 14-16% | 80,394-89,210 | 26,580-28,033 |
| stage 2 | 355,518 | 93,867 | 26% | 20 | 25 | 194 | 1,069 | 58 / 22 / 20% | 63,311 | 21,007 |
| stage 3 | 414,431 | 148,022 | 36% | 21 | 45 | 333 | 2,028 | 81 / 11 / 9% | 113,963 | 24,385 |
| stage 4 | 411,577 | 130,435 | 32% | 28 | 38 | 343 | 1,204 | 54 / 30 / 17% | 85,816 | 32,726 |
| stage 5 | 382,341 | 117,001 | 31% | 30 | 28 | 263 | 1,132 | 55 / 27 / 19% | 73,251 | 32,458 |

- A game loop is 5.3-6.7 harness frames (7.5-9.5 loops a second at the harness's rate, slower on a CPC). The road (`&4895`) takes
  146-169K T of it.
- Peaks seen in a single loop: 3,195 bytes and 214K T of sprite work (stage 3, buildings close).
- By breakpoints (`&039E`→`&03A1` and `&03A1`→`&03A4`): the object pass averages 52-107K T a loop (13K to 153K);
  the player's car 25K T driving straight, up to 60K T with smoke and effects. In the attract mode, 63K T and 31K T.
- A typical in-play loop draws 4-8 roadside objects (15-26 visible parts, 5-8 of them tiled in 25-45 repeats), 0-3
  cars and 5-6 direct sprites (wheels, body, icons).
- Widths of plotted lines: 1 byte 22%, 2 bytes 11%, 4 bytes 22%, 6 bytes 11%, 12-13 bytes 18% (the player's car);
  the rest spread.
- The player's car is about 520-550 bytes over 42 lines every loop: a quarter to a half of all bytes plotted in
  play, more than half in the attract mode.
- Set-up: about 1,100 T a draw (clip, screen address, entry point), plus about 80 T for each tile repeat.

## Oddities and waste

- **Masking everything**: 54-81% of plotted bytes are wholly opaque and 9-20% are 0 (wholly transparent), yet every
  byte pays the table look-up, the screen read and the write. Classifying bytes at build time would skip a fifth
  and store most of the rest directly.
- **Poles**: 1-byte-wide tiled parts (posts, trunks, pylons) are drawn in 4-line repeats, each a separate call
  with its own set-up; a fifth of all lines are 1 byte wide. A vertical strip would be far cheaper as a column fill.
- **The player's car**: the wheels are plotted under the body (10 lines, 130 bytes overdrawn), and the whole car is
  masked every loop though it never changes size or place, and most of it is opaque.
- **Sizes**: 10 slots, usually 5 images; rows 10-20 (scale 22 down to 11) all use the smallest image, so far
  objects don't shrink. Cars have 4 images for 6 slots.
- **Set-up** is about a fifth of the sprite time: every draw re-derives the screen address with shifts and patches
  an entry point.
- The y arrays are written 32 short and fixed up every loop (42 bytes).
- Roadside objects are dropped whole when their anchor is off-screen (high byte not 0), even if part of the sprite
  would show; the left anchor gets an unexplained `+8`.
- The crest rule uses `(ya - yb) - |yoff|`, so a car sitting below its row's line (`yoff > 0`) is hidden by too
  little. Probably a bug; worth reproducing only if it shows.
- Right-side objects aren't clipped on the left; one with a negative `xoff` near column 0 would wrap.
- The right and left id tables overlap their unused id-0 slots with the previous data.
- Sprite memory is used well: mirrored headers share data, small flame sizes are suffixes of each other, and the
  composites build tall objects from small patterns. The gaps hold 5.4K of sprites and each stage about 4K.

## Open questions

- Object id 1 (the raised lamp glow, `&5578`) is in every stage's tables but wasn't drawn in 500 loops of any stage.
  Where the track places it is for the logic spec.
- How the object map `&F7C0`-`&F7FF` and `(&1775)` are fed from the track data, and how the road computes `ya`,
  `yb`, the edges and the phase: for the road and logic specs.
- The criminal-car arrow (`&556E` above the car) is read from the code, not seen in a frame (*unverified*). Its
  sprite points up and to the left.
- The effects table `&540F` is decoded below (Effects, 2026-10-31); the roof light's entries 0-5 and the
  path through `&3DBC` not yet checked frame by frame.
- `&12CF` (`(&1766)` = 2): the playfield AND effect isn't decoded.
- `&D7A0`-`&D7FF` and `&FEB0`-`&FFDF` in the gaps: no reader seen.

## Files

`work/sprites/`: `common.py` (snapshots, a hook runner, start of play), `trace.py` (single-step tracer),
`catalogue.py`, `sheets.py`, `assemble.py` (the sheets), `cost.py`, `cost2.py`, `cost2_report.py`, `bptime.py`,
`counts.py` (the measurements), `plotlog.py`, `hdrlog.py` (logs of every draw). Saved states: `attract30.pkl`,
`game0.pkl`-`game6.pkl` (stage 1 in play), `stage2_0.pkl`-`stage5_0.pkl` (reached with the cheat: `(&1647)` = 1,
then key `2` for the next stage).
