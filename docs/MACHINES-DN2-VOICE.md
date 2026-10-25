# DN2 track-synth investigation

Issue #60 extends the selectable stock clones with a C oscillator before
the stock voice envelope and filter. This page records the first checked
boundary; it is not a released callback contract or a playable mod.

## Checked stock entry

On the owner's Digitone II OS 1.12 (SHA-256
`7e5b8a733d4ab1fdf7e5d22757f7d8eddaa3cbf71d0858874a791844c02ceb35`),
the helper at PC16 `0xb8251b` begins with a six-byte stack adjustment,
`I7 = MODIFY(I7, -18)(NW)`. Its loader bytes are `8715ffffeeff`;
continuation is PC16 `0xb8251e`. The voice-pipeline call is at `0x1c9459`.
These were decoded from section 7, rather than copied from another OS.

A stock coupled-emulator trace observed all 16 slots:

| Value at entry | Observation |
|---|---|
| Slot | `16 - R15`, ranging from 0 to 15 |
| Voice buffer | `R8 == R12 == 0x804acf90 + 128 * slot` |
| I6 / I7 | `0x2d15a8` / `0x2d15a0` |
| M5 / M6 / M7 | 0 / 1 / -1 |
| M13 / M14 | 0 / 1 |
| MODE1 | `0x39011cf8` |
| Hardware PC / loop stack depths | 0 / 0 |

The trace covers 14 idle audio blocks with no DSP halt or missing block,
using DigiKit `ded547e14e63977c1a6e808812d46243e13c43d0` and emulator SHA-256
`1058f5eb8c2cc5e148140960933ec1e9fdfc26fa71a3285a1ead93a083bb5156`.
It establishes entry arguments, not preservation by a new wrapper,
interrupt safety, stack headroom or physical-device behavior. A wrapper
must also distinguish the helper's other caller and preserve its behavior.

DigiKit's [voice-path investigation](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/docs/findings/06-sharc-engine-and-startup.md)
and [context corrections](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/docs/findings/45-dsp-voice-context.md)
are leads for the stock gain, envelope and filter stages after this helper.
The master-output bridge's stack and register qualification does not
qualify this call site.

## Isolated C experiment

An emulator-only injection at that helper calls a compiled C oscillator for
slot 0, with the external sine's table and octave-up phase advance. The
native CLONE fixture and DigiHealth 1.5 supply selection and remote input;
the production mod artifact and firmware builder remain unchanged.

With input note 60, a 300 ms positive-crossing measurement gives 523.268 Hz
(expected 523.251 Hz, +0.056 cents). The callback ran 1,500 times in the
one-second capture. The stock envelope's release remains audible: left
channel RMS is 0.005993 while held, 0.000889 at 100–200 ms after release,
and 0.000058 at 300–400 ms after release. DSP health reported no halt or
missing block. The capture differs from the unchanged FM TONE reference.

This prototype has 1,228 adapter code bytes and 798 C code bytes. The C
body reserves 48 stack bytes and has no nested calls, plus the adapter's
eight-byte call frame. Those figures motivate the proposed bounds below;
they do not measure interrupt headroom or qualify a public stack limit.
The injected adapter only targets slot 0 and does not establish native
custom-type dispatch, coexistence or the final build workflow.

## Proposed next boundary (approval pending)

- Add `dn2_voice_synths`, a separate contribution table using the existing
  four-field synth descriptor. Existing compiled clone descriptors remain
  unchanged. An entry uses its real machine ID on the DSP; its SYN page
  must identify SINE and omit unrelated FM controls. Stock AMP/FLTR stay.
- Add a voice-specific SHARC artifact contract with a machine ID and one
  render entry. The linker must match that ID to the native registration
  and refuse missing or conflicting ownership. Keep existing master-output
  artifacts accepted under their current contract.
- Keep the existing 32 KiB reservation. Allow at most 2 KiB of pinned
  adapter code and 1 KiB of adapter state inside it; the rest holds the
  mod's code and state. Qualify an initial 128-byte callback stack limit
  at this hook, without inheriting the master's allowance.
- Pass the individual slot's output, pitch and retrigger information to
  C. Keep independent phase per slot and use the stock envelope for
  release. The existing external C source advances phase twice per sample;
  preserve its documented octave-up tuning for this increment.

Before acceptance, test the real external source build with DigiHealth,
callback omission or mutation, overlapping notes, release/retrigger and
slot reuse, a stock track alongside SINE, filter response, switching away,
project persistence and the no-custom-voice control. Entry tracing and a
privately injected hook experiment do not satisfy those checks. Issue #65
remains deferred.
