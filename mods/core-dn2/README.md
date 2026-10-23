# core (Digitone II)

The boot copier and the hook bus for Digitone II OS 1.12. Every set of
linkable (format 2) mods for the Digitone II needs it. On its own it changes
nothing the unit does.

0.1 is a checkpoint: it boots and runs `ev_draw`. It builds the shared
[../core/core.s](../core/core.s) with the Digitone II's addresses
(`mod.json`). `core.s` names the `ev_tick`, `ev_key` and `ev_enc` tables and
the key and encoder routines, so 0.1 declares those tables and gives those
addresses, but it does not hook their sites yet: a handler subscribed to
them links and is never called. There is no `settings.s`, `fast.s` (SRAM is
not qualified) or `render.s` (the audio is on the DSP).

- **At boot** (the OS entry's call at 0x40000538, which called 0x400019b0,
  the Digitakt II's: it sets the VBR to 0x40000000 and returns), `boot`
  copies the RAM image the linker built to the device's DDR area
  (0x47F00000), zeroes `.bss`, and goes on to the call it replaced, before
  the OS copies its data to SRAM and clears its `.bss`. It does not start
  DTIM0 (`NO_DTIM0`): as on the Digitakt II, the OS reads its counter at ten
  sites (0xfc07000c) and never writes its mode register, so stock reads it
  as stopped, and this core keeps that.
- **The sites:**

  | site | was | event |
  |---|---|---|
  | 0x40000538 | `jsr 0x400019b0`: sets the VBR | (boot) |
  | 0x4002e4ca | `jsr 0x4011d60a`: `drawAll(ctrl, bmp)`, the 128x64 frame | `ev_draw` |

  Not hooked yet (the next core): the tick at 0x4002e464 (`jsr 0x4011d5d4`),
  the key at 0x4002f20c (`jsr 0x4002c5c8`, `KEYDISP`) and the encoder at
  0x4002f256 (`jsr 0x4002c55c`, `ENCDISP`).

Each address was found by the Digitakt II 1.17's code, with the addresses
masked, then checked in the Digitone II's own: the UI loop around both
sites is the Digitakt II's instruction for instruction (the draw site
pushes the frame's Bitmap, then the view controller, as `core_draw`
expects), and each routine is its site's only caller.
`Bitmap::fillRect`, for hello-marker-dn2, is 0x40114b22: the Digitakt II's
0x401131ae whole (a twin at 0x40114f62 differs in one instruction).

Build it with the SDK (it needs m68k binutils; with Homebrew's
`m68k-elf-binutils`, set `ELEKLOADER_CROSS=m68k-elf-`):

```bash
python -m elekloader.sdk.build mods/core-dn2 --stock Digitone_II_OS1.12.syx      # out/core-0.1.elemod
python -m elekloader.lint mods/core-dn2/out/core-0.1.elemod --stock Digitone_II_OS1.12.syx
```

Checked in digikit's emulator (`boot_gate --base <stock sha>`, ColdFire
only, 23 Oct 2026): alone, it boots to the main screen, and that screen is
identical to stock 1.12's. With [hello-marker-dn2](../../examples/hello-marker-dn2)
the screen differs from stock in exactly the 3x3 square at (125-127,
61-63). After boot, `panel_drive` read the area back: it holds the linked
run image byte for byte, with `.bss` zero. Not yet run on a unit.
