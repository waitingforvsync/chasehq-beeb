# Chase H.Q. (CPC): the text system

A spec of the CPC original's message window, faces, font, pages and dissolve, from its code, for the BBC
version to be written from. It also covers the BBC's data (`tools/gentext.py`) and a proposal for the 6502.
Addresses are CPC addresses and "loop" is one pass of the main loop, as in `docs/cpc-logic.md`. Everything
was checked in the harness (`tools/cpc.py`) with the scripts in `work/text/` unless marked *from the code*.
Measured 2026-10-31.

## Summary
- **The message window** (`&1DB4` request, `&1DD4` run once a loop) prints scripts on the panel: 4 loops of
  static in the face box, then the speaker's face and one character a loop on the message line, each line
  held 10 loops, then 4 loops of static and the face blanked. A request is refused only while another is
  opening or printing with a priority at least as high. Scripts are a face byte or a 3-way random choice,
  English and French line pointers, `&FE` to chain a new speaker, `&FF` to end.
- **The faces** are 8 bytes by 40 lines: Nancy (`&D600`), the partner (`&DE00`) and a stage face (`(&5BCA)`,
  the airborne patrol's pilot, in stages 2 and 4 only). There is no criminal's portrait.
- **The font** (`&56BF`): 41 glyphs of 2 bytes by 8 lines, blue shaded on white. Zero is the O.
- **Pages** (`&139F` request, `&12CF` run) are white boxes of text on the playfield, redrawn whole into the
  back buffer every loop, each entry appearing on a set loop. Size 2 is the same font with its lines doubled.
- **The dissolve** (`&1337`) ANDs the whole back playfield with one of 19 line masks a loop, for 7 or 8
  loops, out to black or in from it. It costs the CPC 230K T a loop.
- **The BBC data** is 2,755 bytes for stage 1: the font 656, two faces 646, the scripts 793, the pages 340,
  the dissolve 316, the static's table 4.

## The message window

### Variables
| Address | Meaning |
|---|---|
| `&17C1` | state: 0 idle, 1 requested, 2 running, 3 closing |
| `&17C2` | the current message's priority (kept after it ends) |
| `&17C0` | static timer: 4 loops |
| `&17B4` | script pointer: the next byte to read |
| `&17B2` | text pointer: the next character |
| `&17B6` | column, 0-30 |
| `&17B7` | line pause: 10 loops |
| `&17AE`, `&17B0` | faces 1 and 2: `&D600`, `&DE00` (never written; face 0 is `(&5BCA)`) |
| `&1644` | language: 0 English, 1 French |

### Where it draws, and in what
- **The face box**: offset `&006B`, rows 1-5 (lines 8-47), bytes 43-50, in both buffers (`&C06B` and
  `&806B`).
- **The message line**: offset `&2181`, lines 52-59, bytes 1-62, in both buffers. Column c is bytes 2c + 1
  and 2c + 2, so a line holds 31 characters. It straddles character rows 6 (lines 4-7) and 7 (lines 0-3).
- **Colours**: the line is cleared to `&0C` (pen 2 both pixels: bright white, hardware 11) and the glyphs
  are copied over it whole, white background and all. The glyphs' ink is pens 4 (blue), 5 (bright blue), 10
  (mauve) and 15 (grey), shaded from mauve at the top to grey at the bottom. The static is random bytes AND
  `&0C`: each pixel pen 0 or pen 2, black or white. A blank face is `&00`.

### Requests (`&1DB4`, HL the script, A the priority)
- Refused if the state is 1 or 2 and the current priority is at least the new one (`CP B : RET NC`).
  Otherwise taken: priority, script pointer, pause 0, state 1. So an idle or closing window takes anything,
  equal priorities don't interrupt, and a higher one restarts the window at once.
- Every request comes earlier in the loop than `&1DD4`, so a taken request's static shows in its own loop.
  Two in one loop: the second is judged against the first (state 1). Seen: loop 199 of `run_b.py`, a ram
  (5) refused under a ram (5), then the 19th ram's (10) taken; stage 2's loop 193, a crash (3) taken, then the
  airborne patrol (15) over it.

### States (`&1DD4`)
| State | Each loop |
|---|---|
| 0 | `&17C0` − 1; at 0 (every 256 loops) the face is blanked again (`&1EE2`). Redundant. |
| 1 | `&1E2F`: state 2; clear the line (`&1FA6`, column 0); `&17C0` = 4; static (`&1EB9`). |
| 2, `&17C0` > 0 | − 1; reaching 0, `&1E3F`: read the script (choices, then the face byte), draw the face (`&1F00`), take the first line's pointers (`&1E79`) and print its character 0, clearing the line first. |
| 2, `&17B7` > 0 | − 1; reaching 0, `&1E0A`: the next script byte. `&FF`: close (`&1E20`: `&17C0` = 4, state 3, static, clear the line). `&FE`: jump, then clear the line, `&17C0` = 4, static (state stays 2). Else the next line's pointers and its character 0. |
| 2, else | `&1E94`: print the next character at the column, column + 1. If it has bit 7 (the line's last), `&17B7` = 10. |
| 3 | `&17C0` − 1; at 0: state 0, the face blanked (`&1EE2`). |

**Timing**, with S the request's loop:
- S to S + 3: static in the face box; the line cleared at S.
- S + 4: the face, and line 1's first character.
- A line of n characters starting on loop L prints on loops L to L + n − 1 and stays whole to L + n + 8. On
  L + n + 9 comes the next line's first character (the line cleared first), or a chained speaker (static and
  a cleared line for 4 loops, then the face and its first character), or the close (static and a cleared line
  for 4 loops).
- The face is blanked 4 loops after the close.

Verified loop by loop: the crash's "OH, NO!" (`run_a.py`, requested on loop 614): face 618, last character
624, closed 634, blanked 638. The stage 1 briefing (`run_intro.py`, requested on loop 1): face 5, lines from
41, 78, 111, 151 and 183 (27, 28, 24, 31, 23 and 30 characters: each n + 9 after the last), the partner's
reply after static on 222 and 226, closed 254, blanked 258.

### Scripts
A script starts with a choice or a face byte:
- **Choice**: `&FC` and three addresses. One random number at `&1E49`: below `&55` the first, below `&AA`
  the second, else the third (85, 85 and 86 in 256). The target is read the same way, so choices nest.
- **Segment**: a face byte (0 the stage's `(&5BCA)`, 1 Nancy, 2 the partner), then lines as pointer pairs,
  English then French (`&1E79` adds 2 for French), then `&FF` (the end) or `&FE` and an address (a new
  speaker: static, then that script).
- Text is ASCII with bit 7 on the last character, up to 31 characters.
- A segment's first line is read without the `&FF`/`&FE` test (`&1E3F` goes straight to `&1E79`); only later
  lines are (`&1E0A`). That's why the crash script's first choice works although its English pointer is
  `&18FF`: it prints "OH, NO!" (seen on loop 624, `work/text/a624.png`). `docs/cpc-logic.md` calls this an
  empty message one time in three: it isn't.

### Random numbers
- 640 calls for each static (`&1EC7`, `&1ECF`): two per byte of the box, 320 bytes. The first of each pair
  goes to the `&C000` buffer, the second to `&8000`, so the static flickers between two patterns as the
  buffers flip. A static comes at each request, each `&FE` and each close.
- One call per choice (two for the nested ram choice), on the loop the face appears, not the request's.
- After 640 calls s0 and s1 (cpc-logic.md, Random numbers) have each changed by `&80`: only their sum enters
  the result, and it steps by `&76` a call. s2 needs all 640 steps.

### Cost on the CPC (T-states, `cost_cpc.py`)
Idle 87; a character about 1,800; a face 44,000 (both buffers); a static 138,000 (both buffers and the 640
calls).

## The faces
- **Format**: 8 bytes by 40 lines, linear, top line first: 16 by 40 MODE 0 pixels. `&1F00` copies each
  line into both buffers. Pens 1 (black), 2 (white) and 15 (grey) only.
- **Nancy** at `&D600` and **the partner** at `&DE00`: in two of the screen's gaps, put there by the
  start-up's scatter from `&8000`.
- **The stage's face**, `(&5BCA)` in the stage record: `&6E0E` in LV2 and `&6D4A` in LV4 (the same picture:
  the airborne patrol's helmeted pilot), 0 in LV1, LV3 and LV5. Only the airborne patrol's messages use it.
  Seen in stage 2 (`run_s2.py`, loop 193, `work/text/s2_air.png`).
- **No criminal's portrait.** `docs/cpc-logic.md` says the sighting makes the portrait the criminal's
  (`&0F55`). It doesn't: `&0F55` is `LD A,1 : JR &0F5A`, the siren lights on (`&0F59` with A = 1). The intro
  shows the target car, a sprite (`&05A0`).

## The font (`&56BF`)
- 41 glyphs of 16 bytes, `&56BF`-`&594E`: 8 lines of 2 bytes, top first. 4 pixels wide, the rightmost
  column mostly white (the spacing). Space is all `&0C`.
- **Mapping** (`&1F61`), from the code AND `&7F`: `A`-`Z` (≥ `&41`) → 0-25; `.` 26, `,` 27, `!` 28, `'`
  29, space 30, `-` 40, `0` → 14 (the O); anything else c − `&12`, so `1`-`9` → 31-39. A glyph is at
  `&56BF` + 16 × index (`&1F95`).
- Anything else lands past the font: `?` would be 45, in code; `:` would be 40, the dash. No text in the
  game uses them. Stage 1's texts use the letters, digits, space and `. , ! '`; the dash only in the title.

## Pages (`&139F`, `&12CF`)

### Format
    [d0] [d1] [size] [offset lo] [offset hi] [text, bit 7 on the last] [d2] [size] ... [dk+1] [0]

`&139F` sets `&1766` = 1 (a page), the delay (`&1372`) = d0, the page pointer (`&136B`) = the address of d1,
and the entries shown (`&136E`) = 1. All three are operands in the code at `&136A`-`&1372`.

### Revealing and redrawing (`&136A`, every loop while `&1766` = 1)
- It walks the page from its start, drawing each entry shown so far (`&1393`). Then it counts the delay
  down; at 0 it loads the byte after the last drawn entry as the new delay, shows one more entry and draws it
  at once, and carries on counting, so a delay of 1 reveals the next entry in the same loop. A size of 0
  ends the page: `&1766` = 0, after drawing.
- So with the request's loop as loop 1: entry 1 appears on loop d0, entry i + 1 on loop A(i) + d(i) − 1,
  and the last loop drawn is A(k) + d(k) − 1. The byte after the last entry (dk+1) is never used.
- Requests come before `&12CF` in their loop. A new request starts the page again. TIME UP, CONTINUE and
  GAME OVER are requested every loop, so they never run out until the requests stop; then they run out
  their delays. A page request cancels a dissolve, and a dissolve request cancels a page (both use `&1766`).

| Page | Entries appear on loops | Last loop | Seen |
|---|---|---|---|
| SIGHTING | 1 | 30 | loops 58-87 of `run_b.py` |
| TIME UP | 1 | 25 | 24 loops after its last request (`run_a.py`, 944 → 968) |
| CONTINUE | all 5 on 1 | 10 | 9 loops after its last request (1050 → 1059) |
| GAME OVER | 1 | 30 | |
| PULL OVER | 1 | 30 | |
| ARREST (stage 1) | 6, 11, 16 | 60 | loops 667-726 |
| BONUS | 5, 8, 11 | 60 | loops 727-786 |

### Drawing an entry (`&1393`, `&13B2`)
`&1393` takes the size in A, then the offset and the text from HL + 1. `&13B2` adds the back buffer's high
byte (`&1645`) to the offset. Nothing is masked through the font: the box is opaque white with the glyphs
copied in. There's no shadow. The box's ends are a byte column each, with a pixel cut from each corner.

**Size 1** (`&146B`): the offset is line 7 of the row above the text, and the box is 10 lines.

| Lines | Left column | Each character (2 bytes) | Right column |
|---|---|---|---|
| −1 | AND `&AA` OR `&04` (right pixel white) | `&0C &0C` | untouched |
| 0-7 | `&0C` | the glyph's lines 0-7 | AND `&55` OR `&08` (left pixel white) |
| 8 | AND `&AA` OR `&04` | `&0C &0C` | untouched |

**Size 2** (`&13BC`): the offset is line 0 of a row, and the box is 16 lines, two rows. The glyph's lines 1-6
are doubled (`&1424`, `&1436`, `&1416`): white, 0, 1, 1, 2, 2, 3, 3 | 4, 4, 5, 5, 6, 6, 7, white.

| Lines | Left column | Each character | Right column |
|---|---|---|---|
| 0-1 | AND `&AA` OR `&04` | white, then glyph line 0 | untouched |
| 2-13 | `&0C` | glyph lines 1-6 twice each, line 7 | AND `&55` OR `&08` |
| 14-15 | AND `&AA` OR `&04` | glyph line 7 (14), white (15) | untouched |

The width is 1 + 2n + 1 bytes: the left column, n characters, the right column. Every page is centred by its
offset in the data.

`&1393` is also called directly, an entry at a time: the intro's "CHASE H.Q. MONITORING SYSTEM" (`&0672`,
size 1 at `&3A43`, every intro loop), the title (`&06ED`, `&0708`, `&072C`) and the redefine screen
(`&0877`-`&0885`).

### Where they go
Offsets are in the CPC's buffer; the BBC playfield's row r is the CPC's row r + 8.

| Page | Entry | Size | CPC offset | BBC playfield row, box cells |
|---|---|---|---|---|
| SIGHTING | SIGHTING OF TARGET VEHICLE | 1 | `&3A45` | 2 (box lines 15-24), 5-58 |
| TIME UP | TIME UP | 2 | `&0298` | 2-3, 24-39 |
| CONTINUE | CONTINUE | 2 | `&0257` | 1-2, 23-40 |
| | THIS MISSION | 2 | `&02D3` | 3-4, 19-44 |
| | PUSH GEAR BUTTON | 1 | `&3B8F` | 7, 15-48 |
| | BEFORE TIMER REACHES 0 | 1 | `&3C09` | 9, 9-54 |
| | TIME nn | 1 | `&3CD8` | 12, 24-39 |
| GAME OVER | GAME OVER | 2 | `&0296` | 2-3, 22-41 |
| PULL OVER | OK! PULL OVER CREEP! | 1 | `&3A4B` | 2, 11-52 |
| ARREST | OK! YOU ARE UNDER ARREST ON / SUSPICION OF FIRST DEGREE / MURDER | 1 | `&3A04`, `&3A85`, `&3B19` | 1, 3, 5 |
| BONUS | CLEAR BONUS / TIME BONUS / SCORE | 2 | `&0249`, `&0349`, `&0449` | 1-2, 5-6, 9-10; 9-54 |

### Patched text
- CONTINUE's "TIME nn" (`&12CB`-`&12CC`, written by `&20C4` every loop): nn = L >> 1, L the countdown 21 to
  0, as "10" or a space and a digit.
- BONUS (written by `&100C` before the request): the clear bonus's two leading figures at `&11A1`-`&11A2`,
  the stage and "0" (stage × 100,000) or, after a continue, a space and the stage (× 10,000); the seconds
  left at `&11B9`-`&11BA`, tens or a space, then units; the score at `&11D4`-`&11DB`, 8 digits, leading zeros
  as spaces, bit 7 on the last. The bonuses are added to the score first, so it shows the new score.

### French
SIGHTING (`&11FF`), PULL OVER (`&123D`) and the arrest page (`(&5BE2)`) have French versions with their own
offsets (centred for their lengths). TIME UP, CONTINUE, GAME OVER and BONUS are English in both languages.

### Cost on the CPC (T-states, all entries shown, `cost_cpc.py`)
SIGHTING 22,835; PULL OVER 18,031; the arrest page 51,750; BONUS 88,081.

## The dissolve (`&1337`, `&12D8`)
- **Request** (`&1337`, A the step): A ≥ 0 out (all callers pass `&10`), A < 0 in (`&F0`). One random
  number: (r AND 3), 0 taken as 1, picks pattern 1-3, so pattern 1 comes half the time. From the 3-byte
  entries at `&5308` (out) and `&5311` (in): a loop count and a starting mask address. `&1766` = 2.
- **Each loop** (`&12D8`): count − 1; if it isn't 0, the mask pointer moves by the step (16 bytes); if it is,
  `&1766` = 0 and the pointer stays, so the last mask is drawn twice. Then the back buffer's playfield (all
  8K: `&200`-`&5FF` of each line's block) is ANDed with the mask: for line l of every row, even bytes with
  mask byte 2l, odd bytes with 2l + 1.
- **Masks**: 19 of 16 bytes at `&FEB0`-`&FFCF`, in the `&C000` screen's last gap. Every byte is `&FF`,
  `&AA`, `&55` or `&00`: whole pixels kept or blacked, so they work unchanged on MODE 2 bytes.

| Pattern | Out: masks a loop | In: masks a loop |
|---|---|---|
| 1 | `&FEB0` ... `&FF10`, `&FF10` (8 loops) | `&FF10` ... `&FEB0`, `&FEB0` (8) |
| 2 | `&FF20` ... `&FF70`, `&FF70` (7) | `&FF70` ... `&FF20`, `&FF20` (7) |
| 3 | `&FF80` ... `&FFD0`, `&FFD0` (7) | `&FFD0` ... `&FF80`, `&FF80` (7) |

  Pattern 1 closes lines 0 and 7 of each row, then thins to a checker; 2 and 3 are scattered pixels. `&FF10`,
  `&FF70` and `&FFD0` are all zero: an out dissolve ends black and an in one starts black. An in dissolve's
  last loop still masks (line 0 of each row black for pattern 1); the next loop is drawn whole.
- While it runs, `&155D` zeroes the controls, the clock stops (`&1FF0` returns) and the checks after the flip
  wait (`&1766` ≠ 0 goes straight back to `&0362`).
- **Cost**: 230,091 T a loop on the CPC, measured: more than half a loop of driving.
- Seen: `run_a.py` loops 1060-1066, out pattern 2 (`&FF20` to `&FF70`, 7 loops), then in pattern 2.

## Every call site in stage 1

### Messages (priority: higher wins)
| Script | Priority | Call | Trigger | English |
|---|---|---|---|---|
| `&1AB0` | 2 | `&158A` | SPACE starts a turbo | partner: WHOAAAAA! (171 in 256) or GREAT! |
| `&1A97` | 3 | `&31A3` | a traffic car hit | partner: OH, NO! / OUCH! / YAOOOOOW! |
| `&1A57` | 5 | `&3035` | a ram (`&2FE1`) | partner: BEAR DOWN. / (OH MAN. / HARDER! / PLEASE!) / MORE, PUSH IT MORE! |
| `&1A83` | 10 | `&3879` | every 100 loops below speed 120 (`&1690`, not reset by speeding up) | partner: LET'S GET MOVIN' MAN! |
| `&1AC3` | 10 | `&3C9C` | the 19th ram | partner: ONE MORE TIME. |
| `&1AF2` | 20 | `&4087` | past the fork on the criminal's branch | partner: LET'S GO. MR. DRIVER. |
| `&1A4D` | 20 | `&4087` | past the fork on the other (and the score) | partner: WHAT ARE YOU DOING MAN! THE BAD / GUYS ARE GOING THE OTHER WAY. |
| `&1A89` | 21 | `&202B` | the clock reaches 15 | Nancy: THIS IS NANCY AT CHASE H.Q. / IF YOU KEEP MESSIN' AROUND / YOUR TIME IS GOING TO RUN OUT. |
| `&1AF8` | 255 | `&035F` | the stage starts, 64K only (in place of speech) | partner: GIDDY UP BOY! / HOLD ON MAN / LET'S GO. MR. DRIVER. |
| `&1AC9` | 255 | `&046D` | the game over sequence | Nancy: YOU'VE PICKED THE WRONG JOB / BETTER CHECK THE CLASSIFIED ADS / " " (a space); or ONE MORE TRY, / FOR BEING A GOOD BOY!; or YOU'RE A MEDIOCRE DRIVER, / SEE YOU LATER. |
| `(&5BDA)` | 255 | `&04FB` | the intro's briefing | Nancy: THIS IS NANCY AT CHASE H.Q. / WE'VE GOT AN EMERGENCY HERE. / RALPH THE IDAHO SLASHER, / IS FLEEING TOWARDS THE SUBURBS. / THE TARGET VEHICLE IS A / BLUE BRITISH SPORTS CAR.. OVER; then the partner: WE READ LOUD AND CLEAR! OVER. / ROGER! / GOTCHA, NANCY BABY! |
| `&1A14`, `&1A24` | 15 | `&32E3` | stages 2 and 4: the road's hint (`&1759` = 3, 4) | stage face: THIS IS AIRBORNE PATROL, / THE TARGET VEHICLE HAS TURNED / LEFT (RIGHT) UP AHEAD... OVER.; then the partner: WE READ LOUD AND CLEAR! OVER. |

"/" separates lines, ";" the choices. The ram's middle choice is itself a choice. The 64K start message's
third choice is the fork's `&1AF2`. Two places close the window directly (`&1E20`): quitting
(`&159C`) and gear during the briefing (`&0526`, then speech 5 and the stage).

Seen in the harness: the turbo (`run_a.py` loop 36), the crash (58, 614), the time warning (682), the slow
nag (419, after the stage start in `run_intro.py` 363), the wrong fork (248), the game over (1069), the rams
(`run_b.py` 163, 194, 199), the briefing, and the airborne patrol in stage 2. The right fork and the 64K
start message are from the code (the bot took the other branch both times; the harness is 128K).

French: each line's French pointer follows its English one. The texts differ in words and length (up to 31
characters), not in structure, faces or timing.

### Pages
| Page | Call | Trigger |
|---|---|---|
| SIGHTING (`&11DE`) | `&3C68` | the criminal's first handler call, within 20 segments; then the siren lights (`&0F55`) |
| TIME UP (`&1269`) | `&203F` | every loop of clock state 1 (time 0, the car coasting). At speed 0, speech 4 and state 2, which waits for the page to end |
| CONTINUE (`&1277`) | `&209D` | every loop of clock state 3, with effects 8 and 9 every 4 loops |
| GAME OVER (`&1259`) | `&0478` | every loop of the game over sequence unless a dissolve runs |
| PULL OVER (`&1222`) | `&1185` | the 20th ram (`&1166`) |
| the arrest page (`(&5BDC)`) | `&1003` | the stage end's state 3 → 4 |
| BONUS (`&118D`) | `&10B6` | the stage end's state 4 → 5, when the arrest page has ended |

### Dissolves
| Call | When | Step |
|---|---|---|
| `&041D` | after a flip, `&179E` 1 → 2: quit, or no continue taken; then the game over sequence | out |
| `&04DF` | the game over sequence's end: the criminal gone, the message closed; then the title | out |
| `&04ED` | the intro starts | in |
| `&052E` | the briefing closing (state 3): the intro ends when the dissolve does | out |
| `&0FB9` | the stage end's state 5 → 6, when the bonus page has ended; then the next stage | out |
| `&162F` | the stage reset (`&15B8`): each stage start, the game over sequence, the title | in |

`&15B8` also clears the message line (`&1FA6`) and blanks the face (`&1EE2`) but leaves the window's state:
a message in progress carries on.

## The BBC's data (`tools/gentext.py`)
`python tools/gentext.py build/gen [stage]` writes `build/gen/text.6502` and previews. It assembles on its own
(given `PanelAddr` and `RowBytes`), and `work/text/check_bin.py` walks the assembled bytes as the 6502 would:
every script, page entry, appearance loop, offset and glyph matches the CPC's.

- **Glyph numbers**: 0-9 the digits (0 is the O), 10 space, the letters without O, then `. , ! ' -`: 41. A
  patched figure is its own digit, and the same numbers serve both sizes. Text is glyph numbers, not ASCII,
  with its length first: the same size, and no `&1F61` lookup or bit 7 test. The length gives a box's right
  column before its glyphs are drawn. In the source the texts stay readable: `GLYPHS "OH, NO!"`, a macro
  over `TextGlyphs`, a Baron function that maps a string through `TextChars` and fails on a character with
  no glyph.
- **Font1** is byte-planar: byte i of glyph g at `Font1 + i * Glyphs1 + g`, a glyph's bytes column by
  column (left cell lines 0-7, right cell 0-7). That is the screen's own order for a glyph on a character
  row: 16 consecutive bytes. With X the glyph, each byte is `LDA Font1+i*Glyphs1,X`, with no source pointer to
  build, as the sprites' column-major layout was chosen for its 8-byte cell step. On the panel the same 16
  bytes go out through two pointers: glyph lines 0-3 to row 6 at `MsgLineTop + 8 × cell + i`, lines 4-7 to
  row 7 at `MsgLineBottom + 8 × cell + i` (4 bytes on, 4 bytes back). Two of the 16 planes cross a page if
  Font1 starts on one: at most 2 cycles a glyph.
- **No double-height font.** Size 2 doubles Font1's lines at run time as the CPC does. A precomposed one,
  dithered on the doubled grid, would cost 928 bytes and about 424 cycles a glyph against about 350 doubled.
  Doubled, each dithered pixel is 2 lines tall, a 4 × 4 checker at the BBC's aspect: compared in
  `work/text/z_cmp_font2.png` (top precomposed, bottom doubled), both read as well.
- **Faces**: 5 rows of 64 bytes, as the panel holds cells 43-50 of rows 1-5: a row is one 64-byte copy to
  `MsgFaceAt + r × 512`. `FaceLo`/`FaceHi` by the scripts' face byte.
- **Scripts**: as the CPC's, English only, with addresses as Baron labels: a choice is `&FC` and three
  `EQUW`; a segment is the face, `GLYPHS` lines, then `&FF` or `&FE` and an `EQUW`. Each requested script's
  priority is a constant (`MsgRamPrio` ...). Stage 1 has 31 nodes in 793 bytes. A stage with a face of its
  own gets the airborne patrol's two scripts too.
- **Pages**: each page is its last loop, then entries of [loop it appears, size, offset (`EQUW row *
  RowBytes + cell * 8`, the box's left cell at the text's first line), length, glyphs], then 0. The loops are
  worked out from the CPC's delays, so the 6502 compares a loop count instead of counting delays. Labels mark
  the patched glyphs: `PageContinueTime` (2), `PageBonusClear` (2), `PageBonusTime` (2), `PageBonusScore`
  (8). The page data is patched in place, as the CPC's is (sideways RAM is RAM).
- **The dissolve**: the 19 masks reordered to a cell pair's 16 bytes in screen order (byte i for cell i DIV 8,
  line i AND 7), so a record is copied straight into 16 patched immediates; `DissolveFirst` and
  `DissolveCount` for out patterns 1-3 then in 1-3.
- **Colours**: D7 pairs over 2x2 blocks of the glyph's or face's own pixels, as gensprites.py does. White is
  exact (`&3F`); the font's dark blue is black/blue, mauve blue/magenta, grey green/magenta; the faces are
  black, white and green/magenta. Glyphs and faces sit at even pixels and lines, so their parity is the
  screen's. Nothing has bit 3 set, so the sirens' palette trick is untouched.
- **Previews** (`build/gen/text_*.png`), drawn from these bytes as the 6502 would: the font at both sizes,
  the faces, every page over a sky and grass backdrop (the bonus and continue pages with sample figures), and
  four messages and the static in the panel. Laid against the CPC's screens (`work/text/a*.png`,
  `b*.png`), the boxes and text sit in the same places.

