# Digitone II synth clones

Experimental, OS 1.12 only. `machines-dn2` is a companion to core-dn2 0.2.
From 0.2 it also supports [SHARC track synths](MACHINES-DN2-VOICE.md).
It puts external synth mods in the native **FUNC+SYN** selector. A clone
keeps its own saved machine ID but uses a stock synth's DSP and parameter
pages. This does not yet run a mod's own per-voice SHARC code.

A mod needs one descriptor and one contribution, without firmware addresses
or hook sites of its own:

```c
#include "digitone-mk2/machines.h"
const struct dn2_synth my_synth = {5, 0, "CLONE", "CLONE"};
```

```json
{
 "id": "synth-clone", "version": "0.1", "license": "GPL-2.0-or-later",
 "device": "digitone-mk2", "os": "1.12", "sources": ["clone.c"],
 "contribute": [
  {"to": "dn2_synths", "data": "00000000",
   "relocs": [[0, "abs32", "sym:my_synth", 0]]}
 ],
 "resources": {"core": "0.2"}, "requires": ["core", "machines-dn2"]
}
```

The fields are the permanent ID (5..31), the stock synth (0 FM TONE,
1 WAVETONE, 2 FM DRUM, 3 SWARMER), the name (ASCII, at most 31 characters)
and the short label (at most 7). Give each independently distributed mod a
different ID. The linker reads the descriptor's ID and refuses conflicts,
even if a mod omits a resource claim. Keep the ID when adding/removing
other mods or changing their order; never reuse it for a different mod.
There is no global ID allocator yet: agree IDs when combining mods.

Build the companion and your mod with the normal SDK, then combine them
with core-dn2 and DigiHealth. No SHARC compiler is needed for a stock clone.
Do not include a master-output replacement when checking the clone's sound.
The companion leaves section 7 unchanged.

```sh
python -m elekloader.sdk.build mods/core-dn2 --stock Digitone_II_OS1.12.syx --out out/core
python -m elekloader.sdk.build mods/machines-dn2 --stock Digitone_II_OS1.12.syx --out out/machines
python -m elekloader.sdk.build /path/to/my-mod --stock Digitone_II_OS1.12.syx --out out/clone
python -m elekloader.patch --stock Digitone_II_OS1.12.syx --mod out/core/core-0.2.elemod --mod out/machines/machines-dn2-0.1.elemod --mod out/clone/synth-clone-0.1.elemod --mod /path/to/digihealth.elemod --out out/clone.syx --version MC01
```

The menu lists stock synths first, added synths by stable ID, then MIDI.
The synth clone shares its original's SYN, FLTR and AMP pages; page titles
retain the stock synth's name. The native FLTR selector is unchanged.

With the companion present, a saved ID 5..31 whose mod is absent is kept,
named MISSING by the name accessors and omitted from the selector. Its DSP
type maps to MIDI (silence), rather than another mod's synth. The native
loader also checks assignment permissions, so missing IDs use MIDI's track
mask to allow the saved sound to load without replacing its identity. Removing the companion
restores stock OS behavior, which clamps an unknown saved type to FM TONE
when loading a sound. Keep backups of projects; do not save over the only
copy when changing the installed mod set.

## Qualification status

The first clone increment was checked with OS 1.12, core 0.2, DigiHealth
1.5 and the coupled DigiKit emulator at
`ded547e14e63977c1a6e808812d46243e13c43d0`. The external consumer is
`digitone-2-mod-hack`'s `machines` branch.

- FUNC+SYN lists CLONE; one YES assigns it and moves the selected marker.
- Reopening the selector and visiting its FLTR category retain the marker.
- CLONE's SYN, FLTR and AMP control areas match FM TONE. The animated top
  status/title strip is excluded from the control comparison.
- Track 1's CLONE and FM TONE first-note captures are byte-identical:
  48,000 stereo frames, WAV SHA-256
  `06b2e1fb1cff83605275df3b52bebc025877e9da59c9505d5eeb70c38c8710b0`.
