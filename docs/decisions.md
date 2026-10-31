# Decisions

The log of design decisions for the port. Each entry has one of three statuses:

- **Decided**: Rich has made the call. To change it, add a new entry that supersedes the old one.
- **Proposed**: Claude's recommendation, waiting for Rich to accept, change or reject it. An accepted
  proposal moves to Decided with a new D number, keeping its old number in brackets.
- **Open**: needs a measurement or a preference before anything can be proposed.

---

## Decided

### D1. A MODE 2 sideways RAM version of the CPC disc version, in Baron (2026-10-31)
Rich: "i would like to create a version for the bbc micro with sideways RAM in mode 2 based upon this
version, using the baron assembler."

### D2. No shadow RAM; a BBC B with sideways RAM if possible (2026-10-31)
Rich: "I prefer not to use shadow RAM and make it Master only. Ideally it will work on a BBC B with sideways
RAM too."
- NMOS opcodes only, even on a Master.

### D3. A vertical rupture double-buffers only the playfield, at the CPC's screen size (2026-10-31)
Rich: "i would suggest using vertical rupture to double buffer just the playfield." And: "BBC MODE 2 is not
64 bytes per scanline normally (it is 80). But we can definitely use the same CRTC screen size."
- 64 bytes × 24 rows: a single 4K panel (8 rows) and two 8K playfields (16 rows), 20K in all. The CPC uses
  24K for the same picture (`plan.md`, Display).

### D4. A multi-load if it doesn't all fit, decided once the sizes are known (2026-10-31)
Rich: "happy to make this a multi-load if it doesn't fit in memory all at once". And: "but doing so means
needing to not touch certain memory locations used by the OS/DFS". Then: "We can revisit the multi-load
question later when we see roughly how everything can fit."
- On the estimates, speech and every stage in memory need 82-87K against about 75.7K; without the packed
  stages, 57-62K. P5 is how the OS's memory would be kept for the DFS.

### D5. Checkerboard dithering for the CPC's colours (2026-10-31)
Rich: "I'm also happy to make liberal use of checkerboard dithering to simulate the CPC palette".

### D6. Keep the sampled speech if possible (2026-10-31)
Rich: "I would definitely like to keep the sampled speech if possible."
- Five phrases: 16,230 bytes raw, 10,153 packed. How to play them while the rupture's IRQ runs is O1.

### D7. A dithered colour uses the pair closest in brightness (2026-10-31)
Rich: "where a colour can be represented as the average of multiple colour pairs, always choose the two that
are closest in brightness. e.g. for white (grey), choose magenta/green over black/white."
- Every CPC colour is exactly the average of two BBC colours. With brightness as Rec. 601 luma, this picks
  yellow/cyan for pastel green, yellow/magenta for pink, red/green for dark yellow and green/magenta for grey.
  The full table is in `plan.md`, Colours.

### D8. Bit 3 free for transparency; rendering is the bottleneck (2026-10-31)
Rich: "also remember that we only have 8 physical colours which means bit 3 is unused and can be used to
indicate transparency (for example). I'm sure you will come up with an optimal format and routine for
rendering, which will almost certainly be the bottleneck."
- Logical 8-15 copy 0-7. A sprite pixel with bit 3 set is transparent. Plotting `(screen AND mask) OR sprite`
  leaves bit 3 on screen there, which shows nothing. Black is plain 0, and opaque.

### D9. Routines run from their bank, with their data (2026-10-31)
Rich: "There will not be a lot of main ram, so we will be relying mostly on routines running from their
sideways ram bank along with the data they have to access."

### D10. First milestone: stage 1 working (2026-10-31)
Rich: "The first milestone should just be getting the first level working, and we can revisit this
afterwards."

### D11. Sprites stored for fast plotting; unroll the hot loops (2026-10-31)
Rich: "store the sprites in any format which lend themselves to quick plotting on the BBC. If it is worth
interleaving them because of the 8 byte step, do that. Feel free to spend more on unrolling in the sprite
routines (hot loop)"

### D12. The sky drawn only where it isn't already (2026-10-31)
Rich: "yeah add the sky skip".
- Each playfield keeps how many top lines hold sky already (`SkyTop`). The sprites, the damage meter, the
  turbo icons and the pages lower it to the top of what they draw, and `road_draw` draws sky only below it.

