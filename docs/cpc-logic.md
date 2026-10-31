# Chase H.Q. (CPC): the game logic

A spec of the CPC original's game logic, from its code (the image at `&0300`-`&79AA` after start-up), for
the BBC version to be written from. The road renderer and the sprite plotters are specced elsewhere; they
are only named here. Everything was checked in the harness (`tools/cpc.py`) with the scripts in
`work/logic/` unless marked *unverified*. Measured 2026-10-31.

## Summary
- **One loop** = one pass of the main loop at `&0362`, ending in the flip (`&0DCD`). Everything is timed in
  loops: no interrupts, no frame counter. In the harness a loop takes about 420K T (6.7 CPC frames with its
  1.2 stretch, about 7.5 loops a second). The clock counts 15 loops a "second".
- **The road** is a ring of segments (`&F700`-`&F7FF`, index `&1775`). The player's position is the
  segment index plus a fraction `&1774`. Speed `&177E` (0-511) is in 1/256 of a segment per loop. Objects
  are placed by depth in segments ahead (1-22) plus a fraction.
- **The car**: LO gear tops out at 230 (188 on the panel), HI at 360 (295), turbo 511 (419). Accelerate
  closes 1/16 of the gap to the gear's maximum each loop. Coasting loses 10 a loop and braking 20. Steering
  is a pair of velocities ramped by 4 to 36; curves push the car outwards. Off-road, roadside objects,
  barriers, traffic and the criminal all use one "bounce": speed shed by a quarter each loop, a sideways
  shove, and only the gear key working.
- **Traffic**: at most 3 cars (5 slots), spawned 21 segments ahead at random intervals in one of 4 lanes,
  each lane with a fixed speed. No AI: a car keeps its lane and speed, unless the road narrows. Overtaking
  scores a chain of 200, 400 ... 8,000. Hitting one removes it and breaks the chain.
- **The criminal** starts 869 segments ahead, crawling until seen. Once within 20 segments it is "sighted":
  the clock resets to 60 and the siren lights start. It weaves between lanes away from the player, sprints
  at random, and can't be passed. 20 rams and it's arrested; the computer pulls over, bonuses are added,
  next stage.
- **Time**: 60 s a stage, reset (not extended) to 60 at the sighting. At 0 the car coasts to a stop; two
  continues a game.
- **Random numbers**: a three-byte additive generator at `&37AD` (state `&37AA`, `&7B &2D &E9` at power-on).
  No `LD A,R`. The sound effects draw from it too (up to 200 calls an effect), which matters for lockstep.
- **Sound**: the AY is written from a shadow once a loop (engine tone, turbo whoosh). Every other effect is a
  blocking bit-banged loop on channel A's volume (up to 234K T, about 3 frames). Speech is blocking too.

## Conventions
- Addresses are CPC addresses. "Code immediate" means a variable held in an instruction's operand (the code
  modifies itself); its address is the operand's.
- x (`&17A0`) grows to the **left**: steering right lowers it.
- Effect requests are "effect n, priority p" (`&0938` with B = n, C = p; lower p wins).
- Messages are `&1DB4` with HL = a script and A = a priority (higher wins). Pages are `&139F` with HL = a page.
- "Speech n" is `&0B75` with A = n (128K only).

## Main loop
`&0300` sets up a game: title (`&068F`, returns when gear is pressed), speech 5, score `&1648`-`&164C` = 0,
`&1650` = 0, stage `&164D` = 1, continues `&1651` = 2, then `CALL &031E` and back to the title.

`&031E` starts a stage: silence (`&0ABE`), siren lights off (`&0F59`, A = 0), load the stage if it isn't
the one in memory (`&0C40`). If the stage is 6 it runs LV6 at `&59AB` (the ending), sets the stage to 1,
reloads LV1 and returns (to the title). Otherwise (`&0339`): the intro (`&04E5`), the reset (`&15B8` with the
stage record at `&5BF3`), the speech rotation `&164F` (3, 2, 1, 3 ...; 4 in the image, so phrase 3 comes
first) into `&179F` = `&164F` × 4 + 2, criminal active (`&16B8` = `&FF`), and on 64K the text in place of the
speech (`&1AF8`, priority `&FF`). Then the loop:

| Call | Name | What it does |
|---|---|---|
| `&0949` | sound | Requests effect 7 (priority 4) when passing roadside objects (`&1771` or `&1772` ≠ 0) outside a tunnel (`&1770` = 0); updates the engine tone or turbo whoosh in the shadow (`&0B2D`/`&0AE9`); writes AY registers 11 down to 0 from `&174E`-`&1743` (`&0AC3`); plays the pending effect, if any, as a blocking loop. |
| `&0E98` | read controls | Scans the keyboard (`&0F14`) and builds `&0E89` (see Controls). |
| `&1FF0` | clock | Counts down the time; time-up, the continue offer and its countdown (`&175E` states). |
| `&155D` | apply controls | Masks `&0E89` with `&1691`; ESC quits, P pauses (blocking), SPACE starts a turbo. |
| `&4219` | advance | Moves the player along the road by speed: `&1774` += speed, 0-2 segment steps (`&1788`). Each step: the next segment's data into the ring 31 ahead (`&423D`), the car's per-segment update (`&3EAD`: pitch, jump, curve, drift lump), objects' depth − 1 (`&4480`). Then the extra collision pass (`&3478`). |
| `&0F8E` | stage end | The arrest sequence, states 1-6 of `&1765`: computer pull-over, the arrest page, bonuses, next stage. |
| `&37DE` | car control | Jump timer, turbo and screech timers, gear, speed, slope, steering, centrifugal drift, x. |
| `&304A` | traffic spawner | Counts segments; spawns a car at depth 21 when the count runs out (3 RNG calls). |
| `&2C7F` | counters | `&1769` = loop mod 4, `&176A` toggles, `&176B` = mod 4 every second loop (animation phases). |
| `&5260` | hill profile | Road: accumulates the hill stream into per-depth heights at `&8E01` (road agent). |
| `&3E23` | background scroll | Scrolls the backdrop (`&4CC4`, 0-21) by the curve, every `&1792` loops. Scenery only. |
| `&3FCF` | road geometry | Road: the road's edges per screen line (`&7Axx`-`&7Exx`; the car's line at `&7CFC`/`&7CFE`), and the fork: detection and which branch the player took. |
| `&4895` | road and scenery | Road: draws the road and backdrop colours from the stage's `&5BBB` (37% of the loop). |
| `&2BEA` | depth table | Road: per-depth screen lines (prefix sums at `&8E4C`) used to project objects. |
| `&44E1` | tunnel | Tunnel state: `&1770` = 0 or 5, patches the object drawer (`&23A9`/`&23CB`). |
| `&3305` | roadside obstacles | Spawns obstacles (cones, barrels) from road stream 5 at depth 20 − `&1788`. |
| `&329E` | fork message | The "AIRBORNE PATROL ... TURNED LEFT/RIGHT" message and its display state (`&1759`). |
| `&350B` | objects | For each of the 6 object slots: move by its velocity, despawn, project to the screen, collision test, insert into the draw list, run its handler (traffic, criminal, obstacle). |
| `&3231` | fork display | Fork-related drawing state (`&1759`; patches `&23C8`). |
| `&2C94` | off-road and roadside | Off-road level `&1773`, wall scrape and barriers, roadside object hits, the fork divider. |
| `&238C` | draw world | Sprites: road and objects back to front from the draw list at `&7B00` (sprite agent). |
| `&3A8D` | bounce and draw car | Runs a bounce, clamps x to `&48`-`&1D8`, requests the skid sound, draws the player's car, smoke, sparks. |
| `&20DE` | distance score | Adds 0-45 points a loop from the speed (see Score). |
| `&216B` | panel | Turbo icons, stage number, bonus popup, gear, speed, time, DIST, score. |
| `&2148` | overtake bonus | Turns each car overtaken (`&1760`) into the chain bonus. |
| `&1DD4` | message window | Runs the message window: static, face, text one character a loop. |
| `&14EE` | damage meter | Draws the criminal's damage bar once sighted. |
| `&12CF` | page or dissolve | Prints a text page (`&1766` = 1) or runs a dissolve (`&1766` = 2). |
| `&0DCD` | flip | Waits for vsync, swaps buffers, patches buffer addresses. |
| `&4144` | fork commit | When a fork has been passed (`&179C`), rewrites the road streams for the branch taken (`&177D`). |

