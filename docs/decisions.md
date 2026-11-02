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

### D15. The rest of the frame-rate review: 01, 06 and 07; not the backdrop skip (2026-11-01)
Rich: "go ahead and merge P10" (P10: 01, 06 and 07 together; not 08, the backdrop skip).
- 01 `edge_table`'s steep segments by patched constants, 06 the fork's lines, 07 Times22 and edge_target's
  tables made by the loader into CodeVars. Exact: bench.py IDENTICAL in all seven runs, check_road.py 0 of
  600 differ on both branches.
- jsbeeb with the real IRQ: 300 loops 187,324 -> 183,867 cycles a loop mean (4.691 -> 4.604 frames); 1,000
  loops 173,109 -> 170,746, 90th percentile 195,928 -> 193,319, 99th 233,177 -> 224,511.
- Code bank 566 -> 536 free (all 30 from the pad before RoadT: the code before it now ends 35 bytes past
  &A800; the bank's end unchanged), CodeVars 168 -> 140, main RAM and the data bank unchanged.

### D16. The tunnel review's p5 and p7 too (2026-11-02; was P11)
Rich: "yes do p5 and p7".
- p5: the mouth's line parity toggled with `TYA:EOR #1:TAY`. +3 code bank bytes, -173 cycles a tunnel loop.
- p7: road_draw doesn't draw what the mouth will cover (the sky, and the road under the band across). +42
  code bank bytes; entrance loops -9,924, exit -7,825, inside +10, every other loop +17.
- With the rest of the review: worst loop of road_draw + plot_objects 129,720 -> 125,209 (py65). Code bank 50
  -> 5 free in front of its data (10 more before RoadT). compare_tunnel.py: the same 25 of 241 tunnel loops
  differ as before; check_road.py 0 of 960.

### D17. 64K of sideways RAM, no multi-load: the speech and every stage kept packed (2026-11-02; for D4)
Rich asked: "If we were to move to a full 64k of sideways ram, could we do without the multiload?" Offered
the measurements below and the options (64K with no multi-load; a multi-load from disc as P5; deciding after
measuring LV6), he chose "64K, no multi-load".
- The speech packs 16,230 -> 3,924 bytes, each phrase on its own with the build's ZX02 (84% of its samples
  are silent). A phrase unpacks into the hidden playfield before it plays: 125,723 / 250,893 / 127,617 /
  137,551 / 127,873 cycles for phrases 1-5 (63-125 ms; py65, the game's decoder, checked byte for byte).
  The game is stopped while it speaks anyway.
- Each stage's own data, packed by bank (code, data, main RAM): 4,656 / 4,793 / 4,150 / 4,399 / 5,090 =
  23,088. A stage unpacks over its slots at its start, about 0.23 s.
- In banks 3 and 4 together: 27,012 of 32,768, so 5,756 left for the helicopter's images, the gantry, LV6
  and the title (not measured yet). If LV6 or the title don't fit, they load from disc between games.
- Supersedes D4's multi-load; P5 and P7 (the speech bank) no longer apply.

### D18. Main RAM is ours down to the stack, small routines in its low gaps (2026-11-02)
Rich: "Note that with no multi-load, we are now free to use main RAM all the way down to the top of a reduced
stack (minus &204,&205,&258,&D00)". And: "I recommend trying to fit small routines into those low areas of
main ram, between the bytes that can't move".
- The stack is &101-&120 (its sentinel at &100) and main RAM's code starts at &121. The gaps between the fixed
  bytes now: 19 at &1F1 (before IRQ1V), 82 at &206-&257 (MainVars, declared but never used) and 27 at &CE5
  (the end of the &259 gap, the speech player having moved in).
- New small routines go into the gaps first; cold routines move in when a gap would otherwise stay empty.
- Rich: "Remember to reduce the stack to whatever size is safe. I would think 64 bytes is more than enough.
  i.e. starting the code at &140". The stack is already 32 bytes (&101-&120, code from &121). Measured
  (jsbeeb, real IRQ, 1,000 loops of the demo rule, the free part filled with &A5 at the loop's top): the
  deepest byte used &10C, 21 of the 32; the sentinel untouched. A re-entrant rupture and a speech IRQ (O1)
  would add a few bytes a level.

### D19. Room for the stage slots: the text code to the store, data-bank code to main RAM (2026-11-02; P12)
Asked where the code bank's and the data bank's shortfalls should come from (the slots sized for the largest
stage need about +250, +320 and +470 bytes in the code bank, data bank and main RAM), Rich chose, for the code
bank: "Do 1 (Text code to the store) but also consider whether glyphs can be bit depth reduced or otherwise
compressed"; option 1 was the message and page code (about 1.3K, with the popup's clear) in the store's bank
behind main RAM stubs, about 20 cycles a call. For the data bank: "Data-bank code to main RAM" (code that runs
with the data bank paged, at the same speed there).
- Refined: only msg_update and page_draw (and what they call) read the text's data; msg_request,
  page_request and text_new_game touch main RAM alone and stay there. So two stubs; flow's page figures
  (PageContinueTime, PageBonus*) written with the store paged; the stage's own text in a slot in the store's
  bank, not main RAM. The &259 gap's 2,448 bytes of text data (Font1 656, two faces 640, scripts and pages)
  go to the store with the code, leaving the store about 1.1K spare with the stages and speech.
- The glyphs (2026-11-02): Font1's lines mix white with one to three shading colours (254 of 328 glyph lines
  have two or more), so not 1 bit a pixel. It has 22 distinct bytes, the 6 rarest used 10 times in all:
  with those 10 bytes changed to near ones, a 4-bit code a byte would halve it (656 -> 328) for a table
  look-up a byte drawn. Each face has 14 distinct bytes: a 4-bit code halves it losslessly (320 -> 160), for
  a look-up a byte when a face is drawn (once a message). Rich: "we can note that maybe there's scope for
  glyph compression if we need it, for now let's continue with the next step".

### D20. The stage switch, in three steps (2026-11-02; was P12)
Offered the plan (each stage's data in fixed slots, every stage packed in the store's and stages' banks, stage 1
unpacked at a game's start like any other, the game moving on after the bonus), Rich: "let's go for it".
- As built: each bank's part of a stage is a list of pieces at fixed addresses (the road's tables where they
  were, so their page crossings stay; the sprites' a slot at the data bank's end; the text's a slot after the
  store's text), each stage's packed by part. stage_load (main RAM) unpacks a part into the hidden playfield
  and copies its pieces up. The stage's four constants are bytes in the code bank, read where they were
  immediates.

### D21. Mirrored sprites stay stored twice; the helicopter's mirrored frame stored too (2026-11-02; was P13)
Rich asked to measure a mirrored path in the plotter first: "If the Mirrored path is sufficiently fast, could it
be used to plot other mirrored sprites which are possibly currently handled by duplicaitng the sprite data
mirrored, and thus save some memory?" Measured (py65): exact (the car's 9 body frames, and 99 clipped
placements, the same bytes as its stored mirrored frames), at 30-38% more a sprite (6 cycles a byte): the car
+2,400-2,900 for its body and +1,400 for its wheels, 4,100 a loop while turned left. Rich: "it sounds as if in
the general case it's not worth dynamically mirroring at draw time, so we'll keep the mirrored sprite data. In
the case of the helicopter, since it's a one off, every other frame, maybe we can take it. Though if it costs
nearly as much in mirroring sprite code and possibly tables, maybe we should just add the extra mirrored
sprite frames." The path's code and tables come to about 660 bytes (its page 227, its set-up about 110, the
table 256 and its alignment, a stub), against 716 for the frame: the frame is stored.
- Rich then asked whether a palette switch could do the rotor ("common pixels in black, and pixels on one frame
  or the other in an unused colour"). Measured: the frames differ only in the blades (pens 1 and 15), but pen
  15 is a dithered pair, so about 10 switched colours (2 with its grey drawn black), and only over plain sky.
  Offered that or both frames stored, he chose "Store both frames": the sprite slot (8,450 bytes) then packs in
  two, its tables and its parts, each under a playfield.

### D22. Room for the gantry: the glyphs and faces as 4-bit codes, the sprite tables in main RAM (2026-11-02)
The gantry (stages 3 and 5: a left pylon, 8 sprites, 768 bytes with its part records, and a striped beam)
needs about 282 more bytes in the data bank (14 free) and about 800 more packed in the store's and stages'
banks (249 free). Offered sources, Rich chose "Glyph and face 4-bit codes, Sprite tables to main RAM": Font1
656 -> 328 bytes (its 10 rarest bytes changed to near ones) and the faces 640 -> 320 (lossless), a table
look-up a byte drawn; and the five per-sprite tables (150 entries each, 750 bytes) from the data bank into
main RAM, read at the same speed. Not chosen: measuring a stronger packer first.
- Measured (bench.py): the font's codes exact, but pages redraw every glyph every loop, so the bonus page went
  23,174 -> 51,960 cycles a loop (the continue 20K -> 49K, the arrest 16K -> 41K, the sighting 7K -> 18K while
  driving), a message's glyph 316 -> 752, for about 280 bytes. Offered instead a stage's road pack in the code
  bank's free bytes (stage_load unpacks from any bank), Rich: "Revert font, pack in code bank": the font plain
  again; the faces stay 4-bit (+2,800 cycles a face drawn).

### D23. The last resort for room: the sampled speech Master-only, in HAZEL (2026-11-02)
With all four banks in use (free: code 11 + 5, data 338, store 172, stages 796, unpacked), Rich: "A stronger
packer will barely win anything. My suggestion if we become desperate for space would be to make the sampled
speech Master-only, and move the samples and player code into HAZEL (&C000..&DFFF). Do this as a last resort
though."
- What it would give back: the five phrases' packs, 3,924 bytes of the store bank (&8EDF-&9E32; 16,230 raw),
  and the player's code from main RAM. Packed, they fit HAZEL's 8K with room for the player; they unpack into
  the hidden playfield as now.

### D24. The gantry's beam from main RAM, runner_row patched only for its columns (review P2) (2026-11-02)
Offered the review's P2 (gantry_beam its own routine in main RAM, paging the code bank itself; runner_row
entered at the beam's first column's patch, an RTS over its last's), as a trade: the beams 7,458 -> 6,280
cycles a loop in stage 3 and 3,938 -> 3,430 in stage 5; the code bank 12 -> 100 free, the main RAM gap 354 ->
237. Rich: "ok let's add p2". Not taken: P24 (the fills read from main RAM: 400 cycles more in stage 3 for 114
more bytes of the gap). The decoder, which P2 pushed across &0B00, moved to the gap's top, under &D00.

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
Superseded by D17 (no multi-load).
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
The bank superseded by D17 (the speech kept packed); the player as described.
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

---

## Open

### O1. How to play the speech
The CPC plays a phrase with everything else stopped. On the BBC the rupture's IRQ must keep running: play in
the main loop and accept the IRQ's jitter, or play from User VIA T1.
- Now (P7's player): the main loop's timed loop, 414 cycles a byte (two samples) in jsbeeb. The rupture's
  IRQs delay 19 of 400 bytes by 72-87 cycles (2026-11-02, `work/store/bytetime.mjs`).
- Rich (2026-11-02): "we will have to try how best to do the speech player, as we can't turn off IRQs (we need
  them for the rupture). Maybe it needs to be a top priority interrupt (first one serviced) from User VIA T1.
  We might also need to make the rupture reentrant, turning on IRQs by wrapping the reentrant part with LDA
  &FC:PHA:CLI.... SEI:PLA:STA &FC... we should keep the keyboard autoscan on so it doesn't conflict with the
  sound chip, other than during the IRQ routine which reads the keys, in which we will need to turn IRQs off."
  And: "The advantage of servicing the sampled speech in interrupts is that we don't need to pause the game.
  But we will have to try things and see what works". And: "Possibly the samples can be done in the same way
  as Exile, using PWM (look at the disassembly). I think this uses variable timing between samples. It can
  also play on multiple channels at once for more volume. But it may be worse quality".
- Exile's player (github.com/tom-seddon/exile_disassembly, `exile.6502` from line 9969 and its IRQ at
  M129B): 1-bit samples as runs, a byte (silent n, on m) in nibbles, or with its low nibble 15 one silent
  run of 15-255; 0 ends it. A unit is 128 us (7,812 Hz). One User VIA T1 interrupt a run: it writes the next
  volume to tone 3 (period 1, a steady level), the on volume scaled by the object's distance, then reloads
  T1 with the next run (`delay << 7`) and decodes the next byte. The game runs on; tone 3 is booked for it.
  The IRQ tests the system VIA first, then T1; nothing is re-entrant.
