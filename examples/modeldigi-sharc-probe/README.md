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

The working cases are a 220 Hz saw, the same 32 frames split 16+16, frequency
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
