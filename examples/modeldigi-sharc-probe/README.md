# ModelDigi SHARC oscillator probe

This is an offline DSP-only experiment for DN2 issue #42. It compiles the
unchanged ModelDigi oscillator baseline with three local compiler adaptations,
runs it in the pinned Digikit SHARC runner, and compares its Q31 samples and
state with a native build of the original source. No firmware or module is
produced.

```sh
mise exec python@3.12.13 -- python examples/modeldigi-sharc-probe/probe.py \
  ~/src/ModelDigi /path/to/selache /path/to/digikit-px-fork
```

The normal DN2 mod build remains the same as
[`sharc-sine`](../sharc-sine/README.md). This probe needs the pinned Selache
compiler and Digikit runner only for author qualification.

The working cases start from ModelDigi's cost-driver scenario 0 (a 220 Hz saw
with two muted oscillators), the same 32 frames split 16+16, frequency
clamping and invalid-shape fallback with muted other voices, and Analog
on/off/on. All output words and the 116-byte oscillator state must match.
The first six output samples are zero as specified by ModelDigi. The probe
also mutates an oscillator constant and requires a sample mismatch.

This synthetic map is **not a DN2 reservation**. Its code, tables, state,
stack, instruction forms, and license dependencies must be qualified for
physical placement before #46. The high-frequency, three-shape/modulated
stress case is outside this first scenario and currently differs from the
host; #43 owns broader numerical qualification. The Q31-to-float output
adapter and audio routing are not covered here.

## Bounded L2 placement experiment

An uncommitted `L201` firmware candidate appended the probe's 12,106 code
bytes at loader address `0x20090000` and 9,952 data bytes at `0x20094000` to
DN2 1.12's section-7 boot stream. The main OS remained byte-identical to the
previous `SK02` keyed-sine build, including the user's DigiHealth fork; the
ModelDigi code was **not called**. Its SHA-256 is
`986507cb887069f1a01b6f77c15c395e3ea496bfc6bfc3ad0713a8d21432463a`.
Stock-section, boot-record, protected-range, decoded/stored-size and container
checks passed. Digikit cold-booted it, read both L2 loads back byte-for-byte,
and rendered the existing sine without a DSP halt.

On the connected DN2, the update completed and the device reported `L201`
after reboot. DigiHealth responded, and a 24.01-second physical capture of the
existing keyed sine had equal stereo channels and pitch within 0.1 cent at
MIDI notes 36, 48, 60, 69, 70, 72, 81 and 84. The private CAF capture's
SHA-256 is
`df528a825db188ed7b8084830a3efae3ef4e27caec02b5a6a6b4b0ff0be84ab9`.
This qualifies startup and one audio/control route with inert L2 loads; it
does not prove physical L2 byte retention, L2 execution, ModelDigi output,
cache behavior, or timing margin. The candidate and capture stay outside Git.