- Our phrases that way (2026-11-02, at our 103.5 us unit): 4,614 bytes for all five (ZX02 of the 4-bit
  samples 3,924), about 2,300-2,900 interrupts a second. 52% of the loud samples are at full volume already;
  the rest, spread over nine levels, would all play at one. Keeping the levels, as runs of one level: about
  9,000 runs (2,400-2,900 a second), about 10,000 bytes at a byte a run.
- If the game runs on, the hidden playfield can't hold the phrase (D17's unpack): the IRQ would read it from
  the store's bank, or decode it as it goes. Measured (2026-11-02): 84% of the 32,460 samples are silent, in
  4,306 runs (the longest 546 samples). Loud samples as nibble pairs and a byte a silent run (one T1 period
  each) come to about 6,910 bytes for all five phrases (ZX02: 3,924); phrase 2 would take about 3,100
  interrupts over its 1.1 s, against 10,700 at one a sample.

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

Measured (2026-11-01, docs/cpc-stages.md): each stage's own data as the BBC stores it is 9,840 / 9,669 /
9,180 / 9,456 / 10,355 bytes (stages 1-5), 48,500 for all five; the shared part 11,095. So stages 2-5 need a
load each whatever the banks. A stage's slots, the most any stage needs: 2,349 in the code bank, 7,806 in the
data bank, 727 in main RAM (stage 1 uses 2,100, 7,486 and 254). Not counted yet: stages 2 and 4's helicopter
(716 bytes of images), the gantry's beam, the tunnel. Stage 1 itself has a tunnel the BBC doesn't draw yet.

Packed (2026-11-01, `work/lv/packed.py`, the build's ZX02): each stage's own data 4,636 / 4,763 / 4,128 /
4,371 / 5,071 bytes. Rich asked whether a full 64K of sideways RAM (a fourth bank) would do without the
multi-load: kept packed there and unpacked over the stage's slots at each stage start, stages 2-5 take 18,333
and stage 1 must be kept too for the next game (22,969 in all), plus the helicopter and the gantry, against
16,384, with the code bank full. Not with the speech; without it (two spare banks, 32K), yes. Mirroring the
sprites as they're drawn saves 0-788 bytes a stage before packing: not the difference.

### O4. Keys, and whether to read a joystick
The ADC is off for the rupture's timing, as in Teddy Boy.
