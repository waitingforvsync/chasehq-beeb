# Journal

What's been done, newest last, with measurements. Decisions are in `docs/decisions.md`; the plan in
`docs/plan.md`.

## 2026-10-31

### The CPC reference harness (`tools/cpc.py`)
- SkoolKit's simulators can't run the game: they treat `&0000`-`&3FFF` as ROM and drop the writes (the stack
  at `&02FF` included). The harness uses kosarev's Z80 (the `z80` package) instead: flat RAM, breakpoints,
  port callbacks.
- It models the gate array (inks, mode, banks C0 and C4-C7, by swapping the `&4000` window), the CRTC's
  registers, the PPI (vsync on port B, the AY's bus on port C) and the AY's registers (the keyboard through
  register 14). BI3's disc loader becomes a `RET`; the LV files are put where it would load them.
- From `&BA00`, the start-up takes 400,736 T to reach `&0300` and finds 128K. The attract mode runs and draws
  the road, the traffic and the dashboard (rendered by `screen_png`). Speed: 30 game loops in well under a
  second.

### Skeleton (`src/`, `Makefile`)
- `make` builds `build/chasehq.ssd` titled with the date and time (`--title YYMMDD-HHMM`). Files: `!BOOT`,
  `CHASEC` and `CHASED` (the banks, ZX02), `CHASE2` (main RAM's code and the panel, ZX02, then the loader).
- `!BOOT` finds two banks (`BanksNeeded`), loads each bank's file at `&3000` and unpacks it into its bank,
  and runs `CHASE2`. The loader takes the machine over as Teddy Boy's does.
- The rupture (`irq.6502`): T1 at the top of the panel (8 rows, R4 = 7, R6 = 8, R7 = `&7F`) and of the
  playfield (31 rows, R4 = 30, R6 = 16, R7 = 23), reloads `&0FFE` and `&3DFE`. R12 alone changes (R13 is 0
  for `&3000`, `&4000` and `&6000`). A playfield is shown by the main loop setting `reqshow` and waiting for
  the panel's handler to take it.
- The palette is the identity (logical 0-7 physical, 8-15 the same), so bit 3 of each pixel is free (D8).
- `tools/gendata.py` runs the CPC to `&0300`, works out each pen's pair from the inks by D7, and writes the
  dashboard as BBC character cells with the dither baked in (4,096 bytes, 551 packed), and each pen's byte for
  even and odd lines.
- In jsbeeb (Model B, DFS 1.2): boots, finds banks 6 and 7, shows the dithered panel over the double-buffered
  playfield (a display test: the 16 pens as bands under a moving marker), stable.
- Sizes: main RAM's code 122 bytes packed (3,040 unpacked, mostly the pad to `&D00`); the code bank 156.

### The CPC's frame rate (the bar for the BBC, O3)
- `tools/cpc.py` now records each game loop's work: the T-states from leaving the flip's vsync wait to the next
  flip, the wait left out.
- Attract mode, stage 1, loops 40-400 (360 loops): median 403,501 T, range 299,057-497,930. That's 5.05
  frames at 4 MHz with no wait states; the CPC's wait states make it slower (an estimate of 1.2 gives 6.06
  frames). Its flips come every 5-7 frames: **about 8-10 fps**.
- So the BBC has about 5-6 frames, 200,000-240,000 cycles, for a game loop to match it. Gameplay is still to
  be measured (the attract mode may be lighter or heavier).

### Timing in jsbeeb (`tools/jsbeeb.mjs`, `tools/jsbeeb_time.mjs`)
- As Teddy Boy's: jsbeeb from jsbeeb-mcp's npm package, headless, the disc booted with SHIFT-BREAK.
  `jsbeeb_time.mjs --label L` gives the cycles between successive arrivals at a label, with the real IRQ.
- The display test's loop: 119,808 cycles every time (3.00 frames: its 8K fill and the wait for the flip).

### A first road primitive, measured (`work/bench/rowrun.6502`, not kept)
- A row runner: 64 `STA abs,X` (column c at `run + 3c`, page-aligned), the row's two pages patched into the
  operands' high bytes once a row (64 stores), X the line within the row. A span is entered by a patched
  `JSR run + 3c0` and ended by an `RTS` patched over the `STA` at `3c1`, put back afterwards.
- The whole playfield, 128 lines of five spans (grass, rumble, road, rumble, grass): 73,415 cycles (1.84
  frames). The stores are 40,960 (8,192 at 5); spans and patching the rest (about 45 cycles a span, 16 row
  patches of about 280).

### Review of the skeleton (agent), and what changed
- Bugs fixed:
  - `!BOOT` skipped any bank the OS's ROM type table lists, so the OS never service-calls into game data and
    a filing system held in RAM is spared;
  - the bank numbers are written to `&00`/`&01` only once nothing can fail back to BASIC: CHASE2 is loaded by
    OSFILE and entered through the exec address OSFILE writes back, not by `*RUN`;
  - the banks' files carry load addresses `&FFFF3000` (they had `&0000`: they'd have gone over the Tube);
  - `keys` zeroed by the loader; the ACIA reset (`LDA #3:STA &FE08`); the timer's own setting counted as 18
    cycles, not 12; a label that shadowed `show` renamed.
