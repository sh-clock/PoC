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

# all 8 local headers fog_poc.c includes (V41 E-7: was 2-of-8, so editing
# e.g. rain_tim_data.h never triggered a rebuild)
$(BIN): $(SRC) src/snow_tim_data.h src/rain_tim_data.h src/flare_tim_data.h \
    src/dr_wave_data.h src/water_tim_data.h src/tv_tim_data.h \
    src/sh_sine_table.h src/sh_font8.h
	$(CC) $(CFLAGS) -o $(BIN) $(SRC) $(LDFLAGS)

clean:
	rm -f $(BIN)

.PHONY: all clean
