# Digitone II SHARC track synths

Experimental, OS 1.12 only. machines-dn2 0.3 can register an external C
oscillator in the native FUNC+SYN selector. Its output passes through the
stock voice envelope, filter, pan, sends and mixer. Other tracks retain
their stock synthesis. This callback has been checked in the coupled
emulator; no hardware or timing qualification is claimed.

## Author interface

Use the existing four-field `mk2_synth` descriptor from
`mk2/machines.h`, contributing its pointer to `mk2_voice_synths`
instead of `mk2_synths`. The fields remain stable ID, stock defaults type,
name and short label. Use permanent IDs 5..31; clones share that namespace.
The companion supplies a named empty SYN page and stock AMP/FLTR controls.
The native machine selector identifies the engine as SINE.

The same mod must carry a `dn2-voice-mono32-l2-v1` artifact with a matching
`machine_id` and `entries: {"render_offset_bytes": ...}`. Require `core`
(core 0.2) and `machines-dn2`. The linker refuses a missing/mismatched
payload, conflicting IDs or registering the voice's ID as a clone too.
One SHARC mod still owns the reservation; coexistence of independent DSP
mods is separate work. Existing clone and master-output contracts remain
accepted.

```c
#include "digitone-mk2/voice.h"
void sharc_voice_render(const struct dn2_voice_input *in);
```

The 16-byte input is an output pointer, slot, unsigned 8.8 pitch and flags.
Write all 32 mono floats at 48 kHz and return nothing. Slot is 0..15,
**not the track number**: keep independent state per slot. A trigger edge's
block is silent; the next block has settled pitch and `DN2_VOICE_START`.
Reset phase on START. The stock envelope supplies release; do not use the
old master callback's newest-note selection, global gate or gain ramp.

## Context and memory

The adapter preserves PEx R0–R15 in full through PX, both halves of PX,
I0–I5/I12/I13, M0–M7/M13–M15, L0–L5, MODE1 and both ASTAT/STKY pairs.
It pins M5=0, M6=1, M7=-1, M13=0, M14=1, M15=-1, L0–L5=0, SIMD off,
32-bit floating-point rounding on, saturation/truncation off. The observed
stock entry also has SIMD off. Register banks and interrupt enablement
are retained. The other stock caller passes through without a callback.

Preserve everything else: the other processing element, accumulators,
FIFO, other DAG registers, MODE2, interrupt masks, stack bases/lengths and
the contents/depth of the hardware PC, loop and status stacks. Do not mask
interrupts. Use the short-word C call/return convention (input in R4),
return I6/I7 unchanged and retain the pinned constants needed by that
convention. The callback may declare at most **128 stack bytes**; its
adapter adds an eight-byte call frame. A declaration is not a measurement
or an instruction sandbox.

The existing 32 KiB L2 reservation contains:

| Part | Loader byte range | Size |
|---|---|---|
| Pinned adapter, including guard | `0x20090000..0x20090800` | 2 KiB |
| Author code, including 64-byte guard | `0x20090800..0x20094000` | 14 KiB |
| Author data | `0x20094000..0x20097c00` | 15 KiB |
| Zeroed adapter state | `0x20097c00..0x20098000` | 1 KiB |

Ranges exclude their end. Link the kernel at PC16 `0xbc8400`, its data
at `0x20094000`. `elekloader.sdk.sharc.voice_artifact` packages the
prelinked bytes with the pinned adapter; it does not invoke a compiler.
The linker writes the render PC and ID at `0x20097e00`. Keep your state
and writes in the author area and the supplied voice buffer.

The exact OS 1.12 hook is PC16 `0xb8251b`, loader `0x20004a36`, called by
the voice pipeline at `0x1c9459`. Its guarded six-byte stack adjustment is
`8715ffffeeff`; the adapter executes it and continues at `0xb8251e`.
The master hook and its L1 reservation are unchanged. Rebuild the adapter
from `mods/machines-dn2/voice-bridge.s` with `rebuild_voice.py`; the checked
Selache pin is `2b26d3b75c53063575bc5c820fa0d38879335187`. Its 1,696 code
bytes are padded to 2 KiB, SHA-256
`7e4f1147a0017c07d330aba3ac3b1ffa64a9fe892c3ab90e5bf27325fe7528e0`.

