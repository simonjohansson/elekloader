# DT2 offline preparation for the first sine

Status on 2026-10-24, for [#34](https://github.com/simonjohansson/elekloader/issues/34)
and [#40](https://github.com/simonjohansson/elekloader/issues/40): exact Digitakt II
1.17 stock, a post-master hook, note delivery, and a small memory candidate have
independent offline evidence. There is no DT2 SHARC profile, runtime adapter or
flashable sine in Elekloader yet. The owner has no DT2 available; physical
qualification remains pending. This work does not delay the DN2 sine.

## Repeat the stock check

```sh
mise exec python@3.12.13 -- python examples/sharc-dt2-probe/check_stock.py \
  /path/to/Digitakt_II_OS1.17.syx
```

This uses Elekloader and the Python standard library. It validates exact stock
identity, section 7 records, seven code landmarks, the sender analysis region,
an exact no-change outer rebuild, and refusal of a damaged boot header. It writes
no firmware and grants no allocation. A wrong or missing stock file fails.
No compiler or Digikit setup is needed for this check.

| DT2 1.17 measurement | Value |
| --- | --- |
| Stock SHA-256 | `26c22f6652625ac2cfd47f7ee970d388ed8b6427dae3563c0a6a2f2d334350d5` |
| Main SHA-256 | `a1e7b657b705eba1a19d81c33c1e11ba9c409816447ad74005d7bbf36da6d964` |
| Stored section 7 SHA-256 | `39113a8ae7f7ac7336bda4a56eeb45108f0618ea451bcf9f466803017184375d` |
| Decoded section 7 SHA-256 | `0f514a12a2255f5c081e292c47f1f29462003177658da4bbae0a22fd737fffa2` |
| SysEx / container bytes | 1,882,016 / 1,484,992 |
| Stored / decoded DSP bytes | 184,856 / 321,016 |
| Records / FILL records | 104 / 42 |
| FIRST / INIT / FINAL | 2 / 1 / 1 |
| Main application FIRST | offset `0x2974`, PC16 `0x1c1338`, distance `0x4bc74` |
| FINAL / end | `0x4e5e8` / `0x4e5f8` |
| Highest boot-loaded L2 endpoint | `0x2001ab7c`; not an allocation boundary |

The 828-byte ColdFire sender at `0x400cd0d8` hashes to
`9ccb1f4780bcca7abbe0f34777d1823f0a1351871c7bf0cf5912192ce92ac923`.
Its two staging buffers support the same distinct limits as DN2: stored DSP
`0x100000` bytes and decoded DSP `0xfffff` bytes, including room for the command
byte. The DT2 flash container limit is 3 MiB. Its current Elekloader profile
has **no measured `update_max`**; flash capacity must not be presented as a
USB receive limit. Physical upload sizing is a separate remaining gate.

## The smaller port starts at the post-master hook

All instruction addresses here are PC16; L1 loader byte =
`0x28000000 + 2 * PC16`. Data addresses are core bytes and do not get multiplied
by two. These DT2 addresses were checked against the exact stock above.

| Landmark | Address / result |
| --- | --- |
| Proposed post-master hook | `0x1c80f2`, displaced `I7 = modify(I7, -4)` in normal words; successor `0x1c80f5` |
| Delayed caller | `0x1c311f`, with frame stores at `0x1c3122` and `0x1c3123`; continuation `0x1c3126` |
| Master left / right | core bytes `0x25f180` / `0x25f200`, 32 binary32 samples each |
| USB pack call | `0x1c3160` calls `0x1c28b5` after the proposed hook |
| DAC pack call | `0x1c7734` calls `0x1c74a1` after the orchestrator returns |
| Control-frame copy | `0x1c2c71` loads destination `0x2558dc`; loop copies 512 halfwords |
| Full voice-render entry | `0x1c4ecf`; different context and scope from the master hook |

Digikit finding 55 calls the earlier DT2 routine `0x1c14e7` “H1”; its chosen
FX hook is the later `0x1c80f2`. Do not confuse those sites, or copy DN2's
`0x1c244d` hook or displaced stack adjustment into DT2.

A diagnostic at the proposed entry replaces only the master data with
alternating +/-0.125 on the left and -/+0.0625 on the right. Resuming the
stock code leaves that master unchanged and yields exactly:

- DAC ring `0x261cc8`: interleaved `-round(sample * 2^31)`.
- USB ring `0x262138`: master in words 0/1 of each 16-word frame,
  `round(float32(sample * float32_bits(0x3fb6db6e)) * 2^31)`.

The observed completed half is `(DM(0x25f780) & 1) ^ 1`. This proves the
modeled output route for a diagnostic signal; it does not install or execute a
new oscillator, or qualify either physical output.

## Recovered context and bounded memory evidence

The PX-fixed Digikit source pin is
`ded547e14e63977c1a6e808812d46243e13c43d0`. A DT2 cold state was built from
this stock's own section 7 plus the recovered ADSP-2156x hardware-reference
reset tables. No DN2 snapshot was reused. The DSP reached idle after
238,000,000 modeled instructions. The coupled boot reached ready at ColdFire
instruction 1,185,735,675; its 8,540 frames had no missing SPORT blocks or halt.

The current firmware-free shared interpreter reports core fingerprint
`e30cc3679e9a4b58439be924d5929f609bb42aec47b9441472a5c59c900a6c4c`.
Its independent replay matches the first 687 SPI replies and SPORT blocks of
the coupled trigger capture. It reaches `0x1c80f2` after 196,825 instructions
in the first idle frame and 197,006 in the first trigger frame.

The observed entry has `R4=0x25f180`, `MODE1=0x39011cf8`, `MODE2=0x21`,
`CMMR_SYSCTL=0x16004`, `I6=0x2cb3c0`, `I7=0x2cb3b8`,
`B6=B7=0x2ca5a0`, `L6=L7=994`, `M6=1`, `M7=-1` and `PCSTKP=0`.
The two whole-frame audits observed stack writes in loader bytes
`[0x282cb19c,0x282cb524)`. A port must preserve the circular stack, register
banks, retained loop resources, interrupts and displaced instruction; copying
only argument registers is insufficient.

The experimental candidate is **2 KiB at loader bytes
`[0x282dd600,0x282dde00)`** (core bytes `[0x2dd600,0x2dde00)`). It is not
currently owned by an Elekloader profile. It lies within physical L1 capacity,
above this stock's block-1 loaded endpoint `0x2d7564` and below the configured
cache tail `0x2ec000`. Those bounds alone do not establish ownership.

| Independent whole-frame access audit | Idle frame | First trigger frame |
| --- | ---: | ---: |
| Instructions through hook to RTOS idle | 208,863 | 209,046 |
| DM/PM reads | 65,902 | 65,972 |
| DM/PM writes | 49,456 | 49,526 |
| Unknown addresses / candidate accesses | 0 / 0 | 0 / 0 |
| Python/native modeled state differences | 0 | 0 |

The observer includes attempted reads, absent bytes, same-value writes and
alias resolution. Its self-check exercises these cases before the run.
Separately, both frames run for 666,667 instructions with the whole candidate
filled with `0xa5`, then `0x5a`: both patterns remain intact, and all modeled
state and memory outside the candidate, SPI replies and SPORT blocks match
the unmodified run. Canary survival alone would not prove the absence of reads;
the access audit supplies that narrower evidence.

Digikit's FX implementation instead allocates in L2 beyond `0x2001ab7c`.
Its broader scenario canaries are useful prior evidence, but its own notes
leave unexercised paths open. Exclude DT2's referenced window
`[0x200fa000,0x200fe000)` and Boot ROM workspace
`[0x200fe000,0x20100000)`. The small L1 candidate above avoids importing
Digikit's broad allocation claim into Elekloader.

## Notes reach the DSP, but pitch is not a gate

With the fresh default project and no sample card, MIDI channel 1 notes 60 and
72 produce `0x3c00` and `0x4800` at frame halfword 1. Channel 2 note 64 produces
`0x4000` at halfword 2. Velocity 100 appears as `0x6400` at halfwords `0x1a`
and `0x1b` respectively. A panel TRIG 1 also delivers note 60 / velocity 100.

In these captures, note-on pulses the corresponding track bit for one frame
at wire byte offsets `0x22` and `0x26`; note-off pulses it at `0x24` and `0x28`.
Track 1 uses bit 0 and track 2 bit 1. **Pitch and velocity remain set after
note-off.** A sine gate therefore needs the event masks or a separately
verified voice-record gate. The relationship between the duplicate masks,
all tracks, sequencer behavior and panic handling remains to be checked.
Channel 16 produced no event under this default configuration; do not assume
MIDI channel N always maps to track N.

All ordinary captured SPORT blocks were silent because no sample card was
attached. This is valid evidence of control delivery and an idle/triggered
execution path, not evidence of rendering a loaded sample.

## Next small slice and remaining gates

1. Adapt only the finite master bridge for entry `0x1c80f2`, using the
   candidate as an experimental local patch. Prove empty-handler equivalence,
   omitted/redirected-hook failures, full context/interrupt preservation and
   canaries on these exact idle and trigger states before granting a profile
   range. Keep code, state and stack within the measured bound.
2. Drive the existing sine from one verified track's note-on/off masks and
   pitch; compare C and assembly behind the same adapter. Demonstrate an
   octave change and silence after release in the emulator. This needs no
   machine page, sample storage or general voice adapter.
3. Broaden ownership checks to loaded-sample and relevant project/recording
   paths, including first accesses and boot-time initialization. The present
   two frames do not prove lifetime ownership. Resolve the DT2 upload budget
   and keep processor stepping unknown until observed.
4. When a DT2 is available, include the owner's DigiHealth fork, flash the
   narrow build, and measure pitch, note release, stereo/DAC/USB routing,
   stability and timing. Leave #40's physical acceptance unchecked meanwhile.

The reset generator flattens boot records and does not execute Boot ROM INIT.
The emulator uses approximate reciprocals, binary32 register/arithmetic
modeling, NW32 options and some modeled zero reads. Its 1 GHz clock is a model,
not a measured DT2 silicon frequency. None of this replaces device checks.

## Evidence and sources

The local investigation, private snapshots, scripts and reports are preserved
in `out/sharc-dt2-probe/`. They are ignored firmware-derived evidence and must
never be committed. `LOCAL-REPRO.md` there records the full machine paths and
commands; the stock checker above is the portable public reproduction route.

- [Digikit DT2 device data](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/devices/digitakt-ii.toml)
  and [1.17 anchors](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/devices/ports/dt2-1.17.toml).
- [Digikit post-master hook, rings and FX adapter](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/docs/findings/55-fx-adapter.md).
- [Digikit sender, memory and canary research](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/docs/findings/06-sharc-engine-and-startup.md).
- [dn2_firmware_explore DT2 comparison](https://github.com/angellinares/dn2_firmware_explore/blob/c06063fb99680c333b356d22919ad67a40d108ec/docs/dt2-machine-port.md):
  useful structural evidence; its reported 1.16 DSP hash matches the measured
  1.17 hash, but this run did not independently open a 1.16 stock file.
- [ADSP-2156x data sheet](https://www.analog.com/media/en/technical-documentation/data-sheets/adsp-21562-21563-21565-21566-21567-21569.pdf)
  for physical address capacity; [reset provenance](SHARC-CONTEXT.md) for
  the recovered hardware-reference input.

The checker and observations are original Elekloader work. Digikit is an
external AGPL research oracle; no emulator or FX adapter implementation was
copied into the Elekloader runtime.