### D13. The rupture's IRQ swaps the buffers; the loop waits only before it draws (2026-10-31)
Rich: "is it using the spritescale method of swapping buffers and base address in the irq routine itself (my
preferred method)?", then "maybe portalc does it like that", and "portalc does busy wait but not until it's
exhausted the next frame's work that it can do without touching the screen ... i.e. the cell capture". And:
"ideally the vertical rupture irq doesn't use vsync at all, other than to establish the timing at the
beginning. It should split at three points: top of the status (to reprogram the CRTC), top of the playfield
(to reprogram it again), and then bottom-ish of the playfield (the point at which it's safe to start
rendering again to the currently displayed buffer). I like an irq handler which selects its states in the
state machine by self-modifying the branch, as per exhale."
- The IRQ already worked that way (T1 only after one vsync sync; three handlers chosen by a patched `BVS`).
  Now it also flips `back`: at the playfield's end if a request is waiting, or at the panel's top if the
  request came after that. `show` only makes the request; `wait_back` comes just before `road_draw`, after
  the next loop's logic.

### D14. Beat the CPC's frame rate (2026-10-31)
Rich: "i would love to find a way of improving on the CPC frame rate somehow", "not that the CPC frame rate
isn't totally acceptable, but i feel like the bbc micro can do it better".

---

## Proposed

### P1. The screen map and the rupture's numbers
Panel `&3000`, playfields `&4000` and `&6000`. Cycles of 8 and 31 rows, T1 reloads `&0FFE` and `&3DFE`,
R1 = 64, R2 = 90, R7 = 23 in the playfield's cycle. Details in `plan.md`.

### P2. Four banks (64K) of sideways RAM as the minimum
What a Master 128 has built in. Whether that holds everything with the speech, or needs a multi-load, is
settled at milestone 1 (D4, D10).

### P3. Graphics converted at build time, dither baked in
Revised 2026-10-31 after Rich asked why the dither would be applied at run time ("P3 sounds expensive"). The
first version mapped the CPC's bytes through two 256-byte tables at plot time. That costs a lookup in every
opaque copy and a switch of table every line, and buys nothing, since the asset pipeline rearranges every
sprite anyway.
- The two MODE layouts match: BBC logical colour = CPC pen with bits 0 and 3 swapped. The pipeline maps each
  pixel to its BBC colour, or to its checkerboard pair (D7) by position in the sprite, and marks transparent
  pixels with bit 3 (D8). The layout is whatever plots fastest (D11).
- The CPC's plotters copy bytes and mirror them through a pixel-swap table; neither samples pixels
  (`&28BC`, `&2A19`). Run-time dithering is only for anything Phase 1 finds scaled by sampling.

### P4. The original as the model
A CPC reference harness on SkoolKit's C simulator. The BBC's game logic is checked against it in lockstep,
frame by frame. The harness also logs every plot, as the benchmark for the BBC's renderers.

### P5. If it comes to a multi-load: swap the OS's memory back in, rather than reserve it
Deferred with D4. Reserving costs zero page `&A0`-`&FF` and 3.75K of main RAM (`&0200`-`&10FF`) for the whole
game. Swapping costs about 4K of saved state in a bank. The loader saves the OS's state just before the
takeover. Between stages the game's bytes go into the free playfields and the OS's come back; OSFILE loads
the stage; then everything swaps back. OSFILE is called from main RAM, and the saved ROM type table must not
list the game's banks.