## Proposed: the 6502 side
Claude's recommendation, for Rich to decide. Cycle counts are estimates from instruction counts, not
measurements.

### What runs when
1. **Requests**, from the game logic during the loop (main RAM, calling into the bank directly, as P6 has
   the code bank paged in outside the sprite stubs):
   - `msg_request` (A the priority, the script's address): the refusal rule, then state 1. About 30 cycles.
   - `page_request` (the page's address): the page, loop 0, screen state 1.
   - `dissolve_request` (the direction): one random number, the pattern's first mask and count, state 2.
2. **The message window**, once a loop where the CPC calls `&1DD4` (after the panel's figures), drawing
   straight into the panel at `&3000`. The panel is single-buffered, so everything is drawn once, not into
   two buffers. There's no tearing worth handling: a glyph drawn under the beam shows half-old for one frame.
   Drop the CPC's re-blank every 256 idle loops.
3. **The page or the dissolve**, every loop after the world and the damage meter, into the back playfield,
   before `show`, as `&12CF`. A page is drawn whole every loop, since the road redraws the playfield.

### Cycles a loop (estimates)
| Work | Cycles | Basis |
|---|---|---|
| Message window idle | 20 | a state test |
| A character | 230 | 16 × (`LDA abs,X` 4 + `STA (zp),Y` 6 + `LDY #` 2), two pointers set |
| A new line | 2,800 + 230 | the line cleared: 496 stores |
| A face | 3,500 | 320 bytes copied; a blank 2,000 |
| A static | 22,000 | 640 generator steps at about 28 (the sum in X stepping by `&76`, s2 in Y), 320 stores; once per request, chain and close |
| Page, size-1 glyph | 257 | 16 × 12, 4 border stores, the glyph fetched, the pointer stepped |
| Page, size-2 glyph | 350 | 16 loads, 32 stores, `LDY #` each, white lines from an immediate |
| Page, an entry's box | 265 (size 1), 390 (size 2) | the end columns, 6-12 of them masked |
| SIGHTING | 6,900 | 26 glyphs, size 1 (the CPC: 22,835 T) |
| PULL OVER | 5,400 | 20, size 1 (18,031 T) |
| ARREST | 15,700 | 58, size 1 (51,750 T) |
| TIME UP, GAME OVER | 2,800, 3,500 | 7 and 9, size 2 |
| CONTINUE | 20,100 | 45 size 1 and 20 size 2 |
| BONUS | 24,300 | 66, size 2 (88,081 T) |
| Dissolve, every byte ANDed | 95,000 | 8,192 × (`LDA abs,X : AND # : STA abs,X`, 11), the 16 immediates patched once a loop (the CPC: 230,091 T) |
| Dissolve, keeping `&FF` and clearing `&00` | 8,000-81,000 by mask | 37,000-51,000 a loop on average by pattern; `gentext.py` prints each mask's |

The bonus page shows while the car is stopped at the stage end; at 24,300 it adds about a tenth to a
228,000-cycle loop. In time every page is cheaper on the BBC than on the CPC: 24,300 cycles is 12 ms
against 88,081 T, 22 ms before the CPC's wait states. Three dissolve masks are all black (6, 12, 18): those
loops could blacken the playfield's palette instead of storing 8K, if the IRQ can switch it with the flip.

Lockstep needs each static's 640 steps in the loop the CPC makes them (a request's, a chain's, a close's):
traffic and the criminal draw from the same generator in the next loop. The BBC shows one static pattern,
the first of each pair of numbers (the CPC's `&C000` buffer's); the second pattern isn't worth 320 bytes or
a second pass.

### Zero page and memory
- **Zero page**, all local to the drawing (`ZA_AUTO`): the message window 4 (two destination pointers for the
  line's halves) and 2 (the script pointer while reading); pages 7 (a destination pointer, a second for size
  2's lower row, the entry pointer, a glyph count). The dissolve can run on patched operands with none.
- **GameVars**, 17 bytes: the window's state, timer, pause, column, priority, script (2), line (2) and its
  length; the screen state; the page (2) and its loop; the dissolve's mask, count and step.

### Banks
| Part | Data | Code (estimate) | Proposed home |
|---|---|---|---|
| Message window | Font1 656, scripts 793, static table 4 | 600 | code bank |
| Pages | pages 340 (Font1 shared) | 550 | code bank |
| Dissolve | masks and patterns 316 | 250 | code bank, or the data bank |
| Faces | 646 | 80 (copy, blank) | data bank, through a stub in main RAM |

- The window and the pages share Font1, so they go together; the logic requests directly, with no paging.
  That is 2,950 bytes of the code bank's 4K, and 3,500 with the dissolve.
- The faces are copied once per speaker, so a main RAM stub paging the data bank in (as `plot_sprite`
  does) costs nothing that matters: 730 bytes of its 2.5K.
- If the code bank needs its room for the road, the dissolve moves to the data bank (about 570 bytes): it
  runs 7-8 loops at a time and costs far more than a stub.
- Main RAM keeps only the 17 bytes of GameVars and the face stub (about 20 bytes).

### Savings, if they're needed
- **Faces at 2 bits a pixel**: after dithering they use four BBC colours (black, white, green, magenta), so
  160 bytes each and a 16-byte nibble table: 304 bytes saved for stage 1, about 5,000 cycles to unpack once
  per speaker.
- **Text at 6 bits a glyph**: about 280 bytes of the scripts and pages, for a shift or two a glyph.
- **The 64K start message** is only needed without speech (P7: the speech bank is optional). **The
  airborne patrol** (471 bytes with its face) is only needed for stages 2 and 4.

## Scripts (`work/text/`)
| Script | What it does |
|---|---|
| `dump.py` | memory at `&0300` and at stage 1's first loop (`m300.bin`, `m362.bin`) |
| `decode.py` | prints the scripts and pages from a dump |
| `trace.py` | a tracer: every request, page, dissolve and static by loop, the window's and page's state after each loop |
| `run_a.py`, `run_b.py`, `run_intro.py`, `run_s2.py` | the bot through stage 1 to game over; the criminal poked close, the arrest into stage 2; the stage 1 intro; stage 2's airborne patrol |
| `shots_a.py` | CPC screens at chosen loops (`a*.png`, `b*.png`, `i*.png`) |
| `cost_cpc.py` | the CPC's T-states in `&1DD4` and `&12CF` each loop |
| `cmp_font2.py` | the precomposed double-height font against doubling at run time |
| `check_bin.py` | walks the assembled `text.6502` (`baron/w.6502`) against the CPC |
