# DN2 SHARC sine

This ordinary format-2 mod carries a fixed 440 Hz, 0.125-peak sine for the
Digitone II OS 1.12. The core's H1 bridge replaces the 32-float master block
and copies it to the right channel. It needs no note, UI wiring or SHARC
compiler at build time. The active path is limited to this exact bridge and
sine artifact while [issue #41](https://github.com/simonjohansson/elekloader/issues/41)
checks physical playback.

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
If you edit the C, regenerate the artifact with a SHARC+ compiler/linker and
qualify the new executable before linking. Elekloader cannot infer whether a
prelinked artifact reflects changed source; this first active gate refuses
other code hashes. [The format](../../docs/FORMAT.md#digitone-ii-sharc-app)
has the exact envelope and limits. No firmware, extracted section or generated
`.elemod` belongs in Git.
