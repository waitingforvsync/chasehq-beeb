# Makefile - the BBC Micro build.
#
#   make           build/chasehq.ssd: !BOOT (*OPT 4,2); CHASEC and CHASED, the sideways RAM banks packed;
#                  CHASE2, main RAM's code, the panel and the loader. Its title is when it was built
#   make release MSG="what's new"
#                  the disc to the site (SITE/beeb/chasehq.ssd, which a jsbeeb link loads), committed there
#                  alone with this repo's commit named, and pushed
#   make clean
#
# The data (build/gen) comes from the CPC disc, docs/chasehq.dsk (git-ignored), through tools/gendata.py,
# which runs the original in tools/cpc.py. Claude's emulator is jsbeeb, through jsbeeb-mcp only.

BARON ?= baron
PY ?= .venv/bin/python
SITE ?= $(HOME)/dev/waitingforvsync.github.io
RELEASE = beeb/chasehq.ssd
BUILD = build
GEN = $(BUILD)/gen
DSK = docs/chasehq.dsk

# the disc's title: when it was built, YYMMDD-HHMM
TITLE := $(shell date +%y%m%d-%H%M)

SRC = src/boot.6502 src/chasehq.6502
GENOUT = $(GEN)/gen.6502 $(GEN)/panel.bin $(GEN)/siren.6502
ROADOUT = $(GEN)/road.6502
SPROUT = $(GEN)/sprites.6502
SPEECHOUT = $(GEN)/speech.6502 $(GEN)/speech.bin
TEXTOUT = $(GEN)/text.6502 $(GEN)/dissolve.6502
DEPS = $(wildcard src/*.6502) $(GENOUT) $(ROADOUT) $(SPROUT) $(SPEECHOUT) $(TEXTOUT)

all: $(BUILD)/chasehq.ssd

$(GENOUT) &: tools/gendata.py tools/cpc.py tools/cpcdsk.py $(DSK) | $(BUILD)
	$(PY) tools/gendata.py $(GEN)

$(ROADOUT): tools/genroad.py tools/gendata.py tools/cpc.py tools/cpcdsk.py $(DSK) | $(BUILD)
	$(PY) tools/genroad.py $(GEN)

$(SPROUT): tools/gensprites.py tools/gendata.py tools/cpc.py tools/cpcdsk.py $(DSK) | $(BUILD)
	$(PY) tools/gensprites.py $(GEN)

$(SPEECHOUT) &: tools/genspeech.py tools/cpc.py tools/cpcdsk.py $(DSK) | $(BUILD)
	$(PY) tools/genspeech.py $(GEN)

$(TEXTOUT) &: tools/gentext.py tools/gendata.py tools/cpc.py tools/cpcdsk.py $(DSK) | $(BUILD)
	$(PY) tools/gentext.py $(GEN)

$(BUILD)/chasehq.ssd: $(DEPS) | $(BUILD)
	$(BARON) -v --symbols $(BUILD)/chasehq.json -o $@ --title $(TITLE) --opt 2 $(SRC) > $(BUILD)/chasehq.lst

$(BUILD):
	mkdir -p $@

# Only the disc is committed there (other projects' releases share the repo): pulled first, so the push
# goes on top of theirs.
release: $(BUILD)/chasehq.ssd
	@test -n "$(MSG)" || { echo 'make release MSG="what changed"'; exit 1; }
	git -C $(SITE) pull --ff-only --quiet
	cp $< $(SITE)/$(RELEASE)
	git -C $(SITE) add $(RELEASE)
	git -C $(SITE) commit --quiet -m "Chase H.Q.: $(MSG) (chasehq-beeb $$(git describe --always --dirty 2>/dev/null || echo uncommitted))" -- $(RELEASE)
	git -C $(SITE) push --quiet

clean:
	rm -rf $(BUILD)

.PHONY: all release clean
