# Digitone II synth and filter

Build a selectable C SINE synth and C LOWPASS filter for DN2 OS 1.12.
Both use the normal SDK and run through the stock track pipeline. The
firmware includes DigiHealth for remote buttons and diagnostics.

Supply your stock OS, a built DN2 DigiHealth module and the ColdFire cross
compiler described in [ADAPTING.md](../../docs/ADAPTING.md). Build the
pinned open [Selache](https://github.com/js216/selache) tools:

```sh
git clone https://github.com/js216/selache.git "$HOME/src/selache"
cd "$HOME/src/selache"
git switch --detach 2b26d3b75c53063575bc5c820fa0d38879335187
mise exec rust@1.98.1 -- cargo build --release --locked -p selcc -p selas -p seld -p seldump
```

From the Elekloader checkout, with your mise-managed Python runtime:

```sh
ELEKLOADER_CROSS=m68k-elf- python examples/dn2-machines/build.py \
  --stock /path/to/Digitone_II_OS1.12.syx \
  --selache "$HOME/src/selache" \
  --digihealth /path/to/digihealth.elemod
```

The same inputs can be supplied through `DN2_STOCK`, `SELACHE` and
`DN2_DIGIHEALTH`. The compiler checkout must be clean at the pinned
revision. Python needs no third-party packages.

Flash `examples/dn2-machines/out/c/firmware.syx`. In **FUNC+SYN**, choose
**SINE** in SYN and **LOWPASS** in FLTR. The pages have no custom controls;
AMP, pan and mixer remain native. SINE uses synth ID 6 and LOWPASS uses
filter ID 8. Keep those IDs when changing the installed mod set.

Edit `examples/sharc-sine/sine.c` or `examples/sharc-filter/filter.c` in
this folder and repeat the build. The SDK supplies memory placement; code
changes need no instruction allowlist update. Compilation and artifact
inspection stay in this example's producer.

SINE plays one octave above integer MIDI notes 36..84, rounds fractional
pitch down and writes zeros outside that range. LOWPASS has a fixed
coefficient of 1/16 at 48 kHz (about 493 Hz cutoff). Its history is
independent per voice and resets on entry and retrigger. See the
[voice](../../docs/MACHINES-DN2-VOICE.md) and
[filter](../../docs/MACHINES-DN2-FILTER.md) contracts for callback limits.

Check artifact refusals, state, reset and sample boundaries without stock
firmware or the SHARC compiler:

```sh
python -m unittest discover -s examples/dn2-machines/tests
```

This is experimental. Builds accept one custom synth and one custom
filter. Timing, full-polyphony and long-duration stability are unqualified.
Build reports and firmware stay in the ignored `out` folder.
