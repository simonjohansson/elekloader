# DN2 SHARC sine

This ordinary format-2 mod carries a 440 Hz, 0.125-peak sine for the
Digitone II OS 1.12. The core's H1 bridge replaces the 32-float master block
and copies it to the right channel. It needs no note, UI wiring or SHARC
compiler at build time. The active path is limited to this exact bridge and
a sine artifact whose phase increment represents 220–880 Hz. [Issue #41](https://github.com/simonjohansson/elekloader/issues/41)
tracks its physical qualification.

Set `DN2_STOCK` to your own exact OS 1.12 file and `DN2_CORE` to a matching
`core-dn2` `.elemod`. Then use the normal module commands:

```sh
python -m elekloader.sdk.build examples/sharc-sine --stock "$DN2_STOCK"
python -m elekloader.lint examples/sharc-sine/out/sharc-sine-0.1.elemod --stock "$DN2_STOCK" --with "$DN2_CORE" --json
python -m elekloader.patch --stock "$DN2_STOCK" --mod "$DN2_CORE" --mod examples/sharc-sine/out/sharc-sine-0.1.elemod --out sine.syx --version SN01
```

The core build uses the normal ColdFire cross compiler; its checked-in
`bridge.sharc.json` supplies the SHARC code. `sine.c` and `entry.c` are the
author source for the prelinked `sine.sharc.json`. Both artifacts were exported
from the pinned Selache executable checked by
[`h1.py`](../sharc-sine-probe/h1.py), SHA-256
`238339a708a64f06e4423736f628db86bb61ed3713b1a419de603ba8a8a82aa8`.
The 548-byte bridge and 424-byte sine code match its sections exactly; owned
NOP padding, 152-byte data, 360-byte zero state and a 12-byte core binding
cover the complete 2 KiB reservation. No artifact contains stock firmware.

The SDK needs no SHARC compiler for these commands. It validates and embeds
the existing artifact, and the patcher independently verifies the firmware.
To change the tone, edit only the phase-increment argument to `sine_init` in
`entry.c`, then rebuild the prelinked artifact with the pinned Selache checkout.
The checked author host is macOS on Apple silicon with mise Python 3.12.13,
Rust 1.98.1 and Apple command-line tools. [Install and build Selache](../sharc-sine-probe/README.md#build-and-check)
at commit `2b26d3b75c53063575bc5c820fa0d38879335187` once, then run:

```sh
mise exec python@3.12.13 -- python examples/sharc-sine/rebuild.py /path/to/selache
```

The producer compiles the source, checks the qualified code, data, layout and
stack cases, and replaces `sine.sharc.json` only after they pass. The linker
accepts only the four phase-increment bytes changed by a 220–880 Hz edit; all
other executable bytes must match the qualified artifact. This is a bounded
source edit, not general SHARC program support. [The format](../../docs/FORMAT.md#digitone-ii-sharc-app)
has the exact envelope and limits. No firmware, extracted section or generated
`.elemod` belongs in Git.
The complete producer is `rebuild.py` plus the checked-in
[`h1.py`](../sharc-sine-probe/h1.py) and
[`qualify.py`](../sharc-sine-probe/qualify.py); no separate assembler repair or
manual binary edit is part of this path.

For a focused contribution, change this source, rebuild, run the three module
commands above, and submit the source, prelinked artifact and checks together.
Key tracking is [#47](https://github.com/simonjohansson/elekloader/issues/47);
other author hosts and arbitrary SHARC programs are not yet qualified.

On a physical DN2, the `SS01` build (stock OS 1.12, core 0.1, DigiHealth
fork 1.3 and this sine 0.1; firmware SHA-256
`89f2cf3b2e0a9c8bfb3d83b50a2f03e51ee896dd729b95dcba153d62ebe30a4a`)
produced a stable 439.999 Hz tone on both USB master channels for 6 seconds,
then 30 seconds after a reinstall. At 48 kHz the measured peak was 0.178571
and RMS 0.126269 per channel: the [DN2 USB pack](https://github.com/ElekLabs/digikit/blob/9dee5d56c328e7091babdfd2c1d363657db78b96/docs/findings/55-fx-adapter.md#L44-L52)
scales the 0.125-peak master buffer by 1.428571. The pre-update baseline and
an `SI01` build carrying the same SHARC data with its callbacks disabled were
both exactly silent. The 30-second capture had no dropped buffers, non-finite
samples or clipping. Its changing samples across the two-page ring rule out a
frozen short-loop replay.
Captures and firmware remain local under ignored `out/`, outside Git. This
qualifies the USB master route for this fixed candidate, not the DAC, other
routes, arbitrary SHARC code or physical timing margin.

The first author iteration changed `sine_init(39370534u)` to
`sine_init(59055800u)` (660 Hz) in a clean copy of this source, then rebuilt
with pinned Selache on macOS arm64. The original author performed this rebuild;
a second contributor and other hosts have not repeated it. The generated
artifact SHA-256 was
`cd821783e36d5e1017980918650e919409a4b7ebf31bdb3e57dd8226e9e7531a`;
it differed from the 440 Hz artifact at only code offsets 328–331. Normal
build/lint/patch, the desktop model, Python web bridge and TypeScript kit
accepted it without Selache. Python and TypeScript built identical firmware
from the same mod set. A DN2 `S660` image with core 0.1, the owner's DigiHealth
fork 1.3 and the generated sine (SHA-256
`b3f18610add6ba4e7985cb75fd3277040b7ab9bd6cea96f8465b0a26646befce`)
booted and left DigiHealth responding. Eight seconds of physical USB master
capture measured 660.004 Hz, peak 0.178571 and RMS 0.126269 on both channels,
with no dropped capture buffers. The capture SHA-256 was
`9a94a3d1c8b0fd3141a22b2e341cbeb36f07b5aba1e26fac6e260685249dc13e`;
the private capture and firmware are not committed. Out-of-range frequency,
changed kernel source, wrong stock, missing core, two SHARC apps and corrupted
app code were each refused. This qualifies one source-edit loop and the USB
master route; it does not qualify arbitrary compiled SHARC code, hardware
timing margin, other audio routes or keyed playing.
