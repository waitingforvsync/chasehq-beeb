# Chase H.Q. → BBC Micro

A version of the Amstrad CPC disc version of *Chase H.Q.* (`docs/chasehq.dsk`, git-ignored) for the BBC Micro:
MODE 2, sideways RAM, written in Baron. The owner is Rich Talbot-Watkins, an expert BBC programmer and the
author of BeebAsm and Baron, so pitch explanations at that level. Use the `beeb-baron` skill for all 6502.

## Read first
- `docs/plan.md`: what the CPC version is (measured), the BBC design, the phases.
- `docs/decisions.md`: the decision log. Record new decisions there in Rich's words, with the date. Never mark
  your own recommendation as decided: it stays Proposed until Rich agrees.
- `JOURNAL.md`: what's been done, with measurements. Keep it up to date.
- `docs/cpc-*.md`: specs of the original, from its code.

## Rules
- **Emulator: jsbeeb-mcp only.** Never launch b2 or talk to its HTTP API: other sessions use it. Create one
  jsbeeb machine at a time and destroy it when you're done.
- **Memory and processes:** the machine has 12 GB, shared with other sessions. Run one heavy process at a
  time and at most one review agent at a time. Never print or copy a whole emulator memory to the terminal.
- **Don't transliterate the Z80.** Get a spec from the code and write the 6502 that suits the 6502: indexed
  tables, self-modification, unrolled hot loops. Where the original is wasteful, do better (Rich,
  2026-10-31).
- **Review:** when a feature works, have an agent review its code for optimisations (Rich, 2026-10-31).
- **Commits:** Rich makes the commits in this repo. Don't commit here unless he asks.
- **Release:** a disc worth releasing goes to `~/dev/waitingforvsync.github.io/beeb/chasehq.ssd`: copy it
  there, commit only that file in that repo, and push (Rich, 2026-10-31; as Teddy Boy and Critical Mass).
- Generated data from the CPC disc goes in `build/` (git-ignored), made from the `.dsk` at build time.

## Toolchain
- **Baron** (`baron` 0.6): `make` builds `build/chasehq.ssd` (its title the build's date and time), with a
  `-v` listing in `build/chasehq.lst` and symbols in `build/chasehq.json`.
- **Python:** `.venv/bin/python` (git-ignored: skoolkit, z80, pillow, py65, numpy). Recreate with
  `python3 -m venv .venv && .venv/bin/pip install skoolkit z80 pillow py65 numpy`.
- **The CPC reference** (`tools/cpc.py`): the original running on kosarev's Z80 (the `z80` package) with a
  minimal CPC round it. `CPC()` starts at `&BA00` with everything loaded; `run_to(addr)` runs to a breakpoint;
  `run_frames(n, keys_for)` runs game loops, each to the flip at `&0DCD`; `screen_png(path)` renders what's
  shown. SkoolKit's own simulator can't be used: it treats `&0000`-`&3FFF` as ROM.
- `tools/cpcdsk.py` reads the disc's files; `tools/z80trace.py` finds code by recursive descent;
  `.venv/bin/sna2skool.py -H -o 0 -s START -e END -c 0 dump.bin` disassembles a 64K dump (named `.bin`).
