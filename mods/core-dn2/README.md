# core (Digitone II)

The boot copier and the hook bus for Digitone II OS 1.12. Every set of
linkable (format 2) mods for the Digitone II needs it. On its own it changes
nothing the unit does.

It builds the shared [../core/core.s](../core/core.s) and
[settings.s](../core/settings.s) with the Digitone II's addresses
(`mod.json`), and the Digitakt II's
[../core-dt2/personalize.s](../core-dt2/personalize.s) unchanged: the
PERSONALIZE builder ends the same way. There is no `fast.s` (SRAM is not
qualified, so there is no `.fast` area) and no `render.s` (the audio renders
on the DSP).

- **At boot** (the OS entry's call at 0x40000538, which called 0x400019b0,
  the Digitakt II's: it sets the VBR to 0x40000000 and returns), `boot`
  copies the RAM image the linker built to the device's DDR area
  (0x47F00000), zeroes `.bss`, and goes on to the call it replaced, before
  the OS copies its data to SRAM and clears its `.bss`. It does not start
  DTIM0 (`NO_DTIM0`): as on the Digitakt II, the OS reads its counter at ten
  sites (0xfc07000c) and never writes its mode register, so stock reads it
  as stopped, and this core keeps that.
- **The sites** become the Digitakt II's events, with the same prototypes
  ([docs/ADAPTING.md](../../docs/ADAPTING.md), "The hook bus"):

  | site | was | event |
  |---|---|---|
  | 0x4002e464 | `jsr 0x4011d5d4`: returns the view controller's byte +0x20 | `ev_tick` |
  | 0x4002e4ca | `jsr 0x4011d60a`: `drawAll(ctrl, bmp)`, the 128x64 frame | `ev_draw` |
  | 0x4002f20c | `jsr 0x4002c5c8`: `Brain::key(brain, event)` | `ev_key` |
  | 0x4002f256 | `jsr 0x4002c55c`: `Brain::enc(brain, event)` | `ev_enc` |
  | 0x4009ff88 | `movea.l (a2),a0; pea 2.w`, the SETTINGS builder 0x4009fbe0 going on at 0x4009ff8e | `ev_settings` |
  | 0x400987a2 | `movem.l $18(a7),d2-d6/a2-a6`, the end of the PERSONALIZE builder 0x40097eac, after NOTE EDIT MENU | `ev_personalize` |

  `core_additem(menu, row)` adds a row with the firmware's routines:
  `operator new` 0x40120544, `MenuItem`'s constructor 0x401173b8,
  `Menu::addItem` 0x40116bee and the `std::function` manager 0x4018de3e
  (for `PFSs15FileStorageInfoE`, as on the Digitakt II). A row's label
  callback builds a `std::string` with 0x401ceab8, as the firmware's own
  labels do (0x4002b294). In SETTINGS the row comes after SYSTEM; in
  PERSONALIZE after NOTE EDIT MENU.

Each address was found by the Digitakt II 1.17's code, with the addresses
masked, then checked in the Digitone II's own, with what the shared
sources assume about it:
- the UI loop around the tick, draw, key and encoder sites is the
  Digitakt II's instruction for instruction. The tick routine is
  `move.l 4(sp),a0; move.b $20(a0),d0; rts`, what `core_tick` does after
  its handlers. The draw site pushes the frame's Bitmap and then the view
  controller; the key and encoder sites push the event and then the brain.
  Each routine is its site's only caller. `Brain::key` hands the event to
  the listeners at brain +0x94..+0x98, as on the Digitakt II.
- the SETTINGS builder keeps the menu in a2 and its site is the two
  instructions `core_settings` replays.
- the PERSONALIZE builder makes its last row exactly as `core_additem`
  does: `new(0x54)`, the constructor with (item, label, select, draw,
  change, -1, 8), each callback a 16-byte `std::function` (manager at +8,
  invoker at +12), then `Menu::addItem(menu, item)` with the menu in a4;
  it ends with the `movem`, `lea $80(a7),a7` and `rts` that `personalize.s`
  replays. Its frame is the Digitakt II's (0x80 bytes).
- `KeyEvent` (built by 0x40116278 from the UI queue's message): +12 the key
  code and +16 the action, as on the other devices (docs/ADAPTING.md);
  read back in the emulator: a tap of TRIG 1 gives code 25, a release 0x10.

`tests/test_digitone2.py` checks each of these against the stock file.

Build it with the SDK (it needs m68k binutils; with Homebrew's
`m68k-elf-binutils`, set `ELEKLOADER_CROSS=m68k-elf-`):

```bash
python -m elekloader.sdk.build mods/core-dn2 --stock Digitone_II_OS1.12.syx      # out/core-0.2.elemod
python -m elekloader.lint mods/core-dn2/out/core-0.2.elemod --stock Digitone_II_OS1.12.syx
```

Checked in digikit's emulator (ColdFire only, no DSP, so no audio; 23 Oct
2026):
- core alone: under the same session as stock (a trig, two encoders, the
  TEMPO page, SETTINGS, PERSONALIZE, PLAY and STOP), every one of its 12
  screens is identical to stock's.
- with [hello-marker-dn2](../../examples/hello-marker-dn2): the screen
  differs from stock only in the 3x3 square; after boot the area holds the
  linked run image byte for byte.
- with [hooks-check-dn2](../../examples/hooks-check-dn2): every event fires,
  the rows are listed once in SETTINGS and PERSONALIZE after reopening each,
  and the handlers' order and a taken key behave as its README says.

0.1 hooked only boot and draw. The first 0.2 builds stalled during USB
transfer before flashing: their decoded updates exceeded 2 MiB. The
profile now caps updates at 2 MiB, measured on a unit rather than found
in code ([docs/DEVICES.md](../../docs/DEVICES.md)). The smaller core-only
CO02 from source `e12a80b` (sha256
`90cdea1d94cbc39907353bc1f3b70c710b0b0e2ef44423e3b5679fdd12cb1832`)
flashed over USB with elektroid-cli on 23 Oct 2026. Its version was read
back as `CO02` after reboot; the user reported a cold boot after 10 seconds
off. A one-minute seeded MIDI exercise completed without transport errors;
fresh device-info and project-directory replies were identical before and
after, and the user reported it playing and responsive. This is smoke
evidence, not full hardware event or audio/workload qualification; HM02
and HC02 have not been flashed.
