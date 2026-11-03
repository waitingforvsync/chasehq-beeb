# The five stages: what LV2-LV5 hold, against LV1

Read from LV1-LV5 and BI2 on 2026-11-01, with the build's own generators run for each stage
(`work/lv/`). The other specs give the formats: the streams in `cpc-road.md`, the sprites in
`cpc-sprites.md`, the text in `cpc-text.md`, the logic in `cpc-logic.md`.

## Sizes, as the BBC stores them

`tools/genroad.py`, `gensprites.py` and `gentext.py` run for every stage without an assert failing (stage 1's
output is byte for byte the build's). Each stage's data assembled into the game with the limits lifted
(`work/lv/relax.py`, `work/lv/split.py`), split into what every stage shares (the same bytes in all five)
and the stage's own:

| Bytes | Stage 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Code bank: streams, backdrop, colour tables, roadside bounds | 2,100 | 2,349 | 2,322 | 2,064 | 2,299 |
| Data bank: roadside sprites and part lists, cars, obstacles | 7,486 | 6,604 | 6,617 | 6,665 | 7,806 |
| Main RAM: the briefing, the arrest page, the stage's face | 254 | 716 | 241 | 727 | 250 |
| The stage's own | 9,840 | 9,669 | 9,180 | 9,456 | 10,355 |
| Shared (the perspective tables, the player's car, the font, Nancy's and the partner's faces, the scripts) | 11,095 | | | | |

- Not counted yet: the airborne patrol's helicopter (stages 2 and 4, below: 716 bytes on the CPC, its
  second frame the first mirrored), the gantry's beam (stages 3 and 5), the tunnel's road colours (3 bytes).
- With the build as it is (stage 1 in, release 5 plus D15): stage 3 fits as it is. Stages 2 and 4 overflow
  main RAM by 211 and 222 bytes in the &259 gap (9 and 20 past everything free in main RAM), stage 5 the
  data bank by 33. The code bank fits every stage (2,349 at most against stage 1's 2,100 and 536 free).
- All five stages' own data is 48,500 bytes, against 21,675 non-zero bytes in LV1-LV5: no number of banks
  holds them together, so stages 2-5 need a load each, as the CPC does. A stage's slots, the most any stage
  needs: 2,349 in the code bank, 7,806 in the data bank, 727 in main RAM.

## The course

S3 walked along every branch (`work/lv/course.py`):

| Stage | Main leg | Tunnels (segments) | Alternative ground (`&C1`) | Loops back |
|---|---|---|---|---|
| 1 | 320 | 588-691 on both branches | 340-517, right branch | 1,170 to 720 |
| 2 | 400 | 630-753 both; 416-461 right | | 1,250 to 800 |
| 3 | 400 | none | 420-597, left branch | 1,246 to 802 |
| 4 | 400 | 412-515 left; 510-563 right | | 1,006/1,004 to 604/602 |
| 5 | 400 | 656-759 both; 566-587 left; 402-423 right | | 1,228 to 784 |

**Stage 1 has a tunnel.** It's 268 segments past the fork on both branches, and the criminal starts 868
segments ahead, so every chase that reaches the criminal drives through it. The BBC's renderer draws its
segments as ordinary road (`roaddraw.6502`'s `special`: "tunnels not yet"); the lane model has the tunnel's
lines. Only stage 3 has none.

## Values stage 1 never produces

`work/lv/streams.py` tallies every value each stream can give, every branch walked:

- **S1 curves**: none new. Stage 1 already uses -6 to 6 (the open question on curves past ±4 is moot).
- **S2 gradients**: none new (-7 to 7).
- **S3 layouts**: `&01`, `&2D`, `&3D`, `&82` (stage 2), `&82` (3), `&0F`, `&1F` (4), `&03`, `&1F`, `&82` (5):
  two-lane roads, three lanes on the right, and tapers on the right or into two lanes. The BBC's road model
  handles them (below).
- **S4, S5 objects**: id 2 in stages 3 and 5. On the left (S5) it's kind 4, **the gantry** (drawn since
  2026-11-02, `objects.6502`'s gantry_beam); on the right (S4), an ordinary composite. Stage 3's right id 8
  has the gantry's handler too, but S4 never places it.
- **S6 codes**: 4 and 5 (obstacle values 1 and 2: one cone or barrier at `&32` or `&DC`, handled by
  `obstacles`), 11 (the criminal takes the left branch, stages 2 and 3: handled), and 15, 17, 18 (stages 2 and
  4): `&1759`, the airborne patrol, below. The BBC decodes all of them (`next_s6`); nothing reads
  `RoadHints`' first byte yet.

## The airborne patrol (stages 2 and 4)

Decoded from `&31AC`-`&3304` (2026-11-02). Its state is `&1759`, set by S6 codes 15, 17 and 18 (code - 14).
Its own variables are operands it patches into itself: X at `&3202` (a word, signed), the target X at
`&3272`, Y at `&3237`, the bob's phase at `&3243`, step at `&324B` and offset at `&3254`, the road X last
loop at `&3262`, and the line it's drawn on at `&31CF`.

- **The state each loop** (`&329E`):
  - 3 or 4 (codes 17, 18): the message `&1A14` (THE TARGET VEHICLE HAS TURNED LEFT UP AHEAD) or `&1A24`
    (... RIGHT ...) at priority 15; X = -24, the target &70; Y = &85; the bob's phase and offset 0, its step
    +1; the road X taken; `CALL &31AC` patched in at `&23C8` (the drawer's per-row hook); state 5.
  - 5: nothing (flying in, then hovering).
  - 1 (code 15): the target -56 (`&FFC8`); state 2.
  - 2: once X's high byte isn't 0 (off the left), the patch taken out (three NOPs) and state 0.
- **The movement each loop** (`&3231`, while the state isn't 0):
  - Y: down 2 a loop from &85 to &61, then held.
  - The bob: the phase counts 0-3, and the step (+1 or -1) turns over when it comes back to 0; the offset
    adds the step each loop. The line it's drawn at is Y + the offset.
  - X: moved by the road X's change since last loop (so it keeps its place over the ground), then 8 a loop
    towards the target, stopping on it.
- **The drawing** (`&31AC`, from the drawer's hook, only when its row count B is 3: so among row 3's
  objects):
  - The frame list at `(&5BDE)`, or `(&5BE0)` on odd loops (`&1769` bit 0). Each lists two parts: an x
    offset (a signed byte) and a 5-byte sprite header (width, flags, height, data).
  - Part one, the helicopter, 14 bytes by 44 lines at x + 0; part two, its shadow, 10 by 10 at x + 8. Each
    is drawn by `&3201` with the drawer's y (`&276D`) set to minus a value: for part one Y + the bob's offset
    less `(IY+&4B)`; for part two `(IY+&4C) - (IY+&4B)` times the fraction's top three bits (`&1774` AND
    `&E0`) / 256 (a shift-and-add, then RRA). `(IY+&4B)` and `(IY+&4C)` are row 3's entries in the drawer's
    row data; what `&276D` is relative to, and so the lines on the screen, is still to check against the
    drawer (`&2703`).
  - The odd loops' frame is the same images with the header's flag bit 0 set: mirrored. The helicopter
    isn't symmetric (15 of its 44 rows), so the mirror flips its rotor's blur each loop.
  - Clipping (`&3201`): a part entirely off the left (x + width x 4 not past 0) or with x past 255 isn't
    drawn; the drawer's `&2703` (and `&274B` for x at or past &80) clip it otherwise.
- **The images**: LV2's (`&6B42`, `&6DAA`) and LV4's (`&6A7E`, `&6CE6`) are the same bytes, 616 + 100 = 716.
  The pointers are 0 and `&000C` in LV1, LV3 and LV5. On the BBC, with its plotter's coded bytes, each frame
  is 716 bytes; the mirrored frame another 716 unless the plotter draws mirrored.

## The road model against the CPC's, stages 2-5

`check_road.py` per stage (`work/lv/roadN/`: the build with only that stage's `road.6502`, the CPC jumped to
the stage by test mode's key '2'), 600 loops each branch:

| Stage | Left | Right |
|---|---|---|
| 2 | 2 loops differ (y) | 1 loop differs (y), 1 bounce |
| 3 | 0 | 0 |
| 4 | 0 | 0, 1 bounce |
| 5 | 0 | 0, 1 bounce |

- **The y difference** (`road_lines`): when the summed gradient C is exactly -128 the BBC adds b × 128 / 64
  (-22 lines at b = 11: y = -11 where the CPC has 11). The CPC builds the product by shifting |C| left
  through A, and its first `ADD A,A` (`&52AA`) drops bit 7 unused: it multiplies by |C| mod 128, so -128 adds
  nothing. Fix: `AND #&7F` on the magnitude (2 bytes, 2 cycles, on the negative path). Stage 1's hills never
  sum to -128. Applied (2026-11-02): stage 2's road now matches in all 600 loops.
- **The rows' anchors**: row 20's anchor is one more than the CPC's in some loops (stage 2: 6 and 6 loops, 3:
  47 and 19, 4: 3 and 0, 5: 35 and 5; stage 1: 0). Found (2026-11-02): it's whichever edge is read from a lane
  table (the right in stage 3's, not the left as first written), at the lanes' top entry, whose borrow the
  CPC chains down from leftovers above the road (`cpc-road.md`, Oddities). Stage 1's row 20 reads only the
  edges. Left (decisions D25).
- **The bounces**: one each, all on right branches, which run into tunnels soon after the fork (the CPC's
  tunnel patches the object drawer and has walls). Probably the tunnel, not confirmed.
- In stages 2 and 5 the CPC went more than 50 frames between two loops (the check's limit; 2,000 let them
  through). Not found out why.

## The stage record, and what the BBC fixes at stage 1's

- **Inks**: the same in every stage (read at each stage's main loop, `work/lv/inks.py`), so the BBC's
  dithered pens hold for all five. The open question in `cpc-road.md` is answered.
- Generated per stage already: the colour blocks (`&5BBB`, `&5BC1`), the streams and start X (`&5BF3`), the
  roadside bounds (`&5BD0`, `&5BD6`), the obstacles' table (`&5BCC`), the cars (`&5BE6`, `&5BE8`), the
  traffic gap (`&5BF0`: 20, 15, 15, 10, 20), the dodge and sprint counts (`&5BF1`: 80, 50, 70, 40, 40;
  `&5BF2`: 90, 40, 85, 30, 40), the face (`&5BCA`), the briefing (`&5BDA`) and the arrest page (`&5BDC`).
- Read since: the tunnel's road colours (`&5BC7`, genroad's FillTunnel) and the helicopter's frames (`&5BDE`,
  `&5BE0`, gensprites' HeliSprite).
- The code's reads of the stage number (`&164D`): the ram's score at `&3015` (stage × 10,000, stage + 4
  for a double), which `car.6502` now takes from `Stage` too; the fork's (`&4077`) and the
  bonuses (`&1018`), which the BBC takes from `Stage`; the intro's car reveal, skipped on stage 5
  (`&05A0`); `&21A7`'s copy to `&1758`; the stage's load (`&0C40`) and the flow (`&0327`, `&0331`,
  `&03C2`, `&0FAB`).
- LV6 (the ending) is untouched.

## What the later stages need that stage 1 doesn't

1. A load per stage: done (D17, D20: every stage packed, `stage_load`).
2. The airborne patrol: done (`airborne.6502`; its images kept once for both stages, both frames, D21).
3. The gantry (3 and 5): done (`objects.6502`'s gantry_beam).
4. The ram's score by stage: done.
5. The `road_lines` fix for C = -128: done. The row 20 anchor: found, left (decisions D25).
6. Shared with stage 1: the tunnel (renderer, mouth, walls, sound): done.
