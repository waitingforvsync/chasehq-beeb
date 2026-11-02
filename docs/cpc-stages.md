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
- **S4, S5 objects**: id 2 in stages 3 and 5. On the left (S4) it's kind 4, **the gantry**, which
  `sprites.6502` drops ("the gantry: not yet"); on the right, an ordinary composite.
- **S6 codes**: 4 and 5 (obstacle values 1 and 2: one cone or barrier at `&32` or `&DC`, handled by
  `obstacles`), 11 (the criminal takes the left branch, stages 2 and 3: handled), and 15, 17, 18 (stages 2 and
  4): `&1759`, the airborne patrol, below. The BBC decodes all of them (`next_s6`); nothing reads
  `RoadHints`' first byte yet.

## The airborne patrol (stages 2 and 4)

`&329E`, each loop, by `&1759` (code − 14):
- **3 or 4** (codes 17, 18): the message `&1A14` or `&1A24` (THE TARGET VEHICLE HAS TURNED LEFT / RIGHT UP
  AHEAD), and `CALL &31AC` patched into the sprite drawer at `&23C8`. The helicopter comes in from X = -24
  towards `&70`, bobbing (`&3243` cycles 0-3, `&324B` ±1); `&3237` counts `&85` down by 2 to `&61`. Then
  `&1759` = 5.
- **1** (code 15): it heads off to -56 (`&3272` = `&FFC8`), state 2; **2**: when its X's high byte is 0
  again, the patch is taken out (`NOP`s at `&23C8`) and `&1759` = 0.
- `&31AC` draws it when the drawer's row count reaches 3 (`LD A,B:CP 3`): two parts from the frame list at `(&5BDE)`, or `(&5BE0)` on
  odd loops (`&1769` bit 0), each an x offset and a 5-byte header. Part one 14 bytes by 44 lines (the
  helicopter from behind, its rotor blurred: `work/lv/stage2_air.png`), part two 10 by 10 at x + 8 (dark: its
  shadow). The second frame is the first mirrored. LV2's at `&6B22`, LV4's at `&6A5E`; 716 bytes of images
  each. The pointers are 0 and `&000C` in LV1, LV3 and LV5.
- Code: `&31AC`-`&3304`, about 340 bytes of Z80.

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
  sum to -128. Not applied yet.
- **The rows' anchors**: row 20's left anchor is one more than the CPC's in some loops (stage 2: 6 and 6
  loops, 3: 47 and 19, 4: 3 and 0, 5: 35 and 5; stage 1: 0). Not found yet.
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
- Not read yet: the tunnel's road colours (`&5BC7`) and the helicopter's frames (`&5BDE`, `&5BE0`).
- The code's reads of the stage number (`&164D`): the ram's score at `&3015` (stage × 10,000, stage + 4
  for a double), which `car.6502` has at stage 1's (10,000 and 50,000); the fork's (`&4077`) and the
  bonuses (`&1018`), which the BBC takes from `Stage`; the intro's car reveal, skipped on stage 5
  (`&05A0`); `&21A7`'s copy to `&1758`; the stage's load (`&0C40`) and the flow (`&0327`, `&0331`,
  `&03C2`, `&0FAB`).
- LV6 (the ending) is untouched.

## What the later stages need that stage 1 doesn't

1. A load per stage, into slots of 2,349 (code bank), 7,806 (data bank) and 727 (main RAM).
2. The airborne patrol: the mover and drawer (about 340 Z80 bytes) and 716 bytes of images a stage (2 and 4).
3. The gantry (3 and 5).
4. The ram's score by stage.
5. The `road_lines` fix for C = -128, and the row 20 anchor.
6. Shared with stage 1: the tunnel (renderer, mouth, walls, sound), which stage 1 itself needs.