### P6. The game's logic in main RAM for now (2026-10-31, Claude)
The code's bank filled up with the fork (19 bytes left). The logic (game loop, car, traffic, criminal, flow,
panel: about 4.1K) moved to main RAM after the sound, `&0FC0`-`&2000`, which freed 4.1K in the code's bank for
the road and its renderer. It needs no stubs: the logic reads main RAM's variables and the code's bank's
tables, and the code's bank is paged in everywhere outside the sprite stubs, which page it back. Against the
plan's "nearly everything runs from a bank": the alternative is a third bank for the logic (the plan's
"the logic" bank), at the cost of stubs for the road's calls into it (car_segment) and its reads of the road's
tables (the lane lines, the roadside bounds). Main RAM left: about 1.9K at `&2000`-`&27FF` and 2.7K at
`&0259`-`&0CFF` (the latter the DFS's if it comes to a multi-load, P5). Easy to undo: one block of INCLUDEs in
`chasehq.6502`.

### P7. Speech: a third bank, played from main RAM with the frame IRQ quiet (2026-10-31, Claude; for O1)
The phrases fill one bank (16,230 bytes), so they go in a third bank when there is one, and the game plays
silent when there isn't (BanksNeeded stays 2). `speak` runs in main RAM, the game stopped meanwhile as the
CPC's is: a timed loop writing tones 1 and 2's attenuations (period 1, a steady level to shape), about 209
cycles a sample. The rupture IRQs keep running, so the display holds; the frame IRQ skips its key scan, sirens
and sound while a phrase plays, since they share port A, which keeps the IRQs' jitter to a few dozen cycles a
frame. Against User VIA T1 at 9.7 kHz: an interrupt every 207 cycles would delay the rupture's CRTC writes.

### P8. The game over without the CPC's drive, for now (2026-10-31, Claude)
The CPC's game over (`&0445`) resets the stage onto a set record and lets the car follow the criminal at 250
with no input, behind a dissolve, then goes to the title. Until there's a title and the dissolve, the BBC's
leaves the world as it is (the car stopped), shows Nancy's verdict and the GAME OVER page, and starts a new
game when the verdict's closed. The continue offer, its countdown and the tenth bonuses after one are the
CPC's.

### P9. Where the text and the turbo icons live (2026-10-31, Claude)
The text's data (2,439 bytes: font, faces, scripts, pages) fills the &259-&CFF gap, read from both banks with
no stubs; its code (1.3K) is in the code bank. The sprite review's compiled turbo icons (415 bytes), meant for
that gap, go in the code bank instead. Left: the code bank about 570 bytes, main RAM about 250 before
GameVars, the gap 288, the data bank about 300. The dissolve's masks (316 bytes) and the rest of the game's
flow will need room: the title and the stage intro may want an overlay or a bank of their own.


### P10. The rest of the frame-rate review: 01, 06 and 07 together; not the backdrop skip (2026-10-31, Claude)
The review (`work/review-frame/`, its patches exact by bench.py and check_road.py) found seven changes. The
four that are faster and smaller are merged. The other three are worth taking together:
- 01 `edge_table` (steep segments by patched constants, the sum in Y): road_frame 2,396 a loop mean, 3,944
  worst, +36 code-bank bytes.
- 06 the fork's lines (fork_e inlined, the span ends kept in the JSR operands): road_draw 1,200 mean, 7,293
  worst (the fork's loops are the slowest: 220K against 174K), +22.
- 07 Times22 and edge_target's tables made by the loader into CodeVars: -28 in the code bank, +28 of
  CodeVars (140 of 168 left), about 40 in the loader. With all seven, the text, turbo, popup and gen.6502
  code keep the addresses they had before the review, so no page checks move.
- Separately: with the four merged, the code before RoadT ends 5 bytes past &A800 (the pad is 251). Five
  bytes saved there would move RoadT down a page and put 256 at the bank's end instead.
- Together with the four merged: jsbeeb, 1,000 loops, 175,838 -> 170,746 cycles a loop mean, 99th percentile
  240,209 -> 224,511; code bank and main RAM as before, CodeVars 28 fewer.
- Not 08, the backdrop skip: 932-1,055 a loop for +125 bytes, its worst loop 331 slower, and after the
  sighting the damage meter would stop most of it.

---

## Open

### O1. How to play the speech
The CPC plays a phrase with everything else stopped. On the BBC the rupture's IRQ must keep running: play in
the main loop and accept the IRQ's jitter, or play from User VIA T1.

### O2. Previews of the colours
D7 fixes each pen's pair. Real frames rendered with it may still show pens worth changing by hand.

### O3. The frame-rate target
Set once the harness has measured the CPC's. Rich's aim is to beat it (D14); the CPC's own figure is still an
estimate (about 6 frames a loop, its wait states guessed at 1.2).

### O5. Room for the rest of the game
Now (after the continue, the popup and the text review): the code bank has about 600 bytes (571 at its end, 27
in the pad before RoadT), main RAM about 217 (256 more if GameVars moves up a page: it uses &2800-&2E98), the
&259 gap 279, the data bank about 290. Still to come: the player's effects (the bounce's burst and the roof
light going on after the sighting: 288 CPC bytes), tyre smoke (240), the criminal's smoke and flames (443),
the dissolve (316 + code), the stage intro and the title, and stages 2-5's data. Ways: a fourth bank (games +
speech: three needed, four with speech), per-stage data loaded between stages (D-something on a multi-load),
the title and intro as an overlay, or the review's offer to split tiled bands at the repeat (266 data-bank
bytes back for about 1.3K cycles a loop). For scale: the CPC itself loads a stage at a time, CHASEHQ.LV1-LV8
at 8K each (odd ones at &4000, even at &6000; LV6 the ending), so stage 1's own data here (its roadside
sprites, streams, briefing and pages) is what a per-stage load would swap.

Measured (2026-10-31): stage 1's own data in this build is about 10K. In the data bank: its roadside sprites
3,573, its cars and obstacles 2,350, and their part lists and table entries about 1,550. In the code bank: its
streams 1,234, backdrop 528, colour tables (fills, rumbles, lanes: from the stage's pens) 480 and collision
bounds 227. One more way: the player's car is stored twice, plain and mirrored (3,689 bytes each). Mirroring
it as it's drawn would give 3,689 back, for a mirrored path through the plotter and a 64-byte swap table for
its opaque bytes (masked bytes already go through tables), about 300 bytes, and 6 cycles an opaque byte (TAX,
LDA swap,X) while steering left, about 2K a loop (estimates, not measured).

### O4. Keys, and whether to read a joystick
The ADC is off for the rupture's timing, as in Teddy Boy.
