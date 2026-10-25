# Digitone II filter clones

`machines-dn2` 0.1 adds stock filter clones to the native **FUNC+SYN →
FLTR** category on OS 1.12. They work independently of synth registration:
one track can retain SINE and select CLONE FILTER. Core-dn2 is 0.1.
Filter clones use stock DSP; custom filter DSP is not supported.

```c
#include "mk2/machines.h"
const struct mk2_filter my_filter = {6, 0, "CLONE FILTER", "CLONE"};
```

Contribute its pointer to `mk2_filters`, with the normal SDK manifest:

```json
"contribute": [
 {"to": "mk2_filters", "data": "00000000",
  "relocs": [[0, "abs32", "sym:my_filter", 0]]}
]
```

Require `core` and `machines-dn2`, and set `resources.core` to `"0.1"`.
The fields are permanent ID **6..31**, stock filter **0..5**, name (ASCII,
at most 31 characters) and label (at most 7). Stock types are MULTI-MODE,
LOWPASS 4, EQUALIZER, COMB-, LEGACY LP/HP and COMB+, respectively. The linker
refuses duplicate filter IDs and stock-ID conflicts. A synth and filter may
use the same numeric ID: their namespaces and stored bytes are separate.
Never reuse a distributed filter's ID for a different filter.

The selector lists the six stock filters in their native order, followed
by registered clones in ID order. Pages, defaults, parameters and audio use
the chosen stock filter. Saving and copying retain the clone's identity.
A missing registration keeps its saved ID, disappears from the selector
and uses **MULTI-MODE**, with the existing parameter values. This can change
the sound. Keep project backups when changing installed mods. Removing the
companion restores the stock loader's unknown-ID clamp.

`mk2_filters` names the registration interface; it does **not** enable
Digitakt II. That device needs independently traced and qualified firmware
adapters and limits. Synths use `mk2_synths` and `mk2_voice_synths`, with
`struct mk2_synth` from the same header.

## OS 1.12 trace

OS 1.12 stock SHA-256:
`7e5b8a733d4ab1fdf7e5d22757f7d8eddaa3cbf71d0858874a791844c02ceb35`.

| Path | OS 1.12 finding |
|---|---|
| Cached list | `0x4004dae2`, vector at `0x405cdfa4`, stock IDs `0,1,4,3,5,2` |
| Assignment | selector YES calls `0x40031a56`; sound setter `0x4004cd7c` writes `sound+0xdf` |
| Saved identity | save `0x400dd8b8`: `sound+0xdf → stored+0xf5`; load `0x400dd42a` reverses it; the filter's bound is at `0x400dd420` |
| Names | `0x400dc508` / `0x400dc52e`, six rows at `0x401f7bbc` |
| Pages | `0x400c2614`, six 44-byte descriptors at `0x424339cc` |
| Defaults and parameters | `0x400dc18e`, filter argument selects three words at `0x42c65cd0` for slots 66..68; native defaults use the same lookup |
| Audio frame | `0x40027586` reads mirror `+0xd8d`; only the transmitted filter type is mapped to its clone |
| DSP filter stage | render table `0x8052dbc0`, setup table `0x8052dba4`; selected filtering precedes the stock amp stage, downstream of the voice synth callback |

The six page descriptors share the envelope/global entries; their filter
control IDs are `36..38`, `39..40`, `41..43`, `54..56`, `57..59`, and
`318..320`. This is not the synth page table or synth owner numbering.

Sources: [DigiKit's machine/parameter investigation](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/docs/findings/02-machines-and-parameters.md),
[native selector research](https://github.com/angellinares/dn2_firmware_explore/blob/39815895720b84c59ce2fa0ff5b13bd47dc415d2/docs/machine-list.md)
and [DSP stage research](https://github.com/angellinares/dn2_firmware_explore/blob/39815895720b84c59ce2fa0ff5b13bd47dc415d2/docs/waverider-feasibility.md).

## Checks

Build the external consumer with `mise run build-c`; its firmware includes
SINE, CLONE FILTER and DigiHealth. The host registry tests cover separate
IDs, stock ordering, invalid registrations and missing filters. Python and
TypeScript check conflicting IDs and produce matching firmware.

For runtime checks, use the same build with DigiHealth. Select SINE and
CLONE FILTER on one track, compare it with MULTI-MODE at identical settings,
and play a stock synth on a second track. Check cutoff, preset copy and
project save/reload. Removing the filter registration must retain SINE's
identity and the saved filter ID; reinstalling it must restore selection.
Run these checks in the coupled emulator and on the device for each
changed workload.