- Switching back to stock uses the next allocated voice with identity 0;
  the earlier voice slot keeps its old identity, as expected.
- Track 2's first CLONE note uses voice slot 0 owned by track 2, with
  identity 5 and transmitted type 0. Its WAV matches the fresh FM TONE
  reference. A subsequent track-1 note retains stock identity 0.
- The build keeps DSP section 7 and the other non-main sections unchanged.
  Duplicate IDs are refused by both the Python and TypeScript engines.

The saved-project and missing-mod checks are qualified in the emulator:

- Save `001 NEW PROJECT` with CLONE, select stock FM TONE, then load that
  named project: CLONE and ID 5 return, with the reference audio unchanged.
- Cold-load firmware without the fixture and load the same project. The
  active voice retains ID 5, transmits MIDI type 4 and renders exact zeros.
  The missing ID has no selected entry in the stock-only machine list.
- Save the project again while CLONE is absent. Cold-load firmware with the
  mod reinstated and load that project: ID 5, the CLONE marker and the
  byte-identical reference audio return. The saved identity is not lost.
- The companion with no registrations lists only IDs `0, 2, 1, 3, 4` and
  its stock FM TONE capture is unchanged. Removing the companion entirely
  makes the stock loader turn the saved unknown ID into FM TONE (ID 0).

The qualified clone firmware SHA-256 is
`404b9f170ffb548323f8475b7010a38c9d7284e0ff062df04ecbcd07ae3d2a3a`.
The missing-fixture control is
`f9d02d5b5a1f97c7b192b344d22322f0a7da3c111556bdb7a861fac311d8d8ca`.
All controls include DigiHealth. No hardware, undo or dedicated sound-pool
transfer qualification is claimed.

For reproducible card tests, retain the emulator's formatted base image
as well as the guest's write overlay. Applying those writes to a zero-filled
file does not recreate the saved card. Wait for saving/loading to complete
and verify the named project in the native load list before checking its
machine. These are emulator qualification steps; the mod build command is
unchanged. The separate DigiKit proof correction remains deferred in #65.

## Maintainer checks

The manifest in `mods/machines-dn2/mod.json` holds every exact OS 1.12 byte
guard and address. The adapters cover the cached list's allocation/end,
name/descriptor/permission lookups, synth grouping, three parameter-page
readers, parameter ownership, the audio frame's type and the saved type
reader. Identity callers retain the real type; page logic sees the stock
clone. The audio frame is indexed by allocated voice slot, not by track;
qualification follows the owner map at `0x40288306 + 0x14*v` during note-on.
A small wrapper gives the native track-type accessor the real reader without embedding a copied firmware function. The sound-load bound
accepts IDs through 31. Unused IDs never enter the cached list.

Firmware-free C checks exercise registration order, gaps, missing mods,
invalid descriptors and stock behavior:

```sh
cc -std=c99 -Wall -Werror -I elekloader/sdk/include tests/test_dn2_machines.c -o /tmp/dn2-machines-test
/tmp/dn2-machines-test
cc -std=c99 -Wall -Werror -DEMPTY -I elekloader/sdk/include tests/test_dn2_machines.c -o /tmp/dn2-machines-empty-test
/tmp/dn2-machines-empty-test
```

`python tests/test_units.py` runs the C checks when a native `cc` is
available (and reports a skip otherwise). It and the TypeScript suite
check conflicting and distinct IDs. Runtime qualification must also
exercise the native selector, stock-equivalent audio, both categories, another track, project save/load
and the missing-mod control. Firmware builds alone do not qualify these.

Sources: [DigiKit's OS 1.12 machine paths](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/docs/findings/02-machines-and-parameters.md),
[cached list](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/docs/findings/33-runtime-machines-dn2.md),
[stable IDs](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/docs/findings/52-sticky-machine-ids.md)
and [reader/load corrections](https://github.com/angellinares/dn2_firmware_explore/blob/39815895720b84c59ce2fa0ff5b13bd47dc415d2/docs/machine-list.md).
Addresses were checked against the owner's stock OS 1.12. No hardware
qualification is claimed by this implementation.
