# Optional DN2 SHARC callback measurement

For Digitone II OS 1.12, `dn2-master-mono32-l2-metrics-v1` adds callback
measurement to the existing exclusive L2 master-output app. Pair its artifact
with [core-dn2-metrics](../mods/core-dn2-metrics/README.md). Ordinary L1 and
unmeasured L2 apps keep core-dn2 and their existing build path. The compiler
and assembler remain the mod project's choice; Elekloader packages their
prelinked artifact with the existing five keys and normal SDK/lint/patch
commands. No per-program code allowlist is added.

Compile/link for the same L2 addresses and supply the same init/render
callbacks as [the ordinary ABI](SHARC-DN2-ABI.md). Select the measurement ABI
in the generated artifact and build the matching core:

```sh
python -m elekloader.sdk.build mods/core-dn2-metrics --stock "$DN2_STOCK"
```

Build the app normally, then lint/patch it with that core. A mismatched core,
inert measured app, changed pinned core, competing channel owner, overlapping
memory or excessive stack declaration refuses. Instrumentation needs no
change to the app's DSP instructions. The optional external C/ASM example
commands compile their current source and choose this pair themselves.

## Memory and stack

L2 remains exactly `[0x20090000,0x20098000)`, with no extra stack. The pinned
measurement core reuses 920 bytes of the existing L1 app gap: 768 code bytes
including the guard and 152 state bytes. Its authored instructions occupy
628 bytes; actual state occupies 76. The original bridge bytes and fixed
pitch table remain unchanged. Ordinary L1/unmeasured builds retain their
byte-exact output and 428-byte app stack ceiling. Measured builds declare
124 core bytes (116 bridge + 8 wrapper), leaving at most **420 app bytes**
inside the existing gross 544-byte ceiling. Declarations do not prove actual
stack depth or make arbitrary instructions safe.

## Reading and interpreting the result

The owner's [DigiHealth 1.5](https://github.com/simonjohansson/digihealth/commit/16758cc)
adds read-only `DSP_METRICS` command 0x05. Its normal stats client reports
callback averages from two coherent, advancing counter snapshots and a
maximum since producer boot, in **raw EMUCLK ticks**. The wrapper times render,
including fixed call/read overhead; init is untimed. These are callback
observations, not total DSP load, free memory or spare real-time capacity.
A hardware timebase and an empty-callback control are needed before making
calibrated timing or overhead-subtracted claims. DigiHealth's previous
METRICS/STATS/input/screen layouts remain unchanged.

The tail hook serializes a frozen eight-word DHS1 record over 17 tagged
halfwords in selected reply-page header word 2, with CRC16 and sequence/index
checks. The receiver rejects incomplete, lost, corrupt and repeated records;
no valid producer or stale transport is explicitly unavailable. Freshness
expires after 64 advancing ColdFire blocks. It is not host wall-time liveness
if that interrupt stops. Interval arithmetic handles unsigned rollover and
rejects impossible averages. Observed resets/gaps need a new baseline; there
is no universal reboot epoch if a client misses the entire restart.

## Qualification boundary

Header word 2 persists in stock. Exact-release analysis found an apparently
unused raw-header accessor; it does not prove every indirect consumer absent.
Marker tests cover all four command paths and preserve the other reply bytes
and audio. The optional core claims `sharc:reply-header:2`, also inferred by
the linker, and changes only the additional exact six-byte tail hook. No
stock getter is disabled. This bounded ownership contract remains
experimental; project/FX/cache/interrupt qualification is separate.

Offline checks cover pinned artifact reproduction, register/stack fixtures,
actual C/ASM callbacks, coherent coupled transport/audio, legacy remote
controls, refusal boundaries and Python/TypeScript parity. Physical installation and the bounded raised-send workload below pass.
Callback clock/overhead calibration and wider measured-core project/
effects coverage remain acceptance gates. [#41](https://github.com/simonjohansson/elekloader/issues/41)
owns timing and [#56](https://github.com/simonjohansson/elekloader/issues/56)
owns the bounded stock-project workload. Whole-DSP idle/busy and physical
stack high-water remain separate work.

The initial integration passes 35 required Python units, five exact-stock
measurement boundary tests, five linker-refusal tests and all 149 TypeScript
tests. Twelve concrete parity cases match (four builds/eight refusals).
Both coupled C/ASM runs produce 16 coherent advancing snapshots with zero
CRC errors/drops and identical 58,432-frame PCM. The unmeasured producer-
absent control stays unavailable while CF blocks advance. Compiled receiver
checks reject frozen/replayed/expired/incomplete/CRC-invalid records. The
DigiHealth host suite passes 49 tests, skipping eight missing-input tests.
These checks do not replace the physical gates above.

## Physical checkpoint — 24 October 2026

The same coupled-tested C `MC15` and ASM `MA15` candidates were installed
on the DN2 with DigiHealth 1.5. Installed versions, remote controls and
8,708 immutable ColdFire runtime bytes matched each candidate after reboot;
this is not direct SHARC memory readback. Firmware SHA-256 values:

- C: `cb98ce33bd2bfe7f5ccf76446461f15ba44adb62b0ce9afe18dc94eb9d433105`
- ASM: `0fcd3798c5aa4bb219bcf85441c2a14a03351b1c6459d4e75f04efff86347e21`

Each completed the same 90.005-second raised chorus/delay/reverb-send
workload: 36 note rounds, 576 requested note pairs across MIDI channels,
page changes and release to silence. Each USB capture contained 4,320,256
frames, with zero dropped capture buffers, finite identical stereo samples
and correct pitch in the analyzed note regions. These requests do not
establish an active-voice count or qualify stock effect sound quality under
the master-output replacement. DigiHealth reported no heap faults.

Each run supplied 50 fresh advancing snapshots (49 valid intervals), with
zero CRC errors or transport drops. Median interval-average callback spans
were 4,586.83 raw ticks for C and 2,904.39 for ASM. This is one run per
variant, includes the timing bracket/call/read cost and supplies no
calibrated microseconds, whole-DSP utilization or spare-capacity claim.
The empty-callback control has not been run on hardware. A later factory-
project capture was retained but not analyzed; it is not a passing result.

Reports and captures remain local under ignored
`out/sharc-metrics-device-20261024/`. Ordinary C/ASM build instructions do
not depend on this optional measurement core or its outstanding calibration.
