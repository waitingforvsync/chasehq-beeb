# Chase H.Q. for the BBC Micro: plan

A port of the Amstrad CPC disc version (`docs/chasehq.dsk`) to the BBC Micro: MODE 2, sideways RAM, written
in Baron. Everything under "The CPC version" was measured from the disc image on 2026-10-31 with the scripts
in `tools/` (SkoolKit 10.1 for the Z80 disassembly, Baron's ZX02 transform for the packed sizes). The memory
budget's code sizes are estimates until Phase 2 measures them.

## Verdict

**Feasible on a BBC B with 64K of sideways RAM (four banks), and on a Master 128 with its built-in 64K, with no
shadow RAM.** Rich's rupture (D3) is what makes the screens fit. Drawing speed is the main risk.

- The CPC already runs a 6845 screen of 64 bytes × 24 rows, 12K a buffer: a 64-line dashboard over a 128-line
  playfield, double-buffered whole. With the rupture, the BBC shows the panel from one 4K buffer and
  double-buffers only the playfield, 8K each. That's 20K of screen, `&3000`-`&7FFF`, instead of 24K.
- That leaves about 11.7K of main RAM (`&0120`-`&2FFF`) and 64K of banks: about 75.7K in all. With the
  speech (D6), the estimate below needs 57-62K with the stages loaded one at a time, and 82-87K with all of
  them in memory. A multi-load (D4) is the fallback, decided at milestone 1 when the sizes are real (D10).
- The CPC's MODE 0 bytes have the BBC MODE 2 layout. Converting the graphics, with the checkerboard dithering
  (D5) baked in, is a per-pixel colour map at build time: the same size, nothing redrawn (see Colours).
- Speed: the Z80 at an effective 3.3 MHz against the 6502 at 2 MHz, with a screen layout that steps 8 bytes
  across a line, not 1. Drawing will set the frame rate (D8). The CPC's frame rate and a log of everything it
  draws are measured first (Phase 1). The BBC's renderers are timed over the same frames before the game is
  built on them (Phase 2).

## The CPC version

### The disc
| File | Loads at | Bytes | What it is |
|---|---|---|---|
| `CHASEHQ.BIN` | `&9000` | 132 | Loader: MODE 1, inks 0/25/11/6, loads BI1-BI4 by CAS IN, `JP &A6B6` |
| `CHASEHQ.BI1` | `&C000` | 16,384 | Loading screen, MODE 1, 320 × 200 |
| `CHASEHQ.BI2` | `&0300` | 34,304 | The game, `&0300`-`&88FF` |
| `CHASEHQ.BI3` | `&0C5B` | 254 | Disc-version patch over BI2: loads the LV files with the firmware, not by track |
| `CHASEHQ.BI4` | `&A610` | 688 | Start-up at `&A6B6`; the rest is the original track loader, unused here |
| `CHASEHQ.LV1`-`LV5` | 8K each | 40,960 | The five stages |
| `CHASEHQ.LV6` | | 8,192 | A code module, called at `&59AB` when the stage number reaches 6 (probably the ending) |
| `CHASEHQ.LV7`, `LV8` | | 16,384 | Speech: five phrases, 16,230 bytes of 4-bit samples (table at `&0B5D`, 4 bytes a phrase, from phrase 1) |

### Start-up
- `&A6B6` copies 63 bytes to `&0100` and runs them: wipes the loader, pages the ROMs out (`&7F8D`), moves
  `&59AF`-`&8670` up to `&8000`-`&ACC0`, copies `&8680`-`&8851` to `&BA00`, blacks all 16 inks, `JP &BA00`.
- `&BA00` probes for 128K (bank `&C4`) and sets `&1646`. With 128K it loads LV1+LV2 into bank 5, LV3+LV4
  into bank 6, LV5+LV6 into bank 7 and LV7+LV8 into bank 4. On both machines it loads LV1 at `&59AB`.
- It scatters 7,360 bytes from `&8000` into the 15 unused 512-byte gaps of the two screens (`&8E00`,
  `&9600` ... `&FE00`: every 2K block's last `&200`). It draws the panel from `&9CC0` into `&C000`, builds a
  pixel-swap table at `&8600` and a pen-0 mask table at `&8700`, and copies the panel into the `&8000` screen.
- It sets the CRTC: R1 = 32 (64 bytes, 128 pixels), R2 = `&2A`, R6 = 24 rows, R7 = 30, start `&C000`. It
  selects MODE 0 (`&7F8C`) and the game palette, then calls `&0300`.

### Running
- **Interrupts are off.** The only `EI` in reach is in LV6. The main loop at `&0362` makes about 32 calls a
  frame.
- **`&0DCD` flips buffers**: it polls vsync (PPI port B bit 0), writes R12 (`&20` or `&30`), toggles `&1645`
  between `&80` and `&C0`, and patches the new high byte into 16 code addresses (table at `&0E1C`), plus 16
  two-byte patches (`&0E3C`).
- **Keys**: `&0F14` scans all ten keyboard rows through the PSG into `&0F4B`.
- **Sound**: the main loop writes the AY directly, once per game frame. There's no interrupt-driven player.
- **Speech**: `&0B76` plays a phrase from bank 4 with a busy loop, a nibble at a time into AY volume
  registers 8 and 9. 128K only.
- **Stages**: `&0BED` copies the stage's 8K from its bank into `&59AB`. It bounces through the back screen,
  since `&59AB` is inside the `&4000` window the banks page into. A 64K CPC loads each stage from disc.

### Sizes
| Block | Bytes | ZX02 |
|---|---|---|
| `&0300`-`&59AA`: code and data | 22,187 | 14,979 |
| of which Z80 code reached from `&0300` (a lower bound: 9 computed jumps aren't followed) | 12,889 | |
| `&59AB`-`&79AA`: the stage in play | 8,192 | |
| `&79AB`-`&7FFF` | 1,621 | 152 |
| The screens' gaps | 7,360 | 2,800 |
| Panel | 4,096 | 584 |
| LV1-LV5 | 40,960 | 21,675 (4,098 / 4,590 / 4,153 / 4,287 / 4,547) |
| LV6 | 8,192 | 3,279 |
| LV7 + LV8 (speech) | 16,384 | 10,153 |

The stages share almost nothing: 20 identical non-zero 64-byte chunks (1,280 bytes) across LV1-LV6.

## Display on the BBC (D3)

- MODE 2 timing (ULA `&F4`, R0 = 127, R3 = `&28`, R9 = 7), with the CPC's width: **R1 = 64, R2 = 90**
  (exhale's `98 - (80 - 64) / 2`). A character row is 512 bytes.
- Two CRTC cycles a frame, 39 rows of 8 lines:

  | Cycle | Rows | R4 | R6 | R7 | Start | T1 reload |
  |---|---|---|---|---|---|---|
  | Panel | 8 | 7 | 8 | none | `&3000` | 8 × 512 - 2 = `&0FFE` |
  | Playfield and blanking | 31 | 30 | 16 | 23 | the front buffer | 31 × 512 - 2 = `&3DFE` |

  The vsync falls at frame row 31 (`35 - (32 - 24) / 2`). Both reloads end `&FE`, so each handler writes
  only `&FE47`. The panel's handler sets R12/R13 to the front playfield; the playfield's handler sets them
  back to the panel. The main loop asks for a swap and the panel's handler does it (Portal's
  `request_swap`), so there's no tearing.
- **Map**: panel `&3000`-`&3FFF`, playfield A `&4000`-`&5FFF`, playfield B `&6000`-`&7FFF`. Nothing crosses
  `&8000`, so the hardware wrap never matters. A flip is `EOR #&20` on the self-modified high bytes, as the
  CPC's is `XOR &40`.
- The panel is drawn once, not into both buffers as the CPC does. Its updates (score, time, speed, gear,
  distance, the sirens) go straight to `&3000`.
- The cycle boundary is a palette split for free: the panel and the playfield each get their own 8 physical
  colours. More splits inside the playfield, such as at the horizon, can come later.
- The screen is in main RAM, so a plotter in a bank writes it directly, whatever is paged in.

## Memory budget (BBC B, the OS taken over)

There's little main RAM, so nearly everything runs from a bank, next to the data it reads (D9; Teddy's rule).
Main RAM keeps the IRQ, the few routines that must see two banks, and their variables.

| Range | Use |
|---|---|
| `&0000`-`&00FF` | The banks' numbers, then `ZA_POOL`; `&FC` the MOS's |
| `&0100`-`&011F` | Stack (32 bytes) with a sentinel |
| `&0120`-`&2FFF` | The rupture IRQ, keys and sound (IRQ1V at `&204`, `&258` = 2, `RTI` at `&D00`); what must see two banks; variables |
| `&3000`-`&7FFF` | Panel, playfield A, playfield B |
| `&8000`-`&BFFF` × 4 | Each bank: routines with the data they read. Sprites and their plotters; the road and its renderer; the logic; the stage in play; the speech and its player |

| Need | Bytes | Basis |
|---|---|---|
| 6502 code | 21,000-25,000 | An estimate: about 14,000 bytes of Z80 × 1.5-1.8. Phase 2 measures it. Unrolled plotters come on top (D11) |
| Common data | 16,700 | The non-code part of `&0300`-`&59AA`, plus the gaps' data |
| Tables made by the loader | about 1,500 | Mask tables, row addresses |
| The stage in play | 8,192 | One LV block unpacked, as the CPC's `&59AB` |
| Speech (D6) | 10,153 packed, 16,230 raw | Measured |
| LV1-LV6 packed, if all are kept in memory | 24,954 | Measured |
| **All of it** | **82,500-86,500** | Against about 75,700: 7-11K over |
| **Without the packed stages** | **57,500-61,500** | 14-18K spare |

The panel's 584 packed bytes ride in the file and unpack straight into `&3000`. LV6 unpacks into the stage
area when it runs, as on the CPC.

On these estimates, speech and every stage won't both fit in four banks. Rich is happy to multi-load (D4), but
that waits until the real sizes are known (D10). Ways to close the gap first:
1. Pack the parts that run only between stages (title, high scores, game over), and unpack them into the stage
   area or the playfields when they're needed.
2. A stronger packer: Exomizer's gain over ZX02 here is unmeasured.
3. Speech at a lower sample rate, or played straight from its packed stream.

If it comes to a multi-load, the OS and DFS need their memory back for the load. Reserving it costs zero page
`&A0`-`&FF` and `&0200`-`&10FF` of main RAM for the whole game. Swapping it out to the free playfields between
stages costs about 4K of saved state in a bank (P5).

## Rendering: the bottleneck

Drawing will set the frame rate, so the format and the routines are chosen by measurement (D8).
- **The workload comes from the CPC.** The harness logs every plot per frame: which sprite, its size, its
  place, mirrored or not, plus the road's spans. That's a fixed benchmark, and each candidate format is timed
  over the same frames.
- **What the CPC does**: `&28BC` plots bytes popped two at a time, with each one's mask looked up by the sprite
  byte (`&8700`). It's unrolled 16 bytes wide and entered by `JP (IX)`. The mirrored version (`&2A19`) swaps
  each byte's pixels through `&8600` first. Sizes are pre-drawn, and sprites move in whole bytes.
- **Sprites are stored in whatever layout plots fastest** (D11), interleaved for the 8-byte step if that
  pays, with memory spent on unrolling the hot loops.
- **Bit 3 marks transparency** (D8). There are 8 physical colours, so logical 8-15 copy 0-7, and bit 3 of a
  pixel never shows. A sprite pixel with bit 3 set is transparent. `(screen AND mask) OR sprite` leaves bit 3
  on screen in the transparent pixels, which shows nothing. Black is plain 0, and opaque.
- Candidates to measure:
  - Bytes classified at build time into wholly transparent (skipped), wholly opaque (stored, no read) and mixed
    (masked through a 256-byte table indexed by the sprite byte). Only the mixed bytes pay for the mask.
  - Interleaved to match the screen: a character cell's 8 lines are consecutive bytes, so one column of a
    sprite is 8 consecutive stores. Across a line it's 8 bytes a step, against 1 on the CPC. Columns,
    cell-sized blocks and per-line rows are timed against each other, unrolled.
  - Compiled sprites for what's drawn every frame. The player's car is always on screen at the same size.
  - Pre-mirrored frames against mirroring through the pixel-swap table, traded against memory.
- **The road**: per-line spans, 64 bytes a line at 8 bytes a step. Whether the road redraws the whole
  playfield every frame, so that nothing needs erasing, is a Phase 1 question.

## Colours

- CPC MODE 0 and BBC MODE 2 both put the left pixel in bits 7, 5, 3, 1 and the right in 6, 4, 2, 0. Only the
  colour bits' order differs: BBC logical colour = CPC pen with bits 0 and 3 swapped.
- The game palette has 15 distinct colours; the BBC has 8. Each CPC channel is 0, ½ or 1, so **every CPC
  colour is exactly the average of two BBC colours**. A ½ channel comes from one of the pair having it and the
  other not.
- Where several pairs average to the same colour, take the two closest in brightness (D7). Brightness here is
  Rec. 601 luma (0.299 R + 0.587 G + 0.114 B):

  | CPC pens | Colour | BBC | Luma apart | Pairs passed over |
  |---|---|---|---|---|
  | 0, 1 | black | black | | |
  | 2 | bright white | white | | |
  | 3 | pastel green | yellow / cyan | 0.18 | green / white 0.41 |
  | 4 | blue | black / blue | 0.11 | |
  | 5 | bright blue | blue | | |
  | 6 | orange | red / yellow | 0.59 | |
  | 7 | bright yellow | yellow | | |
  | 8 | green | black / green | 0.59 | |
  | 9 | lime | green / yellow | 0.30 | |
  | 10 | mauve | blue / magenta | 0.30 | |
  | 11 | pink | yellow / magenta | 0.47 | red / white 0.70 |
  | 12 | bright cyan | cyan | | |
  | 13 | yellow (dark) | red / green | 0.29 | black / yellow 0.89 |
  | 14 | red (dark) | black / red | 0.30 | |
  | 15 | white (grey) | green / magenta | 0.17 | red / cyan 0.40, blue / yellow 0.77, black / white 1.00 |

- The dither is baked into the graphics at build time (P3), by the pipeline that also arranges them for the
  plotter. The pattern is fixed to the sprite, so it moves with it rather than crawling through it. A mirrored
  checkerboard of whole bytes is still a checkerboard, in the other phase.
- Flat fills (road, verges, sky): two fill bytes for each colour, alternating by line.
- The panel's cycle can have its own palette.
- The loading screen is CPC MODE 1. Its pixels match BBC MODE 1 with pens 1 and 2 swapped. It needs re-laying
  into the BBC's character cells, and fits 25 rows. Its colours (black, pastel yellow, sky blue, bright red)
  have only four logical colours to go to in MODE 1, or it could be shown in MODE 2 and dithered like the rest.

## Sound, speech and keys

- The IRQ owns port A and the addressable latch (keys and sound). The main loop posts sound requests to a
  queue, and the 50 Hz IRQ writes the SN76489.
- The AY's effects need re-voicing: the AY has envelopes and mixes noise with tone, and the SN76489 does
  neither. The engine is the classic case for periodic noise clocked by tone 2.
- **Speech stays if it can** (D6). The samples are levels for the AY's logarithmic volume; a table maps them to
  the SN76489's 2 dB steps. The CPC plays a phrase with everything else stopped. On the BBC the rupture's IRQ
  must keep running, so either play in the main loop and accept the IRQ's jitter, or play from User VIA T1
  (O1).
- Keys: read by the IRQ (Teddy's border IRQ is the model). The key layout is O4.

## How the port gets checked

- **A CPC reference harness**: SkoolKit's C simulator with a minimal CPC around it. That's the gate array
  (inks, mode, banks `&C0`-`&C7`), the CRTC's R12/R13, the PPI (vsync, keyboard rows) and a log of AY writes.
  Since the game polls with interrupts off, this is enough to run it. It starts from the image after BI4, with
  the LV files put where BI3 would load them.
- From it, per frame (each call to `&0DCD`): a PNG of the screen, the game's variables, the plots (for the
  rendering benchmark), the AY writes, and the cycles taken. That gives the CPC's frame rate, which is the bar
  for the BBC.
- **Lockstep**: the same scripted keys into the harness and into the BBC build. Compare the game's state at
  each frame: positions, speed, score, time, place on the road. The Z80 original is the model, as Portal's C
  model was. Logic can run in py65; anything timed runs in headless jsbeeb with the real IRQ.
- Random numbers: if the game reads `R` (`LD A,R`) or anything cycle-dependent, lockstep needs a shim there.
  Find out in Phase 1.

## Phases

The first milestone is stage 1 working (D10). Everything is aimed at that; the rest is reviewed afterwards.

### Phase 0: housekeeping
- `git init`, with `build/` ignored. Lay out `src/` as Teddy Boy's: `boot.6502`, `chasehq.6502`,
  `constants.6502`, `memory.6502`, `macros.6502`, `entry.6502`, `irq.6502`.
- A Makefile: Baron to `build/chasehq.ssd` with a `-v` listing and symbols.
- A Python venv with SkoolKit, Pillow and py65.

### Phase 1: understand the original
- A SkoolKit control file (`cpc/chasehq.ctl`) covering BI2, the gaps' data, LV1 and the start-up; LV2-LV6
  later. Every routine named and described, every data block typed. Follow the 9 computed jumps and the
  `PUSH DE : RET` script at `&BA25`.
- The reference harness: stage 1's frame rate, and the plot log.
- Write `docs/cpc.md`: the road model (segments, curves, hills), the traffic and the criminal's car, the
  ramming and damage, turbo, timer, scoring, and the formats of the stage data and the sprite sets.
- Find out what the 16 patched addresses at `&0E1C` draw: they're the CPC's screen-touching routines, and the
  first list of what the BBC rewrites.

### Phase 2: rendering
- `!BOOT` (find the banks, loading screen), the loader, the rupture at 8 + 31 rows with the panel's palette
  and the playfield's.
- The asset pipeline for stage 1's graphics: dither (D7), bit 3 for transparency, the formats under test.
- The road renderer and the sprite plotters, timed over the CPC's logged frames.
- A first block of game logic translated, to measure its size against the Z80's and firm up the budget.
- **Check**: the logged frames drawn on the BBC at or above the CPC's frame rate, measured in jsbeeb.

### Phase 3: stage 1
- Translate the logic routine by routine, each one checked in lockstep with the harness.
- The panel, the sound effects, and the flow of a stage: start, chase, arrest, time out.
- **Milestone 1**: stage 1 playable from start to arrest, at the CPC's frame rate or better.

### After milestone 1 (to be reviewed then)
- Memory against the measured sizes: the other stages, and whether to multi-load (D4).
- Speech (D6), LV6, title and high scores.
- Optimisation reviews, measured as Teddy's were.
- Test on jsbeeb, b2, a Master 128 (`JMP (abs)` and `BIT` timings differ in the IRQ's latency count), and
  real hardware.

## Risks
| Risk | What decides it |
|---|---|
| Too slow: 8 bytes a step across a line on the BBC, against 1 on the CPC | Phase 2's timings over the CPC's logged frames |
| Code larger than 1.8 × the Z80 | Phase 2's first translated block |
| Speech and every stage don't fit together | Sizes measured at milestone 1; then D4 |
