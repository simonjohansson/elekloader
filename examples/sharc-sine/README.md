# DN2 SHARC sine

This ordinary format-2 mod plays a monophonic, 0.125-peak sine from external
MIDI notes 36–84 on Digitone II OS 1.12. The core's H1 bridge reads the stock
SHARC voice frame, selects the newest triggered allocated slot, and takes its
settled pitch on the next render block. A release for a different slot leaves
the selected note playing; a matching release fades it out. The compiled SHARC
code generates the samples and a fixed 32-sample attack/release ramp, then the
bridge copies the 32-float master block to the right channel. No UI or new
control transport is involved. [Issue #47](https://github.com/simonjohansson/elekloader/issues/47)
tracks the device proof.

Both examples require DN2 core **0.2 or newer** through their manifest
`resources.core` field. The source commands build that core automatically.

## Build the current C or assembly source

These example commands compile the current source, export its bounded SHARC
artifact, build the normal DN2 core, lint the modules, and build and independently
verify firmware. They accept source edits without changing Elekloader's core or
application allowlist. They use no development qualification helper or
checked-in application artifact. Elekloader itself remains compiler-independent;
Selache is this example's compiler and assembler. Both commands use the
bounded 32 KiB layout automatically; authors do not select memory locations.

Install [mise](https://mise.jdx.dev/) and the normal
[ColdFire cross tools](../../docs/ADAPTING.md#1-what-you-need) for building
core-dn2. Build the pinned free [Selache](https://github.com/js216/selache)
tools once in a new directory:

```sh
git clone https://github.com/js216/selache.git "$HOME/src/selache"
cd "$HOME/src/selache"
git switch --detach 2b26d3b75c53063575bc5c820fa0d38879335187
mise exec rust@1.98.1 -- cargo build --release --locked -p selcc -p selas -p seld -p seldump
```

Return to this Elekloader checkout, then configure your own stock OS and compiler
paths. Python 3.12.13 is managed by mise; no Python packages are required.

```sh
cd examples/sharc-sine
cp mise.local.example.toml mise.local.toml
# Edit DN2_STOCK and SELACHE in mise.local.toml.
mise trust
mise install
mise run build-c
mise run build-asm
```

`DN2_STOCK` must be your own exact Digitone II OS 1.12 file (SHA-256
`7e5b8a733d4ab1fdf7e5d22757f7d8eddaa3cbf71d0858874a791844c02ceb35`).
`SELACHE` must contain that clean pinned checkout and its four release tools.
`ELEKLOADER_CROSS` selects the ColdFire prefix; the template uses `m68k-elf-`.
To include remote buttons and diagnostics, set optional `DN2_DIGIHEALTH` to a
DN2 DigiHealth `.elemod`. All recorded physical checks included the owner's
DigiHealth fork. These commands use ordinary core-dn2; callback measurements
remain a separate optional workflow.

| Command | Kernel | Output below this example directory |
|---|---|---|
| `mise run build-c` | `sine.c` | `out/c/firmware.syx` |
| `mise run build-asm` | `../sharc-sine-asm/sine.s` | `out/asm/firmware.syx` |

Both kernels share `entry.c`. Every build replaces its output directory before
compilation, so a failed compile cannot leave a previous firmware there.
`out/<variant>/build-report.json` records the source/input/output hashes,
compiler revision and binary hashes, Elekloader revision, and host/Python
versions. Outputs and local configuration remain ignored; no firmware or
extracted stock belongs in Git. `mise run test` checks the producer's bounds,
malformed-output refusals, compiler pin and stale-output handling without
firmware or external compilers.

The default layout permits 16,320 linked instruction bytes plus a 64-byte
NOP guard and 16 KiB data. Both examples declare 128 bytes of app stack;
the larger code/data area supplies no extra stack. Follow the
[callback contract](../../docs/SHARC-DN2-ABI.md),
[artifact format](../../docs/FORMAT.md#digitone-ii-sharc-app) and
[L2 limits](../../docs/SHARC-L2.md). A successful build checks the declared
envelope; each changed program still needs execution and hardware
qualification. The tested host is macOS on Apple silicon, with mise Python
3.12.13, Rust 1.98.1, Apple command-line tools and m68k-elf-gcc 16.2.0.
Other author hosts are not yet qualified.

## Maintainer regression checks

The original 1 KiB layout remains available for compatibility checks:

```sh
mise run build-c-l1
mise run build-asm-l1
```

These tasks pass `--l1` to `build.py` and write `out/c-l1/firmware.syx` and
`out/asm-l1/firmware.syx`. The original layout permits 704 linked instruction
bytes plus the 64-byte guard and 256 data bytes. The callback and stack
contract is unchanged. Ordinary mod development uses `build-c` or `build-asm`.

## Source-workflow verification

The workflow at `a104483` was checked on 24 October 2026, before the
32 KiB layout became the default. Its L2 variants are now the ordinary
`build-c`/`build-asm` commands; L1 variants use the maintainer tasks above.
A clean clone at another path, including spaces, reproduced all four firmware
files byte for byte with the same stock, compiler and DigiHealth 1.5 inputs. C and ASM phase
edits also built there and reproduced the previously qualified edited
external artifacts, without changing Elekloader's checks.
After changing the default, both ordinary builds and both L1 maintainer
builds reproduced those same previously tested firmware files byte for byte.

Fresh coupled Digikit runs checked each ordinary L1/L2 build's installed
code, callback bindings and data. All four produced identical 99,904-frame
PCM captures, tracked notes 60/69/72 and released to silence, with finite
equal stereo channels, peak 0.125 and no modeled halt or missing block.
These are emulator checks; this preparation pass did not flash hardware.

Validation passed 35 Python units, 35 SHARC tests (including the example
producer), five linker-refusal tests, 27 stock-backed DN2 tests and 149
TypeScript tests, with no skips. Python/TypeScript parity matched four fresh
builds and 23 refusal cases. Local reports remain under ignored
`out/sharc-pr-preparation-20261024/` at the repository root. Physical evidence
and its narrower workload limits are recorded separately below and in
[the L2 record](../../docs/SHARC-L2.md).

## Package or reproduce the reference artifact

The ordinary SDK can also package the checked-in application artifact without
a SHARC compiler. From the Elekloader checkout root, with `DN2_CORE` naming a
matching built core-dn2 module:

```sh
python -m elekloader.sdk.build examples/sharc-sine --stock "$DN2_STOCK"
python -m elekloader.lint examples/sharc-sine/out/sharc-sine-0.1.elemod --stock "$DN2_STOCK" --with "$DN2_CORE" --json
python -m elekloader.patch --stock "$DN2_STOCK" --mod "$DN2_CORE" --mod examples/sharc-sine/out/sharc-sine-0.1.elemod --out sine.syx --version SK02
```

Those SDK commands embed an existing artifact; they do not compile `sine.c`.
The checked-in app and core artifacts contain author-owned bytes, not stock
firmware. For development audits, `rebuild.py` and `keyed.py` reproduce the
qualified reference pair with exact code, table and full-width spill checks:

```sh
mise exec python@3.12.13 -- python examples/sharc-sine/rebuild.py /path/to/selache
```

That reference check intentionally rejects source changes. Use `build.py`
through the mise tasks above for editing either example. Other compiler and
artifact producers can use the same normal SDK/lint/patch path.

## Recorded reference qualification

The `SK02` candidate was built from stock OS 1.12 SHA-256
`7e5b8a733d4ab1fdf7e5d22757f7d8eddaa3cbf71d0858874a791844c02ceb35`,
this core, the owner's DigiHealth fork 1.3 and the keyed sine. Its firmware
SHA-256 is `d89cb023a89478d495dfe62b9f71e35c1715f47d595226055253e89f7d52b2cd`.
The author used pinned Selache `2b26d3b75c53063575bc5c820fa0d38879335187`
on macOS arm64 with mise Python 3.12.13 and Rust 1.98.1. Source SHA-256:
`entry.c` `d22f34ce144bb8cfc1670322fdcb00c838e6c8e06e82dadec283144cf77b4dd3`,
`sharc-bridge.s` `46a6fd8a9a7c4a382615b649ec36963d7413903d3646af461f1b13f3a7ef1a3e`;
the unchanged `sine.c` is
`55663cc6d4b6d109b7f607a718fa5a48d3683e4bf4fa09ecf6a9a1c1806fa07e`.
The producer `keyed.py` and layout `keyed.ldf` are
`574979c235db60981eb1ba1108505cb0db2b43e0800af5ac61f9389e4f6273c4` and
`a6133ab1ac516d0200afa948d0e9984781a6fea6f46b6a8c852bef6dcf38e6ee`.
The prelinked app/core artifact SHA-256 values are
`c92cad748f785ece3a75b1492c3d232a4576601eb1ad0cac54b318fa92d44e7f` and
`5a40c795f6d8305a99f679bfb470d37e16e1f81af999f3f4a54a38ca13d8dcf0`.

Digikit cold-booted this exact firmware and reproduced MIDI note/pitch/release
without a DSP halt or missing block. A 16-note burst (36–51) settled on note
51 at 155.575 Hz, then released to silence, again with no halt or missing
block. The DN2 then booted `SK02`, reported
DigiHealth 1.3, and its 24-second USB master capture had 2,251 buffers with
zero drops. The capture SHA-256 is
`d9a4f8611e7053375bc406159a4744d89e0918f9cb4c2eaf8ef925a2d21219b0`.
Both channels were sample-identical. Settled tone peaks were 0.178571 and RMS
about 0.1263; idle and matching releases were silent. Before measurement,
the acceptance limit was at most 2 cents after capture-clock calibration.
A separate 12-second, 1,126-buffer USB callback regression measured
48,000.586 samples/host second (+0.021 cents from nominal 48 kHz). With that
correction, the largest absolute error among notes 36, 48, 60, 69, 70, 72,
81 and 84 was 0.05 cents. Their nominal-rate measurements in Hz were 65.405,
130.8096, 261.6253, 440.0020, 466.1559, 523.2371, 879.9844 and
1046.5184. Octaves doubled and adjacent notes followed equal temperament.

The physical capture also checked two repeated 69s, velocity-zero Note On,
CC123, and selecting 72 over a still-held 69. Releasing old 69 left 72
playing; releasing 72 reached silence. At that note handoff, the largest
adjacent-sample step fell from 0.110 in the earlier `SK01` prototype to
0.012 in `SK02`, normalized to the SHARC output scale. MIDI Stop and
real-time Reset preserved
an externally held note, while the next note and subsequent Note Off/CC123
still worked. That separate 11-second capture had zero dropped buffers and
SHA-256 `1284e291ee8de8f100efef4417387cbc7e22eec22458c8d5fdf8de9be1a933ee`.
That is the observed stock input lifecycle, not a new gate
policy. The local capture and firmware are not committed. This qualifies the
USB master route and the listed input range, not other outputs or worst-case
DSP timing.

Earlier fixed-tone qualification remains useful as a baseline:

On a physical DN2, the `SS01` build (stock OS 1.12, core 0.1, DigiHealth
fork 1.3 and the then-fixed sine 0.1; firmware SHA-256
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