After the flip (`&03BC`): the test-mode keys (if `&1647` ≠ 0). Then if `&1766` ≠ 0 (page or dissolve), back to
`&0362`. Otherwise `&179F` is shifted right; when a 1 drops out, speech `&179F` plays and `&179F` = 0 (so the
stage's phrase plays on the second loop). Then `&179E`: 1 → 2 and a dissolve (`&1337`, `&10`); 2 → the game
over sequence `&0445`.

Order that matters: keys → mask → advance (and its collisions) → car control → ... → road geometry →
off-road → bounce. So off-road and roadside results act on the next loop's speed; traffic hits act this loop.

### Other loops
| Loop | Where | Calls |
|---|---|---|
| Title and attract demo | `&069F` | `&08DC` (the demo's autopilot into `&0E89`, then `&4219 &304A &2C7F &5260 &3E23 &3FCF &4895 &2BEA &3305 &44E1 &350B &37DE &2C94 &238C &3A8D`), `&0E98`, title text or redefine, `&12CF`, flip |
| Stage intro ("monitoring system") | `&04FE` | `&05E9` frame, `&1DD4`, `&053A` bars, `&05A0` car reveal, `&12CF`, flip |
| Game over | `&0470` | `&4219 &5260 &3E23 &3FCF &4895 &2BEA &44E1 &3305 &350B &238C &216B &1DD4 &12CF`, flip |

### Cost per routine
Harness, 200 loops of driving, plain Z80 T-states. Mean 420K T a loop. Heavy: `&4895` 157K (37%), `&238C` 70K
(17%), `&3FCF` 57K (14%), `&3A8D` 37K (9%), `&0DCD` 33K (vsync wait), `&216B` 23.5K (6%: redraws the turbo
icons every loop), `&0949` 19K mean, 222K at worst (the blocking effects). The rest are under 6K each: the
game logic proper is a few thousand T a loop.

## Variables
Sizes in bytes. "Template" means set from `&1652`-`&168E` at each stage reset (`&15B8` copies it to
`&168F`-`&16CB`, zeroes `&16CC`-`&179F`, and copies 14 bytes of the stage record to `&17A0`-`&17AD`).

### Game
| Address | Size | Meaning |
|---|---|---|
| `&1644` | 1 | language: 0 English, 1 French (F1/F2 on the title) |
| `&1645` | 1 | back buffer high byte, `&80`/`&C0` |
| `&1646` | 1 | 128K flag |
| `&1647` | 1 | test mode 0/1 (the SHOCKED cheat) |
| `&1648`-`&164B` | 4 | score, 8 BCD digits, little-endian (`&1648` = units and tens) |
| `&164C` | 1 | continues used this game; ≠ 0 cuts the ram and clear bonuses by 10 |
| `&164D` | 1 | stage 1-5; 6 = the ending |
| `&164E` | 1 | stage loaded at `&59AB` |
| `&164F` | 1 | speech rotation 3, 2, 1 (4 in the image); never reset |
| `&1650` | 1 | overtake chain, BCD hundreds, 0-`&80`; reset only at game start and by hitting a car |
| `&1651` | 1 | continues left, 2 at game start |
| `&179E` | 1 | quit / game-over state 0-2 |
| `&179F` | 1 | speech trigger: phrase × 4 + 2, shifted right each loop |

### Controls
| Address | Size | Meaning |
|---|---|---|
| `&0E89` | 1 | controls this loop: bit 7 ESC, 6 pause, 5 turbo, 4 gear, 3 accelerate, 2 brake, 1 left, 0 right |
| `&0E8A` | 1 | pause/turbo/ESC raw (bits 2-0); never read |
| `&0E8B`-`&0E8F` | 5 | joystick key numbers |
| `&0E90`-`&0E97` | 8 | key numbers: gear, accelerate, brake, left, right, pause, turbo, ESC |
| `&0F4B`-`&0F54` | 10 | keyboard rows, bit clear = pressed |
| `&1691` | 1 | control mask (template `&FF`; `&93` time up; `&C0` arrest; 0 after quit) |
| `&0871` | 1 | code immediate: redefine index 1-7, 0 = off |
| `&086D`, `&086F` | 2 + 2 | redefine prompt pointers |

### The player's car
| Address | Size | Units, range | Meaning |
|---|---|---|---|
| `&177E` | 2 | 1/256 segment a loop, 0-511 | speed |
| `&1774` | 1 | 1/256 segment | position within the segment |
| `&1775` | 1 | 0-255 (`&1776` = `&F7`) | segment index into the ring |
| `&1788` | 1 | 0-2 | segments advanced this loop |
| `&1787` | 1 | 0 LO, 1 HI | gear |
| `&1786` | 1 | 0-3 | gear repeat timer (template 3) |
| `&1782` | 1 | loops, 60 → 0 | turbo running |
| `&1692` | 1 | 0-3 | turbos left (template 3) |
| `&1783` | 1 | loops, 3-4 | screech timer (gear into HI, jump landing, the stop) |
| `&1780` | 1 | 0-3 | slope step timer |
| `&1773` | 1 | 0-2 | off-road level |
| `&1690` | 1 | loops, 100 | "LET'S GET MOVIN' MAN!" countdown at low speed (template 100) |
| `&17A0` | 2 | `&48`-`&1D8` | x, larger = further left; start from the stage record (stage 1: 234) |
| `&1797`, `&1798` | 1 + 1 | 0-36 | right and left steering velocities |
| `&1790` | 1 | signed, even, ±2 to ±8 | curve under the car |
| `&1791` | 1 | | 4 × \|curve\| |
| `&1792` | 1 | loops | backdrop scroll timer |
| `&1793` | 2 | signed | the drift lump for the next loop |
| `&1795` | 1 | | drift reference fraction |
| `&1796` | 1 | | drift ticks this segment |
| `&178C` | 1 | signed | hill two segments ahead, halved |
| `&178D` | 1 | signed | hill of the current segment |
| `&1781` | 1 | 0/1 | skidding |
| `&1784` | 1 | 0-2 | turn level (sprite) |
| `&1785` | 1 | 0/1 | turn direction, 1 = left or straight |
| `&3D31` | 1 | 0, 3, 6 | code immediate: pitch (6 downhill, 3 uphill) |
| `&3D1D` | 1 | | code immediate: jump height |
| `&37DF` | 1 | loops | code immediate: jump loops left |
| `&37F5` | 2 | | code immediate: jump table pointer |
| `&3A9B` | 1 | 0/1 | code immediate: bounce running |
| `&3AA4` | 2 | speed | code immediate: bounce ends below this speed |
| `&3ACC` | 2 | x units a loop | code immediate: bounce's sideways velocity |
| `&3AE4` | 1 | 0-2 | code immediate: bounce side (0 push left, 1 push right, 2 none) |
| `&3AFA`, `&3B03`, `&3B51` | 1 each | | code immediates: bump effect timer (5), bump sprite, spark sprite 0-3 |
| `&3B0B`, `&3B19` | 2 + 2 | | code immediates: x clamp minimum and maximum (`&48`/`&1D8`, or `&D1`/`&195` scraping a wall) |
| `&4CC4` | 1 | 0-21 | code immediate: backdrop scroll |
| `&1769`, `&176A`, `&176B` | 1 each | | animation counters |

### Road
| Address | Size | Meaning |
|---|---|---|
| `&F700`-`&F7FF` | 256 | the ring: six streams of 32 at offsets `&00` curve, `&20` hill, `&40` flags A (walls, lanes, fork), `&60` left roadside objects, `&80` right roadside objects, `&A0` obstacles (stream 5) |
| `&1771`, `&1772` | 1 + 1 | roadside objects just passed, left and right (the whoosh) |
| `&1770` | 1 | 5 in a tunnel, else 0 (set by `&44E1`) |
| `&16B5` | 1 | toggles 1/2: roadside and object streams are read on alternate segments only |
| `&175A` | 1 | no-traffic zone (road codes `&0B` on, `&0A` off) |
| `&1759` | 1 | fork message state |
| `&177D` | 1 | fork branch taken (1 = right, x < `&10C`) |
| `&175B` | 1 | the branch the criminal took + 1 |
| `&179C` | 1 | fork passed: rewrite streams |
| `&4477` | 1 | code immediate: stream 5 value, repeats until changed |
| `&1756` | 1 | `&FF` in the game-over sequence: no collisions, three obstacles for value 6 |

### Objects (`&16B8`: 6 slots of 20 bytes; slot 0 is the criminal, slots 1-5 at `&16CC` + 20n)
| Offset | Meaning |
|---|---|
| +0 | `&FF` active, `&00` free (`&350B` rotates it with `RLC`: only bit 7 matters) |
| +1 | depth, segments ahead, 1-22 |
| +2/+3 | screen x of the left edge, signed, 256 = screen width |
| +4 | fraction, counted down: position = 256 × depth − fraction |
| +5 | lateral, 0 = left of the road's span, 255 = right |
| +6 | line offset within the segment (projection) |
| +7 | collision code 0-5; the criminal's `&FC`-`&FF` is a 4-loop stun after a hit |
| +8 | width in screen x units: traffic `&28`, criminal `&2C`, obstacles from the stage |
| +9/+A | sprite table pointer |
| +B/+C | handler: `&3124` traffic, `&2E8E` criminal, `&33A7` obstacle, `&3564` none |
| +D/+E | velocity relative to the road, signed, 1/256 segment a loop |
| +F | type: `&FF` criminal, `&80` traffic, 0 obstacle, 2 flying, 1 landed |
| +10 | height (a struck obstacle) |
| +11 | traffic: lane 1-4; criminal: distance high byte 0-3; obstacle: flight table index |
| +12 | traffic and criminal: target lane; obstacle: flight loops left |
| +13 | sprite flip / animation |

Criminal (template at `&167B`): depth 100, +11 = 3 (868 segments; the panel shows 0869 by the first loop),
lateral `&47`, width `&2C`, velocity 60, target lane 2.

| Address | Size | Meaning |
|---|---|---|
| `&16B9`, `&16C9` | 1 + 1 | criminal distance in segments, low and high |
| `&16BD` | 1 | criminal lateral |
| `&16C5` | 2 | criminal velocity |
| `&1789`-`&178A` | 2 | DIST, 4 BCD digits |
| `&1757` | 1 | draw list count; list at `&7B00`, 4 bytes an entry |
| `&1760` | 1 | cars overtaken, pending bonus |
| `&1763` | 1 | criminal sighted |
| `&1764` | 1 | car sprite mode: 1 sighted (siren), 2 arrest |
| `&1767` | 1 | criminal damage level 0-6 (smoke sprites) |
| `&1768` | 1 | rams 0-20 |
| `&1695` | 1 | pull-over stop countdown (template 20) |
| `&305B` | 1 | code immediate: traffic spawn count; never reset (`&14` on disc) |
| `&2EF3`, `&2FA1` | 1 + 1 | code immediates: criminal dodge and sprint counts; never reset |
| `&2F96` | 1 | code immediate: sprint loops left |
| `&2EE7` | 1 | code immediate: criminal changing lane |
| `&3C6F`, `&3CC8` | 1 + 1 | code immediates: hit flash sprite 0-3, flash loops (9) |

### Time and flow
| Address | Size | Meaning |
|---|---|---|
| `&16A8` | 1 | time, BCD seconds, 0-`&60` (template `&60`) |
| `&16A7` | 1 | loops left in this second, 15 → 1 (template `&0F`) |
| `&175E` | 1 | clock state 0-4 |
| `&1765` | 1 | stage end state 0-6 |
| `&1766` | 1 | screen state: 0 normal, 1 page, 2 dissolve |
| `&175F` | 1 | pull-in counter (stage end state 2) |
| `&20A1`/`&20A2` | 2 | code immediates: continue countdown, L (21 → 0) and loops (4) |
| `&0FF1` | 1 | code immediate: stage end state 3 wait |
| `&12D9`, `&12E9`, `&12FA` | 1 + 2 + 2 | code immediates: dissolve count, step, mask pointer |
| `&136B`, `&136E`, `&1372` | 2 + 1 + 1 | code immediates: page pointer, entries shown, delay |
| `&0712` | 1 | code immediate: title page toggle |

### Panel and messages
| Address | Size | Meaning |
|---|---|---|
| `&1696` | 1 | gear last drawn (`&FF` forces a redraw) |
| `&1697`-`&16A6` | 16 | score digit shadows, 8 per buffer |
| `&16A9`-`&16AC` | 4 | time digit shadows |
| `&16AD`-`&16B4` | 8 | DIST digit shadows |
| `&1751`-`&1755` | 5 | popup score text |
| `&1758` | 1 | stage number drawn |
| `&1761`, `&1762` | 1 + 1 | popup pending, popup timer (11 loops) |
| `&0F5B` | 1 | code immediate: siren lights state |
| `&17C1` | 1 | message state 0-3 |
| `&17C2` | 1 | message priority |
| `&17C0` | 1 | static timer |
| `&17B2`, `&17B4`, `&17B6`, `&17B7` | 2 + 2 + 1 + 1 | text pointer, script pointer, column, line pause |
| `&17AE`, `&17B0` | 2 + 2 | face pictures: Nancy `&D600`, partner `&DE00` |

### Sound
| Address | Size | Meaning |
|---|---|---|
| `&1743`-`&174E` | 12 | AY registers 0-11, written every loop |
| `&176C`, `&176D` | 1 + 1 | pending effect, its priority |
| `&176F` | 1 | turbo whoosh running |
| `&0A73` | 1 | code immediate: effect 1 plays on alternate requests |
| `&37AA`-`&37AC` | 3 | RNG state |

## Controls

### Reading the keyboard
- `&0F14` scans all ten rows into `&0F4B`-`&0F54` (bit clear = pressed): PSG register 14 selected, PPI port
  A to input (`&92`), port C = `&40` + row for each row, read port A, then port A back to output (`&82`).
  Port C bits 4-5 are kept. Once a loop (from `&0E98`), and in the title and pause loops.
- `&0EF4` tests key A (row × 8 + bit) in that buffer: Z set if pressed. It patches its `BIT` instruction
  (`&0F11`). HL kept.
- `&0E98` builds `&0E89` and returns it in A:

| Bit | Control | Default key | Key no. | Joystick (row 9) |
|---|---|---|---|---|
| 7 | quit | ESC | 66 (`&42`) | |
| 6 | pause | P | 27 (`&1B`) | |
| 5 | turbo | SPACE | 47 (`&2F`) | |
| 4 | gear | N | 46 (`&2E`) | fire, 76 (`&4C`) |
| 3 | accelerate | A | 69 (`&45`) | up, 72 |
| 2 | brake | Z | 71 (`&47`) | down, 73 |
| 1 | left | K | 37 (`&25`) | left, 74 |
| 0 | right | L | 36 (`&24`) | right, 75 |

- Joystick and keys are ORed, for bits 0-4 only: the stick has no turbo or pause. Then left + right clears
  both, and accelerate + brake clears both (`&0EDC`). Bits 5-7 are added after. Verified for every key.
- The controls are levels. The only repeat logic is the gear's (see Gears).
- `&155D` masks: `&0E89 &= &1691`; during a dissolve `&0E89` = 0. The attract demo (`&08DC`), the pull-over
  (`&10B9`) and a jump (low nibble cleared) write `&0E89` themselves.

### Pause, quit and turbo (`&155D`)
- **Pause**: silence (`&0ABE`), then busy-wait for P to be released, then for any of bits 0-6, then for all
  released. No loops run; ESC doesn't resume. Verified.
- **Quit**: if `&179E` = 0: `&1691` = 0, `&179E` = 1, the message closes (`&1E20`). No continue is
  offered. After the next flip a dissolve starts and then the game-over sequence; back at the title about 10
  loops later. Verified.
- **Turbo**: if `&1782` = 0 and `&1692` > 0: `&1782` = 60, message `&1AB0` (priority 2: "WHOAAAAA!" or
  "GREAT!"), and the whoosh (`&0B24`). `&1692` goes down by 1 when `&1782` reaches 0 (`&381D`). Pressing
  again during a turbo does nothing.

### Redefine keys
On the title, ESC (`&06B0`) starts it: `&0871` = 1, `&086D` = `&082B` (the first name). Each loop `&0872`
shows "REDEFINE KEYS / PRESS A KEY FOR... name" and scans keys 71 down to 0 (not the joystick); the highest
numbered key down is taken, unless it's ESC or already defined in this pass. It's stored at
`&0E90 + n − 1`, a beep plays (`&0A9B`) and the next name follows: GEAR, ACCELERATE, BRAKE, LEFT, RIGHT,
PAUSE, TURBO. After the seventh, `&0871` = 0 (back to the title). A held key counts as a duplicate, so each
must be released. Verified.

**The cheat**: if the seven keys are S, H, O, C, K, E, D (`&3C &2C &22 &3E &25 &3A &3D`, table at `&0866`),
`&1647` toggles: test mode, "TEST" bottom right of the playfield. You then play with those keys. Verified.

### Test mode (`&1647` ≠ 0): keys after each flip of the driving loop (`&03C2`)
- `1`: restart the stage. `2`: next stage. `3`: stage 6, the ending (`&164D` = 5, + 1).
- `4`: effect 8 at priority 4 and `&1651` + 1 (a continue).

## The player's car

### Speed (`&37DE`, `&3852`-`&396A`)
Each loop, in this order:
1. **Gear**: if gear is held and `&1786` = 0: `&1787` ^= 1, `&1786` = 3, and into HI sets `&1783` = 4 (the
   screech). Else `&1786` counts down to 0. So a held key toggles every 4 loops: no edge detection.
2. **Slow nag**: if speed < 120 and `&1765` = 0, `&1690` − 1; at 0 it reloads 100 and shows "LET'S GET
   MOVIN' MAN!" (`&1A83`, priority 10). Driving faster doesn't reset it.
3. **Accelerating delta**. Off-road (`&1773` = 1 and speed ≥ 120, or `&1773` = 2 and speed ≥ 110):
   −((speed >> 5) | 1). Otherwise from the gear's maximum M: if speed < M,
   +(((M − speed) >> 4) & 63) | 1; else −((((speed − M) >> 4) & 31) | 1).

   | | No turbo | Turbo (`&1782` ≠ 0) |
   |---|---|---|
   | LO | M = 230 | M = 470 |
   | HI, speed ≥ 220 | M = 360 | M = 695 |
   | HI, speed < 220 | +((speed >> 4) \| 1): 1 a loop from rest | M = 470 |

4. **Keys**: brake −20 (whatever else); else accelerate: the delta; else −10. Floor 0.
5. **Slope**: when `&1780` reaches 0 (it reloads 3: every 4 loops), if `&3D31` ≠ 0 and speed ≠ 0:
   += (`&3D31` − 5) | 1, i.e. +1 downhill, −1 uphill; skipped if the result would be ≥ 695.
6. **Cap** 511.

Verified: LO from rest 15, 28, 41, 52, 63 ... 229, 230. HI from rest +1 a loop. HI 189, 200, 213, 226, 230,
239. HI turbo from 226: 255, 282, 307 ... 511. Without turbo from 511 in HI: 502, 493, 484, 477. Coast −10,
brake −20. Off-road at 303 accelerating: −9 a loop.

**Panel speed** = floor(speed × 82 / 100) (`&2246`: a shift-and-add × 82, then the 10,000s, 1,000s and 100s
digits): 230 → 188, 360 → 295, 511 → 419.

### Turbo
`&1782` = 60 loops, 3 a stage (template) and again on a continue, either gear, any speed. It only raises M:
release accelerate and the car still coasts at −10. The icon in use flashes on the panel.

### Steering (`&396D`-`&3A8C`)
- B = `&1797` (right), C = `&1798` (left). Right held: B = min(B + 4, 36), then C = max(C − B, 0). Left:
  the mirror. Neither: both − 9, floor 0. Both are capped at speed >> 2 (no steering at rest). In a jump
  they keep their values.
- s = (C − B) >> 1 (arithmetic). x += `&1793` + drift + s, then `&1793` = 0. During a bounce the drift and
  `&1793` are 0.
- Outputs: skid `&1781` = 1 when \|C − B\| ≥ 17 and the x step's sign is opposite to s (0 in a jump). Turn
  sprite `&1784` = 2 if \|s\| ≥ 12, 1 if ≥ 6, else 0; `&1785` = 1 if s ≥ 0.
- x is clamped to `&48`-`&1D8` (`&3B07`), or `&D1`-`&195` while scraping a wall.

Verified: right builds B 4, 8 ... 36 with x steps −2 ... −18; released, B falls 9 a loop.

### Curves: centrifugal drift
- c = `&1790` (the curve under the car, signed even, 2-8 seen ±2/±4 in stage 1); T = table `&3E02`[\|c\|] =
  255, 127, 85, 63, 51, 42, 36, 31 for \|c\| = 1-8.
- Each loop: d = (`&1774` − `&1795`) & 255; while d ≥ T: d −= T, n += 1, ref += T. If d ≠ 0 store ref in
  `&1795`. `&1796` += n. Drift this loop = 3n, with c's sign.
- At each segment step (`&3FA0`): r = \|old c\| − `&1796`; if r > 0, `&1793` = ±(4r + (r >> 1)) (old c's
  sign), applied once next loop; then `&1795` = `&1796` = 0. In all about 3\|c\| per segment, outwards.
- Verified: c = −2 at speed 220 drifted −9, −3, −7, −7, −4 a loop (the −9 is the lump).

### Hills and jumps
- Pitch `&3D31` per segment (`&3EAD`): 6 if the segment's hill ≥ 3, 3 if ≤ −3, else 0. It drives the
  slope step and the car sprite's pitch.
- **Jump**: at a crest (the previous segment's hill `&178D` < 0 and this one ≥ 0):
  A = (\|prev\| − 2) − (3 − (speed >> 7)). If A ≥ 1, the pair at `&37D2` + 2A gives the start and length:
  A = 1 → 2 loops, 2 → 4, 3 → 6, 4 → 8, 5 → 10 (and A = 6 reads past the table: no jump).
- Each airborne loop: `&37DF` − 1; (pitch, height step) from `&37C0`: (3,13), (3,10), (3,7), (3,4), (0,2),
  (0,−2), (6,−4), (6,−7), (6,−10), (6,−13), entered part way for short jumps; height `&3D1D` += step (the
  body drawn at y `&75` − height); the low nibble of `&0E89` is cleared (no accelerate, brake or steering,
  so the car coasts) and `&1773` = 0. The last loop: `&1783` = 3 and effect 2, priority 3.
- Verified: a −5 crest at 350 gave 4 loops, heights 4, 6, 4, 0.

### Off-road and walls (`&2C94`, from the road edges at the car's line)
- `&1773`: left edge `&7CFE` in `&6A`-`&84` → 1, ≥ `&85` → 2; else right edge `&7CFC` in `&7C`-`&8D` → 1,
  < `&7C` → 2; else 0. Level 1: speed loss (above) and a wobble (body sprite + 3 on `&176B` bit 0). Level 2:
  the loss and dust.
- With `&1773` > 0 and flags A (`F7[idx + &40]`) bit 6 set, bit 7 clear: bit 3 set → a barrier: bounce,
  threshold 20, side `&17A1` & 1. Bit 3 clear → a wall scrape: x clamp `&D1`-`&195`, sparks, effect 6
  (priority 4) if moving, roadside checks skipped.
- `&1771`/`&1772` are zeroed when that edge is far away (no whoosh from the far side).

### The bounce (`&2DB9`): every collision the car suffers
- Start (ignored if one is running, `&3A9B` ≠ 0): `&3A9B` = 1, side `&3AE4`, effect timer `&3AFA` = 5,
  velocity v = max(24, 16 + speed >> 4), end threshold `&3AA4` = min(A′, speed).
- Each loop (`&3A9A`): if speed ≥ threshold: speed −= (speed >> 2) | 3, `&1784` = 2; else it ends
  (`&3A9B` = 0, `&1784` = 1). `&1781` = 1 (screech). v −= v >> 4; side 0: x += v; 1: x −= v; 2: none.
  The controls are masked to gear only, so the speed code also coasts −10 first.
- Verified: a car hit at 360 gave 263, 190, 134, 124 (end), v 36, 34, 32, 30.

| Cause | Where | Side | A′ | Also |
|---|---|---|---|---|
| left roadside object (`F7[idx+&60]`; table at (`&5BD0`) + 7 × type gives E, C, A′) | `&2D4A` | 0 | table | hit if E < `&7CFC` < C; effect 4, priority 3 |
| right roadside object (`F7[idx+&80]`; table at (`&5BD6`)) | `&2D82` | 1 | table | hit if C ≤ `&7CFE` < E; effect 4, priority 3 |
| barrier | `&2D17` | `&17A1` & 1 | 20 | |
| fork divider | `&2E56`/`&2E72` | 0/1 | 140 | effect 4, priority 3 |
| traffic | `&3187` | from the hit code | 150 | car removed, chain `&1650` = 0, message `&1A97` (priority 3), effect 3 priority 2 |
| criminal | `&2FE1` | from the hit code | 200, 230 in turbo | then threshold += 40; see Ramming |

Obstacles (cones) don't bounce the car: they fly (see Roadside obstacles).

### Collision test (`&34BC`, for each object in `&350B`, and again in `&3478` after advancing)
- Skipped if +7 ≠ 0, x outside 0-255, or depth ≥ 3 (≥ 2 for the criminal).
- Base code E: depth 1: 4 if `&1774` < `&80`, else 1. Depth 0 or 2: 4 only if `&1774` ≥ `&80`.
- Overlap: (x & `&FC`) < `&98` and (x & `&FC`) + width ≥ `&78` (the car's box is `&78`-`&97`).
- x < `&70`: E; `&70`-`&7F`: E − 1; ≥ `&80`: E + 1. Stored in +7. Side = E < 3 ? E : E − 3: with E = 4, an
  object to the left pushes the car right, centred pushes left, to the right **doesn't push** (verified).
  E = 0 (near, centred) never registers.
- `&3478` jumps straight to a non-criminal's handler on a hit, so a handler can run twice in a loop.

## Traffic
- **Spawn** (`&304A`, only when `&1765` = 0, `&175A` = 0 and `&1788` > 0): the count `&305B` −= `&1788`.
  When it goes negative it reloads (RNG & 15) + (`&5BF0`) (+ `&19` once the criminal is sighted). Then:
  the first free slot of 1-5, abandoned if 3 or more traffic cars are in the slots before it. Copy the
  template `&2E7A`: depth 21 (`&15`), width `&28`, handler `&3124`, type `&80`. Lane range (lo, hi) at depth 20
  from `&30F3`; lane = lo + (RNG & 3), capped at hi; lateral = `&303E`[lane]; velocity = `&3042`[lane];
  sprite = (`&5BE8` + (RNG & 6)); after the sighting index 6 becomes 4. 3 RNG calls a spawn (1 if no slot).
- **Lanes**: lateral 1 = `&05`, 2 = `&50`, 3 = `&94`, 4 = `&D8` (1 on the left). Velocity 140, 220, 170, 250
  (before the sighting), 60, 140, 90, 170 (after, `&3046`). Velocity is relative to the road, so a car in
  lane 4 is passed only above 250 (205 on the panel).
- **Lane range** (`&30F3`, flags A at the depth): F = 0 or F & `&C1` = `&C1` → 1-4; F & `&C1` = `&41` → 1-3;
  else bit 7 set: bit 1 set → 2-4, clear → 1-3; bit 7 clear: bit 1 set → 3-4, clear → 1-2.
- **Behaviour** (`&3124`): constant speed and lane. If the lane range at its depth excludes the target
  lane, the target is clamped and lateral moves 5 a loop towards it (*from the code; not seen*). During the
  stage end or a no-traffic zone, velocity = `&1FF`: it runs ahead.
- **Despawn**: ahead at depth ≥ 23; behind when depth reaches 0 at a segment step (`&4480`) or at depth 1
  with fraction > NOT(`&1774` & `&E0`) (`&3529`). Behind counts an overtake (`&1760` + 1).
- **Hit**: see the bounce table. The car vanishes at once.

## Roadside obstacles
- Stream 5 (`&4477`, from road codes 3-9). `&3305` reads it at depth 20 − `&1788` (one of two segments when
  two are crossed). 1 or 4: one at lateral `&32`; 2 or 5: one at `&DC`; 3: two at `&46` and `&B4`; 6: two at
  `&50` and `&A0` (three at `&20`, `&56`, `&8C` in the game-over sequence). 3 and 6 also clear the stream 2
  and 4 segments on. Values 1-3 use kind 0, 4-6 kind 1: (width, sprite) from the 6-byte table at (`&5BCC`).
- First free slot of all six; none → the rest are dropped. Stationary.
- **Hit** (`&33A7`): no effect on the car. The obstacle gets velocity min(2 × speed, `&15E`), depth + 1,
  type 2; effect 5, priority 3. A flight from `&346E` by speed bucket ((speed >> 7) & 3) + bit 8:
  (start, loops) (`&22`, 6), (`&1C`, 12), -, (`&0A`, 18), (`&00`, 20); each loop height = `&3446`[i++],
  velocity −= velocity / 32. Then type 1, landed.

## The criminal
- **Start**: slot 0 from the template, 868 segments ahead (DIST 0869 on the first loop), velocity 60:
  you close at (speed − 60) / 256 segments a loop. Its handler only runs at depth < 20 with +11 = 0.
- **DIST** (`&229B`): `&1789`-`&178A` = BCD of 256 × `&16C9` + `&16B9`; the thousands digit is 0 or 1 only
  (the maximum is 1,023 anyway). Drawn at panel offset `&0122` when a digit changes.
- **Sighting** (`&3C47`, its first handler call): `&1763` = 1, `&1764` = 1; time set to 60 (`&16A8` = `&60`,
  `&16A7` = 15); page "SIGHTING OF TARGET VEHICLE" (`&11DE`, French `&11FF`); siren lights on (`&0F59`, A =
  1); the portrait becomes the criminal (`&0F55`). Traffic slows (the second speed table) and spawns less.
- **Handler** (`&2E8E`, not during the stage end). If +7 is 1-5 it's a ram. If `&FC`-`&FF`, +7 + 1 and
  nothing else (4 loops stunned). Else:
  - avoid traffic: any traffic within ±2 segments in its target lane → a random lane step;
  - dodge: if not changing lane (`&2EE7` = 0) and depth < 7, the player's lanes from x: < `&A4` → 4; <
    `&EA` → 3-4; < `&130` → 2-3; < `&176` → 1-2; else 1. Target lane among them → a random lane step;
  - random lane step: RNG bit 7 clear → +1, set → −1; 0 → 2, 5 → 3; then clamped to the lane range at its
    depth;
  - lateral moves 10 a loop to the lane's value;
  - velocity `&E6` (230), + 30 at depth < 6;
  - sprint: the count `&2FA1` reloads (RNG & 15) + (`&5BF2`) and starts 9 loops of sprint (`&2F96`): at depth
    < 13, velocity = 230 + 30 × (13 − depth) (+ 30 at depth < 6). Seen: `&122` at depth 11, `&24E` at 2.
  - The dodge count `&2EF3` reloads (RNG & 31) + (`&5BF1`) but changes nothing: only an RNG call.
- **Can't be passed**: at a segment step it's held at depth 1, fraction `&FF`; in `&3529` its fraction is
  clamped to NOT(`&1774` & `&E0`).

### Ramming and damage
- A hit (`&2FE1`): +7 = `&FC`; the bounce (cap 200, 230 in turbo, then + 40); score stage × 10,000, or for
  code 1 (close, criminal left of centre) (stage + 4) × 10,000 and two damage points; × 1,000 instead if a
  continue was used; a 4-loop sprint (`&2F96` = 5); message `&1A57` (priority 5: "BEAR DOWN." / "OH MAN." /
  "HARDER!" / "PLEASE!" / "MORE, PUSH IT MORE!"); effect 3, priority 1. Verified: 1 hit + 10,000; 2 + 50,000.
- Damage (`&3C6E`): `&1768` + 1. At 19 "ONE MORE TIME." (`&1AC3`, priority 10); at 20 the arrest. `&1767`
  = 0-6, + 1 at hits 1, 4, 7, 11, 14, 17 (smoke sprites). Hit flash sprite `&3C6F` (0-3) for 9 loops.
- **Damage meter** (`&14EE`, once sighted, `&1765` < 3): 2 bytes wide at back buffer + `&04C2`, 61 lines
  drawn upwards. Each hit is 3 lines: one `&C0 &C0`, then two of colours (E, D), (D, E) from `&1553` by hits
  div 5: (`&85`,`&4A`), (`&C5`,`&CA`), (`&D4`,`&E8`), (`&91`,`&62`), (`&84`,`&48`). The rest `&C0`.

### The arrest and stage end
- `&1166` (20 rams): `&1765` = 1, `&1764` = 2, `&1691` = `&C0` (the player's driving keys off), page "OK!
  PULL OVER CREEP!" (`&1222`/`&123D`), criminal velocity `&190`.
- State 1 (`&10B9`), the pull-over: the criminal's velocity − 5 a loop to `&46`; its lateral ± 5 towards
  `&23` (it jitters between `&1F` and `&24`). An autopilot writes `&0E89`: right if x ≥ `&110`, left if x <
  `&101`; target speed 350, or 69 + 20d at distance d < 14 (no limit at d = 14: a `DJNZ` with B = 0);
  accelerate off at the target, brake at target + 50; gear as the demo. With no steering and d < 3,
  `&1695` (20) counts down; at 0 speed = 0, the criminal at depth 1, `&1765` = 2, `&1783` = 3. About 113 loops.
- State 2 (`&0FBC`, 4 loops): `&175F` + 4, x + 12 (to `&126`), `&1774` + `&20` (pulls in behind).
- State 3 (`&0FF0`, 4 loops), then state 4 and the stage's arrest page (`&5BDC`, French `&5BE2`).
- State 4 (`&100C`), when the page ends: the bonuses (stage × 100,000, or × 10,000 after a continue; plus
  time left × 5,000) and the bonus page; state 5.
- State 5: when that page ends, state 6 and a dissolve. State 6: when it ends, stage + 1, `JP &031E`.

## Time, score and flow

### The clock (`&1FF0`; not during the stage end or a dissolve)
- State 0: `&16A7` − 1; at 0 it reloads 15 and `&16A8` − 1 (BCD). At 15 s Nancy's warning (`&1A89`,
  priority `&15`: "IF YOU KEEP MESSIN' AROUND YOUR TIME IS GOING TO RUN OUT."). At 0: state 1, `&1691` =
  `&93` (ESC, gear, steering only).
- State 1: the "TIME UP" page every loop while the car coasts (−10 a loop). Sighted meanwhile (time ≠ 0
  again): back to state 0, `&1691` = `&FF`. At speed 0: state 2, speech 4.
- State 2, when the page ends: no continues → quit (`&1590`); else `&1651` − 1, state 3, countdown L = 21.
- State 3: "CONTINUE THIS MISSION / PUSH GEAR BUTTON / BEFORE TIMER REACHES 0 / TIME nn" (nn = L >> 1, 10
  to 0); every 4 loops L − 1 with effect 8 (L even) or 9 (odd), priority 1; 84 loops in all. At L = 0:
  `&179E` = 1, state 4 (game over). Gear: continue: state 0, `&1766` = `&1767` = `&1768` = 0 (damage
  reset; the sighting and the criminal's place kept), `&1691` = `&FF`, `&1786` = 3, turbos 3, time 60,
  `&164C` + 1, speech 5.
- 60 s at each stage start and at the sighting: no checkpoints, no extensions.

### Score (BCD, `&1648`-`&164B`)
| What | Points |
|---|---|
| Each loop (`&20DE`) | a = (speed & `&7F`) >> 1; 10 × (a >> 4) + (a & 15): 0-45, a sawtooth in speed (meant to scale with it). Matched 300 loops of 300. |
| Each car overtaken (`&2148`) | `&1650` = min(`&1650` + 2, `&80`) BCD; + `&1650` × 100: 200, 400 ... 8,000, shown as a popup |
| Ram | stage × 10,000; (stage + 4) × 10,000 for a double; ÷ 10 after a continue |
| Fork, wrong branch | (stage + 4) × 10,000 (and "WHAT ARE YOU DOING MAN! THE BAD GUYS ARE GOING THE OTHER WAY.") |
| Stage clear | stage × 100,000 (÷ 10 after a continue) + seconds left × 5,000. Verified: + 350,000 at stage 1 with 50 s. |
| The ending (LV6) | 5,000,000 |

`&20F2` adds A, E, D (BCD) to score bytes 0-2 and builds the popup text. No high-score table.

### Flow
- Title → gear → speech 5 → stage 1: intro → reset → chase (speech on loop 2) → arrest → stage end →
  next stage ... after stage 5, the LV6 ending, +5,000,000, waits for gear, title.
- **Intro** (`&04E5`): a dissolve in, "CHASE H.Q. MONITORING SYSTEM", Nancy's briefing (`&5BDA`, priority
  `&FF`) printed a character a loop, two random bars (2 RNG calls a loop), the target car revealed a line a
  loop for 49 loops (not on stage 5). Gear skips the briefing (speech 5). About 1,000 CPC frames unskipped.
- **Game over** (`&0445`): silence, reset with a fixed record (`&0423`), speed 250, the criminal object 1
  segment ahead at 250 (from `&0431`), `&1756` = `&FF`, Nancy's verdict (`&1AC9`, priority `&FF`: one of
  three), the "GAME OVER" page while the world runs without input or clock, then a dissolve and the title.
- **Messages** (`&1DB4`/`&1DD4`): a new one is refused while one is opening or printing (`&17C1` = 1 or 2)
  with priority ≥ its own. State 1: clear the line, static in the face (`&1EB9`, 640 RNG calls). State 2:
  after 4 loops the face, then a character a loop; 10 loops' pause after each line. Then static again for 4
  loops and the face blanked. Scripts: a face byte (0 = (`&5BCA`), 1 Nancy, 2 the partner) or `&FC a b c`
  (one of three by RNG < `&55`, < `&AA`, else), then [English][French] pointers, `&FE` jump, `&FF` end.
- **Pages** (`&139F`/`&12CF`, `&1766` = 1): entries [size 1/2][screen offset][text, bit 7 on the last
  character][delay], redrawn whole into the back buffer every loop.
- **Dissolve** (`&1337`, `&1766` = 2): A ≥ 0 out, A < 0 in; one RNG call picks one of 3 patterns. 7-8
  loops, each ANDing the whole 8K playfield with a 2-byte mask per line (from `&FEA0`-`&FFFF`). Controls
  are zeroed and the clock stops.

## Title and attract mode (`&068F`)
- Reset with the record at `&5C01` of the stage in memory (the demo shows the last stage played), speed 400.
- Each loop: the demo autopilot (`&08DC`): accelerate; right if x ≥ `&105` + c, left if x < `&F6`; gear when
  (speed ≥ 150) = (LO). c is the carry left by the flip's `CP &C0` (1 when the new back buffer is `&80`), so
  the threshold alternates between `&105` and `&106`. Then the world routines, then the real keys:
  gear → the game; ESC → redefine; F1 → English, F2 → French (a beep, `&0A9B` with DE = `&A0F0`).
- "CHASE HQ" large; "PRESS GEAR TO PLAY" and "ESC TO REDEFINE KEYS" alternate (bit patterns `&C3`, `&0F`
  rotated at `&06F1`/`&06F9`); two pages alternate: "PROGRAM JOBBEEE / GRAPHICS BILL / F1-ENGLISH
  F2-FRANCAIS" and "C 1989 OCEAN SOFTWARE / C 1988 TAITO CORPORATION / ALL RIGHTS RESERVED".

## The dashboard
Offsets within a 12K buffer; digits from the font at `&E600` + 16 × glyph (0-1 "HI", 2-3 "LO", 4-13 the
digits), 2 bytes × 8 lines. Score, time and DIST keep a shadow per buffer and redraw only changed digits
(the flip swaps the shadow pointers at `&22E6`, `&2294`, `&22D7`).

| Item | Where | Written by | When |
|---|---|---|---|
| Score, 8 digits | + `&004C` (row 1, bytes 12-27) | `&216B` (`&22DE`) | changed digits |
| Time, 2 digits | + `&005E` (row 1, bytes 30-33) | `&216B` | changed digits |
| Speed, 3 digits | + `&0064` (row 1, bytes 36-41) | `&216B` (`&2246`) | every loop |
| Gear HI/LO | + `&011C` (row 4, bytes 28-31) | `&216B` | both buffers, on change (`&1696`) |
| DIST, 4 digits | + `&0122` (row 4, bytes 34-41) | `&216B` (`&229B`) | changed digits |
| Stage number | + `&2117` (row 4 line 4, byte 23) | `&21A1` | both buffers, once a stage |
| Bonus popup | + `&10CE` (row 3 line 2, bytes 14-25) | `&21C2` | `&C000` buffer only, so it blinks; 11 loops |
| Face | + `&006B`, 8 bytes × 40 lines | `&1DD4` | both buffers |
| Message line | + `&2181` (lines 52-59, bytes 1-62), font `&56BF` | `&1DD4` | both buffers |
| Turbo icons | playfield, sprite `&8FBD` (16 × 4) at y `&7C`, x 4, `&14`, `&24` | `&216B` | every loop; the one in use flashes on `&1769` bit 0 |
| Damage meter | playfield + `&04C2` | `&14EE` | every loop once sighted |
| Siren lights | 6 bytes at `&C042` swapped with 6 at `&C078`, 32 lines | `&0F59` | on at the sighting |

The lights are swapped in the `&C000` buffer only, so they alternate red/blue as the buffers alternate: a
flash for free.

## Sound and speech
- **Every loop** (`&0949`): effect 7 if passing roadside objects; the engine or whoosh into the shadow; AY
  registers 11 to 0 from the shadow; then the pending effect. Registers 12-13 are never written. No siren
  sound.
- **Engine** (channel C, registers 4/5 and 10): period = k × (255 − (speed >> 1)) + 300, k = 4 in LO, 8 in
  HI; in a tunnel + 500 instead of + 300 and volume 11, else 13. Mixer `&3B`.
- **Turbo whoosh** (`&0B24`, 60 loops): noise period `&1749` 59 → 1 (register 6), tone C = noise + 10,
  volume 11, mixer `&1B`; then mixer |= `&24` and the engine resumes.
- **Effects** (`&097B` + 4n gives D, E and the routine) are blocking: channel A's volume (register 8)
  toggled between 0 and 15 with delay loops (tone and noise A off, so it's a 1-bit DAC). Requests: `&0938`,
  accepted if none is pending or its priority ≤ the pending one's (lower wins). One plays per loop.

| Effect | D, E, routine | Sound | T-states | RNG calls | Requested by |
|---|---|---|---|---|---|
| 1 | `&50`, 1, `&0A72` | random clicks, pitch rising; every second request only | 129K | 80 | skid or screech (`&3B33`, priority 5) |
| 2 | 6, -, `&0A1A` | 32 runs of 0/15, lengths from `&0A31` | 234K | 0 | jump landing (priority 3) |
| 3 | 6, -, `&09A3` | 1-bit sample, 93 bytes at `&09BD` | 133K | 0 | ram (priority 1), car hit (priority 2) |
| 4 | 10, -, `&09A3` | the same, slower | 220K | 0 | roadside, divider (priority 3) |
| 5 | 2, -, `&0A1A` | as 2, higher | 181K | 0 | obstacle hit (priority 3) |
| 6 | 26, 2, `&0A7A` | random clicks | 40K | 52 | wall scrape (priority 4) |
| 7 | 2, 100, `&0A7A` | random clicks | 106K | 200 | passing roadside objects (priority 4) |
| 8 | 120, 120, `&0A9B` | 50 pulses, about 1.5 kHz | 131K | 0 | continue countdown (priority 1), test key 4 |
| 9 | 200, 200, `&0A9B` | 50 pulses, about 1 kHz | 195K | 0 | continue countdown (priority 1) |

  Effects 3 and 4 rotate each sample byte by D mod 8 as they play, so the sample changes for good, cycling
  through 4 variants.
- **Speech** (`&0B75`, 128K only, blocking; silences the AY, then each nibble, high first, into registers 8
  and 9, about 413 T a sample; table `&0B5D`, 4 bytes from phrase 1: length, address in bank `&C4`):

| Phrase | Bytes | Address | Plays |
|---|---|---|---|
| 1 | `&0A8C` | `&4000` | stage start (rotation) |
| 2 | `&14E6` | `&4A8C` | stage start (rotation) |
| 3 | `&0A5A` | `&5F72` | stage start (rotation; the first after power-on) |
| 4 | `&0ABE` | `&69CC` | time up, at speed 0 |
| 5 | `&0ADC` | `&748A` | game start, continue, intro skipped |

  On 64K the stage-start text is "GIDDY UP BOY!", "HOLD ON MAN" or "LET'S GO. MR. DRIVER." at random, which
  suggests what phrases 1-3 say (*order unverified*). Phrase 5 takes 2.30M T, phrase 3 2.19M T.

## Random numbers (`&37AD`)
No `LD A,R` in `&0300`-`&FFFF`, nothing cycle-dependent. Three bytes at `&37AA`-`&37AC`, `&7B &2D &E9` at
power-on, never reseeded:

    s0 = (s0 - &8D) & &FF
    s1 = (s1 + 3) & &FF
    a  = ror8((s0 + s1) & &FF)
    s2 = ror8(s2)
    a  = (a + s2) & &FF
    s2 = a                ; returned in A

Checked against the emulator over 5,308 calls: no mismatch.

| Caller | Use | Calls |
|---|---|---|
| `&3060`, `&30A6`, `&30D0` | traffic: interval, lane, model | 3 a spawn (1 if no slot) |
| `&2E8E` and its subroutines | the criminal: lane steps, sprint and dodge counts | a few a loop near it |
| `&0A7B` | effects 1, 6, 7 | 80, 52, 200 a play; 2,840 in 300 loops of driving |
| `&1349` | dissolve pattern | 1 a dissolve |
| `&1E49`, `&1EC7`, `&1ECF` | message branches (`&FC`), face static | 1 a branch; 640 a static |
| `&053A`, `&0557` | the intro's bars | 2 a loop |

**Lockstep**: the sequence runs on from power-on through the attract demo (which spawns traffic), so the
BBC must start the same number of loops after power-on with the same keys. The sound effects draw from the
same generator, so the BBC must step it the same number of times per effect even if its sound differs:
the counts above (effect 1 only on every second request). s0 and s1 can be stepped N times at once (s0 −
N × `&8D`, s1 + 3N); s2 needs the N rotates and adds. Other state never reset and needed for lockstep: the
traffic count `&305B`, the criminal's counts `&2EF3` and `&2FA1`, `&164F`, and the effect 1 toggle `&0A73`.

## Oddities and waste
- **Score per loop** uses the speed's low 7 bits: a sawtooth, not a scale. `RLA` where `RRA` was meant.
- **The wrong fork branch scores** (stage + 4) × 10,000; the right one scores nothing. Probably inverted.
- **Traffic hit on the right doesn't push** the car; a centred near hit (code 0) doesn't register.
- **Jumps clear `&0E89`** for the rest of the loop; the biggest crest at top speed gives no jump (table overrun).
- **Two segment steps in a loop** lose the first drift lump; stream 5 is read for only one of them.
- **Gear auto-repeats** every 4 loops when held.
- **The pull-over target** has no limit at distance 14 (`DJNZ` with B = 0); the criminal's lateral never
  settles on `&23`. The demo and pull-over autopilots compare with an `SBC` that uses a leftover carry.
- **The crash message** `&1A97`'s first choice ("OH, NO!") has an English pointer whose low byte is `&FF`,
  read as the end: an empty message one time in three.
- **The criminal's speed** adds 30 from a stray DE; it also computes (depth − 1) × 8 and drops it. The dodge
  count only burns RNG values.
- **`&3E2F`** lacks an `LD A,L`, so a backdrop scroll bit comes from A′. **`&2D53`** tests `&1775`'s bit 7
  where `&1774` (or bit 0) was likely meant.
- **The redefine beep** sets BC = `&A0A0` but the beep uses DE. `&0E6C` clears the `&C000` playfield twice.
  Face 0's pointer (`&5BCA`) is 0 in LV1, LV3 and LV5.
- **Waste**: the turbo icons are replotted every loop (23.5K T); the speed digits every loop; pages are
  redrawn whole every loop; the dissolve ANDs all 8K a loop; `&350B` rotates flags that are only ever `&00`
  or `&FF`; the effects and speech stop the game (up to 234K T, about 3 frames, per effect); `&0E8A` is
  written and never read; `&176F` = 1 in `&0B2D` is dead code.

## Open questions
- What the harness's 1.2 stretch hides: real CPC loops a second (and so the clock's real speed), and the
  effects' true length. *Unverified on hardware.*
- Traffic lane changes when the road narrows: from the code only.
- Curves beyond ±4 (stages 2-5) and the drift tables past \|c\| = 8.
- The slope step, the jump landing sound, wall scrape and barriers: from the code only.
- `&4561`/`&455E` (the game over loop waits on them; set by the tunnel code) and `&1756`'s full role.
- Which speech phrase says what.
- The fork's scoring with a continue used (÷ 10 or not).

## The harness: starting a game
`work/logic/game.py` (needs `tools/cpc.py`):

    import sys; sys.path[:0] = ['tools', 'work/logic']
    from game import start_game, drive, bot, K, word
    m = start_game()                                 # 30 attract loops, gear, the intro: at &0362, stage 1
    m.run_frames(100, lambda i: {K.accel})           # 100 loops holding A
    drive(m, 300)                                    # 300 loops with the demo's rule (stay central)
    print(word(m, 0x177E), m.mem[0x16A8])            # speed, time (BCD)

`K` has the default keys (gear N 46, accelerate A 69, brake Z 71, left K 37, right L 36, pause P 27, turbo
SPACE 47, ESC 66, F1 13, F2 14, 1-4). `start_game(attract_loops)` fixes the RNG state: keep it the same for
lockstep. `.venv/bin/python work/logic/game.py 450 out.png` runs a demo. Other scripts there: `rng_test.py`
(the generator), `keys_test.py`, `cost_test.py`, `traf_ram.py` (pokes the criminal close and rams it),
`traf_stage.py N` (jumps to stage N in test mode), `flow_arrest.py` (arrest into stage 2), `flow_bot.py`
(time-over and continue).