- Optimisations taken: R6 = 16 and R7 = 23 serve both cycles (the panel's 8 rows reach neither), so only R4
  and R12 are written; each handler leaves `&FE00` on the register the next writes first; R8 out of the IRQ
  (the main loop turns the display on once, under SEI); no `LDA #0` before the key scan's eight ROLs; the
  keys fall straight out of the last handler.
- A third interrupt at the playfield's end (periods 8, 16 and 15 rows: `&0FFE`, `&1FFE`, `&1DFE`) sets
  `irqphase`: `show` frees the old playfield as soon as its last line has gone, not at the next panel's top
  (up to 15 rows less waiting a flip). The keys moved there, into the border.
- The start-up frame now has its vsync at row 23, as the playfield's cycle does, so the first interrupt is the
  playfield's top, 16 rows after the vsync.
- Not taken: dispatching by patching IRQ1V's low byte (-18 cycles a frame, but no filter for stray IRQs);
  unrolling the key scan (-63 cycles for +45 bytes: Rich's call).
- Style: trailing comments on column 40 (`tools/aligncomments.py`), CamelCase tables, every hardware address
  named.
- jsbeeb: the display test runs as before (3.00 frames a loop) and the display is right.

### The road's model in 6502 (`src/road.6502`), checked against the CPC
- From the specs (docs/cpc-road.md): the six streams decoded a segment at a time into a 32-segment window
  (S1-S3 so far; S4-S6, the objects, written 0), the advance, the horizon (settled at each segment, stepped
  by the fraction), the backdrop's scroll, the boundaries' lines (an 8-bit shift-add multiply, the floor
  taken from the product's bits 6-13), the X steps (16 x 6 bits mod 65536: no sign handling), the two edge
  tables (one macro, expanded for each) and the lane tables with the CPC's chained borrows.
- `tools/genroad.py` writes the data: the perspective tables copied from the CPC, the stage's streams with
  BI2's holds and lead-ins (every jump and fork address found by walking them and relocated at build time),
  the backdrop dithered, fills by the 2x2 rule, rumbles and lane pixels as final bytes.
- `tools/machine.py`: py65 with the banks (ZX02 unpacked in Python, step for step as dzx02 does: checked
  against the panel). `tools/check_road.py` runs the CPC's stage 1 (its bot driving) and the BBC's model
  side by side, feeding the BBC the CPC's speed and X each loop.
- **236 loops, up to the first fork: segment, fraction, horizon, window (S1-S3), boundary lines, both edge
  tables and all three lane tables identical**, apart from the lane tables' top entry (its carry comes from
  stale entries above it, which differ). The fork isn't modelled yet. The backdrop's scroll isn't compared:
  the CPC takes its speed band from a stale register.

### The road drawn (`src/roaddraw.6502`), checked against the CPC
- The whole playfield every frame, bottom up: the road's lines segment by segment as the CPC's (stripes,
  rumble widths, crests' hidden segments, lane-layout sections reading the lane tables as edges, the
  alternative ground), then the backdrop's rows (rows four copies wide, so a scrolled line is 64 bytes from
  one offset), then the sky.
- A line is three spans of the row runner (64 `STA abs,X`, the row's pages patched once a row, an `RTS`
  patched at a span's end), then rumbles (3 bytes) and lane pixels stored as final bytes through two row
  pointers (columns 0-31, 32-63; the line in the row as their low byte, so a column's offset is a table).
- `tools/compare_road.py` draws the BBC's playfield in py65 at the state the CPC's harness reaches and
  renders the two side by side: at loops 3, 100 and 160 of stage 1 (flat, a hill, a curve) the road's
  shape, rumbles, lanes, stripes and horizon are the CPC's.
- Colours: the fills' first rule (the least spread of brightness for a 2x2 block's average) gave P0's road
  (the CPC's grey and black checker) red, green, blue and black: noisy. Now a pen on two of a block's pixels
  takes its D7 pair, one colour each (by occurrence: the CPC's checkers put a pen's two pixels on one
  diagonal, the same x + y parity), so both road stripes use grey's magenta and green, the dark one with
  black between.
- jsbeeb: the test drive (A accelerates, K and L steer: stand-ins) shows the panel over the road.
- **Too slow so far**: `road_draw` takes 104,387-112,351 cycles in py65 (2.6-2.8 frames), against an
  estimate of 75,000. Next: a review for speed.

### The car (`src/car.6502`, `src/sprites.6502`, `src/plotting.6502`)
- Sprites (`tools/gensprites.py`): the CPC's bytes as MODE 2 bytes, a column at a time, each column bottom
  first; pen 0 is logical 8 (bit 3 marks transparency, D8): below `&40` wholly opaque, `&C0` wholly
  transparent, else masked. Opaque pens by the 2x2 rule over the sprite's own pixels (its dither fixed to it).
  The car so far: 9 bodies and 3 wheels, each plain and mirrored: 7,378 bytes, 2,117 packed with the plotter.
- The plotter (data's bank): per column, the cell's pointer and Y the line in it; an opaque byte stored, a
  transparent one skipped, a mixed one masked through `MaskTab` (made by the loader) with the byte patched
  into the `AND` and an `ORA #`. Main RAM's `plot_sprite` pages the data's bank in round it. Car: wheels
  5,966 cycles, body 11,459.
- The car's logic from docs/cpc-logic.md: gear (a held key toggles every 4 loops), speed towards the gear's
  top (230 low, 360 high, 470/695 with a turbo; high crawls below 220), brake -20, coast -10, off-road loss,
  slope steps, cap 511; steering velocities (4 a loop to 36, falling 9), (L - R) / 2 a loop; centrifugal
  drift on curves (3 a unit of the fraction, the rest owed at the segment's end); pitch from the gradient;
  off-road levels from the edges. Frames: (turn + pitch + bump) mod 9, mirrored turning left (the CPC's
  &1785, checked in the harness: right is plain), a column left on full lock.
- Bug found in py65: steering right stored s itself (negative) as the mirror flag, so the sprite index ran
  past the table and the plotter wrote over main RAM. Fixed.
- py65, 400 loops (accelerating, right, left): road_draw median 115,170 cycles, max 203,896; road_frame
  median 44,538, max 51,518; draw_car about 17,500. Too slow: under review.
- jsbeeb: drives up stage 1, steering both ways, curves pushing the car out, hills changing the pitch.
- S4-S6 (the objects) now decoded too: S4 and S5 as nybble runs, S6 its counts and codes (a sticky value,
  the branch, traffic and fork-message hints), all three on alternate segments (the CPC's &16B5, template 1).
  `check_road.py` compares all six window rows: 236 loops, 0 differ.

### Roadside objects (`draw_objects`, `sprite_draw`, `tools/gensprites.py`)
- The stage's object tables converted at build time: each side's ids 1-9 to a kind (raised, on the ground,
  parts, the gantry) and, for each size 1-10, a list of parts (sprite, X offset, fixed or tiled by its k);
  identical lists shared (216 records for stage 1); its five cars' six sizes. 105 sprites, 12,367 bytes;
  the data's bank 14,066 of its 16,128.
- The road's model now keeps each boundary's edges (`RowXR`, `RowXL`) and scale (`RowScale`) for them.
- `sprite_draw` clips columns off either side, skips rows hidden under a crest and tiles a part's rows;
  `draw_objects` goes rows 20 to 1, right then left, stacking parts as the CPC does (raised ones a scale
  less a quarter up, tiled ones k * scale less the stack, at least 1), behind a crest standing on it.
- Compared with the CPC (`compare_road.py 60 x.png --objects`): the trees stand where the CPC's do (the left
  side's a byte to the left: to look at), shapes as the CPC's.
- Cost: `plot_objects` 60,944 cycles at loop 60 (py65). With the road (about 160,000) and the car
  (17,500), a loop is about 240,000 cycles: 6 frames, the CPC's rate. Speed next, after the review.

### Traffic (`src/traffic.6502`)
- Slots 1-5 (struct of arrays; 0 kept for the criminal), each car's distance ahead one 16-bit value in
  1/256ths of a segment: its speed added each loop, 256 taken for each segment the player enters; dropped
  past row 22, or behind (an overtake). Spawning as the CPC: a count of segments run down, reloaded with
  (random AND 15) + the stage's gap (&5BF0: 20), the first free slot unless 3 cars are before it; lane from
  the layout 20 segments on (the CPC's &30F3's ranges); lateral and speed by lane; model at random.
- The CPC's generator ported as it is (three bytes, seeded as at its power-on), for lockstep later.
- Projected each frame: the line between the car's row and the next nearer one's by its fraction, the
  column at its lane's share of the road's width at that line (24-bit product), the sprite by size. The
  object pass draws a row's cars before its roadside objects.
- py65, 260 loops accelerating: cars spawn, approach and are passed. Costs (median, max): traffic_update
  136, 590; traffic_project 795, 1,558; road_draw 112,040, 124,151; plot_objects 53,234, 116,141;
  draw_car 17,525.

### The panel's figures (`src/panel.6502`), and the rate in jsbeeb
- The dashboard's font (HI, LO, 0-9) from the CPC, dithered, each glyph 16 bytes: its two character cells
  in a row, so a figure is one 16-byte copy through a pointer. The panel is one buffer, so a digit is drawn
  only when it changes (no shadows per buffer, as the CPC needed). Speed as the CPC shows it (x 82 / 100)
  and the gear: 897 cycles.
- `jsbeeb_time.mjs` now counts a label in sideways RAM only with the code's bank paged in (the data's bank
  has code at the same addresses: the first timing counted the plotter's arrivals there too).
- **The game loop in jsbeeb, real IRQ, 30 loops: 239,616 cycles, 6.00 frames: the CPC's rate.** The
  drawing's the bulk (road ~112,000, objects ~53,000, car ~17,500, model ~45,000).

### Collisions with traffic and the bounce (`car_collide`, `car_update`)
- A traffic car up to a segment ahead of the player whose span (the CPC's width, &28 quarter-bytes)
  overlaps the player's box (&78-&97) is hit: it goes, and the player bounces to the side away from it.
- The bounce as the CPC's &2DB9: keys masked to the gear, the speed cut by a quarter (OR 3) a loop until
  below min(150, speed), the shove max(24, 16 + speed / 16) fading by a sixteenth a loop.
- py65, hit at 360: speed 263, 190, 133, 123 (the CPC's verified 263, 190, 134, 124: one off in the last
  two, to look at), shove 36, 34, 32, 30 (the CPC's exactly). Two segments ahead, or right of the box: no
  hit. Still to do: the car's frame during the bounce (the CPC shows full lock), the message and the sound.

### The criminal, the clock, the score (`traffic.6502`, `flow.6502`, `panel.6502`)
- **The criminal** as the CPC's handler (`&2E8E`), from its code: 868 segments ahead at 60 (a third distance
  byte, CrimFar); within 20 rows it's sighted and the handler runs: traffic in its lane within 2 rows, or (settled,
  within 6 rows) the player in its lane by RoadX, makes a lane step (random bit 7; from the edges two the other
  way); the road's lanes at its row clamp it two lanes at a time; 10 a loop across. Speed by row from tables
  (230; 260 within 6; sprinting 9 loops, 30 more a row nearer than 13), the sprint starting on the loop the
  count runs out. The CPC's dodge count is kept: it changes nothing but paces an RNG call, and leaves the borrow
  the player-lane thresholds are subtracted with. Its random numbers are drawn in the CPC's order.
- **Held level with the car**, as the CPC: no nearer than (RoadFrac AND &E0) + 1 in my distance (the CPC's
  fraction counts back, clamped to NOT(RoadFrac AND &E0)). My first version held it a whole segment ahead, where
  it could never be rammed.
- **Traffic, as the CPC's**: overtaken when no further on than the car (the same rule), not a segment behind;
  kept to the lanes the road allows at its row, 5 a loop across (`&3124`); after the sighting slower (60, 140,
  90, 170), 25 more segments between spawns, no fourth model. Spawn and lane keeping are routines now.
- **Collisions as the CPC's `&34BC`**: by row (traffic within 2, the criminal within 1) and RoadFrac's half, a
  code from the overlap (centred one less, right one more, 0 never registers), the side from the code. A traffic
  hit during a bounce leaves the car alone; otherwise it goes and the chain with it. A ram: stunned (tests skip 4
  loops, the handler 3), a 4-loop sprint, 10,000 (a double, code 1: 50,000 and two rams' damage), the bounce
  ending 40 higher. **Bug found:** `ObjXLo/Hi` were never written by `traffic_project` (my collision test had
  poked them), so no collision ever happened in the game. It now stores the left edge in quarter-bytes.
- **Flow**: 60 seconds, a second every 15 loops (the CPC's loops, so its "seconds" are about 1.8 s); the
  sighting resets it to 60; at 0 the pedals are masked and the car coasts at -10 to a stop: the game's over, a
  pause, the stage again with the score cleared. 20 rams: arrested, 100,000 and 5,000 a second left, a pause,
  the stage again with the score kept. Score per loop the CPC's sawtooth; overtakes the chain (200 up to 8,000).
- **Panel**: time, score and DIST from their BCD, a table of figures sharing one run of shadows; a digit drawn
  only when it changes.
- py65 (`work/flow/bbc_flow.py`): sighting at row 19 with the clock to 60; sprint 410 at row 7; rams at 10,000
  each with the car steered at it; time up → coast → over → restart. jsbeeb: the panel's figures and the
  sighting in play.
- Not yet: the arrest's pull-over and pages, the stage number in the score, continues, the damage meter and
  smoke, the siren lights, messages, sound, speech, the stage end's no-traffic zones (velocity &1FF).

### Road review (agent), first part
- **Bug:** a span ending at cell 32 put `STA abs,X` back over the runner's final RTS, so later spans ran on into
  CopyRunner (writing wherever it was last patched, possibly the front buffer): about 65K cycles a frame once hit
  (sharp bends). Fixed with its minimal patch, with two others (setup's window index carried for RoadSeg >= &C0;
  segend tested for a crest before the end). `check_road.py`: 0 of 200 differ.
- Its measured rewrite: road_draw 113K → 74K, road_frame 44K → 35K. Being merged onto the current road.6502
  without its sky/backdrop skip (the sprites would need to invalidate it).

### The sirens and the damage meter
- **Sirens by palette.** The CPC flashes its two panel lights by swapping 6 bytes x 32 lines between them in one
  of its two buffers. Swapping bytes in my single panel would cost about 3-4K cycles a loop. Instead
  `gendata.py` draws each light pixel in a logical colour 8-15 standing for its pair (its colour, the other
  light's there); logical 8-15 are otherwise unused, since nothing drawn has bit 3 set. The flash is then 8
  palette writes in `irq_frame`, in the border, when the flow asks: no bytes move, and nothing to restore at the
  rupture. The two lights differ slightly in shape: their pixels make 10 distinct pairs, so the two rarest (one
  pixel each) take the nearest pair with the same normal colour. The normal state is exact; the swapped one is
  out by those two pixels. Seen in jsbeeb: left red / right blue, then swapped the next loop.
- **Damage meter** (the CPC's `&14EE`): playfield lines 88 up to 28, bytes 2-3; from the bottom 3 lines a hit (a
  black line, two of the bar), the bar's colour by hits / 5 (`&1553`; both bar lines are (D, E): the spec's
  "(E, D), (D, E)" was a misreading, corrected from the code), the rest black. The road redraws the playfield
  each frame, so its 61-line column is copied in each loop (2,133 cycles), rebuilt only when the hits change.

### Sound (`src/sound.6502`, main RAM, from the IRQ)
- The SN76489 written a frame at a time in `irq_frame` (in the border), each register only when it changes:
  300-700 cycles a frame. Channels: tone 1 the effects, tone 2 the turbo's whistle, tone 3 the noise's clock
  (silent), the noise the engine / whoosh / an effect's noise.
- **Engine**: the CPC's AY period k(255 - speed/2) + 300 is 47-208 Hz, below the SN's tones, so it's periodic
  noise clocked by tone 3 (1/15 of its rate), tone 3's period 2/15 of the CPC's: idle LO 174 (2/15 of 1320 is
  176), HI at 360 119 (120). Computed each loop by `sound_update` (car.6502), stored under SEI.
- **Turbo**: white noise clocked by tone 3 at twice the CPC's noise period (59 down), a whistle on tone 2 at
  twice the period + 10, as the CPC's tone C.
- **Effects** as envelopes, 4 bytes a frame (noise control and attenuation, tone 1's period / 4 and
  attenuation), not the CPC's 1-bit samples, which stop its game for 40-230K T each. Requests by the CPC's
  numbers and priorities (`sound_effect`, A effect, Y priority, lower wins): so far the crunch (3) for a car
  hit (2) and a ram (1), the screech (1, priority 5, every second request as the CPC's) while skidding (left
  and right steering 17 apart with the step against the steer), bouncing, or 4 loops after shifting into HI.
- **Hardware detail found in jsbeeb**: with the keyboard's auto-scan off (as the game runs it) the keyboard's
  multiplexer drives PA7, so every latch byte lost bit 7. The writes now set the addressable latch's bit 3
  (auto-scan on) around them, as the MOS has it while it makes sound; CA2 is masked, so no interrupt. WE is
  held low 8 us (the chip's 32 clocks). jsbeeb's capture timestamps are lazy: order by entry, not by cycle.
- Not yet: the effects for roadside hits, landings, obstacles, scrapes and passing objects (their causes aren't
  in yet), the tunnel's engine, speech.

### The stage number, the turbo icons, and a sprite fix the sirens needed
- **Stage number** (the CPC's `&21A1`): the panel font's digit at row 4 line 4, byte 23, straddling two
  character rows; drawn once a stage by `panel_start`. `Stage` (1) in GameVars, set by `flow_new_game`.
- **Turbo icons** (`&216B`, sprite `&8FBD` 4 x 16, added to gensprites as `SprTurbo`): one per turbo left at
  the playfield's bottom left (columns 1, 5, 9; bottom line 124), the running one flashing each loop. The CPC
  counts a turbo off when it ends (`&3810`), not when it starts: `car_update` now does the same, so the icon
  in use is the last one. **Cost: 7,972 cycles a loop for three** through the general plotter (about 40 a
  byte): a target for the sprite review (a fixed-place blit would be a fraction of it).
- **Bug the sirens exposed:** the plotter's masked bytes ORed the sprite byte in whole, transparency bit
  included, so every sprite's edge pixels gained bit 3 on screen: invisible under the identity palette, but
  logical 8-15 are now the sirens' colours. It now ORs in the byte AND &3F (2 cycles a masked byte): nothing on
  screen has bit 3, which the sirens' palette trick relies on.

### Road review merged
- The reviewer's rewrite, merged onto the current tree (without its sky/backdrop skip, which the sprites would
  have had to invalidate): road_draw 113K → **88K** mean (83-94K), road_frame 45K → **36K**, both byte-exact on
  the recorded inputs and a steering sweep; `check_road.py` 0 of 200 differ; game logic unchanged in py65.
  - Renderer: rumbles and lanes inline, cell tables (`Col8`, `E6Of`, `R6Of`), a column-planar backdrop
    (`BackPlanar`, 528 bytes for 2,112), patching only on change; the line code is one Baron `FOR odd = {1, 0}`
    (both parities, one source); a spare store before the runner's RTS (cell 32 needs no test); `INPAGE`
    instead of `ALIGN`.
  - Model: steep edge segments by one divide and Bresenham, quarter-square multiplies, tail calls.
  - The loader makes the tables (`make_tables` in entry.6502): squares, cell tables, lane entries 104-127 off
    the screen. CodeVars now from &B500; the code bank has 611 bytes free.
  - Fixes: the &C1 ground's left table; a top guard (the old code could write page &7E on a full playfield).
- **jsbeeb, real IRQ, standing at the start: 228,710 cycles a loop median (5.73 frames)**, down from 6.00
  despite tonight's additions (criminal, flow, sound, meter, icons, panel figures). Sprites next: a review
  agent is measuring plot_objects (53K), draw_car (17.5K), the icons (8K).

### The fork (stage 1's, 320 segments in; the chase happens past it)
- **Why it couldn't wait**: without the CPC's commit (`&4144`) the model ran on past the 255-segment hold into
  the wrong stream data (220 segments of `&60`, read as a tunnel). The criminal starts 868 segments ahead, so
  the whole chase is past the fork.
- **Model** (`road.6502`, from the code: docs/cpc-road.md, "The fork, from the code"): `road_fork` finds the
  first window row with flags `&E1` all set; there (unless it's its run's first segment) the branch is chosen
  once by RoadX (right under `&10C`), and the separation grows 16 every 2 segments, interpolated by the
  fraction. Two roads: the one the car's on, and the other `sep` across with each segment's curve negated (not
  the starting heading's: the CPC patches a NEG into the loop only). `edge_table` is now one routine with its
  table addresses patched (the macro's two copies couldn't become four in the space), writing the second
  road's right edge (`EdgeR2`, the CPC's `&7F`, in main RAM) and its left into Lane3 (`&7D`), as the CPC does.
  `road_split` makes the fork's lines two 2-lane roads (middles halved with their signs, EdgeR becoming the
  second road's lane line); nearer lines get the normal lanes, their borrows starting afresh. `road_commit`
  (after the flip) points the six streams at their branch: each continues at the address its own fork code
  recorded (I first misread the commit's EXX as crossing them: it doesn't), from a short lead-in; refills 32
  window rows (curve -4 or +4, flags `&01`/`&03`, the other side's objects gone). `RoadC0` is negated on the
  right branch once chosen, as the CPC's `&3F4C`.
- **Checked against the CPC in lockstep** (`check_road.py`, now through forks and commits; `right` for a bot
  taking the right branch): 0 of 520 loops differ on the left branch, 0 of 700 on the right. S6 is reported
  separately: the CPC's obstacle code (`&3305`, not ported yet) clears S6 entries for values 3 and 6.
- **Renderer**: from the first fork-hold segment to the road's end, the CPC's fork renderer (`&4DCE`): five
  spans by the row runner (grass, road 1, grass, road 2, grass; the cells kept in order), four rumbles (road 2's
  start like a left edge; road 1's end one byte left of a right edge's, so when x/4 is even its last byte is
  over road: genroad now makes `RumbleRR` for that), lane lines on P1; its own phase and level carried on (the
  right rumbles at the left's level), a crest's segments an entry each, its lines not the backdrop's road. Byte
  positions compared with the CPC's screen line by line: they match. Cost: road_draw about 120K cycles (py65)
  with the fork filling the screen, against 88K for a plain road: a target (it isn't unrolled).
- **The car's anchors** (the CPC's `&7CFE`/`&7CFC`): found that the CPC's off-road and roadside tests read the
  *sprites'* first anchors, the edges where segment 0 ends (by its layout's tables), not the bottom line (my
  off-road) nor the middle lane line (my roadside test, wrong). The CPC's sprite code writes them over `&7C`'s
  entries, which had made `&7C` look wrong when read after the renderer. Ported (`road_anchor`); in a fork at
  row 0 they're the two roads' inner edges, which the divider test uses (a bounce ending at 140), and with the
  fork a row on the CPC skips the off-road test. `check_road` compares them and CarOff: 39 of 520 loops still
  differ. One is segment 0 starting a taper (the CPC's renderer reshapes the lane tables for tapers, which mine
  doesn't yet); the CPC's CarOff being cleared later in its loop is being traced.
- **Flow**: a branch chosen other than the criminal's slows it (`&5F`) and scores (stage + 4) x 10,000, as the
  CPC's (which looks inverted); messages later.
- **The code bank filled up** (19 bytes left): the game's logic (game loop, car, traffic, flow, panel, 4.1K)
  moved to main RAM after the sound (`&0FC0`-`&2000`), no stubs needed (proposed for Rich: decisions P6).
- Still to do for the fork: the sprites' anchors beyond it (the divider's posts should stand on the inner
  edges); tapers; the messages.
- **Tapers** (the CPC's `&4724`), in the renderer's `setup`: a lane layout's segment with bit 2 or 3 (j up to
  17) has one table redrawn as a straight Bresenham line over its lines (the table, the lines, the fraction's
  offset, the clamp and both steppers as the CPC's). Visually as the CPC's.
- **The car's tests, now exact against the CPC** (`check_road.py`, both branches, through the fork): the anchors
  are computed after the renderer (so its tapers are in the tables, as the CPC's), `car_offroad` runs after
  `road_draw`, and the right edge's thresholds are the CPC's effective ones (143 and 125: its compares carry
  the previous one's borrow; in the fork path 142 and 125). Found on the way: for a bounce's first 5 loops the
  CPC draws sparks on its side and clears CarOff (`&3B02`'s operand is the side + 1): ported as `car_spark`
  (the sparks' sprites later). 0 of 520 loops differ (left branch), 0 of 700 (right), anchors and CarOff
  included.

### First release (site commit a30f1a6)
- `make release`: stage 1 playable: the road with its fork and tapers, traffic, the criminal to chase and ram,
  the clock and score, sirens, damage meter, engine and effects. Driven in jsbeeb with the real IRQ by the
  CPC's demo rule (`tools/jsbeeb_drive.mjs`, screenshots by loop) through the fork and its commit: 5-6 frames
  a loop on the plain road, 7 in the fork (the fork renderer isn't unrolled yet). py65 over 650 loops through
  the fork (`work/flow/game_run.py`): no stray writes into main RAM's code or the panel from the drawing.

### Obstacles (cones and barriers, the CPC's `&3305`, `&33A7`)
- Spawned once a loop a segment's entered from S6 at row 20 less the segments entered: 1-3 cones, 4-6 barriers;
  one (at &32 or &DC) or two (&46/&B4, or &50/&A0), the two kinds clearing S6 two and four rows on; the first
  free slots, the rest dropped. Widths by kind from the stage (`(&5BCC)`: 16, 32); their sprites the stage's
  descriptors, as car models 5 and 6 in `CarSprite` (gensprites).
- Hit (no bounce; effect 5, priority 3): it flies a row on at twice the car's speed (350 at most), its flight's
  start and length by the speed's bucket (`&346E`), heights from `&3446` a loop (raising its sprite by lines),
  its speed less the CPC's lopsided 32nd, the sprite flipped each loop (not drawn yet: traffic sprites have no
  mirrored copies), then landed. Obstacles aren't overtakes, aren't in the criminal's traffic avoidance, keep no
  lanes; traffic's spawn counts only traffic. Speeds are 16-bit now (flights; traffic's &1FF later).
- `check_road.py` now runs the BBC's spawn after its compare, as the CPC's runs after its render: S6 matches too,
  so the whole window is compared again: 0 of 700 loops differ (right branch, where stage 1's S6 has them).
- Seen in jsbeeb on the right branch (its red ground, barriers on the road).

### The arrest (the CPC's `&1166`, `&10B9`, `&0F8E`)
- 20 rams: the criminal at 400, the arrest's states. 1, the pull-over: the criminal 5 a loop towards lateral
  &23 (jittering, as the CPC's) and 5 slower a loop to 70; the player on autopilot (`arrest_keys` replaces the
  keys): steered right at X &110 or more, left under &101, accelerating to a target (350; 69 + 20 a row within
  14 rows, the CPC's borrow; none at 14, its DJNZ from 0), braking 50 over it, the gear as the demo's; not
  steering and within 3 rows, 20 loops on: both stopped, the criminal a row ahead, a screech. 2, pulling in
  behind: the car 4 lines higher a loop to 16 (`CarLift`, the CPC's `&175F`), 12 across to &126, a 32nd of a
  segment on unless that carries. 3, 4 loops. 4, the bonus (100,000 and 5,000 a second left) and a pause, then
  the stage again with the score kept (the CPC's pages and its next stage later).
- Meanwhile: the criminal's handler off, no traffic spawned and traffic running off at &1FF (the CPC's &3124;
  also in its no-traffic zones, S6's code 14), the damage meter gone from state 3.
- py65 (`work/flow/arrest.py`): from 20 rams with the criminal near, the pull-over takes 91 loops (the CPC's
  about 113 from its usual distance), then the rest as above.
- **The rows' anchors** (the CPC's `&2BEA`): the sprites' anchors for row r are now the edge tables' entries
  where segment r - 1 ends (`edge_table` records each segment's cumulative entries), by that segment's layout,
  the fork's inner edges from its row on, taken after the renderer (tapers in). They were the X steps'
  boundaries (one Bresenham step off, ignoring layouts and the fork). Row 1's are the car's. `check_road.py`
  compares rows 1-20 (anchors off the screen as equal: past the tables they're stale on the CPC): 0 differ on
  both branches. The divider's posts now stand between the fork's roads, and the "left side a byte to the
  left" noted with the first objects is gone.

### Speech (`tools/genspeech.py`, `speak` in sound.6502, a third bank)
- The CPC's five phrases (CHASEHQ.BI1, its 128K bank 4; table `&0B5D`: length, address) are 16,230 bytes of
  4-bit AY volumes, two a byte: one sideways RAM bank. `genspeech.py` maps each to the SN76489's attenuation
  (AY steps about 3 dB, the SN's 2 dB: round((15 - v) * 1.5), 15 off; the data's mostly silence and full-volume
  pulses) and emits `speech.bin` (the bank, CHASES, ZX02-packed) and the phrases' places.
- `!BOOT` looks for a third bank after the two it needs (the ROM type table respected as before) and loads
  CHASES into it if there is one; its number goes to &02 (&FF none: the game plays silent). The zero-page pool
  starts at &03 now.
- `speak` (main RAM): tones 1 and 2 at period 1, a steady level, their attenuations written a sample at a time
  (two writes, as the CPC's two AY channels), the game stopped as the CPC's is while the rupture IRQs keep the
  display. The frame IRQ skips its keys, sirens and sound meanwhile (`speaking`): they share port A. After, the
  sound's shadows are forgotten so its next frame writes the chip afresh. Sample period tuned in jsbeeb from
  259 to about 209 cycles (the CPC's 414 T at 4 MHz).
- Played: phrase 5 at the game's start, the stage's on its second loop (3, then 1, 2, 3 ... as the CPC's),
  4 when the time's up and the car has stopped. Checked in jsbeeb: banks 6, 7 and 5 found, the attenuation
  writes during a phrase, the game going on after. (Not heard: there's no audio here.)

### Second release (site commit b444a7e)
- The arrest's pull-over, cones and barriers, speech (with a third bank), the car's and objects' anchors as
  the CPC's. jsbeeb drive (right branch, 450 loops): 5-6 frames a loop, 7 in the fork; the stage's phrase
  stops the game for 35 frames on its second loop, as the CPC's does.
- The fork renderer's rumbles and lane pixels now store through page-patched `STA abs,Y` (`fork_row` patches
  them a row) instead of a pointer set up per byte: road_draw with the fork on screen 120K → 116K, the
  playfield identical. The split is limited to the road's entries (road_frame in the fork 59K → 56K).
- During a bounce the drift and lump add nothing, though both run on (the CPC's `&3A1A`).

### The message window and the pages (`src/text.6502`, `tools/gentext.py`) - 2026-10-31
- The data (`build/gen/text.6502`: the font, Nancy's and the partner's faces, the stage's scripts and pages,
  2,439 bytes) is in main RAM at &259-&BDF, readable from both banks; the dissolve's masks are split out to
  `build/gen/dissolve.6502` (not used yet). The code, 1.3K, is in the code bank.
- **The message window** (the CPC's `&1DB4`, `&1DD4`): busy states have bit 6 set, closing bit 7, so a request
  is `BIT MsgState:BVC take` then the priority compare. The script and line pointers are zero page. A glyph is
  16 `LDA Font1+i*Glyphs1,X` through two pointers sharing a low byte (16c), the offsets in Y. The static steps
  the generator inline: s0 and s1 only enter as their sum, which steps by &76 a call, and after the 640 calls
  each has moved &80 (EOR), so only s2 is stepped for real: the generator ends as the CPC's. Timing in py65,
  loop by loop as the CPC's (`work/text/bbc_text.py window`): a crash's message requested at S has its face at
  S + 4, its last glyph at S + 10, the close at S + 20 and the face blanked at S + 24; the briefing's lines
  start on S + 40, 77, 110, 150 and 182 (the CPC's 41, 78, 111, 151, 183 from loop 1).
- A bug found by eye: the bottom half's pointer took its carry from an `ADC #0` the top half's had already
  used, so from column 16 each glyph's lower lines landed 16 columns back. Now `ADC #HI(LineBottom) -
  HI(LineTop)` after the top's.
- **The pages** (`&12CF`, `&13B2`): drawn whole into the back playfield each loop after the sprites, entries by
  their appearance loop (the generator works them out from the CPC's delays), stopping at the first not yet
  shown. Three row pointers with low bytes 0 (the text's row, above, below), Y walking along them 8 a cell, a
  page crossed moving all three. Size 2 interleaves its two rows' stores so each glyph line is loaded about
  once. All seven render as the generator's previews (`work/text/bbc_pages.png`).
- **Wired**: the turbo (2), a traffic crash (3), a ram (5), the 19th ram (10), the slow nag (10: 100 loops
  under speed 120 outside the arrest, `CarNag`), the fork's branch (20, right or wrong), the clock at 15 (21);
  the SIGHTING page, TIME UP (every loop while coasting), PULL OVER (the 20th ram). The arrest now waits for its
  pages as the CPC's: state 3 then the arrest page; 4, when it's gone, the bonuses (`arrest_bonus` also patches
  the bonus page's figures: the stage and 0, the seconds, the new score with leading spaces) and the bonus
  page; 5, when that's gone, the stage again.
- py65, 700 loops of the bot driving: the crash, the fork, the nag and the clock's messages, no stray writes.
  jsbeeb: "WHOAAAAA!" at a turbo, with the partner's face.
- The py65 bot crawls after the fork (speeds 10-30, bouncing off the roadside): so does the CPC's own demo
  rule there (30-70, bouncing). `check_road.py` now also compares the bounces car_offroad starts with the
  CPC's: 0 differ in 450 loops through the fork.

### The sprite review's patches (`work/review-sprites/`), merged
- A band-at-a-time plotter (8 unrolled steps in a page, one `(zp),Y` for sprite and screen, a `BMI` for the
  opaque test, the 16 half-transparent bytes &80-&8F through MaskTab/OrTab), cars found by a per-row bitmap,
  the turbo icons compiled, and traffic_project's multiplies by quarter squares. The reviewer's bench: sprites
  76.5K → 48.7K cycles a loop on average, 152.7K → 85.3K at worst; the merged build's playfields hash the same
  as the reviewer's after every drawing routine, 400 loops.
- The compiled turbo icons (415 bytes) go in the code bank rather than the &259 gap, which the text now holds.
- Space now: the code bank about 570 bytes free, main RAM about 460 before GameVars, the &259 gap 288, the data
  bank about 300.

### Third release (site commit ffc7731)
- The messages and pages, the sprite review's plotter. jsbeeb (Master): the turbo's message with the partner's
  face, the TIME UP page over the coasting car, 97 seconds of play without a hitch.

### The continue and the game over (flow.6502) - 2026-10-31
- States now: driving, time up (coasting), stopped (TIME UP's page running out), arrested, a continue offered,
  over. Stopped, when the page has gone: a continue offered if one's left (2 a game), else the game over.
- The offer (the CPC's clock state 3): CONTINUE every loop with its TIME patched (the count of 21 halved:
  "10", or a space and a digit), the count down every 4 loops with effect 8 or 9 at priority 1, 84 loops in
  all, then the game over. The gear (game.6502, the only key while it's offered) takes it: driving, 60
  seconds, rams 0, 3 turbos, the gear held off 3 loops, the page gone, phrase 5. After one, a ram scores a
  tenth (add_score1 with the figure shifted up) and the clear bonus is the stage x 10,000 (" n" on its page).
- The game over: Nancy's verdict (priority 255) and the GAME OVER page every loop; when the verdict's closed,
  a new game. The CPC's own drive after the dissolve waits for the title (decisions P8).
- py65 (`work/text/bbc_text.py over`): time up at loop 44, the offer at 69 (TIME UP's 25 loops), taken at 89;
  time up again at 134, the offer at 159 running out at 243 (84 loops), the verdict ("ONE MORE TRY, / FOR
  BEING A GOOD BOY!") closed at 304 and a new game, score 0, two continues.
- Main RAM: about 250 bytes left before GameVars.

### The bonus popup (`src/popup.6502`) and the 64K start message - 2026-10-31
- The CPC builds a popup in `&20F2`, which only the overtakes (`&2160`), the ram (`&302A`) and the wrong
  fork (`&407F`) call (the loop's score goes in at `&2131`, without one): the figures added, no leading zero,
  drawn at panel row 3 line 2, cells 14-25, in one buffer only (so it blinks), 11 loops, then cleared.
- BBC: `popup_score` (A the BCD byte, X its place; no ADC, so it's called in decimal mode before the add)
  writes the figures and sets 12 loops; `popup_update`, after panel_update, clears the place each loop and
  draws the panel font's glyphs on odd loops left. py65: "200", "50000" and "8000" at their place, the area
  black again after.
- With no speech bank the stage starts with the 64K CPC's message in place of the phrase (`MsgStart`, 255).
- Space: the code bank about 315 bytes free, main RAM about 217.
- one_object now leaves undrawn the two kinds of part the CPC's handlers don't draw (the sprite review's
  find): a right part landing exactly on 0, and a left one whose edge + 8 carries. The part is put off the
  screen (column 64) so its stack still grows. Bench: no playfield differs in 400 loops, plot_objects +98
  cycles a loop. The data bank has about 290 bytes free (not 100, as noted above).
- jsbeeb (Master), accelerating from the start without steering: 103 loops in 500 frames, 4.85 frames a loop
  (the first release's drive was 5-6).
- The arrest with its pages, py65 (criminal near, 20 rams at loop 30): PULL OVER 30 loops, the pull-over to
  loop 120, states 2-3, the arrest page 129-188, the bonus (100,000 + 58 x 5,000) and its page 189-248, the
  stage again with the score kept. Against the CPC (its criminal brought near, `&1166` called at loop 120): the
  same picture at the end, the criminal bottom left and the car lifted behind; the CPC adds the criminal's
  flames and a flash on the car (effects not ported yet). DIST is now worked out every loop (it froze in the
  arrest); the CPC's panel does it every loop.

### The player's effects, decoded (docs/cpc-sprites.md, Effects)
- `&3DC1`'s table (`&540F`, 39 entries) and its two callers, with the six images rendered from the CPC's
  memory: the 6×20 image is the bounce's burst (5 loops from a bounce's start, by its side and the steering),
  the 2×6, 2×4, 3×8 and 2×11 ones are the siren light going onto the roof after the sighting, with a 6×17
  flare, and a 3×8 flash in the arrest. No turbo flame: the spec's earlier labels were guesses. 288 bytes in
  all on the CPC; they wait on where the room comes from (decisions O5).

### The text code's review, merged - 2026-10-31
- A review agent (`work/review-text/`, its tools and every variant's build kept there) found no bugs, and five
  changes that are both faster and smaller, all merged:
  - `msg_static`: the s0 + s1 sum steps by &76, so its bit 0 never changes. A step is then `CLC:ADC s2:ROR A`
    and a branch patched once a static to BCC or BCS, with an `EOR #&80` past it. The pixels come from a
    spread table read by `AND #&0C:TAY`, and the store is `STA abs,X` with its high byte patched each row.
  - `msg_clear`: one loop doing both halves of the line.
  - `page_draw`: size 2's doubled lines through pointers a line on, and line 7's white through pointers at
    line 7. The glyphs are fetched with `LDA (at,X)` as `at` walks on, counting down.
- Measured (py65, the reviewer's `bench.py`): `msg_static` 33,941 -> 22,858 cycles; `page_draw`'s worst loop
  on each page -82 to -2,102 (BONUS 25,283 -> 23,181). The heaviest loops are the statics', so the worst loop
  falls about 10,800 cycles (drive 277,122 -> 266,322).
- Merged, the panel, both playfields, `Rng` and the text's state are identical loop by loop to the build
  before in the window, all 7 pages, 200 statics and the 700-loop arrest; `bbc_text.py run 1200` prints
  the same. jsbeeb (B-DFS1.2): the turbo's static, the partner's face and "WHOAAAAA!".
- The spread table (13 bytes) is gentext's `MsgStaticBytes` in the gap at &259, not the code bank: the code
  bank has 38 bytes more free (560 -> 598, counting the pad before RoadT: RoadT is now a page lower, so the
  pad is 27 and the end 571), the gap 9 fewer (279).
  It also puts Font1 9 bytes on, which leaves only its plane 3 crossing a page (the reviewer's note).
- gentext checks that a page entry has a glyph (`page_draw` counts them down). Its rows were already checked.
- Not merged, as they cost bytes (decisions O5): size-2 glyphs through patched absolute stores (+102 bytes,
  BONUS -3,233 a loop), the same for size 1 (+75, ARREST -2,236), and `msg_face` five rows a pass (+27,
  -1,732 a face). The heavy pages all show while the car is stopped.
- Release 4 (site commit 0d52c56): continue and game over, the popup, the 64K start message without speech,
  the sprite edge fix, DIST every loop and the text review.
- Measured for decisions O5: stage 1's own data here is about 10K (7.4K in the data bank, 2.5K in the code
  bank), and the player's car's mirrored copies are 3,689 bytes, which mirroring as it's drawn would give back.

### The wait for the flip moved, and the sky skip (decisions D12, D13) - 2026-10-31
- **Measured first** (jsbeeb B-DFS1.2, real IRQ, 300 loops of the CPC demo's steering): `show` waited 9,390
  cycles a loop on average (4.6% of the loop) for the old playfield to be free, in 199 of 300 loops, up to
  25,024. The wait ended at the playfield's end, so the loops locked to it: median exactly 5.00 frames.
- **The wait now comes just before `road_draw`** (portalc's way): `show` only sets `reqshow`, and the next
  loop's logic (`road_frame` and the rest, about 50K cycles, more than a frame) runs meanwhile. The IRQ flips
  `back` itself: at the playfield's end if a request is waiting (`reqshow`'s bit 7 then set), else at the
  panel's top when it takes one. `wait_back` waits for `reqshow` to be 0 or negative; `irqphase` is gone.
- **The sky skip:** `SkyTop` is how many top lines of the back playfield are sky already; `SkyOther` the other
  playfield's, swapped in by `road_draw` when `back` changes (`SkyBuf`), so the py65 harnesses that flip
  `back` themselves work unchanged. `road_draw` draws sky only from the first sky line down to `SkyTop`, then
  sets it to the sky's lines. `sprite_draw` lowers it to a sprite's top (bottom + 1 - lines), as do the
  damage meter (line 28) and the turbo icons (109); `page_draw` sets it to 0 while a page is on. Both
  marks are 0 at each stage's start.
- Measured before (from py65, 400 loops, the same buffer two loops apart): the sky is 20 lines and 7,900
  cycles a loop, its lines 99.7% unchanged and 90% untouched by sprites. Road lines: 3% unchanged; 60%
  differ in 49-64 of their 64 bytes (the stripes' colours flip), 36% in 1-16. So a delta renderer for the
  road would save at most about 9K before its bookkeeping and the sprites' dirt: not worth it.
- **Exact:** against release 4 (HEAD, rebuilt), the reviewer's `bench.py`: the panel, both playfields, `Rng`
  and the text's state identical every loop in the window (360), the 7 pages, the arrest (700), a 600-loop
  drive and a 400-loop time up.
- **Cycles:**
  - py65 (400 loops): `road_draw` 93,790 -> 86,860 mean; the sprites +474 (the top's compare); the loop
    188,982 -> 182,508.
  - jsbeeb, both together: **204,644 -> 188,941 cycles a loop mean (5.12 -> 4.73 frames, 9.8 -> 10.6
    loops a second)**; median 199,680 -> 181,804. `wait_back` took 6 cycles in all 300 loops: it never waits.
- **Bytes:**
  - Code bank: 598 -> 536 free. RoadT's page moved up one: the pad before it is now 221 and the end 315.
  - Main RAM: the end 217 -> 202; the &259 gap 279 -> 251 (the sprite stubs moved there from the IRQ's
    block, which the handlers outgrew; the block now has 19 free); GameVars +3.
  - Data bank: 6 fewer.
- Moved for the page checks: `msg_blank` after `msg_static` (its byte loop had crossed &9F00).
- Where a loop goes now (py65 mean 182.5K): `road_draw` 86.9K (its line code 31.7K, the runner's fills
  31.0K, the backdrop 8.7K), `road_frame` 40.5K (the lane tables 13.2K, `edge_table` about 12K,
  `road_xsteps` 6K), the objects 30.9K, the car 12.8K, the rest about 11K. jsbeeb's IRQ adds about 6.4K.

### The frame-rate review (agent, `work/review-frame/`) - 2026-10-31
- No bugs in the sky skip or the IRQ's buffer swap. It noted:
  - The meter lowers SkyTop to 28 every loop (harmless now).
  - `page_draw` zeroes SkyTop before a page's first entry shows.
  - The runner's `INPAGE 196` would silently pad up to 195 bytes if road.6502 grew past its 21 bytes of
    headroom.
- Merged, the four that are faster and smaller:
  - 02 `road_xsteps` (a dead sum gone, the multiply through X and Y, the negation's carry patched once).
  - 03 `road_lines`' squares through X and Y.
  - 04 `road_split`'s halvings through Y, `road_lanes`' rare carry out of line.
  - 05 the sprites' top line where C is known set: 13 cycles a sprite, not 19.
- Merged: bench.py IDENTICAL in all five runs (window, pages, arrest 700, drive 600, time up 400);
  check_road.py 0 of 600 differ on both branches. jsbeeb, 300 loops: **188,941 -> 187,324 cycles a loop
  (4.73 -> 4.69 frames)**. Code bank 536 -> 566 free (all 30 in the pad before RoadT, which now starts 5
  bytes past &A800); data bank 4 more free.
- Held for Rich (decisions P10):
  - 01, 06 and 07, which together are the biggest gain: 01 `edge_table`'s steep segments by patched
    constants (+36), 06 the fork's lines (+22, the worst loops), 07 two tables made by the loader into
    CodeVars (-28 in the bank, +28 of CodeVars' 168).
  - 08, a backdrop skip: 932-1,055 a loop for +125 bytes, its worst loop slower.
- The reviewer's figures for all seven: jsbeeb 1,000 loops 175,838 -> 170,746 mean, 99th percentile
  240,209 -> 224,511.
- Release 5.
