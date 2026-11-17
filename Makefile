# Silent Hill fog+snow PoC — GLTF-native edition
# Linux/POSIX build. No dependencies beyond libc/libm.
# zlib (PNG output compression) and SDL2/X11 (window) are loaded at runtime
# via dlopen when present — never build-time requirements.

CC      ?= cc
CFLAGS  ?= -O2 -std=c99 -Wall -Wextra -Wno-unused-parameter
LDFLAGS ?= -lm

SRC = src/fog_poc.c
BIN = fog_poc

all: $(BIN)

$(BIN): $(SRC) src/snow_tim_data.h src/sh_font8.h
	$(CC) $(CFLAGS) -o $(BIN) $(SRC) $(LDFLAGS)

clean:
	rm -f $(BIN)

.PHONY: all clean
