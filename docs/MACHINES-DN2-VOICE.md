# Digitone II SHARC track synths

Experimental, OS 1.12 only. machines-dn2 0.1 can register an external C
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
(core 0.1) and `machines-dn2`. The linker refuses a missing/mismatched
payload, conflicting IDs or registering the voice's ID as a clone too.
One SHARC mod still owns the reservation; coexistence of independent DSP
mods is separate work. The master-output SHARC contract is unchanged.

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

## Example and checks

The external `digitone-2-mod-hack` consumer builds SINE with
`mise run build-c`, including DigiHealth and CLONE FILTER. The C example
supports integer MIDI pitches 36..84 and plays one octave above its input;
fractional pitch rounds down and other pitches produce zeros. Each voice
slot keeps independent phase and resets it on START.

Run `python tests/test_units.py` and the TypeScript suite for the artifact,
registration, callback binding and stack-bound checks. Runtime checks must
cover native selection, overlapping notes and slot reuse, stock-track
coexistence, AMP/filter controls, preset copy and saved/missing registrations.
The coupled emulator checks these paths; hardware timing needs separate
qualification. Investigation evidence is in
[the machine roadmap](https://github.com/simonjohansson/elekloader/issues/58).