## Qualification

The consumer is `digitone-2-mod-hack` on `machines`: `mise run build-c`
compiles its current C source, registers **SINE (ID 6)** and includes
DigiHealth 1.5. It deliberately retains the earlier example's octave-up
tuning. Integer pitches 36..84 are supported; fractional pitch is rounded
down and unsupported pitches write zeros. The separate CLONE keeps ID 5.

Checked with the owner's OS 1.12 (SHA-256
`7e5b8a733d4ab1fdf7e5d22757f7d8eddaa3cbf71d0858874a791844c02ceb35`),
DigiKit `ded547e14e63977c1a6e808812d46243e13c43d0`, emulator SHA-256
`1058f5eb8c2cc5e148140960933ec1e9fdfc26fa71a3285a1ead93a083bb5156`:

- Native selection assigns ID/type 6. The SYN page omits FM controls;
  stock AMP volume reaches silence and the filter reduces a 2,093 Hz test
  tone by 33.4 dB.
- Input notes 36, 60, 69 and 84 measure 130.809, 523.262, 880.064 and
  2,092.966 Hz. Notes 60/64 overlap with independent output, and a stock
  track can play alongside SINE. All 16 slots were allocated successfully.
- A 24-note repeat trace includes every slot and slot reuse, with exactly
  24 START events and phase resets. With injected tick/context interrupts
  (`bc8000-bca000:80400000:127`), no halt or missing block occurred.
  The C kernel uses 44 stack bytes plus the adapter's eight: 52 observed,
  within its 128-byte declaration. This is not a hardware deadline result.
- A half-gain C source edit builds without changing an allowlist and halves
  output within final Q31 rounding (maximum error `2^-32`). Restoring the
  source reproduces the original firmware and byte-identical capture.
- Saving `001 NEW PROJECT`, switching to stock and loading that named
  project restores SINE ID/type 6 and byte-identical audio. Without SINE,
  the saved ID 6 is retained, maps to MIDI type 4 and renders exact zeros.
- The no-custom-voice build keeps section 7 stock and produces the exact
  original stock FM TONE capture after selecting stock again.

Candidate firmware SHA-256:
`ca46a25493bd13cd37ebbb73256a2820015bb63f6b324c089918a99f2932b798`.
The restored one-second capture SHA-256 is
`2b6f66d32d5d36069dfb14be648091cace2748e8e3f989e23505dec9498670d1`.
Non-main sections 2, 4, 5 and 8 remain stock. Section 7 contains the
bounded voice adapter/kernel and the guarded voice hook only.

Omitting the callback exposes FM TONE around 261.623 Hz for input note 60,
rather than silence, despite transmitted type 6. The possible remaining
stock oscillator cost is [#66](https://github.com/simonjohansson/elekloader/issues/66).
DigiKit's [voice-path findings](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/docs/findings/06-sharc-engine-and-startup.md)
and [context corrections](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/docs/findings/45-dsp-voice-context.md)
are leads; the stock-buffer silence assumption did not hold for this
candidate. #65 remains deferred. Hardware, calibrated load/timing, custom
SYN knobs and combining independent DSP mods are not qualified here.

For a device demo, build this exact candidate with `mise run build-c` and
the configured DigiHealth 1.5. Its update passes the device's update/flash
budgets and the remote input protocol works in the emulator. After the
normal OS installation, select SINE on track 1 and play notes 60 and 64
together; keep FM TONE on track 2, then check AMP volume, filter cutoff
and release. Record device audio and DigiHealth responsiveness separately
from the emulator results above before claiming hardware qualification.
